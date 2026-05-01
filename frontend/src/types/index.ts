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
