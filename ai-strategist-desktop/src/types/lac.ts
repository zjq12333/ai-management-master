export interface LacControlSpaceAvailabilityCheck {
  name: string;
  ok: boolean;
  value?: unknown;
}

export interface LacControlSpaceGap {
  id: string;
  reason: string;
}

export interface LacControlSpaceSnapshot {
  source_room: "lac_control_space";
  purpose: string;
  generated_at: number;
  availability: {
    status: string;
    health_status: string;
    failed_checks: string[];
    checks: LacControlSpaceAvailabilityCheck[];
  };
  latency: {
    recent_request_count: number;
    mode_counts: Record<string, number>;
    request_ms: {
      status: string;
      sample_count: number;
      avg_ms?: number;
      min_ms?: number;
      max_ms?: number;
    };
  };
  routing_quality: {
    ordinary_chat_default: string;
    advisory_context_enabled: boolean;
    semantic_router_enabled: boolean;
    local_cache_lookup_enabled: boolean;
    recent_mode_counts: Record<string, number>;
  };
  safety: {
    ordinary_chat_default: string;
    memory_on_ordinary_chat: boolean;
    router_model_on_ordinary_chat: boolean;
    advisory_context_enabled: boolean;
    relay_response_cache_write_enabled: boolean;
    semantic_router_runtime_enabled: boolean;
  };
  memory_quality: {
    backend?: string | null;
    backend_root?: string | null;
    local_cache: {
      enabled: boolean;
      active_entry_count: number;
      expired_entry_count: number;
      store_relay_responses: boolean;
    };
    memory_candidates: {
      enabled: boolean;
      path: string;
      candidate_count: number;
    };
  };
  cost_control: {
    budget_policy_enabled: boolean;
    default_profile: string;
    profiles: Record<string, { default_max_output_tokens?: number; hard_max_output_tokens?: number }>;
    recent_budget_profile_counts: Record<string, number>;
  };
  execution_reliability: {
    health_status: string;
    recent_request_count: number;
    recent_non_2xx_count: number;
    recent_status_codes: number[];
  };
  gaps: LacControlSpaceGap[];
}

export interface LacControlSpaceStatusPayload {
  ok: boolean;
  reachable: boolean;
  endpoint: string;
  status_code: number | null;
  error: string | null;
  snapshot: LacControlSpaceSnapshot | null;
}
