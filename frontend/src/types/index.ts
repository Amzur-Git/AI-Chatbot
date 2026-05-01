export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  id?: number;
  created_at?: string;
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
  content: string;
  created_at: string;
};

export type ChatSidebarItem = {
  id: number;
  title: string;
  user_message: string;
  assistant_preview: string | null;
  created_at: string;
};
