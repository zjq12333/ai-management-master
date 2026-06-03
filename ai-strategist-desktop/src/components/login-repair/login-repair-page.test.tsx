import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { appNavItems } from "@/components/layout/sidebar";
import { DEFAULT_CODEX_HOME, LoginRepairPage } from "@/components/login-repair/login-repair-page";
import { OverviewPage } from "@/components/overview/overview-page";
import { ALL_APP_ROUTES } from "@/types/navigation";

const {
  prelaunchStatusMock,
  prelaunchEnvironmentMock,
  getEnhancerSettingsMock,
  prelaunchRuntimeStatusMock,
  prelaunchStopRuntimeMock,
  prelaunchLaunchMock,
  prelaunchEnhancedLaunchMock,
  prelaunchRepairMock,
  modelGatewaySnapshotMock,
  modelRelayStatusMock,
} = vi.hoisted(() => ({
  prelaunchStatusMock: vi.fn(),
  prelaunchEnvironmentMock: vi.fn(),
  getEnhancerSettingsMock: vi.fn(),
  prelaunchRuntimeStatusMock: vi.fn(),
  prelaunchStopRuntimeMock: vi.fn(),
  prelaunchLaunchMock: vi.fn(),
  prelaunchEnhancedLaunchMock: vi.fn(),
  prelaunchRepairMock: vi.fn(),
  modelGatewaySnapshotMock: vi.fn(),
  modelRelayStatusMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    prelaunchStatus: prelaunchStatusMock,
    prelaunchEnvironment: prelaunchEnvironmentMock,
    getEnhancerSettings: getEnhancerSettingsMock,
    prelaunchRuntimeStatus: prelaunchRuntimeStatusMock,
    prelaunchStopRuntime: prelaunchStopRuntimeMock,
    prelaunchLaunch: prelaunchLaunchMock,
    prelaunchEnhancedLaunch: prelaunchEnhancedLaunchMock,
    prelaunchRepair: prelaunchRepairMock,
    modelGatewaySnapshot: modelGatewaySnapshotMock,
    modelRelayStatus: modelRelayStatusMock,
  },
}));

const hybridRelayStatus = {
  ok: true,
  evidence: {
    config_model_provider: "codexzh",
    auth_mode: "chatgpt",
    rows_needing_reconcile: 0,
    provider_distribution: { codexzh: 12 },
  },
  codexPlus: {
    relay: {
      authenticated: true,
      authSource: "config",
      accountLabel: null,
      configPath: "C:/Users/test/.codex/config.toml",
      configured: true,
      requiresOpenaiAuth: true,
      hasBearerToken: true,
    },
    providerSync: {
      status: "readOnly" as const,
      targetProvider: "codexzh",
    },
  },
};

const apiOnlyRelayStatus = {
  ...hybridRelayStatus,
  evidence: {
    ...hybridRelayStatus.evidence,
    auth_mode: "apikey",
  },
  codexPlus: {
    ...hybridRelayStatus.codexPlus,
    relay: {
      ...hybridRelayStatus.codexPlus.relay,
      authenticated: false,
    },
  },
};

