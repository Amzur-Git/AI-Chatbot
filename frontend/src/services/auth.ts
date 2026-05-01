import api from './api';
import type { AuthResponse, User } from '../types';

type ManualRegisterPayload = {
  name: string;
  email: string;
  password: string;
};

type ManualLoginPayload = {
  email: string;
  password: string;
};

export const authService = {
  async register(payload: ManualRegisterPayload): Promise<AuthResponse> {
    const response = await api.post('/api/auth/register', payload);
    return response.data;
  },

  async login(payload: ManualLoginPayload): Promise<AuthResponse> {
    const response = await api.post('/api/auth/login', payload);
    return response.data;
  },

  async getGoogleAuthUrl(): Promise<{ auth_url: string }> {
    const response = await api.get('/api/auth/google/login');
    return response.data;
  },

  async handleGoogleCallback(code: string): Promise<AuthResponse> {
    const response = await api.get(`/api/auth/google/callback?code=${encodeURIComponent(code)}&mode=json`);
    return response.data;
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get('/api/auth/me');
    return response.data;
  },

  setAuthData(data: AuthResponse) {
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
  },

  getAuthData(): { token: string | null; user: User | null } {
    const token = localStorage.getItem('access_token');
    const user = localStorage.getItem('user');
    return {
      token,
      user: user ? JSON.parse(user) : null,
    };
  },

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token');
  },
};