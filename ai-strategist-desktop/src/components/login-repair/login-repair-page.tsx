import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Rocket, ServerCog } from "lucide-react";

import { BentoCard } from "@/components/ui/bento-card";
import { Button } from "@/components/ui/button";
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
  PrelaunchEnvironmentPayload,
  PrelaunchLaunchPayload,
  PrelaunchMode,
  PrelaunchProviderPayload,
  PrelaunchRecoveryOptionsPayload,
  PrelaunchThreadAttributionPayload,
  PrelaunchStatusPayload,
} from "@/types/prelaunch";
import type { ModelGatewaySnapshot, ModelRelayStatusPayload } from "@/types/model-management";

function getDefaultCodexHome() {
  const injectedCodexHome = import.meta.env.VITE_DEFAULT_CODEX_HOME?.trim();
  if (injectedCodexHome) return injectedCodexHome;
  return globalThis.navigator?.platform?.toLowerCase().startsWith("win")
    ? "%USERPROFILE%\\.codex"
    : "~/.codex";
}

export const DEFAULT_CODEX_HOME = getDefaultCodexHome();

const launchModes: LaunchCard[] = [
  { mode: "api", title: "本地模型桶启动", desc: "Codex 连接本地统一模型入口；provider、路由和 token 在模型管理中治理。" },
  { mode: "hybrid", title: "混合登录启动", desc: "保留官方登录态，同时使用本地模型桶；适合插件 + relay 双需求。" },
  { mode: "enhanced", title: "增强启动", desc: "启动已登录的 Codex，并加载插件和增强功能。" },
];

type LaunchCardMode = Exclude<PrelaunchMode, "official"> | "enhanced";
type RunningAction = PrelaunchMode | LaunchCardMode | "repair";

type PendingRuntimeAction =
  | { type: "enhanced-launch" }
  | { type: "launch"; mode: PrelaunchMode; hideOfficialQuotaNotice: boolean; restoreHistory: boolean }
  | { type: "repair"; recoveryOptions?: PrelaunchRecoveryOptionsPayload };

type LaunchMutationVars = {
  mode: PrelaunchMode;
  provider: PrelaunchProviderPayload | null;
  hideOfficialQuotaNotice: boolean;
  restoreHistory: boolean;
};

type LaunchCard = {
  mode: LaunchCardMode;
  title: string;
  desc: string;
};

type RepairMutationVars = PrelaunchRecoveryOptionsPayload | undefined;

const defaultRecoveryOptions: PrelaunchRecoveryOptionsPayload = {
  includeArchived: false,
  allowMissingCwd: false,
  allowEmptyCwd: false,
  allowMissingSession: false,
  projectlessMode: "none",
  unarchiveSelected: false,
};