beforeEach(() => {
  prelaunchStatusMock.mockReset();
  prelaunchStatusMock.mockResolvedValue({
    ok: true,
    evidence: {
      config_model_provider: "openai",
      auth_mode: "chatgpt",
      rows_needing_reconcile: 0,
      provider_distribution: { openai: 12 },
    },
  });
  getEnhancerSettingsMock.mockReset();
  getEnhancerSettingsMock.mockResolvedValue({
    chatInfoMoveEnabled: false,
    oneClickHandoffEnabled: false,
    hideOfficialQuotaNoticeEnabled: false,
  });
  prelaunchRuntimeStatusMock.mockReset();
  prelaunchRuntimeStatusMock.mockResolvedValue({
    ok: true,
    codex_running: false,
    processes: [],
  });
  prelaunchStopRuntimeMock.mockReset();
  prelaunchStopRuntimeMock.mockResolvedValue({
    ok: true,
    killed: [],
    remaining: [],
  });
  modelGatewaySnapshotMock.mockReset();
  modelGatewaySnapshotMock.mockResolvedValue({
    schemaVersion: 1,
    providers: [
      {
        id: "cliproxy",
        name: "CLIProxy",
        kind: "openai-compatible",
        baseUrl: "https://upstream.example/v1",
        defaultModel: "gpt-4.1",
        enabled: true,
      },
    ],
    defaultProviderId: "cliproxy",
    configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
    relay: { enabled: true, port: 17431, autoStart: false, managementToken: "bucket-token" },
    modelRoutes: [],
    fallbackOrder: ["cliproxy"],
    routingPolicy: "first-match-then-default",
  });
  modelRelayStatusMock.mockReset();
  modelRelayStatusMock.mockResolvedValue({
    enabled: true,
    running: true,
    port: 17431,
    baseUrl: "http://127.0.0.1:17431",
    configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
  });
  prelaunchLaunchMock.mockReset();
  prelaunchLaunchMock.mockResolvedValue({
    ok: true,
    report_dir: "D:/repo/reports/20260522-123456-配置并启动-hybrid",
    provider_config: { target_model_provider: "cliproxy" },
    provider_compatibility: { status: { rows_needing_reconcile: 12 } },
    sync: { status: { rows_needing_reconcile: 12 } },
    repair: {
      summary: {
        threads_selected: 53,
        threads_skipped: 7,
        workspace_roots_selected: 3,
        skip_reasons: { missing_session_file: 5, archived: 2 },
        thread_attributions: [
          {
            id: "thread-a",
            target_location: "workspace",
            workspace_root: "D:/repo/project-a",
            reason: "cwd_exists_and_session_exists",
            provider: "openai",
          },
          {
            id: "thread-b",
            target_location: "workspace",
            workspace_root: "D:/repo/project-a",
            reason: "cwd_exists_and_session_exists",
            provider: "cliproxy",
          },
          {
            id: "thread-c",
            target_location: "workspace",
            workspace_root: "D:/repo/project-b",
            reason: "cwd_exists_and_session_exists",
            provider: "openai",
          },
          {
            id: "thread-d",
            target_location: "skipped",
            workspace_root: null,
            reason: "missing_session_file",
            provider: "openai",
          },
        ],
      },
    },
    launch: { method: "appid" },
  });
  prelaunchEnhancedLaunchMock.mockReset();
  prelaunchEnhancedLaunchMock.mockResolvedValue({
    ok: true,
    mode: "existing-session",
    report_dir: "D:/repo/reports/20260522-123456-增强启动",
    provider_config: { target_model_provider: "openai" },
    provider_compatibility: { status: { rows_needing_reconcile: 0 } },
    repair: { ok: true, skipped: true, reason: "enhanced_reuse_keeps_existing_chat_state" },
    launch: { method: "enhancer_runtime" },
  });
  prelaunchEnvironmentMock.mockReset();
  prelaunchEnvironmentMock.mockResolvedValue({
    ok: true,
    codexHome: { path: "C:/Users/test/.codex", exists: true },
    config: {
      path: "C:/Users/test/.codex/config.toml",
      exists: true,
      modelProvider: "openai",
      hybridProviderConfigured: false,
      hybridProviderKey: null,
      authMode: "chatgpt",
      authPath: { path: "C:/Users/test/.codex/auth.json", exists: true },
      statePath: { path: "C:/Users/test/.codex/state_5.sqlite", exists: true },
    },
    bridge: {
      programPath: "D:/repo/prelaunch_bridge.exe",
      scriptPath: "D:/repo/prelaunch_bridge.py",
      exePath: "D:/repo/prelaunch_bridge.exe",
      usesExe: true,
      available: true,
    },
    runtimes: {
      python: { path: "D:/Tools/Python312/pythonw.exe", source: "bundled" },
      threadripper: "D:/repo/codex-threadripper.exe",
      threadripperAvailable: true,
    },
    codexDesktop: {
      productResolvedExe: "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
      productResolvedSource: "installed",
      appid: null,
      lastResortExe: null,
      launchAvailable: true,
      running: false,
    },
    runtime: { ok: true, codex_running: false, processes: [] },
    blockers: [],
    warnings: [],
  });
  prelaunchRepairMock.mockReset();
  prelaunchRepairMock.mockResolvedValue({
    ok: true,
    mode: "repair",
    report_dir: "D:/repo/reports/20260522-123456-修复恢复-repair",
    repair: {
      summary: {
        threads_selected: 53,
        threads_skipped: 7,
        workspace_roots_selected: 3,
        skip_reasons: { missing_session_file: 5, archived: 2 },
      },
    },
  });
});

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <LoginRepairPage />
    </QueryClientProvider>,
  );
}

