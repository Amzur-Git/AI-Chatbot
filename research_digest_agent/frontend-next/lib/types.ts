export type AgentEventType =
  | "agent_start"
  | "reasoning"
  | "searching"
  | "papers_found"
  | "summarizing"
  | "evaluation_result"
  | "synthesizing"
  | "digest_chunk"
  | "done"
  | "error";

export type AgentEvent = {
  event: AgentEventType;
  data: Record<string, unknown>;
};

export type Paper = {
  arxiv_id: string;
  title: string;
  authors: string[];
  abstract: string;
  published: string;
  url: string;
  categories: string[];
};
