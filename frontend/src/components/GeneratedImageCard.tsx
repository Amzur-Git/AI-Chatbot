import type { AttachmentPreview } from "../types";
import { useState } from "react";

type Props = {
  attachment: AttachmentPreview;
  prompt: string;
  disabled?: boolean;
  onRegenerate: (prompt?: string) => void;
};

export default function GeneratedImageCard({
  attachment,
  prompt,
  disabled = false,
  onRegenerate,
}: Props) {
  const [isExpanded, setIsExpanded] = useState(false);
  const imageUrl = attachment.downloadUrl || attachment.previewUrl;
  if (!imageUrl) {
    return null;
  }

  return (
    <>
      <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-3">
        <button
          type="button"
          onClick={() => setIsExpanded(true)}
          className="w-full"
          aria-label="Expand generated image"
        >
          <img
            src={imageUrl}
            alt={prompt || "Generated"}
            className="max-h-72 w-full rounded-xl object-contain"
          />
        </button>

        {prompt && <p className="mt-2 text-xs text-slate-500">Prompt: {prompt}</p>}

        <div className="mt-3 flex gap-2">
          <a
            href={imageUrl}
            target="_blank"
            rel="noreferrer"
            className="rounded-xl border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Open
          </a>
          <a
            href={imageUrl}
            download={attachment.name}
            className="rounded-xl border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Download
          </a>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onRegenerate(prompt)}
            className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:bg-slate-400"
          >
            Regenerate
          </button>
        </div>
      </div>

      {isExpanded ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true">
          <div className="max-h-[95vh] w-full max-w-5xl rounded-2xl bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-700">Generated Image</p>
              <button
                type="button"
                onClick={() => setIsExpanded(false)}
                className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700"
              >
                Close
              </button>
            </div>
            <img src={imageUrl} alt={prompt || "Generated"} className="max-h-[80vh] w-full rounded-xl object-contain" />
          </div>
        </div>
      ) : null}
    </>
  );
}
