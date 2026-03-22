export type ValidationIssue = { level: 'info' | 'warning' | 'error'; message: string; action_id?: string | null };

export type ResearchSource = { title: string; domain: string; url: string; summary: string; official: boolean };

export type SecurityFinding = {
  id: string;
  title: string;
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical';
  confidence: number;
  category: string;
  evidence: string[];
  affected_path_or_process: string;
  first_seen: string;
  recommended_action: string;
  false_positive_possible: boolean;
  status: string;
};

export type PlanAction = {
  id: string;
  type: string;
  description: string;
  params: Record<string, unknown>;
  risk_level: 'low' | 'medium' | 'high';
  requires_confirmation: boolean;
  execution_lane: 'background_safe' | 'reserved_control';
  target_app: string;
  confidence: number;
  evidence: string[];
  fallback_strategy: string;
  status: string;
};

export type Plan = {
  plan_id: string;
  prompt: string;
  mode: 'mock' | 'llm';
  created_at: string;
  target_directory: string;
  actions: PlanAction[];
  notes: string[];
  validation: { allowed: boolean; issues: ValidationIssue[] };
  sources: ResearchSource[];
  findings: SecurityFinding[];
};

export type Message = {
  id: string;
  chat_id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  created_at: string;
  message_type: string;
  run_id?: string | null;
  plan?: Plan | null;
  sources: ResearchSource[];
  findings: SecurityFinding[];
  metadata: Record<string, unknown>;
};

export type Chat = { id: string; title: string; project_id?: string | null; created_at: string; updated_at: string };
export type Project = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  approved_directories: string[];
  browser_memory: Record<string, unknown>;
  docs_memory: Record<string, unknown>;
  task_recipes: Array<Record<string, unknown>>;
};

export type Settings = {
  planner_mode: string;
  model_mode: string;
  local_model_provider: string;
  local_model_endpoint: string;
  theme: string;
  browser_automation_enabled: boolean;
  browser_mode: string;
  browser_profile_path: string;
  preferred_docs_domains: string[];
  docs_research_enabled: boolean;
  allow_community_sources: boolean;
  max_research_depth: number;
  project_memory_enabled: boolean;
  allowed_directories: string[];
  backup_location: string;
  quarantine_location: string;
  logs_export_folder: string;
  retention_runs: number;
  security_watched_folders: string[];
  scan_exclusions: string[];
  yara_path: string;
  clamav_path: string;
  voice_mode: string;
  require_approval_before_foreground_control: boolean;
  maximum_concurrent_background_jobs: number;
  default_dry_run: boolean;
};

export type RunRecord = {
  run_id: string;
  created_at: string;
  prompt: string;
  status: string;
  target_directory: string;
  planner_mode: string;
  chat_id: string;
  project_id?: string | null;
  plan: Plan;
  validation: { allowed: boolean; issues: ValidationIssue[] };
  execution_summary?: {
    run_id: string;
    success: boolean;
    completed_actions: number;
    failed_actions: number;
    rollback_available: boolean;
    message: string;
    high_level_result: string;
    lane_usage: string[];
    highlights: string[];
  } | null;
  rollback_available: boolean;
  sources: ResearchSource[];
  findings: SecurityFinding[];
};

export type Bootstrap = {
  settings: Settings;
  projects: Project[];
  chats: Chat[];
  sample_prompts: string[];
  demo_paths: Record<string, string>;
  security: { findings: SecurityFinding[]; monitors: Array<Record<string, unknown>> };
};
