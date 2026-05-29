import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Database, KeyRound, Rocket, ShieldCheck, Wrench } from "lucide-react";

import { BentoCard } from "@/components/ui/bento-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { api } from "@/lib/api";
import type { EnhancerSettingsPayload } from "@/types/enhancer";
import type {
  PrelaunchLaunchPayload,
  PrelaunchMode,
  PrelaunchProviderPayload,
  PrelaunchRecoveryOptionsPayload,
  PrelaunchStopRuntimePayload,
  PrelaunchThreadAttributionPayload,
  PrelaunchStatusPayload,
} from "@/types/prelaunch";

function getDefaultCodexHome() {
  const injectedCodexHome = import.meta.env.VITE_DEFAULT_CODEX_HOME?.trim();
  if (injectedCodexHome) return injectedCodexHome;
  return globalThis.navigator?.platform?.toLowerCase().startsWith("win")
    ? "%USERPROFILE%\\.codex"
    : "~/.codex";
}

export const DEFAULT_CODEX_HOME = getDefaultCodexHome();

const launchModes: { mode: PrelaunchMode; title: string; desc: string }[] = [
  { mode: "official", title: "打开 Codex", desc: "普通用户入口。只打开 Codex；如果 Codex 已经在运行，就不会关闭、聚焦或重复启动。" },
  { mode: "api", title: "API 供应商启动", desc: "使用第三方 API / Relay provider 启动，适合纯 API 通道。" },
  { mode: "hybrid", title: "混合登录", desc: "官方账号 + API（第三方也行）同时登录，保持插件等原生功能。" },
];

type PendingRuntimeAction =
  | { type: "launch"; mode: PrelaunchMode; hideOfficialQuotaNotice: boolean; restoreHistory: boolean; provider: PrelaunchProviderPayload | null }
  | { type: "repair"; recoveryOptions?: PrelaunchRecoveryOptionsPayload };

type LaunchMutationVars = {
  mode: PrelaunchMode;
  provider: PrelaunchProviderPayload | null;
  hideOfficialQuotaNotice: boolean;
  restoreHistory: boolean;
};

type RepairMutationVars = PrelaunchRecoveryOptionsPayload | undefined;

type ProviderDraft = {
  key: string;
  name: string;
  baseUrl: string;
  envKey: string;
  requiresOpenaiAuth: boolean;
  experimentalBearerToken: string;
};

const defaultProviderDraft: ProviderDraft = {
  key: "",
  name: "",
  baseUrl: "",
  envKey: "OPENAI_API_KEY",
  requiresOpenaiAuth: false,
  experimentalBearerToken: "",
};

const defaultRecoveryOptions: PrelaunchRecoveryOptionsPayload = {
  includeArchived: false,
  allowMissingCwd: false,
  allowEmptyCwd: false,
  allowMissingSession: false,
  projectlessMode: "none",
  unarchiveSelected: false,
};

function trimDraft(mode: PrelaunchMode, draft: ProviderDraft): ProviderDraft {
  const requiresOpenaiAuth = mode === "hybrid" || draft.requiresOpenaiAuth;
  return {
    key: draft.key.trim(),
    name: draft.name.trim(),
    baseUrl: draft.baseUrl.trim(),
    envKey: requiresOpenaiAuth ? "" : draft.envKey.trim(),
    requiresOpenaiAuth,
    experimentalBearerToken: draft.experimentalBearerToken.trim(),
  };
}

function validateProvider(mode: PrelaunchMode, draft: ProviderDraft): string | null {
  if (mode === "official") return null;
  const normalized = trimDraft(mode, draft);
  if (!normalized.key) return "请先填写 Provider Key。";
  if (!normalized.name) return "请先填写 Provider Name。";
  if (!normalized.baseUrl) return "请先填写 Base URL。";
  if (normalized.requiresOpenaiAuth) {
    if (!normalized.experimentalBearerToken) return "当前模式要求填写 Bearer Token。";
  } else if (!normalized.envKey) {
    return "未启用 OpenAI Auth 时必须填写 Env Key。";
  }
  if (mode === "hybrid") {
    if (!normalized.experimentalBearerToken) return "混合登录必须填写 Bearer Token。";
  }
  return null;
}

