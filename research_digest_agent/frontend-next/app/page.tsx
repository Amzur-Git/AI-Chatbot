"use client";

import { useMemo, useState } from "react";
import EventBadge from "../components/EventBadge";
import type { AgentEvent, Paper } from "../lib/types";

const API_BASE = process.env.NEXT_PUBLIC_RESEARCH_API_BASE ?? "http://127.0.0.1:8010";

const quickTopics = [
  "Retrieval Augmented Generation",
  "Vision Language Models",
  "Graph Neural Networks",
  "AI Agents",
  "Reinforcement Learning from Human Feedback",
];

function parseSseChunk(raw: string): AgentEvent[] {
  const events: AgentEvent[] = [];
  const packets = raw.split("\n\n");

  for (const packet of packets) {
    const line = packet
      .split("\n")
      .find((entry) => entry.startsWith("data:"));
    if (!line) {
      continue;
    }

    const payload = line.replace(/^data:\s*/, "").trim();
    if (!payload) {
      continue;
    }

    try {
      const parsed = JSON.parse(payload) as AgentEvent;
      events.push(parsed);
    } catch {
      // Ignore malformed chunks and continue processing stream.
    }
  }

  return events;
}

export default function HomePage() {
  const [topic, setTopic] = useState("Retrieval Augmented Generation");
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [digest, setDigest] = useState("");
  const [error, setError] = useState<string | null>(null);

  const statusText = useMemo(() => {
    if (!events.length) {
      return "Idle";
    }
    const latest = events[events.length - 1]?.event;
    return latest.replace(/_/g, " ");
  }, [events]);

  const pushEvent = (evt: AgentEvent) => {
    setEvents((prev) => [...prev, evt]);

    if (evt.event === "papers_found") {
      const fresh = (evt.data.papers as Paper[]) ?? [];
      setPapers((prev) => {
        const byId = new Map(prev.map((p) => [p.arxiv_id, p]));
        for (const paper of fresh) {
          byId.set(paper.arxiv_id, paper);
        }
        return Array.from(byId.values());
      });
    }

    if (evt.event === "digest_chunk") {
      const chunk = String(evt.data.chunk ?? "");
      setDigest((prev) => prev + chunk);
    }

    if (evt.event === "error") {
      setError(String(evt.data.message ?? "Unknown backend error"));
      setRunning(false);
    }

    if (evt.event === "done") {
      setRunning(false);
    }
  };

  const runResearch = async () => {
    if (!topic.trim() || running) {
      return;
    }

    setRunning(true);
    setEvents([]);
    setPapers([]);
    setDigest("");
    setError(null);

    const response = await fetch(`${API_BASE}/api/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic: topic.trim() }),
    });

    if (!response.ok || !response.body) {
      setError(`Request failed with status ${response.status}`);
      setRunning(false);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const parsed = parseSseChunk(`${part}\n\n`);
        for (const evt of parsed) {
          pushEvent(evt);
        }
      }
    }
  };

  const toneForEvent = (event: AgentEvent["event"]) => {
    if (event === "done") return "success" as const;
    if (event === "error") return "warn" as const;
    if (event === "searching" || event === "summarizing") return "info" as const;
    return "muted" as const;
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 md:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink">AI Research Digest Agent</h1>
          <p className="mt-2 text-sm text-slate-600">
            LangGraph workflow that searches arXiv, summarizes papers with AI, and streams live reasoning.
          </p>
        </div>
        <EventBadge label={statusText} tone={running ? "info" : "muted"} />
      </div>

      <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3">
          <label className="text-sm font-semibold text-slate-700">Research Topic</label>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. diffusion models in drug discovery"
            className="rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none ring-sky-500 transition focus:ring-2"
          />
          <div className="flex flex-wrap gap-2">
            {quickTopics.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setTopic(item)}
                className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
              >
                {item}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => {
              void runResearch();
            }}
            disabled={running}
            className="w-full rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:bg-sky-300"
          >
            {running ? "Running agent..." : "Run Research Agent"}
          </button>
        </div>
      </section>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-1">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Live Agent Updates</h2>
          <div className="max-h-[560px] space-y-2 overflow-y-auto pr-1">
            {events.length === 0 && <p className="text-sm text-slate-500">No updates yet.</p>}
            {events.map((evt, index) => (
              <div key={`${evt.event}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 p-2">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <EventBadge label={evt.event.replace(/_/g, " ")} tone={toneForEvent(evt.event)} />
                </div>
                <pre className="whitespace-pre-wrap text-xs text-slate-700">{JSON.stringify(evt.data, null, 2)}</pre>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-1">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Important Papers</h2>
          <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
            {papers.length === 0 && <p className="text-sm text-slate-500">No papers captured yet.</p>}
            {papers.map((paper) => (
              <article key={paper.arxiv_id} className="rounded-xl border border-slate-200 p-3">
                <a
                  href={paper.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-semibold text-sky-700 hover:underline"
                >
                  {paper.title}
                </a>
                <p className="mt-1 text-xs text-slate-600">{paper.published || "Unknown date"}</p>
                <p className="mt-2 text-xs text-slate-700">{paper.abstract.slice(0, 220)}...</p>
              </article>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-1">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Final Research Digest</h2>
          <div className="max-h-[560px] overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-3">
            {digest ? (
              <pre className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{digest}</pre>
            ) : (
              <p className="text-sm text-slate-500">Digest stream will appear here.</p>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
