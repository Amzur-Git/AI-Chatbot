import { useEffect } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-clike";
import "prismjs/components/prism-c";
import "prismjs/components/prism-python";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-java";
import "prismjs/components/prism-cpp";
import "prismjs/components/prism-json";
import "prismjs/components/prism-sql";
import { BlockMath } from "react-katex";
import type { AttachmentPreview } from "../types";

type Props = {
  content: string;
  attachments?: AttachmentPreview[];
};

function renderMessageContent(content: string) {
  const parts = content.split(/```([\s\S]*?)```/g);

  return parts.map((part, index) => {
    if (index % 2 === 1) {
      return (
        <pre key={`code-${index}`} className="mt-2 overflow-x-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">
          <code className="language-javascript">{part}</code>
        </pre>
      );
    }

    return (
      <p key={`text-${index}`} className="whitespace-pre-wrap leading-relaxed">
        {part}
      </p>
    );
  });
}

function languageFromExtension(ext: string): string {
  switch (ext) {
    case "py":
      return "python";
    case "js":
      return "javascript";
    case "ts":
      return "typescript";
    case "java":
      return "java";
    case "cpp":
      return "cpp";
    case "json":
      return "json";
    case "sql":
      return "sql";
    default:
      return "none";
  }
}

export default function MessageContent({ content, attachments = [] }: Props) {
  useEffect(() => {
    Prism.highlightAll();
  }, [content, attachments]);

  return (
    <div>
      {renderMessageContent(content)}
      {attachments.length > 0 && (
        <div className="mt-3 space-y-3">
          {attachments.map((attachment) => {
            const href = attachment.downloadUrl || attachment.previewUrl;
            if (attachment.category === "image" && href) {
              return (
                <div key={attachment.id} className="rounded-xl border border-slate-200 bg-white p-2">
                  <img src={href} alt={attachment.name} className="max-h-72 w-full rounded-lg object-contain" />
                  <a href={href} target="_blank" rel="noreferrer" className="mt-2 block text-xs font-medium underline">
                    {attachment.name}
                  </a>
                </div>
              );
            }

            if (attachment.category === "video" && href) {
              return (
                <div key={attachment.id} className="rounded-xl border border-slate-200 bg-white p-2">
                  <video controls className="max-h-72 w-full rounded-lg" src={href} />
                  <a href={href} target="_blank" rel="noreferrer" className="mt-2 block text-xs font-medium underline">
                    {attachment.name}
                  </a>
                </div>
              );
            }

            if (attachment.category === "formula" && attachment.textContent) {
              return (
                <div key={attachment.id} className="rounded-xl border border-slate-200 bg-white p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Formula</p>
                  <BlockMath math={attachment.textContent} />
                  {href && (
                    <a href={href} target="_blank" rel="noreferrer" className="mt-2 block text-xs font-medium underline">
                      {attachment.name}
                    </a>
                  )}
                </div>
              );
            }

            if (attachment.category === "code" && attachment.textContent) {
              const language = languageFromExtension(attachment.extension);
              return (
                <div key={attachment.id} className="rounded-xl border border-slate-200 bg-white p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Code</p>
                  <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                    <code className={`language-${language}`}>{attachment.textContent}</code>
                  </pre>
                  {href && (
                    <a href={href} target="_blank" rel="noreferrer" className="mt-2 block text-xs font-medium underline">
                      {attachment.name}
                    </a>
                  )}
                </div>
              );
            }

            if (attachment.category === "table") {
              return (
                <div key={attachment.id} className="rounded-xl border border-slate-200 bg-white p-3">
                  <p className="text-sm font-semibold text-slate-800">{attachment.name}</p>
                  <p className="mt-1 text-xs text-slate-500">Table file • {(attachment.size / 1024).toFixed(1)} KB</p>
                  {attachment.textContent && (
                    <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-slate-50 p-2 text-xs text-slate-700">
                      <code>{attachment.textContent}</code>
                    </pre>
                  )}
                  {href && (
                    <a href={href} target="_blank" rel="noreferrer" className="mt-2 block text-xs font-medium underline">
                      Open file
                    </a>
                  )}
                </div>
              );
            }

            return (
              <div key={attachment.id} className="rounded-xl border border-slate-200 bg-white p-3 text-xs">
                {href ? (
                  <a href={href} target="_blank" rel="noreferrer" className="font-medium underline">
                    {attachment.name} ({attachment.category})
                  </a>
                ) : (
                  <span className="font-medium">{attachment.name} ({attachment.category})</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