function buildProviderPayload(mode: PrelaunchMode, draft: ProviderDraft): PrelaunchProviderPayload | null {
  if (mode === "official") return null;
  const normalized = trimDraft(mode, draft);
  return {
    key: normalized.key,
    name: normalized.name,
    base_url: normalized.baseUrl,
    wire_api: "responses",
    env_key: normalized.requiresOpenaiAuth ? "" : normalized.envKey,
    requires_openai_auth: normalized.requiresOpenaiAuth,
    experimental_bearer_token: normalized.experimentalBearerToken,
  };
}

function hasOfficialLogin(status?: PrelaunchStatusPayload): boolean {
  const authMode = status?.evidence?.auth_mode?.trim().toLowerCase();
  return status?.codexPlus?.relay?.authenticated === true || authMode === "chatgpt";
}

function hasReusableHybridProvider(status?: PrelaunchStatusPayload): boolean {
  const evidence = status?.evidence;
  if (evidence?.hybrid_provider_configured) return true;
  const relay = status?.codexPlus?.relay;
  if (relay?.configured && relay.requiresOpenaiAuth && relay.hasBearerToken) return true;

  const provider = evidence?.config_model_provider?.trim().toLowerCase();
  return !!provider && provider !== "openai" && evidence?.auth_mode?.trim().toLowerCase() === "chatgpt";
}

function enhancedLoginReadinessMessage(status?: PrelaunchStatusPayload): string | null {
  if (!status) return "正在读取登录状态，请稍后再试。";
  const hasOfficial = hasOfficialLogin(status);
  const hasHybridProvider = hasReusableHybridProvider(status);
  if (hasOfficial && hasHybridProvider) return null;
  if (hasOfficial) {
    return "增强登录需要先保存混合登录信息：当前只检测到官方账号，请先使用混合登录填写 Relay/API 信息。";
  }
  if (hasHybridProvider) {
    return "增强登录需要官方账号和 Relay/API 混合信息：当前只检测到 Relay/API 配置，请先完成官方账号登录并用混合登录保存一次。";
  }
  return "增强登录需要先完成混合登录：请先登录官方账号，并在混合登录里保存 Relay/API 信息。";
}

