import { useMemo } from "react";
import { useDropzone } from "react-dropzone";
import type { AttachmentPreview } from "../types";

type Props = {
  attachments: AttachmentPreview[];
  disabled?: boolean;
  helperText?: string | null;
  onFilesAdded: (files: File[]) => void;
  onRemoveAttachment: (attachmentId: string) => void;
  onClearAttachments: () => void;
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AttachmentComposer({
  attachments,
  disabled = false,
  helperText,
  onFilesAdded,
  onRemoveAttachment,
  onClearAttachments,
}: Props) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    disabled,
    multiple: true,
    onDrop: (files) => {
      if (files.length > 0) {
        onFilesAdded(files);
      }
    },
  });

  const pendingCount = useMemo(
    () => attachments.filter((item) => !item.isReady && !item.error).length,
    [attachments]
  );

  return (
    <div className="space-y-2">
      <div
        {...getRootProps()}
        className={`rounded-2xl border border-dashed px-4 py-3 text-sm transition ${
          disabled
            ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
            : isDragActive
            ? "cursor-pointer border-blue-500 bg-blue-50 text-blue-700"
            : "cursor-pointer border-slate-300 bg-slate-50 text-slate-600 hover:border-slate-400"
        }`}
      >
        <input {...getInputProps()} />
        {isDragActive ? "Drop files here..." : "Drop files here or click to attach"}
      </div>

      {attachments.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Attachments ({attachments.length})
            </p>
            <button
              type="button"
              onClick={onClearAttachments}
              className="text-xs font-medium text-red-600 hover:text-red-700"
            >
              Clear all
            </button>
          </div>

          <div className="space-y-2">
            {attachments.map((item) => (
              <div key={item.id} className="rounded-xl border border-slate-200 p-2.5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{item.name}</p>
                    <p className="text-xs text-slate-500">
                      {item.category.toUpperCase()} • {formatSize(item.size)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onRemoveAttachment(item.id)}
                    className="text-xs font-medium text-slate-500 hover:text-slate-700"
                  >
                    Remove
                  </button>
                </div>

                <div className="mt-2 h-1.5 rounded bg-slate-200">
                  <div
                    className={`h-1.5 rounded ${item.error ? "bg-red-500" : "bg-blue-500"}`}
                    style={{ width: `${Math.min(100, Math.max(0, item.progress))}%` }}
                  />
                </div>

                {item.error ? (
                  <p className="mt-1 text-xs text-red-600">{item.error}</p>
                ) : item.isReady ? (
                  <p className="mt-1 text-xs text-emerald-700">Ready</p>
                ) : (
                  <p className="mt-1 text-xs text-slate-500">Processing...</p>
                )}
              </div>
            ))}
          </div>

          {pendingCount > 0 && (
            <p className="mt-2 text-xs text-slate-500">
              {pendingCount} file(s) still processing.
            </p>
          )}
        </div>
      )}

      {helperText && <p className="text-xs text-amber-700">{helperText}</p>}
    </div>
  );
}
