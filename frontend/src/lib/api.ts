import type { Bootstrap, Message, RunRecord, Settings, Chat, Project, SecurityFinding } from './types';

const BASE_URL = 'http://127.0.0.1:8765';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export const api = {
  bootstrap: () => request<Bootstrap>('/bootstrap'),
  messages: (chatId: string) => request<{ messages: Message[] }>(`/chats/${chatId}/messages`),
  createProject: (payload: { name: string; description: string; approved_directories: string[] }) =>
    request<{ project: Project }>('/projects', { method: 'POST', body: JSON.stringify(payload) }),
  createChat: (payload: { title: string; project_id?: string | null }) =>
    request<{ chat: Chat }>('/chats', { method: 'POST', body: JSON.stringify(payload) }),
  sendMessage: (payload: { chat_id: string; project_id?: string | null; content: string; current_url?: string; target_directory?: string }) =>
    request<{ message: Message; run_id: string; plan: RunRecord['plan']; intent: string }>('/messages', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  execute: (payload: { run_id: string; approved: boolean; dry_run: boolean }) =>
    request<{ summary: RunRecord['execution_summary']; logs: Array<Record<string, unknown>>; findings: SecurityFinding[] }>('/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  rollback: (runId: string) => request<{ status: string; messages: string[] }>(`/rollback/${runId}`, { method: 'POST' }),
  history: () => request<{ runs: RunRecord[] }>('/history'),
  settings: () => request<Settings>('/settings'),
  saveSettings: (settings: Settings) => request<Settings>('/settings', { method: 'POST', body: JSON.stringify(settings) }),
  quickScan: (paths: string[]) => request<{ findings: SecurityFinding[] }>('/security/quick-scan', { method: 'POST', body: JSON.stringify({ paths }) }),
  startMonitor: (folder_path: string) => request<Record<string, unknown>>('/security/monitor/start', { method: 'POST', body: JSON.stringify({ folder_path }) }),
  stopMonitor: (monitor_id: string) => request<Record<string, unknown>>('/security/monitor/stop', { method: 'POST', body: JSON.stringify({ monitor_id }) }),
  findings: () => request<{ findings: SecurityFinding[]; monitors: Array<Record<string, unknown>> }>('/security/findings'),
};
