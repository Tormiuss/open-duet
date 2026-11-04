"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGate } from "@/components/AuthGate";
import { api, request } from "@/lib/api";

type Profile = { id: string; provider: string; configured: boolean; quota: string };
type Source = { state: string; observed_at?: string; message?: string; data: unknown };
type Overview = { enabled: boolean; profiles: Profile[]; sources: Record<string, Source>; budget?: { day: string; cap: number; reserved: number; scope: string } };
type Project = { id: string; card?: { title?: string; summary?: string; phase?: string; health?: string; status?: string } };
type Hit = { id: string; title?: string; summary?: string };
const panel = "rounded-xl border border-line p-5 bg-surface space-y-3";

function Workspace() {
  const router = useRouter();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [problem, setProblem] = useState("");
  const [updated, setUpdated] = useState("");
  const [account, setAccount] = useState("codex-me");
  const [model, setModel] = useState("");
  const [effort, setEffort] = useState("medium");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [entry, setEntry] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    try {
      setOverview(await request<Overview>("/personal-operations"));
      setUpdated(new Date().toLocaleTimeString());
      setProblem("");
    } catch (error) { setProblem(String(error)); }
  }, []);
  useEffect(() => {
    const initial = setTimeout(() => { void refresh(); }, 0);
    const timer = setInterval(() => { void refresh(); }, 15000);
    return () => { clearTimeout(initial); clearInterval(timer); };
  }, [refresh]);
  async function start() {
    setBusy(true);
    try {
      if (!model.trim()) throw new Error("Choose an explicit model ID before creating a conversation.");
      const thread = await api.createThread(null, {
        provider: account.startsWith("codex-") ? "codex" : "claude",
        account_profile: account, model: model.trim(), effort,
      });
      router.push(`/chat/?thread=${thread.id}`);
    } catch (error) { setProblem(String(error)); }
    finally { setBusy(false); }
  }
  async function search() {
    try {
      const result = await request<{ hits: Hit[] }>(`/personal-operations/search?query=${encodeURIComponent(query)}`);
      setHits(result.hits); setEntry(null);
    } catch (error) { setProblem(String(error)); }
  }
  async function read(id: string) {
    try { setEntry(await request(`/personal-operations/entry/${encodeURIComponent(id)}`)); }
    catch (error) { setProblem(String(error)); }
  }
  const atlas = overview?.sources.atlas;
  const projects = atlas?.state === "connected" && Array.isArray(atlas.data) ? atlas.data as Project[] : [];
  return <main className="mx-auto max-w-6xl space-y-6 p-6 text-ink">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-2xl font-semibold">Personal operations</h1><p className="text-sm text-muted">Projects, canonical knowledge, conversations and execution evidence.</p></div>
      <nav className="flex gap-4 text-sm underline"><Link href="/chat/">Conversations & agents</Link><Link href="/settings/">Settings</Link><button onClick={() => void refresh()}>Refresh</button></nav>
    </div>
    <p className="text-sm text-muted">Refreshes every 15 seconds · Last successful refresh: {updated || "waiting"}. Refreshing makes no model calls.</p>
    {overview?.budget && <p className="rounded border border-line p-3">AI turns reserved today: {overview.budget.reserved} / {overview.budget.cap} · {overview.budget.day} · {overview.budget.scope}</p>}
    {problem && <p role="alert" className="rounded border border-red-500 p-3">{problem}</p>}
    {overview && !overview.enabled && <p>This deployment has no personal operations configuration.</p>}
    <div className="grid gap-5 lg:grid-cols-2">
      <section className={panel}><h2 className="text-lg font-semibold">Start with an explicit account</h2>
        <p className="text-sm text-muted">No automatic account rotation. Subscription quota is unknown; a local daily turn cap applies. A turn can include several model requests. Creating a conversation makes no model call.</p>
        <label className="block">Account<select className="ml-3 rounded border p-2 bg-surface" value={account} onChange={e => setAccount(e.target.value)}>{(overview?.profiles || []).map(p => <option key={p.id} value={p.id} disabled={!p.configured}>{p.id} · {p.configured ? "folder present; login checked before run" : "not configured"}</option>)}</select></label>
        <label className="block">Model ID<input className="ml-3 rounded border p-2 bg-surface" value={model} onChange={e => setModel(e.target.value)} placeholder="Exact model ID from your CLI" /></label>
        <label className="block">Effort<select className="ml-3 rounded border p-2 bg-surface" value={effort} onChange={e => setEffort(e.target.value)}>{["low", "medium", "high"].map(e => <option key={e}>{e}</option>)}</select></label>
        <button className="rounded bg-accent px-4 py-2 text-accent-fg disabled:opacity-50" disabled={busy || !overview?.enabled} onClick={() => void start()}>Create conversation</button>
        <p className="text-xs text-muted">A conversation pins its account. Nested agent jobs currently use each engine’s default account. Use separate conversations for codex-son work.</p>
      </section>
      <section className={panel}><h2 className="text-lg font-semibold">Execution controller</h2>
        <p>{overview?.sources.controller?.state || "checking"}</p>
        <p className="text-sm text-muted">The controller owns its task steps, evidence and bounded execution. Open its dashboard for live jobs and approvals.</p>
        <a className="underline" href="http://127.0.0.1:4321" target="_blank" rel="noreferrer">Open controller dashboard</a>
        <details><summary className="cursor-pointer">Latest controller snapshot</summary><pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(overview?.sources.controller, null, 2)}</pre></details>
      </section>
    </div>
    <section className={panel}><h2 className="text-lg font-semibold">Projects from Personal Atlas</h2><p className="text-sm text-muted">{atlas?.state || "checking"} · {atlas?.message || "Atlas owns project cards and historical context."}</p>
      <div className="grid gap-3 md:grid-cols-3">{projects.map(project => <article key={project.id} className="rounded border border-line p-3"><h3 className="font-semibold">{project.card?.title || project.id}</h3><p className="text-sm">{project.card?.summary}</p><p className="text-xs text-muted">{project.card?.status} {project.card?.phase} {project.card?.health}</p><a className="text-sm underline" href={`http://127.0.0.1:4317/#/project/${project.id}`} target="_blank" rel="noreferrer">Open canonical project</a></article>)}</div>
    </section>
    <section className={panel}><h2 className="text-lg font-semibold">Search the Atlas brain</h2>
      <form className="flex gap-3" onSubmit={e => { e.preventDefault(); void search(); }}><input aria-label="Search Atlas" className="flex-1 rounded border bg-surface p-2" maxLength={200} required value={query} onChange={e => setQuery(e.target.value)} /><button className="underline">Search</button></form>
      <ul>{hits.map(hit => <li key={hit.id} className="py-2"><button className="text-left underline" onClick={() => void read(hit.id)}>{hit.title || hit.id}</button><p className="text-sm text-muted">{hit.summary}</p></li>)}</ul>
      {entry !== null && <details open><summary>Full canonical entry, notes and provenance</summary><pre className="max-h-96 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(entry, null, 2)}</pre></details>}
      <p className="text-sm text-muted">Read-only connector. Agents retrieve relevant entries on demand; the full brain is not copied into each prompt.</p>
    </section>
  </main>;
}

export default function OperationsPage() { return <AuthGate><Workspace /></AuthGate>; }
