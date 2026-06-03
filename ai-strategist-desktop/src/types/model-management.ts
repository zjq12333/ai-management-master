export type ModelProviderKind = "openai-compatible" | "responses";

export interface ModelProviderConfig {
  id: string;
  name: string;
  kind: ModelProviderKind;
  baseUrl: string;
  apiKey?: string;
  defaultModel?: string;
  enabled: boolean;
}

export interface ModelRelayConfig {
  enabled: boolean;
  port: number;
  autoStart?: boolean;
  managementToken?: string;
}

export interface ModelGatewaySnapshot {
  schemaVersion?: number;
  providers: ModelProviderConfig[];
  defaultProviderId?: string;
  configPath: string;
  relay: ModelRelayConfig;
  modelRoutes: ModelRouteConfig[];
  fallbackOrder?: string[];
  routingPolicy?: ModelRoutingPolicy;
}

export type ModelRoutingPolicy = "first-match-then-default";

export interface ModelRouteConfig {
  id: string;
  modelPattern: string;
  providerId: string;
  enabled: boolean;
}

export interface ModelRouteSavePayload {
  route: ModelRouteConfig;
}

export interface ModelRelayStatusPayload {
  enabled: boolean;
  running: boolean;
  port: number;
  baseUrl: string;
  configPath: string;
}

export interface ModelRelayLogEntry {
  timestampMs: number;
  method: string;
  path: string;
  providerId?: string;
  status: number;
  latencyMs: number;
  error?: string;
}

export interface ModelRelayConfigPayload {
  enabled: boolean;
  port: number;
  autoStart?: boolean;
  managementToken?: string;
}

export interface ModelProviderSavePayload {
  provider: ModelProviderConfig;
  makeDefault?: boolean;
}

export interface UpstreamModel {
  id: string;
  ownedBy?: string;
}

export interface UpstreamModelsPayload {
  ok: boolean;
  providerId: string;
  endpoint: string;
  models: UpstreamModel[];
  error?: string;
}

export interface ModelProviderHealthPayload {
  ok: boolean;
  providerId: string;
  endpoint: string;
  status: string;
  latencyMs: number;
  modelCount: number;
  error?: string;
}