function clickEnhancedLaunch() {
  fireEvent.click(screen.getByRole("button", { name: "启动并加载" }));
}

function clickRepair() {
  fireEvent.click(screen.getByRole("button", { name: "修复历史" }));
}

function openAdvancedRecoveryOptions() {
  fireEvent.click(screen.getByRole("button", { name: "显示高级恢复选项" }));
}

describe("LoginRepairPage", () => {
  it("renders the current prelaunch status summary", async () => {
    renderPage();

    expect(await screen.findByText("chatgpt")).toBeInTheDocument();
    expect(screen.getByText("模型通道")).toBeInTheDocument();
    expect(screen.getAllByText("openai").length).toBeGreaterThanOrEqual(2);
    expect(prelaunchStatusMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME);
  });

  it("starts API launch through the model bucket without provider fields", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    expect(screen.queryByLabelText("Provider Key")).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "使用模型桶启动" })[0]);

    await waitFor(() => {
      expect(prelaunchLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME, "api", null, false, false);
    });
    expect(screen.queryByLabelText("Provider Key")).not.toBeInTheDocument();
  });

  it("shows model management as the only provider configuration source", async () => {
    renderPage();

    await screen.findByText("chatgpt");

    expect(screen.getByText("Codex 连接本地统一模型入口；provider、路由和 token 在模型管理中治理。")).toBeInTheDocument();
    expect(screen.getByText("保留官方登录态，同时使用本地模型桶；适合插件 + relay 双需求。")).toBeInTheDocument();
    expect(screen.queryByLabelText("Provider Key")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Base URL")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Experimental Bearer Token")).not.toBeInTheDocument();
  });

  it("places the login methods at the top without the login intro card", () => {
    renderPage();

    expect(screen.queryByText("Login & Repair")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "登录与修复" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "只检查状态" })).not.toBeInTheDocument();
    expect(screen.queryByText("隐藏 Codex 官方额度提醒")).not.toBeInTheDocument();

    const firstAction = screen.getByText("本地模型桶启动").closest(".rounded-2xl");
    const repairCard = screen.getByText("历史恢复").closest(".rounded-2xl");
    const firstStatus = screen.getByText("登录态").closest(".rounded-2xl");

    expect(screen.getByText("本地模型桶启动")).toBeInTheDocument();
    expect(screen.getByText("混合登录启动")).toBeInTheDocument();
    expect(screen.getByText("增强启动")).toBeInTheDocument();
    expect(screen.getByText("启动已登录的 Codex，并加载插件和增强功能。")).toBeInTheDocument();
    expect(screen.getByText("历史恢复")).toBeInTheDocument();
    expect(firstAction?.compareDocumentPosition(firstStatus as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(firstAction?.compareDocumentPosition(repairCard as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("renders the error state when status loading fails", async () => {
    prelaunchStatusMock.mockRejectedValueOnce(new Error("status failed"));

    renderPage();

    expect(await screen.findByText("启动前状态读取失败")).toBeInTheDocument();
    expect(screen.getByText("status failed")).toBeInTheDocument();
  });

  it("launches enhanced mode through the enhanced launch API", async () => {
    prelaunchStatusMock.mockResolvedValueOnce(hybridRelayStatus);
    prelaunchEnhancedLaunchMock.mockResolvedValueOnce({
      ok: true,
      mode: "existing-session",
      report_dir: "D:/repo/reports/20260522-123456-增强启动",
      provider_config: { target_model_provider: "codexzh" },
      provider_compatibility: { status: { rows_needing_reconcile: 0 } },
      sync: { status: { rows_needing_reconcile: 0 } },
      repair: { ok: true, summary: { threads_selected: 1, threads_skipped: 0, workspace_roots_selected: 1 } },
      launch: { method: "enhancer_runtime" },
    });

    renderPage();

    await screen.findByText("chatgpt");
    clickEnhancedLaunch();

    expect(await screen.findByText("D:/repo/reports/20260522-123456-增强启动")).toBeInTheDocument();
    expect(screen.getAllByText("codexzh").length).toBeGreaterThan(0);
    expect(screen.getByText("enhancer_runtime")).toBeInTheDocument();
    expect(prelaunchEnhancedLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME);
  });

  it("allows enhanced launch when only official account state is available", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    clickEnhancedLaunch();

    expect(await screen.findByText("D:/repo/reports/20260522-123456-增强启动")).toBeInTheDocument();
    expect(prelaunchRuntimeStatusMock).toHaveBeenCalled();
    expect(prelaunchEnhancedLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME);
  });

  it("allows enhanced launch when relay exists without official account state", async () => {
    prelaunchStatusMock.mockResolvedValueOnce(apiOnlyRelayStatus);

    renderPage();

    await screen.findByText("apikey");
    clickEnhancedLaunch();

    expect(await screen.findByText("D:/repo/reports/20260522-123456-增强启动")).toBeInTheDocument();
    expect(prelaunchRuntimeStatusMock).toHaveBeenCalled();
    expect(prelaunchEnhancedLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME);
  });

  it("shows repair summary for enhanced relay launch", async () => {
    prelaunchStatusMock.mockResolvedValueOnce(hybridRelayStatus);
    prelaunchEnhancedLaunchMock.mockResolvedValueOnce({
      ok: true,
      mode: "existing-session",
      report_dir: "D:/repo/reports/20260522-123456-增强启动",
      provider_config: { target_model_provider: "codexzh" },
      provider_compatibility: { status: { rows_needing_reconcile: 0 } },
      sync: { status: { rows_needing_reconcile: 0 } },
      repair: { ok: true, summary: { threads_selected: 1, threads_skipped: 0, workspace_roots_selected: 1 } },
      launch: { method: "enhancer_runtime" },
    });

    renderPage();

    await screen.findByText("chatgpt");
    clickEnhancedLaunch();

    expect(await screen.findByText("D:/repo/reports/20260522-123456-增强启动")).toBeInTheDocument();
    expect(screen.getByText("归属分析摘要")).toBeInTheDocument();
    expect(screen.getAllByText("恢复 workspace 数").length).toBeGreaterThan(0);
  });

  it("shows workspace-focused repair summary without provider sync wording for API launch", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "使用模型桶启动" })[0]);

    expect(await screen.findByText("归属分析摘要")).toBeInTheDocument();
    expect(screen.getAllByText("恢复 workspace 数").length).toBeGreaterThan(0);
    expect(screen.getAllByText("跳过线程数").length).toBeGreaterThan(0);
    expect(screen.getByText("主要跳过原因")).toBeInTheDocument();
    expect(screen.getByText("D:/repo/project-a")).toBeInTheDocument();
    expect(screen.getByText("D:/repo/project-b")).toBeInTheDocument();
    expect(screen.getByText("missing_session_file: 5")).toBeInTheDocument();
    expect(screen.getByText("archived: 2")).toBeInTheDocument();
    expect(screen.getAllByText("兼容差异行数").length).toBeGreaterThan(0);
    expect(screen.queryByText("待同步行数")).not.toBeInTheDocument();
  });

  it("sends no provider form payload for API launch", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "使用模型桶启动" })[0]);

    expect(await screen.findByText("D:/repo/reports/20260522-123456-配置并启动-hybrid")).toBeInTheDocument();
    expect(prelaunchLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME, "api", null, false, false);
  });

  it("keeps chat restore off by default for mixed login", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "使用模型桶启动" })[1]);

    expect(await screen.findByText("D:/repo/reports/20260522-123456-配置并启动-hybrid")).toBeInTheDocument();
    expect(prelaunchLaunchMock).toHaveBeenCalledWith(
      DEFAULT_CODEX_HOME,
      "hybrid",
      null,
      false,
      false,
    );
  });

  it("keeps mixed login provider payload on the model bucket path", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "使用模型桶启动" })[1]);

    await waitFor(() => {
      expect(prelaunchLaunchMock).toHaveBeenCalledWith(
        DEFAULT_CODEX_HOME,
        "hybrid",
        null,
        false,
        false,
      );
    });
  });

  it("uses the enhanced launch API and still forwards the quota notice flag for API launch", async () => {
    prelaunchStatusMock.mockResolvedValueOnce(hybridRelayStatus);
    getEnhancerSettingsMock.mockResolvedValueOnce({
      chatInfoMoveEnabled: false,
      oneClickHandoffEnabled: false,
      hideOfficialQuotaNoticeEnabled: true,
    });

    renderPage();

    await screen.findByText("chatgpt");
    clickEnhancedLaunch();
    await waitFor(() => {
      expect(prelaunchEnhancedLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME);
    });

    fireEvent.click(screen.getAllByRole("button", { name: "使用模型桶启动" })[0]);

    await waitFor(() => {
      expect(prelaunchLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME, "api", null, true, false);
    });
  });

  it("warns and blocks enhanced launch when Codex is still running until the user decides", async () => {
    prelaunchRuntimeStatusMock.mockResolvedValueOnce({
      ok: true,
      codex_running: true,
      processes: [{ image: "Codex.exe", pid: 1234 }],
    });

    renderPage();

    await screen.findByText("chatgpt");
    clickEnhancedLaunch();

    expect(await screen.findByText("需要重启 Codex")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "停止并重新启动" })).toBeInTheDocument();
    expect(screen.getAllByText(/Codex\.exe/).length).toBeGreaterThan(0);
    expect(prelaunchEnhancedLaunchMock).not.toHaveBeenCalled();
  });

  it("can stop Codex and continue the pending enhanced launch action", async () => {
    prelaunchRuntimeStatusMock
      .mockResolvedValueOnce({
        ok: true,
        codex_running: true,
        processes: [{ image: "Codex.exe", pid: 1234 }],
      })
      .mockResolvedValueOnce({
        ok: true,
        codex_running: false,
        processes: [],
      });

    renderPage();

    await screen.findByText("chatgpt");
    clickEnhancedLaunch();
    fireEvent.click(await screen.findByRole("button", { name: "停止并重新启动" }));

    expect(await screen.findByText("D:/repo/reports/20260522-123456-增强启动")).toBeInTheDocument();
    expect(prelaunchStopRuntimeMock).toHaveBeenCalledTimes(1);
    expect(prelaunchEnhancedLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME);
  });

  it("runs repair from the login and repair module", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    clickRepair();

    expect(await screen.findByText("D:/repo/reports/20260522-123456-修复恢复-repair")).toBeInTheDocument();
    expect(screen.getByText("53")).toBeInTheDocument();
    expect(prelaunchRepairMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME);
  });

  it("forwards advanced recovery options when running repair", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    openAdvancedRecoveryOptions();
    fireEvent.click(screen.getByRole("switch", { name: "包含归档聊天" }));
    fireEvent.click(screen.getByRole("switch", { name: "允许缺失 cwd" }));
    fireEvent.click(screen.getByRole("switch", { name: "允许空 workspace" }));
    fireEvent.click(screen.getByRole("switch", { name: "允许缺失 session" }));
    fireEvent.click(screen.getByRole("switch", { name: "恢复到 projectless" }));
    fireEvent.click(screen.getByRole("switch", { name: "取消归档选中聊天" }));
    clickRepair();

    expect(await screen.findByText("D:/repo/reports/20260522-123456-修复恢复-repair")).toBeInTheDocument();
    expect(prelaunchRepairMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME, {
      includeArchived: true,
      allowMissingCwd: true,
      allowEmptyCwd: true,
      allowMissingSession: true,
      projectlessMode: "all",
      unarchiveSelected: true,
    });
  });

  it("registers login and repair as the replacement module", () => {
    expect(ALL_APP_ROUTES).toContain("loginRepair");
    expect(ALL_APP_ROUTES).not.toContain("prelaunch");
    expect(ALL_APP_ROUTES).not.toContain("tasks");
    expect(appNavItems.map((item) => item.labelKey)).toEqual(
      expect.arrayContaining(["nav.loginRepair"]),
    );
    expect(appNavItems.every((item) => ALL_APP_ROUTES.includes(item.route))).toBe(true);
  });

  it("does not place login and repair actions inside the dashboard", () => {
    render(<OverviewPage />);

    expect(screen.queryByRole("button", { name: /配置并启动|修复历史|进入登录与修复/ })).not.toBeInTheDocument();
    expect(screen.queryByText("官方账号启动")).not.toBeInTheDocument();
    expect(screen.queryByText("本地模型桶启动")).not.toBeInTheDocument();
    expect(screen.queryByText("混合登录")).not.toBeInTheDocument();
    expect(screen.queryByText("修复恢复")).not.toBeInTheDocument();
  });
});
