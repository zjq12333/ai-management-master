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
  getEnhancerSettingsMock,
  prelaunchRuntimeStatusMock,
  prelaunchStopRuntimeMock,
  prelaunchLaunchMock,
  prelaunchRepairMock,
} = vi.hoisted(() => ({
  prelaunchStatusMock: vi.fn(),
  getEnhancerSettingsMock: vi.fn(),
  prelaunchRuntimeStatusMock: vi.fn(),
  prelaunchStopRuntimeMock: vi.fn(),
  prelaunchLaunchMock: vi.fn(),
  prelaunchRepairMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    prelaunchStatus: prelaunchStatusMock,
    getEnhancerSettings: getEnhancerSettingsMock,
    prelaunchRuntimeStatus: prelaunchRuntimeStatusMock,
    prelaunchStopRuntime: prelaunchStopRuntimeMock,
    prelaunchLaunch: prelaunchLaunchMock,
    prelaunchRepair: prelaunchRepairMock,
  },
}));

const providerPayload = {
  key: "cliproxy",
  name: "CLIProxy",
  base_url: "http://127.0.0.1:20128/v1",
  wire_api: "responses",
  env_key: "OPENAI_API_KEY",
  requires_openai_auth: false,
  experimental_bearer_token: "",
};

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
    mustInstallPluginsEnabled: false,
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

function fillProviderForm() {
  fireEvent.change(screen.getByLabelText("Provider Key"), { target: { value: providerPayload.key } });
  fireEvent.change(screen.getByLabelText("Provider Name"), { target: { value: providerPayload.name } });
  fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: providerPayload.base_url } });
  fireEvent.change(screen.getByLabelText("Env Key"), { target: { value: providerPayload.env_key } });
}