export function LoginRepairPage() {
  const [runningWarningOpen, setRunningWarningOpen] = useState(false);
  const [runningProcessLabel, setRunningProcessLabel] = useState("");
  const [pendingRuntimeAction, setPendingRuntimeAction] = useState<PendingRuntimeAction | null>(null);
  const [stopRuntimeError, setStopRuntimeError] = useState<string | null>(null);
  const [runtimeSafetyNotice, setRuntimeSafetyNotice] = useState<string | null>(null);
  const [codexRunning, setCodexRunning] = useState<boolean | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activeProviderMode, setActiveProviderMode] = useState<PrelaunchMode | null>(null);
  const [providerDraft, setProviderDraft] = useState<ProviderDraft>(defaultProviderDraft);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [restoreHistoryOnLaunch, setRestoreHistoryOnLaunch] = useState(false);
  const [recoveryOptions, setRecoveryOptions] = useState<PrelaunchRecoveryOptionsPayload>(defaultRecoveryOptions);

  const statusQuery = useQuery<PrelaunchStatusPayload>({
    queryKey: ["prelaunch-status", DEFAULT_CODEX_HOME],
    queryFn: () => api.prelaunchStatus(DEFAULT_CODEX_HOME),
  });
  const enhancerSettingsQuery = useQuery<EnhancerSettingsPayload>({
    queryKey: ["enhancer-settings"],
    queryFn: () => api.getEnhancerSettings(),
  });
  const launchMutation = useMutation<PrelaunchLaunchPayload, Error, LaunchMutationVars>({
    mutationFn: ({ mode, provider, hideOfficialQuotaNotice, restoreHistory }) =>
      api.prelaunchLaunch(DEFAULT_CODEX_HOME, mode, provider, hideOfficialQuotaNotice, restoreHistory),
  });
  const repairMutation = useMutation<PrelaunchLaunchPayload, Error, RepairMutationVars>({
    mutationFn: (options) =>
      options ? api.prelaunchRepair(DEFAULT_CODEX_HOME, options) : api.prelaunchRepair(DEFAULT_CODEX_HOME),
  });
  const stopRuntimeMutation = useMutation({
    mutationFn: () => api.prelaunchStopRuntime(),
  });

  const evidence = statusQuery.data?.evidence;
  const hideOfficialQuotaNotice = enhancerSettingsQuery.data?.hideOfficialQuotaNoticeEnabled ?? false;
  const providerBuckets = Object.keys(evidence?.provider_distribution ?? {});
  const latestResult = repairMutation.data ?? launchMutation.data;
  const runningMode = launchMutation.variables?.mode;

  const executePendingAction = (action: PendingRuntimeAction) => {
    if (action.type === "launch") {
      launchMutation.mutate({
        mode: action.mode,
        provider: action.provider,
        hideOfficialQuotaNotice: action.hideOfficialQuotaNotice,
        restoreHistory: action.restoreHistory,
      });
    } else {
      repairMutation.mutate(action.recoveryOptions);
    }
  };

  const activeRecoveryOptions = () => {
    const options = {
      ...recoveryOptions,
      unarchiveSelected: recoveryOptions.includeArchived && recoveryOptions.unarchiveSelected,
    };
    const hasAdvancedOption =
      options.includeArchived ||
      options.allowMissingCwd ||
      options.allowEmptyCwd ||
      options.allowMissingSession ||
      options.projectlessMode !== "none" ||
      options.unarchiveSelected;
    return hasAdvancedOption ? options : undefined;
  };

  const checkRuntimeReady = async (action: PendingRuntimeAction) => {
    const runtime = await api.prelaunchRuntimeStatus();
    setCodexRunning(runtime.codex_running);
    if (runtime.codex_running) {
      const processLabel = runtime.processes
        .map((process) => [process.image, process.pid == null ? null : `PID ${process.pid}`].filter(Boolean).join(" "))
        .filter(Boolean)
        .slice(0, 8)
        .join("、");
      if (action.type === "launch") {
        setRuntimeSafetyNotice(
          `检测到 ${processLabel || "已有 Codex 进程"}。如果 Codex 窗口能正常使用，不需要再操作；如果卡住或打不开，请点“重启并打开 Codex”。`,
        );
        return false;
      }
      setRuntimeSafetyNotice(null);
      setPendingRuntimeAction(action);
      setStopRuntimeError(null);
      setRunningProcessLabel(processLabel);
      setRunningWarningOpen(true);
      return false;
    }
    setRuntimeSafetyNotice(null);
    return true;
  };

  const launchWithRuntimeCheck = async (mode: PrelaunchMode) => {
    const validationError = validateProvider(mode, providerDraft);
    if (validationError) {
      setProviderError(validationError);
      return;
    }
    setProviderError(null);
    const action: PendingRuntimeAction = {
      type: "launch",
      mode,
      provider: buildProviderPayload(mode, providerDraft),
      hideOfficialQuotaNotice,
      restoreHistory: restoreHistoryOnLaunch,
    };
    if (await checkRuntimeReady(action)) {
      executePendingAction(action);
    }
  };

  const launchEnhancedWithRuntimeCheck = async () => {
    const readinessError = enhancedLoginReadinessMessage(statusQuery.data);
    if (readinessError) {
      setActiveProviderMode(null);
      setProviderError(readinessError);
      return;
    }
    setProviderError(null);
    const action: PendingRuntimeAction = {
      type: "launch",
      mode: "hybrid",
      provider: null,
      hideOfficialQuotaNotice,
      restoreHistory: false,
    };
    if (await checkRuntimeReady(action)) {
      executePendingAction(action);
    }
  };

  const repairWithRuntimeCheck = async () => {
    const action: PendingRuntimeAction = { type: "repair", recoveryOptions: activeRecoveryOptions() };
    if (await checkRuntimeReady(action)) {
      executePendingAction(action);
    }
  };

  const closeRuntimeWarning = () => {
    setRunningWarningOpen(false);
    setPendingRuntimeAction(null);
    setStopRuntimeError(null);
  };

  const stopAndContinue = async () => {
    if (!pendingRuntimeAction) return;
    setStopRuntimeError(null);
    try {
      const result = await stopRuntimeMutation.mutateAsync();
      if (!result.ok) {
        setStopRuntimeError(buildStopRuntimeError(result));
        return;
      }
      const action = pendingRuntimeAction;
      setRunningWarningOpen(false);
      setPendingRuntimeAction(null);
      executePendingAction(action);
    } catch (error) {
      setStopRuntimeError(error instanceof Error ? error.message : "关闭 Codex 失败");
    }
  };

  const handleLaunchClick = (mode: PrelaunchMode) => {
    if (mode === "official") {
      void launchEnhancedWithRuntimeCheck();
      return;
    }
    setProviderError(null);
    setRestoreHistoryOnLaunch(false);
    setActiveProviderMode(mode);
    if (mode === "hybrid") {
      setProviderDraft((current) => ({
        ...current,
        requiresOpenaiAuth: true,
        envKey: "",
      }));
    }
  };

  const handlePrimaryAction = async () => {
    if (codexRunning) {
      await repairWithRuntimeCheck();
      return;
    }
    await launchEnhancedWithRuntimeCheck();
  };

  const submitProviderLaunch = () => {
    if (!activeProviderMode) return;
    void launchWithRuntimeCheck(activeProviderMode);
  };

  const providerDisabled = launchMutation.isPending || repairMutation.isPending;
  const requiresOpenaiAuth = activeProviderMode === "hybrid" || providerDraft.requiresOpenaiAuth;
  const activeProviderTitle =
    activeProviderMode === "api"
      ? "API 供应商启动"
      : activeProviderMode === "hybrid"
        ? "混合登录"
        : "";

  return (
    <div className="space-y-6">
      <BentoCard>
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-lg font-semibold">
              <Rocket className="h-5 w-5 text-primary" />
              Codex 启动器
            </div>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              普通用户只需要点这里。若 Codex 没开，会打开 Codex；若检测到后台残留，会走“重启并打开”流程。
            </p>
          </div>
          <Button className="min-w-44" disabled={providerDisabled} onClick={() => void handlePrimaryAction()}>
            {repairMutation.isPending || launchMutation.isPending ? "处理中..." : codexRunning ? "重启并打开 Codex" : "启动 Codex"}
          </Button>
        </div>
      </BentoCard>

      {providerError && !activeProviderMode ? (
        <BentoCard>
          <div className="text-sm text-destructive">{providerError}</div>
        </BentoCard>
      ) : null}

      {runtimeSafetyNotice ? (
        <BentoCard>
          <div className="space-y-2 text-sm">
            <div className="font-semibold text-amber-700">Codex 已在运行</div>
            <p className="leading-6 text-muted-foreground">{runtimeSafetyNotice}</p>
          </div>
        </BentoCard>
      ) : null}

      <BentoCard>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-semibold">高级选项</div>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">只有需要第三方 API、混合登录或恢复历史时才打开。</p>
          </div>
          <Button variant="outline" onClick={() => setAdvancedOpen((open) => !open)}>
            {advancedOpen ? "收起高级选项" : "显示高级选项"}
          </Button>
        </div>
      </BentoCard>

      {advancedOpen ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {launchModes
            .filter(({ mode }) => mode !== "official")
            .map(({ mode, title, desc }) => (
              <ActionCard
                key={mode}
                title={title}
                desc={desc}
                icon={Rocket}
                busy={launchMutation.isPending && runningMode === mode}
                disabled={providerDisabled}
                actionLabel="填写信息"
                busyLabel="启动中..."
                onClick={() => handleLaunchClick(mode)}
              />
            ))}
        </div>
      ) : null}

      {advancedOpen && activeProviderMode ? (
        <BentoCard>
          <div className="space-y-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <div className="text-sm font-semibold">{activeProviderTitle} - Provider 信息</div>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">
                  API 供应商启动和混合登录不会再静默吃旧配置。点击功能后，在这里填写本次 provider 信息再启动。
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => setActiveProviderMode(null)} disabled={providerDisabled}>
                收起
              </Button>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <FieldBlock label="Provider Key" htmlFor="provider-key">
                <Input
                  id="provider-key"
                  value={providerDraft.key}
                  onChange={(event) => setProviderDraft((current) => ({ ...current, key: event.target.value }))}
                  disabled={providerDisabled}
                  placeholder="cliproxy"
                />
              </FieldBlock>
              <FieldBlock label="Provider Name" htmlFor="provider-name">
                <Input
                  id="provider-name"
                  value={providerDraft.name}
                  onChange={(event) => setProviderDraft((current) => ({ ...current, name: event.target.value }))}
                  disabled={providerDisabled}
                  placeholder="CLIProxy"
                />
              </FieldBlock>
              <FieldBlock label="Base URL" htmlFor="provider-base-url">
                <Input
                  id="provider-base-url"
                  value={providerDraft.baseUrl}
                  onChange={(event) => setProviderDraft((current) => ({ ...current, baseUrl: event.target.value }))}
                  disabled={providerDisabled}
                  placeholder="http://127.0.0.1:20128/v1"
                />
              </FieldBlock>
              <FieldBlock label="Env Key" htmlFor="provider-env-key">
                <Input
                  id="provider-env-key"
                  value={providerDraft.envKey}
                  onChange={(event) => setProviderDraft((current) => ({ ...current, envKey: event.target.value }))}
                  disabled={providerDisabled || requiresOpenaiAuth}
                  placeholder="OPENAI_API_KEY"
                />
              </FieldBlock>
            </div>
            <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)] md:items-end">
              <div className="flex items-center justify-between rounded-xl border border-border px-4 py-3">
                <div className="space-y-1">
                  <Label htmlFor="provider-restore-history">恢复聊天信息</Label>
                  <p className="text-xs text-muted-foreground">
                    关闭时只配置登录并启动；打开后会把聊天记录恢复到原 workspace，耗时会更久。
                  </p>
                </div>
                <Switch
                  id="provider-restore-history"
                  checked={restoreHistoryOnLaunch}
                  onCheckedChange={setRestoreHistoryOnLaunch}
                  disabled={providerDisabled}
                  aria-label="恢复聊天信息"
                />
              </div>
              <FieldBlock label="Bearer Token" htmlFor="provider-bearer-token">
                <Input
                  id="provider-bearer-token"
                  value={providerDraft.experimentalBearerToken}
                  onChange={(event) =>
                    setProviderDraft((current) => ({ ...current, experimentalBearerToken: event.target.value }))
                  }
                  disabled={providerDisabled}
                  placeholder="sk-..."
                />
              </FieldBlock>
            </div>
            {providerError ? <div className="text-sm text-destructive">{providerError}</div> : null}
            <Button onClick={submitProviderLaunch} disabled={providerDisabled}>
              {launchMutation.isPending && runningMode === activeProviderMode ? "启动中..." : `确认并启动 ${activeProviderTitle}`}
            </Button>
          </div>
        </BentoCard>
      ) : null}

      {advancedOpen ? (
        <ActionCard
          title="历史恢复"
          desc="高级修复入口。会先要求确认关闭当前 Codex，然后修复历史、workspace 和 session index。"
          icon={Wrench}
          busy={repairMutation.isPending}
          disabled={providerDisabled}
          actionLabel="修复历史"
          busyLabel="修复中..."
          onClick={() => void repairWithRuntimeCheck()}
        />
      ) : null}

      {advancedOpen ? (
      <BentoCard>
        <div className="space-y-4">
          <div>
            <div className="text-sm font-semibold">高级恢复</div>
            <p className="mt-1 max-w-3xl text-sm leading-5 text-muted-foreground">
              默认只恢复有明确 workspace 和 session 的聊天；这里用于放宽筛选、处理归档聊天或把选中聊天放回 projectless。
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <RecoverySwitch
              id="recovery-include-archived"
              label="包含归档聊天"
              checked={recoveryOptions.includeArchived}
              disabled={providerDisabled}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({
                  ...current,
                  includeArchived: checked,
                  unarchiveSelected: checked ? current.unarchiveSelected : false,
                }))
              }
            />
            <RecoverySwitch
              id="recovery-allow-missing-cwd"
              label="允许缺失 cwd"
              checked={recoveryOptions.allowMissingCwd}
              disabled={providerDisabled}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({ ...current, allowMissingCwd: checked }))
              }
            />
            <RecoverySwitch
              id="recovery-allow-empty-cwd"
              label="允许空 workspace"
              checked={recoveryOptions.allowEmptyCwd}
              disabled={providerDisabled}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({ ...current, allowEmptyCwd: checked }))
              }
            />
            <RecoverySwitch
              id="recovery-allow-missing-session"
              label="允许缺失 session"
              checked={recoveryOptions.allowMissingSession}
              disabled={providerDisabled}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({ ...current, allowMissingSession: checked }))
              }
            />
            <RecoverySwitch
              id="recovery-projectless"
              label="恢复到 projectless"
              checked={recoveryOptions.projectlessMode === "all"}
              disabled={providerDisabled}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({ ...current, projectlessMode: checked ? "all" : "none" }))
              }
            />
            <RecoverySwitch
              id="recovery-unarchive-selected"
              label="取消归档选中聊天"
              checked={recoveryOptions.unarchiveSelected}
              disabled={providerDisabled || !recoveryOptions.includeArchived}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({ ...current, unarchiveSelected: checked }))
              }
            />
          </div>
        </div>
      </BentoCard>
      ) : null}

      {statusQuery.isError ? <ErrorCard title="启动前状态读取失败" error={statusQuery.error} /> : null}
      {launchMutation.isError ? <ErrorCard title="启动流程失败" error={launchMutation.error} /> : null}
      {repairMutation.isError ? <ErrorCard title="修复恢复失败" error={repairMutation.error} /> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard icon={KeyRound} label="登录态" value={evidence?.auth_mode} loading={statusQuery.isLoading} />
        <StatusCard icon={Rocket} label="模型通道" value={evidence?.config_model_provider} loading={statusQuery.isLoading} />
        <StatusCard
          icon={ShieldCheck}
          label="兼容差异行数"
          value={evidence?.rows_needing_reconcile == null ? null : String(evidence.rows_needing_reconcile)}
          loading={statusQuery.isLoading}
        />
        <StatusCard icon={Database} label="历史桶" value={providerBuckets.length > 0 ? providerBuckets.join(", ") : "none"} loading={statusQuery.isLoading} />
      </div>

      {latestResult ? <ResultCard result={latestResult} /> : null}

      <RunningCodexWarningDialog
        open={runningWarningOpen}
        processLabel={runningProcessLabel}
        stopping={stopRuntimeMutation.isPending}
        error={stopRuntimeError}
        onClose={closeRuntimeWarning}
        onStopAndContinue={() => void stopAndContinue()}
      />
    </div>
  );
}

