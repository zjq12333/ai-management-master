import type {
  CoreEnvelope,
  CoreSnapshotPayload,
  CleanPayload,
  BackupCleanupPayload,
  RebuildRegistryPayload,
  AutoSwitchConfigPayload,
  ApiProxyMode,
  ApiModePayload,
  ApiProxyDetectPayload,
  ApiProxyTestPayload,
  UpdateInstallabilityPayload,
  DaemonRunPayload,
  DiagnosePayload,
  DiagnosticsBundlePayload,
  FirstRunCheckStatusPayload,
  McpServerListPayload,
  McpServerMutationPayload,
  McpServerRemovePayload,
  SkillListPayload,
  SkillBackupListPayload,
  SkillImportPayload,
  SkillRemovePayload,
  SkillRestorePayload,
  SkillDeleteBackupPayload,
  SkillTranslationCachePayload,
  SkillTranslationPayload,
  SkillTranslationRequestItem,
  CustomInstructionPreviewPayload,
  CustomInstructionStatePayload,
} from "@/types";
import type {
  PrelaunchLaunchPayload,
  PrelaunchMode,
  PrelaunchProviderPayload,
  PrelaunchRecoveryOptionsPayload,
  PrelaunchRuntimeStatusPayload,
  PrelaunchStopRuntimePayload,
  PrelaunchStatusPayload,
} from "@/types/prelaunch";
import type { EnhancerSettingsPayload } from "@/types/enhancer";
import type { LacControlSpaceStatusPayload } from "@/types/lac";
import { isTauriRuntime } from "@/lib/tauri-runtime";

async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (isTauriRuntime()) {
    const { invoke: tauriInvoke } = await import("@tauri-apps/api/core");
    return tauriInvoke<T>(cmd, args);
  }
  throw new Error(`Command "${cmd}" is only available in Tauri runtime`);
}

