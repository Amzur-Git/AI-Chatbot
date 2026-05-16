import { useEffect, useMemo, useState } from "react";

type AgentEvent = {
  event: string;
  data: Record<string, unknown>;
};

type Paper = {
  arxiv_id: string;
  title: string;
  authors: string[];
  abstract: string;
  published: string;
  url: string;
  categories: string[];
};

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
    const line = packet.split("\n").find((entry) => entry.startsWith("data:"));
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
      // Ignore malformed chunks
    }
  }

  return events;
}

export default function ResearchDigest() {
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

    const response = await fetch("http://127.0.0.1:8010/api/research", {
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

  const toneForEvent = (event: string) => {
    if (event === "done") return "success";
    if (event === "error") return "warn";
    if (event === "searching" || event === "summarizing") return "info";
    return "muted";
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">AI Research Digest Agent</h1>
            <p className="mt-2 text-sm text-slate-600">
              LangGraph workflow that searches arXiv, summarizes papers with AI, and streams live reasoning.
            </p>
          </div>
          <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-700">
            {statusText}
          </span>
        </div>

        <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4">
            <div>
              <label className="text-sm font-semibold text-slate-700">Research Topic</label>
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. diffusion models in drug discovery"
                className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-2 text-sm outline-none ring-blue-500 transition focus:ring-2"
              />
            </div>
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
              className="w-full rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {running ? "Running agent..." : "Run Research Agent"}
            </button>
          </div>
        </section>

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-600">Live Agent Updates</h2>
            <div className="max-h-[560px] space-y-2 overflow-y-auto pr-2">
              {events.length === 0 && <p className="text-sm text-slate-500">No updates yet.</p>}
              {events.map((evt, index) => (
                <div key={`${evt.event}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="mb-1 text-xs font-semibold text-slate-600">{evt.event.replace(/_/g, " ")}</div>
                  <pre className="whitespace-pre-wrap text-xs text-slate-700">
                    {JSON.stringify(evt.data, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-600">Important Papers</h2>
            <div className="max-h-[560px] space-y-3 overflow-y-auto pr-2">
              {papers.length === 0 && <p className="text-sm text-slate-500">No papers captured yet.</p>}
              {papers.map((paper) => (
                <article key={paper.arxiv_id} className="rounded-lg border border-slate-200 p-3">
                  <a
                    href={paper.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-semibold text-blue-600 hover:underline"
                  >
                    {paper.title}
                  </a>
                  <p className="mt-1 text-xs text-slate-600">{paper.published || "Unknown date"}</p>
                  <p className="mt-2 text-xs text-slate-700">{paper.abstract.slice(0, 220)}...</p>
                </article>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-600">Final Research Digest</h2>
            <div className="max-h-[560px] overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-4">
              {digest ? (
                <pre className="whitespace-pre-wrap text-xs leading-6 text-slate-800">{digest}</pre>
              ) : (
                <p className="text-sm text-slate-500">Digest stream will appear here.</p>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
