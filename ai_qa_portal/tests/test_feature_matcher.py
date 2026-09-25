"""Deterministic feature matching and Salesforce Core seed guards."""

from __future__ import annotations

from ai_qa_portal.backend.services.feature_matcher import (
    MatchSignals,
    match_signals,
    normalize_token,
    token_variants,
)
from ai_qa_portal.backend.services.prompt_seeds import read_seed_body
from ai_qa_portal.backend.services.salesforce_feature_seeds import (
    facts_for_template,
    list_seed_templates,
)


def test_normalize_collapses_punctuation():
    assert normalize_token("  Campaign-Management!! ") == "campaign management"


def test_plural_variant():
    assert "campaign" in token_variants("Campaigns")
    assert "campaigns" in token_variants("Campaign")


def test_epic_only_match():
    maps = {"epic": {"cam 12": "feat-a"}, "label": {}, "component": {}}
    result = match_signals(MatchSignals(epic_keys=["CAM-12"]), maps)
    assert result.status == "matched"
    assert result.feature_id == "feat-a"


def test_label_only_match():
    maps = {"epic": {}, "label": {"rebate": "feat-b", "rebates": "feat-b"}, "component": {}}
    result = match_signals(MatchSignals(labels=["Rebates"]), maps)
    assert result.status == "matched"
    assert result.feature_id == "feat-b"


def test_component_only_match():
    maps = {"epic": {}, "label": {}, "component": {"sales agreement": "feat-c"}}
    result = match_signals(MatchSignals(components=["Sales Agreements"]), maps)
    assert result.status == "matched"
    assert result.feature_id == "feat-c"


def test_no_match():
    result = match_signals(MatchSignals(labels=["unknown"]), {"epic": {}, "label": {}, "component": {}})
    assert result.status == "unmatched"
    assert result.feature_id is None


def test_conflict_when_rules_disagree():
    maps = {
        "epic": {"cam 1": "feat-a"},
        "label": {"accounts": "feat-b"},
        "component": {},
    }
    result = match_signals(MatchSignals(epic_keys=["CAM-1"], labels=["Accounts"]), maps)
    assert result.status == "conflict"
    assert result.feature_id is None
    assert len(result.hits) == 2


def test_seed_facts_are_user_provenance():
    facts = facts_for_template("campaign_management")
    assert facts
    assert all(f.source_kind == "user" for f in facts)
    assert all((f.source_note or "").startswith("seed_template:") for f in facts)
    ids = {row["id"] for row in list_seed_templates()}
    assert "account_management" in ids
    assert "rebate_programs" in ids
    assert "sales_agreements" in ids


def test_grounded_prompts_forbid_invention():
    analyzer = read_seed_body("grounded_requirement_analyzer.md")
    drafter = read_seed_body("grounded_test_case_drafter.md")
    assert "Insufficient information" in analyzer
    assert "Do not invent" in analyzer or "do not invent" in analyzer.lower()
    assert "ONLY" in drafter
    assert "User memory facts" in drafter or "User-authored" in analyzer
