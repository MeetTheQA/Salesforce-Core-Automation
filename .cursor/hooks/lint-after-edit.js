#!/usr/bin/env node
/**
 * Cursor `afterFileEdit` hook -- runs ruff on Python files just edited
 * and feeds errors back to the agent via `additional_context`.
 *
 * Failure handling: fail-open. Print {} and exit 0 on any hook error.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const BACKEND_DIR = path.join(REPO_ROOT, "ai_qa_portal");

function readStdin() {
  try {
    return fs.readFileSync(0, "utf8");
  } catch (_err) {
    return "";
  }
}

function extractEditedPath(payload) {
  const ti = (payload && payload.tool_input) || {};
  return (
    ti.path ||
    ti.target_notebook ||
    ti.file_path ||
    (payload && payload.file_path) ||
    ""
  );
}

function emit(obj) {
  try {
    process.stdout.write(JSON.stringify(obj || {}));
  } catch (_err) {
    /* nothing useful we can do */
  }
  process.exit(0);
}

function _startsWithDir(absPath, dir) {
  const needle = process.platform === "win32" ? dir.toLowerCase() : dir;
  const hay = process.platform === "win32" ? absPath.toLowerCase() : absPath;
  return hay.startsWith(needle);
}

function isBackendPython(absPath) {
  if (!absPath) return false;
  const isInBackend = _startsWithDir(absPath, BACKEND_DIR);
  const isRepoRootPython = (
    !isInBackend &&
    _startsWithDir(absPath, REPO_ROOT) &&
    !absPath.includes(`${path.sep}venv${path.sep}`) &&
    !absPath.includes(`${path.sep}__pycache__${path.sep}`) &&
    !absPath.includes(`${path.sep}.cursor${path.sep}`) &&
    !absPath.includes(`${path.sep}node_modules${path.sep}`)
  );
  if (!isInBackend && !isRepoRootPython) return false;
  return /\.py$/.test(absPath);
}

function runQuiet(cmd, args, opts) {
  try {
    const proc = spawnSync(cmd, args, {
      cwd: opts && opts.cwd,
      encoding: "utf8",
      shell: process.platform === "win32",
      timeout: 50_000,
      maxBuffer: 5 * 1024 * 1024,
    });
    return {
      ok: proc.status === 0,
      status: proc.status,
      stdout: proc.stdout || "",
      stderr: proc.stderr || "",
    };
  } catch (_err) {
    return { ok: false, status: -1, stdout: "", stderr: "" };
  }
}

function lintPythonFile(absPath) {
  const rel = path.relative(REPO_ROOT, absPath).replace(/\\/g, "/");
  const proc = runQuiet(
    "py",
    ["-3", "-m", "ruff", "check", "--select", "F", "--output-format", "json", rel],
    { cwd: REPO_ROOT },
  );
  if (!proc.stdout.trim()) return null;

  let parsed;
  try {
    parsed = JSON.parse(proc.stdout);
  } catch {
    return null;
  }
  if (!Array.isArray(parsed) || parsed.length === 0) return null;

  const lines = parsed.slice(0, 12).map((m) => {
    const code = m.code || "?";
    const msg = (m.message || "").split("\n")[0].slice(0, 200);
    const row = (m.location && m.location.row) || "?";
    const col = (m.location && m.location.column) || "?";
    return `  ${rel}:${row}:${col}  [${code}]  ${msg}`;
  });
  const more = parsed.length > 12 ? `\n  ... ${parsed.length - 12} more error(s) suppressed` : "";
  return (
    `Ruff detected ${parsed.length} Python issue(s) in the file you just edited:\n` +
    lines.join("\n") +
    more +
    `\n\nPlease fix these before continuing. Run ` +
    `\`py -3 -m ruff check ${rel} --select F\` to reproduce.`
  );
}

const raw = readStdin();
let payload = {};
try {
  payload = raw ? JSON.parse(raw) : {};
} catch {
  emit({});
}

const editedPath = extractEditedPath(payload);
if (!editedPath) emit({});

let absPath = path.isAbsolute(editedPath)
  ? path.normalize(editedPath)
  : path.resolve(REPO_ROOT, editedPath);
if (process.platform === "win32") {
  absPath = path.normalize(absPath);
}

if (isBackendPython(absPath)) {
  const ctx = lintPythonFile(absPath);
  if (ctx) emit({ additional_context: ctx });
}

emit({});