describe("LoginRepairPage", () => {
  it("renders the current prelaunch status summary", async () => {
    renderPage();

    expect(await screen.findByText("chatgpt")).toBeInTheDocument();
    expect(screen.getByText("模型通道")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getAllByText("openai")).toHaveLength(2);
    expect(prelaunchStatusMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME);
  });

  it("shows provider input fields only after choosing API or mixed login", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    expect(screen.queryByLabelText("Provider Key")).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "填写信息" })[0]);

    expect(screen.getByLabelText("Provider Key")).toBeInTheDocument();
    expect(screen.getByLabelText("Provider Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Base URL")).toBeInTheDocument();
    expect(screen.getByLabelText("Env Key")).toBeInTheDocument();
  });

  it("places the login methods at the top without the login intro card", () => {
    renderPage();

    expect(screen.queryByText("Login & Repair")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "登录与修复" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "只检查状态" })).not.toBeInTheDocument();
    expect(screen.queryByText("隐藏 Codex 官方额度提醒")).not.toBeInTheDocument();

    const firstAction = screen.getByText("增强登录").closest(".rounded-2xl");
    const repairCard = screen.getByText("修复恢复").closest(".rounded-2xl");
    const firstStatus = screen.getByText("登录态").closest(".rounded-2xl");

    expect(screen.getByText("API 供应商启动")).toBeInTheDocument();
    expect(screen.getByText("混合登录")).toBeInTheDocument();
    expect(screen.getByText("复用上次混合登录保存的官方账号 + Relay 配置，不需要重复填写 Provider 信息。")).toBeInTheDocument();
    expect(screen.getByText("官方账号 + API（第三方也行）同时登录，保持插件等原生功能。")).toBeInTheDocument();
    expect(screen.getByText("修复恢复")).toBeInTheDocument();
    expect(firstAction?.compareDocumentPosition(firstStatus as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(firstAction?.compareDocumentPosition(repairCard as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("renders the error state when status loading fails", async () => {
    prelaunchStatusMock.mockRejectedValueOnce(new Error("status failed"));

    renderPage();

    expect(await screen.findByText("启动前状态读取失败")).toBeInTheDocument();
    expect(screen.getByText("status failed")).toBeInTheDocument();
  });

  it("launches enhanced mode by reusing the configured hybrid relay provider", async () => {
    prelaunchStatusMock.mockResolvedValueOnce(hybridRelayStatus);
    prelaunchLaunchMock.mockResolvedValueOnce({
      ok: true,
      mode: "hybrid",
      report_dir: "D:/repo/reports/20260522-123456-配置并启动-hybrid",
      provider_config: { target_model_provider: "codexzh" },
      provider_compatibility: { status: { rows_needing_reconcile: 0 } },
      sync: { status: { rows_needing_reconcile: 0 } },
      repair: { ok: true, summary: { threads_selected: 1, threads_skipped: 0, workspace_roots_selected: 1 } },
      launch: { method: "enhancer_runtime" },
    });

    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getByRole("button", { name: "直接启动" }));

    expect(await screen.findByText("D:/repo/reports/20260522-123456-配置并启动-hybrid")).toBeInTheDocument();
    expect(screen.getAllByText("codexzh").length).toBeGreaterThan(0);
    expect(screen.getByText("enhancer_runtime")).toBeInTheDocument();
    expect(prelaunchLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME, "hybrid", null, false, false);
  });

  it("blocks enhanced login when only official account state is available", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getByRole("button", { name: "直接启动" }));

    expect(screen.getByText("增强登录需要先保存混合登录信息：当前只检测到官方账号，请先使用混合登录填写 Relay/API 信息。")).toBeInTheDocument();
    expect(prelaunchRuntimeStatusMock).not.toHaveBeenCalled();
    expect(prelaunchLaunchMock).not.toHaveBeenCalled();
  });

  it("blocks enhanced login when relay exists without official account state", async () => {
    prelaunchStatusMock.mockResolvedValueOnce(apiOnlyRelayStatus);

    renderPage();

    await screen.findByText("apikey");
    fireEvent.click(screen.getByRole("button", { name: "直接启动" }));

    expect(screen.getByText("增强登录需要官方账号和 Relay/API 混合信息：当前只检测到 Relay/API 配置，请先完成官方账号登录并用混合登录保存一次。")).toBeInTheDocument();
    expect(prelaunchRuntimeStatusMock).not.toHaveBeenCalled();
    expect(prelaunchLaunchMock).not.toHaveBeenCalled();
  });

  it("shows repair summary for enhanced relay launch", async () => {
    prelaunchStatusMock.mockResolvedValueOnce(hybridRelayStatus);
    prelaunchLaunchMock.mockResolvedValueOnce({
      ok: true,
      mode: "hybrid",
      report_dir: "D:/repo/reports/20260522-123456-配置并启动-hybrid",
      provider_config: { target_model_provider: "codexzh" },
      provider_compatibility: { status: { rows_needing_reconcile: 0 } },
      sync: { status: { rows_needing_reconcile: 0 } },
      repair: { ok: true, summary: { threads_selected: 1, threads_skipped: 0, workspace_roots_selected: 1 } },
      launch: { method: "enhancer_runtime" },
    });

    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getByRole("button", { name: "直接启动" }));

    expect(await screen.findByText("D:/repo/reports/20260522-123456-配置并启动-hybrid")).toBeInTheDocument();
    expect(screen.getByText("归属分析摘要")).toBeInTheDocument();
    expect(screen.getAllByText("恢复 workspace 数").length).toBeGreaterThan(0);
  });

  it("shows workspace-focused repair summary without provider sync wording for API launch", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "填写信息" })[0]);
    fillProviderForm();
    fireEvent.click(screen.getByRole("button", { name: "确认并启动 API 供应商启动" }));

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

  it("sends the provider form payload for API launch", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "填写信息" })[0]);
    fillProviderForm();
    fireEvent.click(screen.getByRole("button", { name: "确认并启动 API 供应商启动" }));

    expect(await screen.findByText("D:/repo/reports/20260522-123456-配置并启动-hybrid")).toBeInTheDocument();
    expect(prelaunchLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME, "api", providerPayload, false, false);
  });

  it("keeps chat restore off by default and allows mixed login token input", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "填写信息" })[1]);

    const restoreSwitch = screen.getByRole("switch", { name: "恢复聊天信息" });
    expect(restoreSwitch).not.toBeChecked();
    expect(screen.getByLabelText("Bearer Token")).not.toBeDisabled();

    fireEvent.change(screen.getByLabelText("Provider Key"), { target: { value: providerPayload.key } });
    fireEvent.change(screen.getByLabelText("Provider Name"), { target: { value: providerPayload.name } });
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: providerPayload.base_url } });
    fireEvent.change(screen.getByLabelText("Bearer Token"), { target: { value: "sk-test-token" } });
    fireEvent.click(screen.getByRole("button", { name: "确认并启动 混合登录" }));

    expect(await screen.findByText("D:/repo/reports/20260522-123456-配置并启动-hybrid")).toBeInTheDocument();
    expect(prelaunchLaunchMock).toHaveBeenCalledWith(
      DEFAULT_CODEX_HOME,
      "hybrid",
      {
        ...providerPayload,
        env_key: "",
        requires_openai_auth: true,
        experimental_bearer_token: "sk-test-token",
      },
      false,
      false,
    );
  });

  it("forwards chat restore choice when mixed login restore switch is enabled", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "填写信息" })[1]);
    fireEvent.click(screen.getByRole("switch", { name: "恢复聊天信息" }));

    fireEvent.change(screen.getByLabelText("Provider Key"), { target: { value: providerPayload.key } });
    fireEvent.change(screen.getByLabelText("Provider Name"), { target: { value: providerPayload.name } });
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: providerPayload.base_url } });
    fireEvent.change(screen.getByLabelText("Bearer Token"), { target: { value: "sk-test-token" } });
    fireEvent.click(screen.getByRole("button", { name: "确认并启动 混合登录" }));

    await waitFor(() => {
      expect(prelaunchLaunchMock).toHaveBeenCalledWith(
        DEFAULT_CODEX_HOME,
        "hybrid",
        {
          ...providerPayload,
          env_key: "",
          requires_openai_auth: true,
          experimental_bearer_token: "sk-test-token",
        },
        false,
        true,
      );
    });
  });

  it("still forwards the quota notice flag for enhanced relay launch", async () => {
    prelaunchStatusMock.mockResolvedValueOnce(hybridRelayStatus);
    getEnhancerSettingsMock.mockResolvedValueOnce({
      chatInfoMoveEnabled: false,
      oneClickHandoffEnabled: false,
      hideOfficialQuotaNoticeEnabled: true,
      mustInstallPluginsEnabled: false,
    });

    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getByRole("button", { name: "直接启动" }));
    await waitFor(() => {
      expect(prelaunchLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME, "hybrid", null, true, false);
    });

    fireEvent.click(screen.getAllByRole("button", { name: "填写信息" })[0]);
    fillProviderForm();
    fireEvent.click(screen.getByRole("button", { name: "确认并启动 API 供应商启动" }));

    expect(await screen.findByText("D:/repo/reports/20260522-123456-配置并启动-hybrid")).toBeInTheDocument();
    expect(prelaunchLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME, "api", providerPayload, true, false);
  });

  it("warns and blocks launch when Codex is still running until the user decides", async () => {
    prelaunchRuntimeStatusMock.mockResolvedValueOnce({
      ok: true,
      codex_running: true,
      processes: [{ image: "Codex.exe", pid: 1234 }],
    });

    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "填写信息" })[0]);
    fillProviderForm();
    fireEvent.click(screen.getByRole("button", { name: "确认并启动 API 供应商启动" }));

    expect(await screen.findByText("Codex 正在运行")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "我自己关闭" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "帮我关闭并继续" })).toBeInTheDocument();
    expect(screen.getByText(/Codex\.exe/)).toBeInTheDocument();
    expect(prelaunchLaunchMock).not.toHaveBeenCalled();
  });

  it("can stop Codex and continue the pending API launch action", async () => {
    prelaunchRuntimeStatusMock.mockResolvedValueOnce({
      ok: true,
      codex_running: true,
      processes: [{ image: "Codex.exe", pid: 1234 }],
    });

    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getAllByRole("button", { name: "填写信息" })[0]);
    fillProviderForm();
    fireEvent.click(screen.getByRole("button", { name: "确认并启动 API 供应商启动" }));
    fireEvent.click(await screen.findByRole("button", { name: "帮我关闭并继续" }));

    expect(await screen.findByText("D:/repo/reports/20260522-123456-配置并启动-hybrid")).toBeInTheDocument();
    expect(prelaunchStopRuntimeMock).toHaveBeenCalledTimes(1);
    expect(prelaunchLaunchMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME, "api", providerPayload, false, false);
  });

  it("runs repair from the login and repair module", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getByRole("button", { name: "开始修复" }));

    expect(await screen.findByText("D:/repo/reports/20260522-123456-修复恢复-repair")).toBeInTheDocument();
    expect(screen.getByText("53")).toBeInTheDocument();
    expect(prelaunchRepairMock).toHaveBeenCalledWith(DEFAULT_CODEX_HOME);
  });

  it("forwards advanced recovery options when running repair", async () => {
    renderPage();

    await screen.findByText("chatgpt");
    fireEvent.click(screen.getByRole("switch", { name: "包含归档聊天" }));
    fireEvent.click(screen.getByRole("switch", { name: "允许缺失 cwd" }));
    fireEvent.click(screen.getByRole("switch", { name: "允许空 workspace" }));
    fireEvent.click(screen.getByRole("switch", { name: "允许缺失 session" }));
    fireEvent.click(screen.getByRole("switch", { name: "恢复到 projectless" }));
    fireEvent.click(screen.getByRole("switch", { name: "取消归档选中聊天" }));
    fireEvent.click(screen.getByRole("button", { name: "开始修复" }));

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

    expect(screen.queryByRole("button", { name: /配置并启动|开始修复|进入登录与修复/ })).not.toBeInTheDocument();
    expect(screen.queryByText("官方账号启动")).not.toBeInTheDocument();
    expect(screen.queryByText("API 供应商启动")).not.toBeInTheDocument();
    expect(screen.queryByText("混合登录")).not.toBeInTheDocument();
    expect(screen.queryByText("修复恢复")).not.toBeInTheDocument();
  });
});
