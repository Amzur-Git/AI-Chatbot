import api from './api';
import type {
  AttachmentCategory,
  ChatAttachmentPayload,
  ChatMode,
  ChatHistoryItem,
  ImageHistoryResponse,
  ChatSidebarItem,
  GenerateImageResponse,
  ImageCapabilityResponse,
  RagDebugResponse,
  UploadAttachmentResponse,
} from '../types';

export const chatService = {
  async sendMessage(
    message: string,
    attachments: ChatAttachmentPayload[] = [],
    onUploadProgress?: (progress: number) => void,
    threadId?: number | null,
    mode: ChatMode = "normal",
    ragAttachmentIds: number[] = [],
    resetHistory: boolean = false
  ): Promise<{ answer: string }> {
    const response = await api.post(
      '/api/chat',
      {
        message,
        attachments,
        thread_id: threadId || null,
        mode,
        rag_attachment_ids: ragAttachmentIds,
        reset_history: resetHistory,
      },
      {
        timeout: 90000,
        onUploadProgress: (event) => {
          if (!event.total || !onUploadProgress) {
            return;
          }
          const progress = Math.round((event.loaded / event.total) * 100);
          onUploadProgress(progress);
        },
      }
    );
    return response.data;
  },

  async getChatHistory(): Promise<ChatHistoryItem[]> {
    const response = await api.get('/api/history');
    return response.data;
  },

  async getSidebarHistory(): Promise<ChatSidebarItem[]> {
    const response = await api.get('/api/history/sidebar');
    return response.data;
  },

  async uploadAttachment(
    file: File,
    _category: AttachmentCategory,
    onUploadProgress?: (progress: number) => void
  ): Promise<UploadAttachmentResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/api/uploads', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (event) => {
        if (!event.total || !onUploadProgress) {
          return;
        }
        const progress = Math.round((event.loaded / event.total) * 100);
        onUploadProgress(progress);
      },
    });

    return response.data;
  },

  async deleteAttachment(uploadId: number): Promise<void> {
    await api.delete(`/api/uploads/${uploadId}`);
  },

  async generateImage(prompt: string, threadId?: number | null): Promise<GenerateImageResponse> {
    const response = await api.post('/api/chat/image', { prompt, thread_id: threadId ?? null });
    return response.data;
  },

  async getImageHistory(threadId?: number | null, limit: number = 30): Promise<ImageHistoryResponse> {
    const response = await api.get('/api/chat/image/history', {
      params: {
        thread_id: threadId ?? undefined,
        limit,
      },
    });
    return response.data;
  },

  async getImageCapabilities(): Promise<ImageCapabilityResponse> {
    const response = await api.get('/api/chat/image/capabilities');
    return response.data;
  },

  async getRagDebugInfo(): Promise<RagDebugResponse> {
    const response = await api.get('/api/rag/debug');
    return response.data;
  },

  async deleteThread(threadId: number): Promise<void> {
    await api.delete(`/api/history/${threadId}`);
  },
};