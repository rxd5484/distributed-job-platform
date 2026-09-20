"use client";

import { FormEvent, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Job = {
  id: string;
  job_type: string;
  status: string;
  priority: number;
  attempts: number;
  max_retries: number;
  timeout_seconds: number;
  result: Record<string, unknown> | null;
  error: string | null;
};

type Stats = {
  ready: number;
  delayed: number;
  processing: number;
  dead_letter: number;
  active_workers: number;
};

const presets: Record<string, Record<string, unknown>> = {
  generate_report: { records: 5000 },
  process_csv: { rows: 10000, invalid_ratio: 0.02 },
  send_notification: { channel: "email", recipient: "demo@example.com" },
  fail_first_n: { fail_first_n: 2 },
  slow_task: { seconds: 8 },
  fibonacci: { n: 35 }
};

export default function Home() {
  const [jobType, setJobType] = useState("generate_report");
  const [payload, setPayload] = useState(JSON.stringify(presets.generate_report, null, 2));
  const [priority, setPriority] = useState(7);
  const [timeout, setTimeout] = useState(10);
  const [maxRetries, setMaxRetries] = useState(3);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [j, s] = await Promise.all([
        fetch(`${API_URL}/jobs?limit=30`, { cache: "no-store" }),
        fetch(`${API_URL}/stats`, { cache: "no-store" })
      ]);
      setJobs(await j.json());
      setStats(await s.json());
      setError("");
    } catch {
      setError("Could not reach TaskForge API.");
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 1500);
    return () => clearInterval(timer);
  }, []);

  function chooseType(type: string) {
    setJobType(type);
    setPayload(JSON.stringify(presets[type], null, 2));
    setTimeout(type === "slow_task" ? 2 : 10);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const response = await fetch(`${API_URL}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_type: jobType,
          payload: JSON.parse(payload),
          priority,
          timeout_seconds: timeout,
          max_retries: maxRetries
        })
      });
      if (!response.ok) throw new Error("Submit failed");
      await refresh();
    } catch {
      setError("Job submission failed.");
    }
  }

  async function requeue(id: string) {
    await fetch(`${API_URL}/dlq/${id}/requeue`, { method: "POST" });
    await refresh();
  }

  return (
    <main>
      <section className="hero">
        <div className="eyebrow">DISTRIBUTED SYSTEMS · BACKEND ENGINEERING</div>
        <h1>TaskForge</h1>
        <p>Priority queues, retries, timeouts, worker recovery, idempotency, and dead-letter handling.</p>
        <div className="flow">
          <span>Next.js</span><b>→</b><span>FastAPI</span><b>→</b>
          <span>Redis</span><b>→</b><span>Workers</span><b>→</b><span>PostgreSQL</span>
        </div>
      </section>

      <section className="stats">
        <div><span>Ready</span><strong>{stats?.ready ?? "—"}</strong></div>
        <div><span>Processing</span><strong>{stats?.processing ?? "—"}</strong></div>
        <div><span>Retrying</span><strong>{stats?.delayed ?? "—"}</strong></div>
        <div><span>DLQ</span><strong>{stats?.dead_letter ?? "—"}</strong></div>
        <div><span>Workers</span><strong>{stats?.active_workers ?? "—"}</strong></div>
      </section>

      <section className="grid">
        <form className="card" onSubmit={submit}>
          <div className="kicker">SUBMIT JOB</div>
          <h2>Create work</h2>

          <label>Job type
            <select value={jobType} onChange={(e) => chooseType(e.target.value)}>
              {Object.keys(presets).map((x) => <option key={x}>{x}</option>)}
            </select>
          </label>

          <label>Payload JSON
            <textarea rows={8} value={payload} onChange={(e) => setPayload(e.target.value)} />
          </label>

          <div className="triple">
            <label>Priority<input type="number" min="1" max="10" value={priority} onChange={(e) => setPriority(Number(e.target.value))} /></label>
            <label>Timeout<input type="number" min="1" max="120" value={timeout} onChange={(e) => setTimeout(Number(e.target.value))} /></label>
            <label>Retries<input type="number" min="0" max="10" value={maxRetries} onChange={(e) => setMaxRetries(Number(e.target.value))} /></label>
          </div>

          <button>Submit job</button>
        </form>

        <section className="card">
          <div className="kicker">LIVE QUEUE</div>
          <h2>Recent jobs</h2>
          {error && <p className="error">{error}</p>}

          <div className="joblist">
            {jobs.map((job) => (
              <article key={job.id} className="job">
                <div className="jobtop">
                  <div><h3>{job.job_type}</h3><code>{job.id.slice(0, 8)}</code></div>
                  <span className={`pill ${job.status.toLowerCase()}`}>{job.status}</span>
                </div>
                <p>priority {job.priority} · attempt {job.attempts}/{job.max_retries + 1} · timeout {job.timeout_seconds}s</p>
                {job.error && <p className="joberror">{job.error}</p>}
                {job.result && <pre>{JSON.stringify(job.result, null, 2)}</pre>}
                {job.status === "DEAD_LETTER" && <button onClick={() => requeue(job.id)} type="button">Requeue</button>}
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