export const api = {
  lacControlSpaceStatus: () =>
    invoke<LacControlSpaceStatusPayload>("lac_control_space_status"),

  prelaunchStatus: (codexHome: string) =>
    invoke<PrelaunchStatusPayload>("prelaunch_status", { codexHome }),

  prelaunchRuntimeStatus: () =>
    invoke<PrelaunchRuntimeStatusPayload>("prelaunch_runtime_status"),

  prelaunchStopRuntime: () =>
    invoke<PrelaunchStopRuntimePayload>("prelaunch_stop_runtime"),

  prelaunchLaunch: (
    codexHome: string,
    mode: PrelaunchMode = "official",
    provider: PrelaunchProviderPayload | null,
    hideOfficialQuotaNotice = false,
    restoreHistory = false,
  ) =>
    invoke<PrelaunchLaunchPayload>("prelaunch_launch", {
      codexHome,
      mode,
      providerJson: provider ? JSON.stringify(provider) : null,
      hideOfficialQuotaNotice,
      restoreHistory,
    }),

  prelaunchRepair: (codexHome: string, options?: PrelaunchRecoveryOptionsPayload) =>
    invoke<PrelaunchLaunchPayload>("prelaunch_repair", { codexHome, ...options }),

  loadSnapshot: (localOnly = false) =>
    invoke<CoreEnvelope<CoreSnapshotPayload>>("load_snapshot", { localOnly }),

  clean: () =>
    invoke<CoreEnvelope<CleanPayload>>("clean"),

  cleanupDesktopHistoryBackups: (keepLatest: number) =>
    invoke<CoreEnvelope<BackupCleanupPayload>>("cleanup_desktop_history_backups", { keepLatest }),

  rebuildRegistry: () =>
    invoke<CoreEnvelope<RebuildRegistryPayload>>("rebuild_registry"),

  setAutoSwitch: (enabled: boolean) =>
    invoke<CoreEnvelope<AutoSwitchConfigPayload>>("set_auto_switch", { enabled }),

  configureAutoSwitch: (threshold5hPercent?: number, thresholdWeeklyPercent?: number) =>
    invoke<CoreEnvelope<AutoSwitchConfigPayload>>("configure_auto_switch", {
      threshold5hPercent,
      thresholdWeeklyPercent,
    }),

  setApiProxyConfig: (mode: ApiProxyMode, url?: string) =>
    invoke<CoreEnvelope<ApiModePayload>>("set_api_proxy_config", { mode, url }),

  getUsageRefreshInterval: () =>
    invoke<string>("get_usage_refresh_interval"),

  setUsageRefreshInterval: (interval: string) =>
    invoke<string>("set_usage_refresh_interval", { interval }),

  testApiProxyConfig: (mode: ApiProxyMode, url?: string) =>
    invoke<CoreEnvelope<ApiProxyTestPayload>>("test_api_proxy_config", { mode, url }),

  detectApiProxyConfig: () =>
    invoke<CoreEnvelope<ApiProxyDetectPayload>>("detect_api_proxy_config"),

  checkUpdateInstallability: () =>
    invoke<UpdateInstallabilityPayload>("check_update_installability"),

  runDaemonOnce: () =>
    invoke<CoreEnvelope<DaemonRunPayload>>("run_daemon_once"),

  diagnose: () =>
    invoke<CoreEnvelope<DiagnosePayload>>("diagnose"),

  firstRunSelfCheck: () =>
    invoke<CoreEnvelope<FirstRunCheckStatusPayload>>("first_run_self_check"),

  exportDiagnosticsBundle: () =>
    invoke<CoreEnvelope<DiagnosticsBundlePayload>>("export_diagnostics_bundle"),

  restartCodex: () =>
    invoke<void>("restart_codex"),

  gracefulRestartForUpdate: () =>
    invoke<void>("graceful_restart_for_update"),

  loadMcpServers: () =>
    invoke<CoreEnvelope<McpServerListPayload>>("load_mcp_servers"),

  upsertMcpServer: (config: Record<string, unknown> & { name: string }) =>
    invoke<CoreEnvelope<McpServerMutationPayload>>("upsert_mcp_server", config),

  setMcpServerEnabled: (name: string, enabled: boolean) =>
    invoke<CoreEnvelope<McpServerMutationPayload>>("set_mcp_server_enabled", { name, enabled }),

  removeMcpServer: (name: string) =>
    invoke<CoreEnvelope<McpServerRemovePayload>>("remove_mcp_server", { name }),

  loadInstalledSkills: () =>
    invoke<CoreEnvelope<SkillListPayload>>("load_installed_skills"),

  loadSkillBackups: () =>
    invoke<CoreEnvelope<SkillBackupListPayload>>("load_skill_backups"),

  loadSkillTranslations: () =>
    invoke<CoreEnvelope<SkillTranslationCachePayload>>("load_skill_translations"),

  translateSkillSummaries: (apiKey: string | null, items: SkillTranslationRequestItem[]) =>
    invoke<CoreEnvelope<SkillTranslationPayload>>("translate_skill_summaries", { apiKey, items }),

  importSkill: (sourcePath: string) =>
    invoke<CoreEnvelope<SkillImportPayload>>("import_skill", { sourcePath }),

  removeSkill: (name: string) =>
    invoke<CoreEnvelope<SkillRemovePayload>>("remove_skill", { name }),

  restoreSkillBackup: (name: string) =>
    invoke<CoreEnvelope<SkillRestorePayload>>("restore_skill_backup", { name }),

  deleteSkillBackup: (name: string) =>
    invoke<CoreEnvelope<SkillDeleteBackupPayload>>("delete_skill_backup", { name }),

  loadCustomInstructionState: () =>
    invoke<CoreEnvelope<CustomInstructionStatePayload>>("load_custom_instruction_state"),

  previewCustomInstructionApply: (params: { templateId?: string; templateCode?: string; templateTitle?: string; content: string; source?: string } | string, content?: string) => {
    const payload = typeof params === "string" ? { content: params, templateId: params, templateCode: params } : params;
    return invoke<CoreEnvelope<CustomInstructionPreviewPayload>>("preview_custom_instruction_apply", {
      templateId: payload.templateId ?? payload.templateCode ?? "manual",
      templateCode: payload.templateCode,
      templateTitle: payload.templateTitle,
      content: content ?? payload.content,
      source: payload.source,
    });
  },

  applyCustomInstruction: (params: { templateId?: string; templateCode?: string; templateTitle?: string; content: string; source?: string } | string, content?: string) => {
    const payload = typeof params === "string" ? { content: content ?? "", templateId: params } : params;
    return invoke<CoreEnvelope<CustomInstructionStatePayload>>("apply_custom_instruction", {
      templateId: payload.templateId ?? payload.templateCode ?? "manual",
      templateCode: payload.templateCode,
      templateTitle: payload.templateTitle,
      content: content ?? payload.content,
      source: payload.source,
    });
  },

  clearCustomInstructionBlock: () =>
    invoke<CoreEnvelope<CustomInstructionStatePayload>>("clear_custom_instruction_block"),

  rollbackCustomInstruction: (historyId?: string) =>
    invoke<CoreEnvelope<CustomInstructionStatePayload>>("rollback_custom_instruction", historyId ? { historyId } : undefined),

  hasNotch: () =>
    invoke<boolean>("has_notch").catch(() => false),

  getHotspotEnabled: () =>
    invoke<boolean>("get_hotspot_enabled"),

  setHotspotEnabled: (enabled: boolean) =>
    invoke<boolean>("set_hotspot_enabled", { enabled }),

  getEnhancerSettings: () =>
    invoke<EnhancerSettingsPayload>("get_enhancer_settings"),

  setChatInfoMoveEnabled: (enabled: boolean) =>
    invoke<EnhancerSettingsPayload>("set_chat_info_move_enabled", { enabled }),

  setOneClickHandoffEnabled: (enabled: boolean) =>
    invoke<EnhancerSettingsPayload>("set_one_click_handoff_enabled", { enabled }),

  setHideOfficialQuotaNoticeEnabled: (enabled: boolean) =>
    invoke<EnhancerSettingsPayload>("set_hide_official_quota_notice_enabled", { enabled }),

  setMustInstallPluginsEnabled: (enabled: boolean) =>
    invoke<EnhancerSettingsPayload>("set_must_install_plugins_enabled", { enabled }),

  focusMainWindow: () =>
    invoke<void>("focus_main_window"),

  hotspotReady: () =>
    invoke<void>("hotspot_ready"),

  openPath: (path: string) =>
    invoke<void>("open_path", { path }),

  getSystemInfo: () =>
    invoke<{ os: string; osVersion: string; arch: string; hostname: string }>("get_system_info"),

  windowControl: (action: "minimize" | "toggleMaximize" | "hide") =>
    invoke<void>("window_control", { action }),
};
