"""AI QA Portal — IDE-first FastAPI backend (Feature Memory + Robot runs)."""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import settings
from .services.auth import get_current_user
from .services.db import User, get_db, init_db, list_memberships_for_user

logger = logging.getLogger("ai_qa_portal.main")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from .routers import (  # noqa: E402
    features,
    integrations,
    orgs,
    personas,
    projects,
    runs,
    test_cases,
    user_stories,
)

app = FastAPI(
    title="AI QA Portal",
    description="IDE-first API for Feature Memory QA and Salesforce Robot runs.",
    version="3.0.0",
)

# IDE / local clients only. Extra origins via CORS_ORIGINS or EXTRA_CORS_ORIGINS.
_explicit_origins = sorted({
    o.strip()
    for raw in (settings.cors_origins, settings.extra_cors_origins)
    for o in raw.split(",")
    if o.strip()
})
_origin_regex = (
    r"^(https?://localhost(:\d+)?"
    r"|https?://127\.0\.0\.1(:\d+)?"
    r"|https?://10(?:\.\d{1,3}){3}(:\d+)?"
    r"|https?://192\.168(?:\.\d{1,3}){2}(:\d+)?"
    r"|https?://172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}(:\d+)?)$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_explicit_origins,
    allow_origin_regex=_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Alias /api/<bare>/... for bare-prefixed routers (user-stories, orgs, run, …).
from .services.api_alias_middleware import ApiPrefixAliasMiddleware  # noqa: E402

app.add_middleware(ApiPrefixAliasMiddleware)

app.include_router(projects.router)
app.include_router(orgs.router)
app.include_router(personas.router)
app.include_router(runs.router)
app.include_router(user_stories.router)
app.include_router(features.router)
app.include_router(test_cases.router)
app.include_router(integrations.router)

results_dir = Path(settings.results_dir)
results_dir.mkdir(parents=True, exist_ok=True)
app.mount("/results", StaticFiles(directory=str(results_dir)), name="results")


def _prewarm_rfmcp() -> None:
    """Best-effort RF-MCP pre-warm for script generation (non-blocking)."""
    try:
        import mcp_bridge
        if mcp_bridge.is_server_running():
            return
        mcp_bridge.start_mcp_server()
        logger.info("RF-MCP pre-warmed at %s", mcp_bridge.mcp_url())
    except Exception as exc:  # noqa: BLE001 -- pre-warm is best-effort
        logger.warning("RF-MCP pre-warm failed (non-fatal): %s", exc)


def _prewarm_memory_model() -> None:
    try:
        import mcp_bridge
        mcp_bridge.prewarm_memory_model()
    except Exception as exc:  # noqa: BLE001
        logger.debug("memory model prewarm skipped: %s", exc)


def _probe_ollama() -> None:
    try:
        import requests

        from ai_bridge import _ollama_base_url, _ollama_is_reachable

        if not _ollama_is_reachable(force=True):
            logger.info(
                "Ollama (local LLM) not detected at %s; "
                "failover chain will skip the local tier until it's started.",
                _ollama_base_url(),
            )
            return

        try:
            resp = requests.get(f"{_ollama_base_url()}/api/tags", timeout=2.0)
            tags = resp.json().get("models") or []
            names = [m.get("name") for m in tags if m.get("name")]
            logger.info(
                "Ollama (local LLM) detected at %s; models available: %s",
                _ollama_base_url(),
                ", ".join(names) if names else "(none pulled yet)",
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.info("Ollama detected at %s; model list unavailable.", _ollama_base_url())
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug("Ollama probe skipped: %s", exc)


@app.on_event("startup")
def _on_startup() -> None:
    init_db()
    try:
        from .services.db import SessionLocal
        from .services.prompt_registry import seed_system_templates
        db = SessionLocal()
        try:
            seed_system_templates(db)
        finally:
            db.close()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("prompt seed failed at startup: %s", exc)
    if os.environ.get("MCP_PREWARM", "1").strip() not in ("0", "false", "False", ""):
        threading.Thread(target=_prewarm_rfmcp, name="rfmcp-prewarm", daemon=True).start()
    threading.Thread(target=_probe_ollama, name="ollama-probe", daemon=True).start()
    if os.environ.get("MCP_MEMORY_PREWARM", "1").strip() not in ("0", "false", "False", ""):
        threading.Thread(
            target=_prewarm_memory_model,
            name="rfmcp-memory-prewarm",
            daemon=True,
        ).start()

    try:
        from .services import scheduler as _scheduler_service
        from .services.db import SessionLocal

        _scheduler_service.start()
        if settings.scheduler_enabled:
            with SessionLocal() as session:
                reloaded = _scheduler_service.reload_all(session)
            logger.info("APScheduler: re-registered %d local schedule(s)", reloaded)
    except Exception as exc:  # noqa: BLE001 -- scheduler failure should never block boot
        logger.warning("Scheduler startup failed (non-fatal): %s", exc)


@app.on_event("shutdown")
def _on_shutdown() -> None:
    try:
        from .services import scheduler as _scheduler_service
        _scheduler_service.shutdown()
    except Exception:  # noqa: BLE001
        pass
    try:
        from .services.generation_worker import shutdown_generation_pool
        shutdown_generation_pool()
    except Exception:  # noqa: BLE001
        pass


@app.get("/")
def root():
    return {
        "name": "AI QA Portal",
        "version": "3.0.0",
        "mode": "ide",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/me")
def whoami(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user + memberships (AUTH_DISABLED pilot returns local user)."""
    payload = current_user.to_dict()
    payload["memberships"] = [
        m.to_dict() for m in list_memberships_for_user(db, current_user.id)
    ]
    return payload
