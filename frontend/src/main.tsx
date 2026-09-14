import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ShieldCheck, Database, Terminal, GitBranch, Activity, Send, Upload, CheckCircle2, XCircle } from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "";
type Citation = { source: { filename: string; page?: number; section?: string; start_line?: number; end_line?: number }; content: string; score: number; prompt_injection_detected?: boolean };
type Task = { task_id: string; plan: string; evidence: Citation[]; diff: string; test: any; critique: string; report: string; status: string; approval_required: boolean };

async function jsonFetch(path: string, init?: RequestInit) {
  const response = await fetch(`${API}${path}`, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.error || `Request failed (${response.status})`);
  return data;
}

function App() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<Citation[]>([]);
  const [task, setTask] = useState("");
  const [taskResult, setTaskResult] = useState<Task | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<any>(null);

  useEffect(() => { jsonFetch("/api/status").then(setStatus).catch(e => setMessage(e.message)); }, []);

  async function ask() {
  setBusy(true);
  setMessage("");

  try {
    const r = await jsonFetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    let results = r.results || [];

    // The deployed MCP bridge may return the tool result
    // inside the content field as a JSON string.
    if (!results.length && Array.isArray(r.content)) {
      for (const item of r.content) {
        if (typeof item === "string") {
          try {
            const parsed = JSON.parse(item);
            if (Array.isArray(parsed.results)) {
              results = parsed.results;
              break;
            }
          } catch {
            // Ignore non-JSON content items.
          }
        }
      }
    }

    setAnswer(results);

    if (!results.length) {
      setMessage("No relevant results found.");
    }
  } catch (e: any) {
    setMessage(e.message);
  } finally {
    setBusy(false);
  }
}

  async function uploadDocument(file: File) {
    setBusy(true); setMessage("");
    try { const body = new FormData(); body.append("file", file); const r = await jsonFetch("/api/documents/ingest", { method: "POST", body }); setMessage(`${r.status}: ${r.filename} (${r.chunks} chunks)`); }
    catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  }

  async function runTask() {
    setBusy(true); setMessage("");
    try { setTaskResult(await jsonFetch("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task, workspace_id: "demo" }) })); }
    catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  }

  async function decide(approved: boolean) {
    if (!taskResult) return;
    setBusy(true); setMessage("");
    try { const r = await jsonFetch(`/api/tasks/${taskResult.task_id}/approval`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approved }) }); setTaskResult({ ...taskResult, status: r.status, approval_required: false }); setMessage(r.status); }
    catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="mark">S</div><div><strong>SentinelForge</strong><small>AI Developer Platform</small></div></div>
      <nav><span className="active"><Activity size={17}/>Workspace</span><span><Database size={17}/>Knowledge</span><span><GitBranch size={17}/>Repository</span><span><Terminal size={17}/>Sandbox</span></nav>
      <div className="privacy"><ShieldCheck size={18}/><div><b>Privacy-first</b><small>Local processing enabled</small></div></div>
    </aside>
    <main>
      <header><div><p className="eyebrow">SENTINELFORGE / CONTROL PLANE</p><h1>Build with evidence. Execute with control.</h1></div><div className="status"><span></span> {status?.model_provider ? `${status.model_provider.toUpperCase()} / LOCAL` : "LOCAL MODE"}</div></header>
      {message && <div className="notice">{message}</div>}
      <section className="cards"><div className="card"><Database/><b>Local RAG</b><small>{status?.rag ? `${status.rag.documents} docs · ${status.rag.chunks} chunks` : "Indexed knowledge + citations"}</small></div><div className="card"><GitBranch/><b>MCP</b><small>Tool-driven developer workflow</small></div><div className="card"><Terminal/><b>Sandbox</b><small>Network isolated execution</small></div><div className="card"><ShieldCheck/><b>Approval Gate</b><small>No silent code changes</small></div></section>
      <section className="grid">
        <div className="panel">
          <div className="panelhead"><div><p className="label">KNOWLEDGE QUERY</p><h2>Ask about your workspace</h2></div><label className="upload"><Upload size={14}/> Upload<input type="file" accept=".pdf,.md,.markdown,.txt,.json,.py,.js,.ts,.tsx,.jsx" onChange={e => e.target.files?.[0] && uploadDocument(e.target.files[0])}/></label></div>
          <div className="inputrow"><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key === "Enter" && ask()} placeholder="Where is authentication implemented?"/><button onClick={ask} disabled={busy || !query}><Send size={16}/>{busy?"Working":"Retrieve"}</button></div>
          {answer.length>0 && <div className="results">{answer.map((x,i)=><article key={i}><div className="citation"><CheckCircle2 size={14}/> {x.source.filename} · {x.source.start_line ? `lines ${x.source.start_line}-${x.source.end_line}` : x.source.page ? `page ${x.source.page}` : x.source.section}</div><p>{x.content}</p></article>)}</div>}
        </div>
        <div className="panel">
          <p className="label">CODING AGENT</p><h2>Propose a safe change</h2>
          <textarea value={task} onChange={e=>setTask(e.target.value)} placeholder="Add email validation to register_user()"/>
          <button className="primary" onClick={runTask} disabled={busy || !task}><Terminal size={16}/>{busy?"Running agent":"Analyze & propose patch"}</button>
          {taskResult && <div className="agent"><div className="stage">PLAN</div><pre>{taskResult.plan}</pre><div className="stage">EVIDENCE</div><pre>{JSON.stringify(taskResult.evidence, null, 2)}</pre><div className="stage">UNIFIED DIFF</div><pre className="diff">{taskResult.diff || "No diff returned"}</pre><div className="stage">SANDBOX</div><pre>{JSON.stringify(taskResult.test,null,2)}</pre><div className="stage">SELF-CRITIQUE</div><pre>{taskResult.critique}</pre>{taskResult.approval_required ? <div className="approval"><span>Human approval required</span><button onClick={() => decide(false)} disabled={busy}><XCircle size={14}/>Reject</button><button className="approve" onClick={() => decide(true)} disabled={busy}><CheckCircle2 size={14}/>Approve patch</button></div> : <div className="approval"><span>Status: {taskResult.status}</span></div>}</div>}
        </div>
      </section>
      <footer><span><ShieldCheck size={14}/> Generated changes are never applied silently</span><span>OpenAPI: <code>/docs</code> · MCP: <code>/mcp</code></span></footer>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
