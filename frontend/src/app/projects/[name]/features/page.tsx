"use client";

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { api, type FeatureMemory, type FeatureRow } from "@/lib/api";

type StoryRow = {
  id: string;
  title: string;
  feature_id?: string | null;
};

type DeltaRow = {
  id: string;
  source: string;
  status: string;
  facts: Array<{ id: string; section: string; text: string; source_kind: string; source_note?: string | null }>;
  updated_at: string;
};

export default function ProjectFeaturesPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = use(params);
  const [projectId, setProjectId] = useState("");
  const [features, setFeatures] = useState<FeatureRow[]>([]);
  const [stories, setStories] = useState<StoryRow[]>([]);
  const [selectedFeatureId, setSelectedFeatureId] = useState("");
  const [memory, setMemory] = useState<FeatureMemory | null>(null);
  const [deltas, setDeltas] = useState<DeltaRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [newFeatureName, setNewFeatureName] = useState("");
  const [newFeatureSummary, setNewFeatureSummary] = useState("");
  const [factSection, setFactSection] = useState("open_questions");
  const [factText, setFactText] = useState("");
  const [factSourceNote, setFactSourceNote] = useState("");
  const [storyToLink, setStoryToLink] = useState("");
  const [rules, setRules] = useState<Array<{ kind: string; key: string; feature_id: string }>>([]);
  const [ruleKind, setRuleKind] = useState<"epic" | "label" | "component">("label");
  const [ruleKey, setRuleKey] = useState("");
  const [templates, setTemplates] = useState<Array<{ id: string; name: string; summary: string }>>([]);
  const [templateId, setTemplateId] = useState("");
  const [queue, setQueue] = useState<{
    unmatched: Array<{ id: string; title: string }>;
    conflicts: Array<{ story_id: string; reason: string; hits: Array<{ kind: string; value: string }> }>;
  }>({ unmatched: [], conflicts: [] });

  const selectedFeature = useMemo(
    () => features.find((f) => f.id === selectedFeatureId) || null,
    [features, selectedFeatureId],
  );

  const refreshFeatures = async (pid: string) => {
    const rows = await api.features.list(pid);
    setFeatures(rows);
    if (!selectedFeatureId && rows.length > 0) setSelectedFeatureId(rows[0].id);
  };

  const refreshOps = async (pid: string) => {
    const [ruleRows, seedRows, review] = await Promise.all([
      api.features.matchRules(pid),
      api.features.seedTemplates(pid),
      api.features.reviewQueue(pid),
    ]);
    setRules(ruleRows.rules || []);
    setTemplates(seedRows.templates || []);
    setQueue({ unmatched: review.unmatched || [], conflicts: review.conflicts || [] });
    if (!templateId && seedRows.templates?.length) setTemplateId(seedRows.templates[0].id);
  };

  const refreshStories = async (pid: string) => {
    const rows = await api.userStories.list(pid);
    setStories(rows as StoryRow[]);
  };

  const refreshFeatureDetail = async (featureId: string) => {
    const [mem, deltaRows] = await Promise.all([
      api.features.memory(featureId),
      api.features.deltas(featureId, "pending"),
    ]);
    setMemory(mem);
    setDeltas(deltaRows as DeltaRow[]);
  };

  useEffect(() => {
    api.projects
      .portalProjectId(name)
      .then(async (r) => {
        setProjectId(r.project_id);
        await Promise.all([refreshFeatures(r.project_id), refreshStories(r.project_id), refreshOps(r.project_id)]);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Could not resolve project"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

  useEffect(() => {
    if (!selectedFeatureId) {
      setMemory(null);
      setDeltas([]);
      return;
    }
    refreshFeatureDetail(selectedFeatureId).catch((e: unknown) =>
      setErr(e instanceof Error ? e.message : "Failed loading feature memory"),
    );
  }, [selectedFeatureId]);

  const createFeature = async () => {
    if (!projectId) return;
    if (!newFeatureName.trim()) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      const row = await api.features.create({
        project_id: projectId,
        name: newFeatureName.trim(),
        summary: newFeatureSummary.trim(),
      });
      setNewFeatureName("");
      setNewFeatureSummary("");
      await refreshFeatures(projectId);
      setSelectedFeatureId(row.id);
      setMsg("Feature created.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed creating feature");
    } finally {
      setBusy(false);
    }
  };

  const addUserContextFact = async () => {
    if (!selectedFeatureId || !factText.trim()) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.features.editMemory(selectedFeatureId, {
        reason: "user_context_edit",
        facts: [
          {
            section: factSection,
            text: factText.trim(),
            source_kind: "user",
            source_story_keys: [],
            source_note: factSourceNote.trim() || "manual note",
          },
        ],
      });
      setFactText("");
      setFactSourceNote("");
      await refreshFeatureDetail(selectedFeatureId);
      setMsg("Feature memory updated.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not update memory");
    } finally {
      setBusy(false);
    }
  };

  const linkStory = async () => {
    if (!selectedFeatureId || !storyToLink) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.features.linkStory(selectedFeatureId, storyToLink);
      await refreshStories(projectId);
      setStoryToLink("");
      setMsg("Story linked to feature.");
      if (projectId) await refreshOps(projectId);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not link story");
    } finally {
      setBusy(false);
    }
  };

  const runAnalysis = async (storyId: string) => {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.userStories.analyze(storyId);
      await refreshFeatureDetail(selectedFeatureId);
      setMsg("Analysis complete. Review pending memory delta.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  };

  const runGenerate = async (storyId: string) => {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.userStories.generate(storyId);
      setMsg("Test cases generated.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  };

  const acceptDelta = async (deltaId: string) => {
    if (!selectedFeatureId) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.features.acceptDelta(selectedFeatureId, deltaId, "manual_accept");
      await refreshFeatureDetail(selectedFeatureId);
      setMsg("Delta accepted and merged into memory.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not accept delta");
    } finally {
      setBusy(false);
    }
  };

  const rejectDelta = async (deltaId: string) => {
    if (!selectedFeatureId) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.features.rejectDelta(selectedFeatureId, deltaId, "manual_reject");
      await refreshFeatureDetail(selectedFeatureId);
      setMsg("Delta rejected.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not reject delta");
    } finally {
      setBusy(false);
    }
  };

  const saveRule = async () => {
    if (!projectId || !selectedFeatureId || !ruleKey.trim()) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.features.upsertMatchRule({
        project_id: projectId,
        kind: ruleKind,
        key: ruleKey.trim(),
        feature_id: selectedFeatureId,
      });
      setRuleKey("");
      await refreshOps(projectId);
      setMsg("Match rule saved.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not save rule");
    } finally {
      setBusy(false);
    }
  };

  const removeRule = async (kind: string, key: string) => {
    if (!projectId) return;
    setBusy(true);
    setErr("");
    try {
      await api.features.deleteMatchRule({ project_id: projectId, kind, key });
      await refreshOps(projectId);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not delete rule");
    } finally {
      setBusy(false);
    }
  };

  const applySeed = async () => {
    if (!selectedFeatureId || !templateId) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.features.applySeed(selectedFeatureId, templateId);
      await refreshFeatureDetail(selectedFeatureId);
      setMsg("Salesforce Core seed applied to empty memory.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not apply seed");
    } finally {
      setBusy(false);
    }
  };

  const linkedStories = stories.filter((s) => s.feature_id === selectedFeatureId);
  const unlinkedStories = stories.filter((s) => !s.feature_id);

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <Link href="/projects" className="hover:text-white">
          Projects
        </Link>
        <span>/</span>
        <Link href={`/projects/${encodeURIComponent(name)}`} className="hover:text-white">
          {name}
        </Link>
        <span>/</span>
        <span className="text-slate-300">Features</span>
      </div>

      <div>
        <h1 className="text-3xl font-bold text-white">Feature Knowledge</h1>
        <p className="text-sm text-slate-400 mt-1">
          Keep feature memory editable. Add Jira-derived facts and offline context, then analyze and generate from it.
        </p>
      </div>

      {err && <div className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">{err}</div>}
      {msg && <div className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">{msg}</div>}

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
          <h2 className="text-white font-semibold">Create feature</h2>
          <input
            value={newFeatureName}
            onChange={(e) => setNewFeatureName(e.target.value)}
            placeholder="Feature name (e.g. Campaign Management)"
            className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2 text-sm"
          />
          <textarea
            value={newFeatureSummary}
            onChange={(e) => setNewFeatureSummary(e.target.value)}
            placeholder="Summary"
            rows={3}
            className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2 text-sm"
          />
          <button disabled={busy} onClick={createFeature} className="px-3 py-2 rounded bg-purple-600 text-white text-sm">
            Create
          </button>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3 lg:col-span-2">
          <h2 className="text-white font-semibold">Select feature</h2>
          <select
            value={selectedFeatureId}
            onChange={(e) => setSelectedFeatureId(e.target.value)}
            className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2 text-sm"
          >
            <option value="">Select...</option>
            {features.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
          {selectedFeature && <p className="text-sm text-slate-400">{selectedFeature.summary || "No summary yet."}</p>}
        </div>
      </div>

      {selectedFeatureId && (
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="text-white font-semibold">Memory editor</h2>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={factSection}
                onChange={(e) => setFactSection(e.target.value)}
                className="rounded bg-slate-900 border border-slate-700 px-3 py-2 text-sm"
              >
                <option value="business_rules">business_rules</option>
                <option value="salesforce_objects">salesforce_objects</option>
                <option value="permissions">permissions</option>
                <option value="validation">validation</option>
                <option value="known_risks">known_risks</option>
                <option value="open_questions">open_questions</option>
                <option value="testing_notes">testing_notes</option>
              </select>
              <input
                value={factSourceNote}
                onChange={(e) => setFactSourceNote(e.target.value)}
                placeholder="Source note (offline conversation)"
                className="rounded bg-slate-900 border border-slate-700 px-3 py-2 text-sm"
              />
            </div>
            <textarea
              value={factText}
              onChange={(e) => setFactText(e.target.value)}
              placeholder="Add user context, incomplete-story clarification, or org rule"
              rows={3}
              className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2 text-sm"
            />
            <button disabled={busy} onClick={addUserContextFact} className="px-3 py-2 rounded bg-cyan-600 text-white text-sm">
              Add to memory
            </button>
            <div className="text-xs text-slate-400">Memory version: {memory?.version ?? "-"}</div>
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs bg-slate-950/60 border border-slate-800 rounded p-3">
              {memory?.markdown || "No memory facts yet."}
            </pre>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="text-white font-semibold">Stories and actions</h2>
            <div className="flex gap-2">
              <select
                value={storyToLink}
                onChange={(e) => setStoryToLink(e.target.value)}
                className="flex-1 rounded bg-slate-900 border border-slate-700 px-3 py-2 text-sm"
              >
                <option value="">Link an unlinked story...</option>
                {unlinkedStories.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
              <button disabled={busy || !storyToLink} onClick={linkStory} className="px-3 py-2 rounded bg-purple-600 text-white text-sm">
                Link
              </button>
            </div>
            <div className="space-y-2 max-h-52 overflow-auto">
              {linkedStories.map((s) => (
                <div key={s.id} className="rounded border border-slate-700 p-2 text-sm">
                  <div className="text-slate-200">{s.title}</div>
                  <div className="flex gap-2 mt-2">
                    <button disabled={busy} onClick={() => runAnalysis(s.id)} className="px-2 py-1 rounded bg-indigo-600 text-white text-xs">
                      Analyze
                    </button>
                    <button disabled={busy} onClick={() => runGenerate(s.id)} className="px-2 py-1 rounded bg-emerald-600 text-white text-xs">
                      Generate TCs
                    </button>
                    <Link href={`/user-stories/${encodeURIComponent(s.id)}?project=${encodeURIComponent(name)}`} className="px-2 py-1 rounded bg-slate-700 text-white text-xs">
                      Open
                    </Link>
                  </div>
                </div>
              ))}
              {linkedStories.length === 0 && <div className="text-sm text-slate-400">No stories linked yet.</div>}
            </div>
          </div>
        </div>
      )}

      {projectId && (
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="text-white font-semibold">Deterministic match rules</h2>
            <p className="text-xs text-slate-400">Epic, label, or component must map to exactly one feature. Disagreement stays unlinked.</p>
            <div className="flex gap-2">
              <select value={ruleKind} onChange={(e) => setRuleKind(e.target.value as "epic" | "label" | "component")} className="rounded bg-slate-900 border border-slate-700 px-2 py-2 text-sm">
                <option value="epic">epic</option>
                <option value="label">label</option>
                <option value="component">component</option>
              </select>
              <input value={ruleKey} onChange={(e) => setRuleKey(e.target.value)} placeholder="CAM-12 or Campaigns" className="flex-1 rounded bg-slate-900 border border-slate-700 px-3 py-2 text-sm" />
              <button disabled={busy || !selectedFeatureId} onClick={saveRule} className="px-3 py-2 rounded bg-purple-600 text-white text-sm">Save</button>
            </div>
            <ul className="text-sm text-slate-200 space-y-1 max-h-40 overflow-auto">
              {rules.filter((r) => !selectedFeatureId || r.feature_id === selectedFeatureId).map((r) => (
                <li key={`${r.kind}:${r.key}`} className="flex justify-between gap-2">
                  <span>{r.kind}: {r.key}</span>
                  <button className="text-xs text-rose-300" onClick={() => removeRule(r.kind, r.key)}>Remove</button>
                </li>
              ))}
              {rules.length === 0 && <li className="text-slate-400">No rules yet.</li>}
            </ul>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <h2 className="text-white font-semibold">Salesforce Core seed</h2>
            <p className="text-xs text-slate-400">Applies only when the selected feature memory is empty. Facts stay editable.</p>
            <div className="flex gap-2">
              <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="flex-1 rounded bg-slate-900 border border-slate-700 px-3 py-2 text-sm">
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              <button disabled={busy || !selectedFeatureId} onClick={applySeed} className="px-3 py-2 rounded bg-cyan-600 text-white text-sm">Apply</button>
            </div>
            <div className="text-xs text-slate-400">{templates.find((t) => t.id === templateId)?.summary}</div>
          </div>
        </div>
      )}

      {projectId && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
          <h2 className="text-white font-semibold">Unmatched and conflicts</h2>
          <div className="grid md:grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-slate-300 mb-2">Unmatched</div>
              {queue.unmatched.length === 0 && <div className="text-slate-400">None</div>}
              {queue.unmatched.map((s) => (
                <div key={s.id} className="mb-1 text-slate-200">{s.title}</div>
              ))}
            </div>
            <div>
              <div className="text-slate-300 mb-2">Conflicts</div>
              {queue.conflicts.length === 0 && <div className="text-slate-400">None</div>}
              {queue.conflicts.map((c) => (
                <div key={c.story_id} className="mb-2 text-slate-200">
                  {c.story_id.slice(0, 8)} — {c.reason}
                  <div className="text-xs text-slate-400">{c.hits.map((h) => `${h.kind}:${h.value}`).join(", ")}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {selectedFeatureId && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
          <h2 className="text-white font-semibold">Pending memory deltas</h2>
          {deltas.length === 0 && <div className="text-sm text-slate-400">No pending deltas.</div>}
          {deltas.map((d) => (
            <div key={d.id} className="rounded border border-slate-700 p-3 space-y-2">
              <div className="text-xs text-slate-400">
                {d.source} • {new Date(d.updated_at).toLocaleString()}
              </div>
              <ul className="list-disc pl-5 text-sm text-slate-200">
                {d.facts.slice(0, 6).map((f) => (
                  <li key={f.id}>
                    [{f.section}] {f.text}
                  </li>
                ))}
              </ul>
              <div className="flex gap-2">
                <button disabled={busy} onClick={() => acceptDelta(d.id)} className="px-2 py-1 rounded bg-emerald-600 text-white text-xs">
                  Accept
                </button>
                <button disabled={busy} onClick={() => rejectDelta(d.id)} className="px-2 py-1 rounded bg-rose-600 text-white text-xs">
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

