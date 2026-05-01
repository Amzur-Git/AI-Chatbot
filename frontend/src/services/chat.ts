import api from './api';
import type { ChatHistoryItem, ChatSidebarItem } from '../types';

export const chatService = {
  async sendMessage(message: string): Promise<{ answer: string }> {
    const response = await api.post('/api/chat', { message });
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
};