export function LoginRepairPage() {
  const [runningWarningOpen, setRunningWarningOpen] = useState(false);
  const [runningProcessLabel, setRunningProcessLabel] = useState("");
  const [pendingRuntimeAction, setPendingRuntimeAction] = useState<PendingRuntimeAction | null>(null);
  const [runtimeSafetyNotice, setRuntimeSafetyNotice] = useState<string | null>(null);
  const [codexRunning, setCodexRunning] = useState<boolean | null>(null);
  const [stoppingRuntime, setStoppingRuntime] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activeProviderMode, setActiveProviderMode] = useState<PrelaunchMode | null>(null);
  const [restoreHistoryOnLaunch, setRestoreHistoryOnLaunch] = useState(false);
  const [recoveryOptions, setRecoveryOptions] = useState<PrelaunchRecoveryOptionsPayload>(defaultRecoveryOptions);

  const statusQuery = useQuery<PrelaunchStatusPayload>({
    queryKey: ["prelaunch-status", DEFAULT_CODEX_HOME],
    queryFn: () => api.prelaunchStatus(DEFAULT_CODEX_HOME),
  });
  const environmentQuery = useQuery<PrelaunchEnvironmentPayload>({
    queryKey: ["prelaunch-environment", DEFAULT_CODEX_HOME],
    queryFn: () => api.prelaunchEnvironment(DEFAULT_CODEX_HOME),
  });
  const modelBucketQuery = useQuery({
    queryKey: ["model-bucket-summary"],
    queryFn: async () => {
      const [snapshot, relayStatus] = await Promise.all([api.modelGatewaySnapshot(), api.modelRelayStatus()]);
      return { snapshot, relayStatus };
    },
  });
  const enhancerSettingsQuery = useQuery<EnhancerSettingsPayload>({
    queryKey: ["enhancer-settings"],
    queryFn: () => api.getEnhancerSettings(),
  });
  const launchMutation = useMutation<PrelaunchLaunchPayload, Error, LaunchMutationVars>({
    mutationFn: ({ mode, provider, hideOfficialQuotaNotice, restoreHistory }) =>
      api.prelaunchLaunch(DEFAULT_CODEX_HOME, mode, provider, hideOfficialQuotaNotice, restoreHistory),
  });
  const enhancedLaunchMutation = useMutation<PrelaunchLaunchPayload, Error>({
    mutationFn: () => api.prelaunchEnhancedLaunch(DEFAULT_CODEX_HOME),
  });
  const repairMutation = useMutation<PrelaunchLaunchPayload, Error, RepairMutationVars>({
    mutationFn: (options) =>
      options ? api.prelaunchRepair(DEFAULT_CODEX_HOME, options) : api.prelaunchRepair(DEFAULT_CODEX_HOME),
  });
  const evidence = statusQuery.data?.evidence;
  const hideOfficialQuotaNotice = enhancerSettingsQuery.data?.hideOfficialQuotaNoticeEnabled ?? false;
  const latestResult = repairMutation.data ?? enhancedLaunchMutation.data ?? launchMutation.data;
  const [runningAction, setRunningAction] = useState<RunningAction | null>(null);

  const executePendingAction = (action: PendingRuntimeAction) => {
    if (action.type === "enhanced-launch") {
      setRunningAction("enhanced");
      enhancedLaunchMutation.mutate();
    } else if (action.type === "launch") {
      setRunningAction(action.mode);
      launchMutation.mutate({
        mode: action.mode,
        provider: null,
        hideOfficialQuotaNotice: action.hideOfficialQuotaNotice,
        restoreHistory: action.restoreHistory,
      });
    } else {
      setRunningAction("repair");
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
    if (action.type === "launch") {
      setRuntimeSafetyNotice(null);
      return true;
    }
    if (runtime.codex_running) {
      const processLabel = runtime.processes
        .map((process) => [process.image, process.pid == null ? null : `PID ${process.pid}`].filter(Boolean).join(" "))
        .filter(Boolean)
        .slice(0, 8)
        .join("、");
      setRuntimeSafetyNotice(null);
      setPendingRuntimeAction(action);
      setRunningProcessLabel(processLabel);
      setRunningWarningOpen(true);
      return false;
    }
    setRuntimeSafetyNotice(null);
    return true;
  };

  const launchWithRuntimeCheck = async (mode: PrelaunchMode) => {
    const action: PendingRuntimeAction = {
      type: "launch",
      mode,
      hideOfficialQuotaNotice,
      restoreHistory: restoreHistoryOnLaunch,
    };
    if (await checkRuntimeReady(action)) {
      executePendingAction(action);
    } else {
      setRunningAction(null);
    }
  };

  const launchEnhancedWithRuntimeCheck = async () => {
    setActiveProviderMode(null);
    const action: PendingRuntimeAction = { type: "enhanced-launch" };
    if (await checkRuntimeReady(action)) {
      executePendingAction(action);
    } else {
      setRunningAction(null);
    }
  };

  const repairWithRuntimeCheck = async () => {
    setRunningAction("repair");
    const action: PendingRuntimeAction = { type: "repair", recoveryOptions: activeRecoveryOptions() };
    if (await checkRuntimeReady(action)) {
      executePendingAction(action);
    } else {
      setRunningAction(null);
    }
  };

  const closeRuntimeWarning = () => {
    setRunningWarningOpen(false);
    setPendingRuntimeAction(null);
  };

  const stopRuntimeAndContinue = async () => {
    if (!pendingRuntimeAction) return;
    const action = pendingRuntimeAction;
    setStoppingRuntime(true);
    const stopResult = await api.prelaunchStopRuntime();
    setStoppingRuntime(false);
    if (!stopResult.ok || stopResult.remaining.length > 0) {
      const remainingLabel = stopResult.remaining
        .map((process) => [process.image, process.pid == null ? null : `PID ${process.pid}`].filter(Boolean).join(" "))
        .filter(Boolean)
        .slice(0, 8)
        .join("、");
      const errorLabel = stopResult.errors?.filter(Boolean).join("；");
      setRuntimeSafetyNotice(
        remainingLabel
          ? `仍有 Codex 运行时未退出：${remainingLabel}`
          : errorLabel || "未能停止正在运行的 Codex，请手动退出后再试。",
      );
      return;
    }
    const runtime = await api.prelaunchRuntimeStatus();
    setCodexRunning(runtime.codex_running);
    if (runtime.codex_running) {
      const processLabel = runtime.processes
        .map((process) => [process.image, process.pid == null ? null : `PID ${process.pid}`].filter(Boolean).join(" "))
        .filter(Boolean)
        .slice(0, 8)
        .join("、");
      setRunningProcessLabel(processLabel);
      return;
    }
    setRunningWarningOpen(false);
    setPendingRuntimeAction(null);
    executePendingAction(action);
  };

  const handleLaunchClick = (mode: LaunchCardMode) => {
    setRunningAction(mode);
    if (mode === "enhanced") {
      void launchEnhancedWithRuntimeCheck();
      return;
    }
    setRestoreHistoryOnLaunch(false);
    setActiveProviderMode(null);
    void launchWithRuntimeCheck(mode);
  };

  const submitProviderLaunch = () => {
    if (!activeProviderMode) return;
    setRunningAction(activeProviderMode);
    void launchWithRuntimeCheck(activeProviderMode);
  };

  const actionsDisabled = launchMutation.isPending || enhancedLaunchMutation.isPending || repairMutation.isPending || stoppingRuntime;
  const activeProviderTitle =
    activeProviderMode === "api"
      ? "本地模型桶启动"
      : activeProviderMode === "hybrid"
        ? "混合登录"
        : "";

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-3">
        {launchModes.map(({ mode, title, desc }) => (
          <ActionCard
            key={mode}
            title={title}
            desc={desc}
            icon={Rocket}
            busy={(mode === "enhanced" ? enhancedLaunchMutation.isPending : launchMutation.isPending) && runningAction === mode}
            disabled={actionsDisabled}
            actionLabel={mode === "api" || mode === "hybrid" ? "使用模型桶启动" : codexRunning ? "加载增强" : "启动并加载"}
            busyLabel="启动中..."
            onClick={() => handleLaunchClick(mode)}
          />
        ))}
      </div>

      {environmentQuery.data ? <EnvironmentCard environment={environmentQuery.data} /> : null}
      {environmentQuery.isError ? <ErrorCard title="环境自检失败" error={environmentQuery.error} /> : null}
      {modelBucketQuery.data ? <ModelBucketCard summary={modelBucketQuery.data} /> : null}
      {modelBucketQuery.isError ? <ErrorCard title="模型桶状态读取失败" error={modelBucketQuery.error} /> : null}

      {runtimeSafetyNotice ? (
        <BentoCard>
          <div className="space-y-2 text-sm">
            <div className="font-semibold text-amber-700">Codex 已在运行</div>
            <p className="leading-6 text-muted-foreground">{runtimeSafetyNotice}</p>
          </div>
        </BentoCard>
      ) : null}

      {activeProviderMode ? (
        <BentoCard>
          <div className="space-y-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <div className="text-sm font-semibold">{activeProviderTitle} - 模型桶配置</div>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">
                  本页不再接收一次性 provider 输入；启动会读取「模型管理」里的默认 provider、路由、token 和 relay 配置。
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => setActiveProviderMode(null)} disabled={actionsDisabled}>
                收起
              </Button>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <InlineStatus label="默认 Provider" value={modelBucketQuery.data?.snapshot.defaultProviderId ?? "未配置"} />
              <InlineStatus label="Relay" value={modelBucketQuery.data?.relayStatus.running ? "运行中" : "未运行"} />
              <InlineStatus label="配置入口" value="模型管理" />
            </div>
            <p className="text-xs text-muted-foreground">
              如需修改 Base URL、API key、模型路由或 fallback，请先打开顶部导航的「模型管理」。
            </p>
            <Button onClick={submitProviderLaunch} disabled={actionsDisabled}>
              {launchMutation.isPending && runningAction === activeProviderMode ? "启动中..." : `使用模型桶启动 ${activeProviderTitle}`}
            </Button>
          </div>
        </BentoCard>
      ) : null}

      <BentoCard>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-semibold">历史恢复</div>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">聊天记录、workspace 或 session index 不正常时使用。</p>
          </div>
          <Button variant="outline" disabled={actionsDisabled} onClick={() => void repairWithRuntimeCheck()}>
            {repairMutation.isPending ? "修复中..." : "修复历史"}
          </Button>
        </div>
      </BentoCard>

      <BentoCard>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-semibold">高级恢复选项</div>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">只有需要放宽恢复范围、处理归档聊天时才打开。</p>
          </div>
          <Button variant="outline" onClick={() => setAdvancedOpen((open) => !open)}>
            {advancedOpen ? "收起高级恢复选项" : "显示高级恢复选项"}
          </Button>
        </div>
      </BentoCard>

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
              disabled={actionsDisabled}
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
              disabled={actionsDisabled}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({ ...current, allowMissingCwd: checked }))
              }
            />
            <RecoverySwitch
              id="recovery-allow-empty-cwd"
              label="允许空 workspace"
              checked={recoveryOptions.allowEmptyCwd}
              disabled={actionsDisabled}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({ ...current, allowEmptyCwd: checked }))
              }
            />
            <RecoverySwitch
              id="recovery-allow-missing-session"
              label="允许缺失 session"
              checked={recoveryOptions.allowMissingSession}
              disabled={actionsDisabled}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({ ...current, allowMissingSession: checked }))
              }
            />
            <RecoverySwitch
              id="recovery-projectless"
              label="恢复到 projectless"
              checked={recoveryOptions.projectlessMode === "all"}
              disabled={actionsDisabled}
              onCheckedChange={(checked) =>
                setRecoveryOptions((current) => ({ ...current, projectlessMode: checked ? "all" : "none" }))
              }
            />
            <RecoverySwitch
              id="recovery-unarchive-selected"
              label="取消归档选中聊天"
              checked={recoveryOptions.unarchiveSelected}
              disabled={actionsDisabled || !recoveryOptions.includeArchived}
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

      <div className="grid gap-4 md:grid-cols-2">
        <StatusCard icon={KeyRound} label="登录态" value={evidence?.auth_mode} loading={statusQuery.isLoading} />
        <StatusCard icon={Rocket} label="模型通道" value={evidence?.config_model_provider} loading={statusQuery.isLoading} />
      </div>

      {latestResult ? <ResultCard result={latestResult} /> : null}

      <RunningCodexWarningDialog
        open={runningWarningOpen}
        processLabel={runningProcessLabel}
        busy={stoppingRuntime}
        error={runtimeSafetyNotice}
        onClose={closeRuntimeWarning}
        onContinue={() => void stopRuntimeAndContinue()}
      />
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
  busy,
  error,
  onClose,
  onContinue,
}: {
  open: boolean;
  processLabel: string;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onContinue: () => void;
}) {
  return (
    <AlertDialog open={open}>
      <AlertDialogContent className="max-w-md">
          <AlertDialogHeader>
          <AlertDialogTitle>需要重启 Codex</AlertDialogTitle>
          <AlertDialogDescription>
            检测到 Codex 正在运行。继续后会先停止可安全停止的运行时，再按当前配置重新启动。
            {processLabel ? <span className="mt-3 block break-words text-xs">检测到：{processLabel}</span> : null}
            {error ? <span className="mt-3 block text-xs text-destructive">{error}</span> : null}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            取消
          </Button>
          <AlertDialogAction onClick={onContinue} disabled={busy}>
            {busy ? "正在重启..." : "停止并重新启动"}
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

function ModelBucketCard({
  summary,
}: {
  summary: { snapshot: ModelGatewaySnapshot; relayStatus: ModelRelayStatusPayload };
}) {
  const { snapshot, relayStatus } = summary;
  const defaultProvider = snapshot.providers.find((provider) => provider.id === snapshot.defaultProviderId);
  const enabledProviders = snapshot.providers.filter((provider) => provider.enabled).length;
  const routeCount = snapshot.modelRoutes.filter((route) => route.enabled).length;
  const fallbackOrder = snapshot.fallbackOrder ?? [];
  const tokenMode = snapshot.relay.managementToken?.trim() ? "Bearer / x-ai-strategist-token" : "未启用";

  return (
    <BentoCard>
      <div className="space-y-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <ServerCog className="h-4 w-4 text-primary" />
              本地模型桶
            </div>
            <p className="mt-1 max-w-3xl text-sm leading-5 text-muted-foreground">
              启动与修复只消费本地模型桶；provider、路由、fallback、token 和日志在模型管理中维护。
            </p>
          </div>
          <span className={relayStatus.running ? "text-sm font-semibold text-primary" : "text-sm font-semibold text-amber-700"}>
            {relayStatus.running ? "Relay 运行中" : "Relay 未运行"}
          </span>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Detail label="Base URL" value={relayStatus.baseUrl} />
          <Detail label="默认 Provider" value={defaultProvider?.name ?? snapshot.defaultProviderId ?? "未设置"} />
          <Detail label="可用 Provider" value={enabledProviders} />
          <Detail label="启用路由" value={routeCount} />
          <Detail label="Fallback 顺序" value={fallbackOrder.length ? fallbackOrder.join(" -> ") : "默认 provider"} />
          <Detail label="Token" value={tokenMode} />
          <Detail label="Schema" value={snapshot.schemaVersion ?? 1} />
          <Detail label="Config" value={snapshot.configPath} />
        </div>
      </div>
    </BentoCard>
  );
}

function EnvironmentCard({ environment }: { environment: PrelaunchEnvironmentPayload }) {
  const bridgeMode = environment.bridge.usesExe ? "内置 bridge.exe" : "Python bridge";
  const codexTarget =
    environment.codexDesktop.productResolvedExe ??
    environment.codexDesktop.appid ??
    environment.codexDesktop.lastResortExe ??
    "未找到";
  const statusText = environment.ok ? "可启动" : "需要修复";
  const issueList = [...environment.blockers, ...environment.warnings];

  return (
    <BentoCard>
      <div className="space-y-4">
        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="text-sm font-semibold">环境自检</div>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">
              {statusText} · {bridgeMode} · {environment.runtime.codex_running ? "Codex 正在运行" : "Codex 未运行"}
            </p>
          </div>
          <span className={environment.ok ? "text-sm font-semibold text-primary" : "text-sm font-semibold text-destructive"}>
            {statusText}
          </span>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Detail label="Codex Home" value={environment.codexHome.exists ? environment.codexHome.path : "未找到"} />
          <Detail label="Codex Desktop" value={codexTarget} />
          <Detail label="Provider" value={environment.config.modelProvider ?? "未配置"} />
          <Detail label="Python Runtime" value={`${environment.runtimes.python.source}: ${environment.runtimes.python.path}`} />
        </div>
        {issueList.length ? (
          <div className="flex flex-wrap gap-2">
            {issueList.map((item) => (
              <span key={item} className="rounded border border-border px-2 py-1 text-xs text-muted-foreground">
                {environment.blockers.includes(item) ? "阻断" : "提示"} · {environmentIssueLabel(item)}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </BentoCard>
  );
}

function environmentIssueLabel(issue: string) {
  const labels: Record<string, string> = {
    codex_home_missing: "找不到 .codex",
    prelaunch_bridge_missing: "找不到 prelaunch bridge",
    codex_desktop_not_found: "找不到 Codex Desktop",
    config_missing: "缺少 config.toml",
    auth_missing: "未检测到登录态",
    threadripper_unavailable: "Threadripper 不可用",
    hybrid_provider_missing: "缺少混合登录 provider",
  };
  return labels[issue] ?? issue;
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

function InlineStatus({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 truncate text-sm font-medium" title={value}>
        {value}
      </div>
    </div>
  );
}
