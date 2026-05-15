export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  id?: number;
  thread_id?: number | null;
  created_at?: string;
  attachments?: AttachmentPreview[];
  mode_used?: ChatMode;
  is_image_generation?: boolean;
  image_prompt?: string;
  image_loading?: boolean;
  image_error?: string;
};

export type AttachmentCategory = "image" | "video" | "document" | "table" | "code" | "formula";

export type AttachmentPreview = {
  id: string;
  file?: File;
  uploadId?: number;
  downloadUrl?: string;
  name: string;
  mimeType: string;
  extension: string;
  size: number;
  category: AttachmentCategory;
  progress: number;
  previewUrl?: string;
  textContent?: string;
  isReady: boolean;
  error?: string;
};

export type ChatAttachmentPayload = {
  upload_id?: number;
  name: string;
  mime_type: string;
  size: number;
  category: AttachmentCategory;
  text_content?: string;
};

export type ChatMode = "normal" | "rag" | "db";

export type UploadAttachmentResponse = {
  id: number;
  name: string;
  mime_type: string;
  category: AttachmentCategory;
  size: number;
  text_content?: string;
  download_url: string;
};

export type GenerateImagePayload = {
  id?: number;
  name: string;
  mime_type: string;
  category: "image";
  size: number;
  download_url?: string;
  data_url?: string;
};

export type GenerateImageResponse = {
  answer: string;
  prompt: string;
  thread_id?: number | null;
  generation_id: number;
  status: string;
  image: GenerateImagePayload;
};

export type ImageCapabilityResponse = {
  available: boolean;
  reason?: string | null;
  model?: string;
  normalized_model?: string;
  fallback_models?: string[];
  max_prompt_chars?: number;
  rate_limit_per_minute?: number;
};

export type ImageHistoryItem = {
  id: number;
  thread_id?: number | null;
  prompt: string;
  status: string;
  error_message?: string | null;
  requested_by_message_id?: number | null;
  result_message_id?: number | null;
  created_at?: string | null;
  completed_at?: string | null;
  image?: UploadAttachmentResponse | null;
};

export type ImageHistoryResponse = {
  items: ImageHistoryItem[];
};

export type RagChunkSample = {
  id: string;
  attachment_id?: number | null;
  source_name?: string | null;
  chunk_index?: number | null;
  preview: string;
};

export type RagDebugResponse = {
  collection: string;
  total_chunks: number;
  sample_count: number;
  samples: RagChunkSample[];
};

export type User = {
  id: number;
  email: string;
  name: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type ChatHistoryItem = {
  id: number;
  role: string;
  thread_id?: number | null;
  content: string;
  created_at: string;
  attachments?: ChatHistoryAttachment[];
};

export type ChatHistoryAttachment = {
  id: number;
  name: string;
  mime_type: string;
  category: AttachmentCategory;
  size: number;
  text_content?: string;
  download_url: string;
};

export type ChatSidebarItem = {
  id: number;
  title: string;
  preview?: string;
  user_message?: string;
  assistant_preview?: string | null;
  created_at: string;
};
