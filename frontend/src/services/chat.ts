import api from './api';
import type { ChatHistoryItem } from '../types';

export const chatService = {
  async sendMessage(message: string): Promise<{ answer: string }> {
    const response = await api.post('/api/chat', { message });
    return response.data;
  },

  async getChatHistory(): Promise<ChatHistoryItem[]> {
    const response = await api.get('/api/history');
    return response.data;
  },
};
