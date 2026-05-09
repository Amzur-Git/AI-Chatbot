import type { AttachmentCategory, AttachmentPreview, ChatAttachmentPayload } from "../types";

export const MAX_ATTACHMENTS_PER_MESSAGE = 5;

export const SUPPORTED_EXTENSIONS = [
  "png",
  "jpg",
  "jpeg",
  "webp",
  "gif",
  "mp4",
  "mov",
  "webm",
  "csv",
  "xlsx",
  "pdf",
  "tex",
  "latex",
  "py",
  "java",
  "cpp",
  "sql",
  "ts",
  "js",
  "json",
] as const;

function inferCategory(extension: string, mimeType: string): AttachmentCategory {
  if (["png", "jpg", "jpeg", "webp", "gif"].includes(extension) || mimeType.startsWith("image/")) {
    return "image";
  }
  if (["mp4", "mov", "webm"].includes(extension) || mimeType.startsWith("video/")) {
    return "video";
  }
  if (["csv", "xlsx"].includes(extension)) {
    return "table";
  }
  if (["tex", "latex"].includes(extension)) {
    return "formula";
  }
  if (["py", "js", "ts", "java", "cpp", "json", "sql"].includes(extension)) {
    return "code";
  }
  return "document";
}

async function readTextIfSupported(file: File, extension: string): Promise<string | undefined> {
  if (["csv", "tex", "latex", "py", "js", "ts", "java", "cpp", "json", "sql"].includes(extension)) {
    const text = await file.text();
    return text.slice(0, 15000);
  }
  return undefined;
}

export async function buildAttachmentPreview(
  file: File,
  onProgress?: (progress: number) => void
): Promise<AttachmentPreview> {
  const extension = file.name.split(".").pop()?.toLowerCase() || "";
  const category = inferCategory(extension, file.type || "application/octet-stream");

  onProgress?.(0.25);
  const textContent = await readTextIfSupported(file, extension);
  onProgress?.(0.7);

  const previewUrl = category === "image" || category === "video" ? URL.createObjectURL(file) : undefined;

  onProgress?.(1);

  return {
    id: `${file.name}-${file.lastModified}`,
    file,
    name: file.name,
    mimeType: file.type || "application/octet-stream",
    extension,
    size: file.size,
    category,
    progress: 100,
    previewUrl,
    textContent,
    isReady: true,
  };
}

export function toAttachmentPayload(item: AttachmentPreview): ChatAttachmentPayload {
  return {
    upload_id: item.uploadId,
    name: item.name,
    mime_type: item.mimeType,
    size: item.size,
    category: item.category,
    text_content: item.textContent,
  };
}
