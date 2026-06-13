export type PrelaunchMode = "official" | "api" | "hybrid";

export type PrelaunchProjectlessMode = "none" | "all" | "current-only";

export interface PrelaunchRecoveryOptionsPayload {
  includeArchived: boolean;
  allowMissingCwd: boolean;
  allowEmptyCwd: boolean;
  allowMissingSession: boolean;
  projectlessMode: PrelaunchProjectlessMode;
  unarchiveSelected: boolean;
  historyRoot: string;
}

export interface PrelaunchProviderPayload {
  key: string;
  name: string;
  base_url: string;
  wire_api: string;
  env_key: string;
  requires_openai_auth: boolean;
  experimental_bearer_token: string;
}

export interface PrelaunchEvidencePayload {
  config_path?: string;
  config_model_provider: string | null;
  hybrid_provider_configured?: boolean;
  hybrid_provider_key?: string | null;
  auth_mode: string | null;
  threadripper_available?: boolean;
  threadripper_target_provider?: string | null;
  rows_needing_reconcile: number | null;
  provider_distribution: Record<string, number>;
}

export interface PrelaunchCodexPlusStatusPayload {
  relay: {
    authenticated: boolean;
    authSource: string;
    accountLabel: string | null;
    configPath: string;
    configured: boolean;
    requiresOpenaiAuth: boolean;
    hasBearerToken: boolean;
  };
  providerSync: {
    status: "readOnly";
    targetProvider: string;
  };
}

export interface PrelaunchStatusPayload {
  ok: boolean;
  evidence: PrelaunchEvidencePayload;
  codexPlus?: PrelaunchCodexPlusStatusPayload;
}

export interface PrelaunchRuntimeStatusPayload {
  ok: boolean;
  codex_running: boolean;
  processes: Array<{
    image?: string;
    pid?: number | null;
  }>;
}

export interface PrelaunchEnvironmentPayload {
  ok: boolean;
  codexHome: {
    path: string;
    exists: boolean;
  };
  config: {
    path: string;
    exists: boolean;
    modelProvider: string | null;
    hybridProviderConfigured: boolean;
    hybridProviderKey: string | null;
    authMode: string | null;
    authPath: {
      path: string;
      exists: boolean;
    };
    statePath: {
      path: string;
      exists: boolean;
    };
  };
  bridge: {
    programPath: string | null;
    scriptPath: string;
    exePath: string | null;
    usesExe: boolean;
    available: boolean;
  };
  runtimes: {
    python: {
      path: string;
      source: string;
    };
    threadripper: string | null;
    threadripperAvailable: boolean;
  };
  codexDesktop: {
    productResolvedExe: string | null;
    productResolvedSource: string | null;
    appid: string | null;
    lastResortExe: string | null;
    launchAvailable: boolean;
    running: boolean;
  };
  runtime: PrelaunchRuntimeStatusPayload;
  blockers: string[];
  warnings: string[];
}

export interface PrelaunchStopRuntimePayload {
  ok: boolean;
  killed: Array<{
    image?: string;
    pid?: number | null;
  }>;
  remaining: Array<{
    image?: string;
    pid?: number | null;
  }>;
  errors?: string[];
}

export interface PrelaunchProviderCompatibilityPayload {
  ok?: boolean;
  skipped?: boolean;
  reason?: string;
  error?: string;
  status?: {
    target_provider?: string | null;
    rows_needing_reconcile?: number | null;
    raw?: string;
  };
}

export interface PrelaunchThreadAttributionPayload {
  id?: string | null;
  target_location?: string;
  workspace_root?: string | null;
  reason?: string;
  provider?: string;
  session_path?: string | null;
  title?: string | null;
}

export interface PrelaunchLaunchPayload {
  ok: boolean;
  started_at?: string;
  finished_at?: string;
  kind?: string;
  mode?: string;
  codex_home?: string;
  report_dir?: string;
  provider_config?: {
    config_path?: string;
    backup_path?: string;
    mode?: string;
    target_model_provider?: string;
    verified_model_provider?: string;
  };
  notice_suppression?: {
    ok?: boolean;
    skipped?: boolean;
    reason?: string;
    method?: string;
    marker_path?: string;
    error?: string;
    leveldb_present?: boolean;
  };
  provider_compatibility?: PrelaunchProviderCompatibilityPayload;
  sync?: PrelaunchProviderCompatibilityPayload;
  repair?: {
    ok?: boolean;
    error?: string;
    summary?: {
      codex_home?: string;
      dry_run?: boolean;
      threads_total?: number;
      threads_selected?: number;
      threads_skipped?: number;
      skip_reasons?: Record<string, number>;
      providers?: Record<string, number>;
      provider_diagnostics?: Record<string, number>;
      archived_total?: number;
      workspace_roots_selected?: number;
      thread_attributions?: PrelaunchThreadAttributionPayload[];
      backup_dir?: string;
      session_index_rows?: number;
      unarchived?: number;
      thread_hints?: number;
      saved_workspace_roots?: number;
      active_workspace_roots?: string[];
      projectless_thread_ids?: number;
    };
  };
  launch?: {
    ok?: boolean;
    method?: string;
    exe?: string;
    appid?: string;
    error?: string;
    skipped?: boolean;
    reason?: string;
  };
  error?: string;
  status?: string;
}