function FieldBlock({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}

function RecoverySwitch({
  id,
  label,
  checked,
  disabled,
  onCheckedChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  disabled: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3">
      <Label htmlFor={id} className="text-sm font-medium">
        {label}
      </Label>
      <Switch
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-label={label}
      />
    </div>
  );
}

function RunningCodexWarningDialog({
  open,
  processLabel,
  stopping,
  error,
  onClose,
  onStopAndContinue,
}: {
  open: boolean;
  processLabel: string;
  stopping: boolean;
  error: string | null;
  onClose: () => void;
  onStopAndContinue: () => void;
}) {
  return (
    <AlertDialog open={open}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>要重启 Codex 吗？</AlertDialogTitle>
          <AlertDialogDescription>
            重启前需要先关闭当前 Codex。继续后我会先关闭它，再重新准备启动。
            {processLabel ? <span className="mt-3 block break-words text-xs">检测到：{processLabel}</span> : null}
            {error ? <span className="mt-3 block text-xs text-destructive">没关掉：{error}</span> : null}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <Button variant="outline" onClick={onClose} disabled={stopping}>
            取消
          </Button>
          <AlertDialogAction onClick={onStopAndContinue} disabled={stopping}>
            {stopping ? "正在关闭..." : "关闭并重启"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ActionCard({ title, desc, icon: Icon, busy, disabled, actionLabel, busyLabel, onClick }: { title: string; desc: string; icon: typeof Rocket; busy: boolean; disabled: boolean; actionLabel: string; busyLabel: string; onClick: () => void }) {
  return (
    <BentoCard className="flex min-h-[190px] flex-col justify-between transition-colors hover:bg-muted/35">
      <div>
        <div className="mb-3 inline-flex rounded-xl bg-primary/10 p-2 text-primary"><Icon className="h-5 w-5" /></div>
        <div className="text-sm font-semibold">{title}</div>
        <p className="mt-2 text-sm leading-5 text-muted-foreground">{desc}</p>
      </div>
      <Button className="mt-4 w-full" variant="outline" disabled={disabled} onClick={onClick}>{busy ? busyLabel : actionLabel}</Button>
    </BentoCard>
  );
}

function ResultCard({ result }: { result: PrelaunchLaunchPayload }) {
  const attributionSummary = buildAttributionSummary(result);
  const hasRepairSummary = Boolean(result.repair?.summary);
  const launchNotice = buildLaunchNotice(result);

  return (
    <BentoCard>
      <div className="space-y-4 text-sm">
        <div className="flex items-center gap-2 text-sm font-semibold"><CheckCircle2 className="h-4 w-4 text-primary" />最近一次执行结果</div>
        <div className="grid gap-4 md:grid-cols-3">
          <Detail label="模式" value={result.mode} />
          <Detail label="目标 provider" value={result.provider_config?.target_model_provider} />
          <Detail label="启动方式" value={result.launch?.method} />
          <Detail label="执行报告" value={result.report_dir} />
          {result.notice_suppression ? <Detail label="额度提醒策略" value={noticeSuppressionLabel(result)} /> : null}
          <Detail label="兼容差异行数" value={result.provider_compatibility?.status?.rows_needing_reconcile == null ? undefined : String(result.provider_compatibility.status.rows_needing_reconcile)} />
          {hasRepairSummary ? <Detail label="恢复线程数" value={result.repair?.summary?.threads_selected == null ? undefined : String(result.repair.summary.threads_selected)} /> : null}
          {hasRepairSummary ? <Detail label="恢复 workspace 数" value={attributionSummary.workspaceCount == null ? undefined : String(attributionSummary.workspaceCount)} /> : null}
          {hasRepairSummary ? <Detail label="跳过线程数" value={attributionSummary.skippedCount == null ? undefined : String(attributionSummary.skippedCount)} /> : null}
          <Detail label="结果" value={result.ok ? "成功" : "失败"} />
          {result.error ? <Detail label="错误" value={result.error} /> : null}
        </div>
        {launchNotice ? <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">{launchNotice}</p> : null}
        {hasRepairSummary ? <AttributionSummaryPanel summary={attributionSummary} /> : null}
      </div>
    </BentoCard>
  );
}

function buildLaunchNotice(result: PrelaunchLaunchPayload): string | null {
  const method = result.launch?.method;
  if (method === "already_running") {
    return "Codex 已经在运行，本次普通启动没有关闭、聚焦或重复拉起 Codex。";
  }
  if (method === "retry_takeover_not_allowed") {
    return "Codex 没有按预期就绪。普通启动不会自动接管或杀进程；如需强制重启，请使用“修复/重启 Codex”。";
  }
  if (method === "takeover_failed") {
    return "接管 Codex 失败。请先手动关闭 Codex，或使用明确的修复/重启入口。";
  }
  return null;
}

function buildStopRuntimeError(result: PrelaunchStopRuntimePayload): string {
  const remaining = result.remaining ?? [];
  const errors = result.errors ?? [];
  const processText =
    remaining.length > 0
      ? `还有 ${remaining.length} 个 Codex 进程没有退出：${remaining
          .slice(0, 4)
          .map((process) => `${process.image ?? "codex"}${process.pid == null ? "" : ` PID ${process.pid}`}`)
          .join("、")}`
      : "仍检测到 Codex 进程";
  const errorText = errors.length > 0 ? `。系统返回：${errors.slice(0, 2).join("；")}` : "";
  return `${processText}${errorText}`;
}

type AttributionSummary = {
  workspaceCount: number | null;
  skippedCount: number | null;
  topWorkspaces: Array<{ root: string; count: number }>;
  skipReasons: Array<{ reason: string; count: number }>;
};

function buildAttributionSummary(result: PrelaunchLaunchPayload): AttributionSummary {
  const summary = result.repair?.summary;
  const attributions = summary?.thread_attributions ?? [];
  const workspaceCounts = countWorkspaces(attributions);
  const skipReasonsFromAttributions = countReasons(
    attributions.filter((item) => item.target_location === "skipped"),
  );
  const skipReasonsFromSummary = Object.entries(summary?.skip_reasons ?? {}).map(([reason, count]) => ({
    reason,
    count,
  }));

  return {
    workspaceCount: summary?.workspace_roots_selected ?? (workspaceCounts.length ? workspaceCounts.length : null),
    skippedCount: summary?.threads_skipped ?? null,
    topWorkspaces: workspaceCounts.slice(0, 3),
    skipReasons: (skipReasonsFromSummary.length ? skipReasonsFromSummary : skipReasonsFromAttributions).slice(0, 3),
  };
}

function countWorkspaces(attributions: PrelaunchThreadAttributionPayload[]) {
  const counts = new Map<string, number>();
  for (const item of attributions) {
    if (item.target_location !== "workspace" || !item.workspace_root) continue;
    counts.set(item.workspace_root, (counts.get(item.workspace_root) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([root, count]) => ({ root, count }))
    .sort((a, b) => b.count - a.count || a.root.localeCompare(b.root));
}

function countReasons(attributions: PrelaunchThreadAttributionPayload[]) {
  const counts = new Map<string, number>();
  for (const item of attributions) {
    const reason = item.reason ?? "unknown";
    counts.set(reason, (counts.get(reason) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason));
}

function AttributionSummaryPanel({ summary }: { summary: AttributionSummary }) {
  const hasContent = summary.topWorkspaces.length > 0 || summary.skipReasons.length > 0;
  if (!hasContent && summary.workspaceCount == null && summary.skippedCount == null) return null;

  return (
    <div className="rounded-xl border border-border/70 bg-muted/25 p-4">
      <div className="text-sm font-semibold">归属分析摘要</div>
      <div className="mt-3 grid gap-4 md:grid-cols-3">
        <Detail label="恢复 workspace 数" value={summary.workspaceCount == null ? undefined : String(summary.workspaceCount)} />
        <Detail label="跳过线程数" value={summary.skippedCount == null ? undefined : String(summary.skippedCount)} />
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">主要跳过原因</div>
          <div className="mt-1 space-y-1 text-sm font-medium">
            {summary.skipReasons.length ? summary.skipReasons.map((item) => (
              <div key={item.reason}>{item.reason}: {item.count}</div>
            )) : <div>none</div>}
          </div>
        </div>
      </div>
      {summary.topWorkspaces.length ? (
        <div className="mt-4 space-y-2">
          <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">主要 workspace</div>
          <div className="grid gap-2 md:grid-cols-2">
            {summary.topWorkspaces.map((item) => (
              <div key={item.root} className="min-w-0 rounded-lg border border-border/70 bg-background/70 px-3 py-2">
                <div className="truncate text-sm font-medium" title={item.root}>{item.root}</div>
                <div className="mt-1 text-xs text-muted-foreground">{item.count} threads</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function noticeSuppressionLabel(result: PrelaunchLaunchPayload) {
  const notice = result.notice_suppression;
  if (!notice) return undefined;
  if (notice.ok) return notice.method ?? "已准备";
  if (notice.skipped) return notice.reason ?? "已跳过";
  return notice.error ?? "失败";
}

function ErrorCard({ title, error }: { title: string; error: unknown }) {
  return <BentoCard><div className="space-y-1"><span className="text-sm font-medium">{title}</span><span className="text-sm text-muted-foreground">{error instanceof Error ? error.message : "未知错误"}</span></div></BentoCard>;
}

function Detail({ label, value }: { label: string; value: string | number | undefined }) {
  return <div className="min-w-0"><div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</div><div className="mt-1 truncate text-sm font-medium" title={value === undefined ? undefined : String(value)}>{value ?? "unknown"}</div></div>;
}

function StatusCard({ icon: Icon, label, value, loading }: { icon: typeof KeyRound; label: string; value: string | null | undefined; loading: boolean }) {
  return <BentoCard compact><div className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground"><Icon className="h-4 w-4" />{label}</div><span className="mt-2 text-lg font-semibold">{loading ? "加载中..." : value ?? "unknown"}</span></BentoCard>;
}
