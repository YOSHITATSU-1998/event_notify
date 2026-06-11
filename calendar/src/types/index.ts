// 共有型定義

export type Event = {
  id: number;
  date: string;
  time?: string;
  title: string;
  venue: string;
  source_url?: string;
  notes?: string;
};

export type Notice = {
  id: number;
  title: string;
  body: string;
  start_at: string; // YYYY-MM-DD
  end_at: string;   // YYYY-MM-DD
  is_active: boolean;
  created_at: string;
};
