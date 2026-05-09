import type { RagDebugResponse } from "../types";

type Props = {
  data: RagDebugResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
};

export default function RagDebugPanel({ data, loading, error, onRefresh }: Props) {
  return (
    <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">RAG Debug</p>
        <button
          type="button"
          onClick={onRefresh}
          className="text-xs font-medium text-slate-700 hover:text-slate-900"
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {!error && !data && <p className="text-xs text-slate-500">No debug data yet.</p>}

      {data && (
        <div className="space-y-1 text-xs text-slate-600">
          <p>Collection: {data.collection}</p>
          <p>Total chunks: {data.total_chunks}</p>
          <p>Sample chunks: {data.sample_count}</p>
        </div>
      )}
    </div>
  );
}
