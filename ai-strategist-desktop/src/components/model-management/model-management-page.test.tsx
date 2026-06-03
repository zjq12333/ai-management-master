import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModelManagementPage } from "@/components/model-management/model-management-page";
import { appNavItems } from "@/components/layout/sidebar";
import { api } from "@/lib/api";
import i18n from "@/lib/i18n";
import { ALL_APP_ROUTES } from "@/types/navigation";

vi.mock("@/lib/api", () => ({
  api: {
    modelGatewaySnapshot: vi.fn(),
    saveModelProvider: vi.fn(),
    deleteModelProvider: vi.fn(),
    setDefaultModelProvider: vi.fn(),
    saveModelRoute: vi.fn(),
    deleteModelRoute: vi.fn(),
    checkModelProviderHealth: vi.fn(),
    listUpstreamModels: vi.fn(),
    modelRelayStatus: vi.fn(),
    saveModelRelayConfig: vi.fn(),
    startModelRelay: vi.fn(),
    stopModelRelay: vi.fn(),
    restartModelRelay: vi.fn(),
    modelRelayLogs: vi.fn(),
  },
}));

const apiMock = vi.mocked(api);

describe("ModelManagementPage", () => {
  beforeEach(() => {
    i18n.changeLanguage("zh");
    vi.clearAllMocks();
    apiMock.modelGatewaySnapshot.mockResolvedValue({
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
      defaultProviderId: "deepseek",
      relay: {
        enabled: false,
        port: 17431,
        managementToken: "",
      },
      modelRoutes: [],
      providers: [
        {
          id: "deepseek",
          name: "DeepSeek",
          kind: "openai-compatible",
          baseUrl: "https://api.deepseek.com/v1",
          defaultModel: "deepseek-chat",
          enabled: true,
        },
      ],
    });
    apiMock.modelRelayStatus.mockResolvedValue({
      enabled: false,
      running: false,
      port: 17431,
      baseUrl: "http://127.0.0.1:17431",
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
    });
    apiMock.modelRelayLogs.mockResolvedValue([]);
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("adds model management as a top-level route", () => {
    expect(ALL_APP_ROUTES).toContain("modelManagement");
    expect(appNavItems.map((item) => item.route)).toEqual([
      "overview",
      "loginRepair",
      "enhancer",
      "aiManagement",
      "modelManagement",
      "maintenance",
      "settings",
    ]);
    expect(appNavItems.map((item) => item.labelKey)).toContain("nav.modelManagement");
  });

  it("loads providers and fetches upstream models", async () => {
    apiMock.listUpstreamModels.mockResolvedValue({
      ok: true,
      providerId: "deepseek",
      endpoint: "https://api.deepseek.com/v1/models",
      models: [{ id: "deepseek-chat", ownedBy: "deepseek" }],
    });

    render(<ModelManagementPage />);

    expect((await screen.findAllByText("DeepSeek")).length).toBeGreaterThan(0);
    expect(screen.getByText("默认上游")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "拉取模型" }));

    expect(await screen.findByText("deepseek-chat")).toBeInTheDocument();
    expect(apiMock.listUpstreamModels).toHaveBeenCalledWith("deepseek");
  });

  it("checks health, sets default, and deletes providers from local gateway config", async () => {
    apiMock.checkModelProviderHealth.mockResolvedValue({
      ok: true,
      providerId: "deepseek",
      endpoint: "https://api.deepseek.com/v1/models",
      status: "healthy",
      latencyMs: 42,
      modelCount: 1,
    });
    apiMock.setDefaultModelProvider.mockResolvedValue({
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
      defaultProviderId: "deepseek",
      relay: {
        enabled: false,
        port: 17431,
      },
      modelRoutes: [],
      providers: [
        {
          id: "deepseek",
          name: "DeepSeek",
          kind: "openai-compatible",
          baseUrl: "https://api.deepseek.com/v1",
          enabled: true,
        },
      ],
    });
    apiMock.deleteModelProvider.mockResolvedValue({
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
      relay: {
        enabled: false,
        port: 17431,
      },
      modelRoutes: [],
      providers: [],
    });

    render(<ModelManagementPage />);

    expect((await screen.findAllByText("DeepSeek")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "健康检查" }));
    expect(await screen.findByText("健康")).toBeInTheDocument();
    expect(apiMock.checkModelProviderHealth).toHaveBeenCalledWith("deepseek");

    fireEvent.click(screen.getByRole("button", { name: "设为默认" }));
    await waitFor(() => expect(apiMock.setDefaultModelProvider).toHaveBeenCalledWith("deepseek"));

    fireEvent.click(screen.getByRole("button", { name: "删除上游" }));
    await waitFor(() => expect(apiMock.deleteModelProvider).toHaveBeenCalledWith("deepseek"));
  });

  it("saves and deletes model routes", async () => {
    apiMock.saveModelRoute.mockResolvedValue({
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
      defaultProviderId: "deepseek",
      relay: {
        enabled: false,
        port: 17431,
      },
      modelRoutes: [
        {
          id: "route-qwen--",
          modelPattern: "qwen-*",
          providerId: "deepseek",
          enabled: true,
        },
      ],
      providers: [
        {
          id: "deepseek",
          name: "DeepSeek",
          kind: "openai-compatible",
          baseUrl: "https://api.deepseek.com/v1",
          enabled: true,
        },
      ],
    });
    apiMock.deleteModelRoute.mockResolvedValue({
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
      defaultProviderId: "deepseek",
      relay: {
        enabled: false,
        port: 17431,
      },
      modelRoutes: [],
      providers: [
        {
          id: "deepseek",
          name: "DeepSeek",
          kind: "openai-compatible",
          baseUrl: "https://api.deepseek.com/v1",
          enabled: true,
        },
      ],
    });

    render(<ModelManagementPage />);

    fireEvent.change(await screen.findByLabelText("模型匹配"), { target: { value: "qwen-*" } });
    fireEvent.click(screen.getByRole("button", { name: "保存路由" }));

    await waitFor(() => {
      expect(apiMock.saveModelRoute).toHaveBeenCalledWith({
        route: {
          id: "route-qwen--",
          modelPattern: "qwen-*",
          providerId: "deepseek",
          enabled: true,
        },
      });
    });
    expect(await screen.findByText("qwen-*")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => expect(apiMock.deleteModelRoute).toHaveBeenCalledWith("route-qwen--"));
  });

  it("saves a provider without depending on external LAC", async () => {
    apiMock.saveModelProvider.mockResolvedValue({
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
      defaultProviderId: "qwen",
      relay: {
        enabled: false,
        port: 17431,
      },
      modelRoutes: [],
      providers: [
        {
          id: "qwen",
          name: "Qwen",
          kind: "openai-compatible",
          baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
          enabled: true,
        },
      ],
    });

    render(<ModelManagementPage />);

    expect((await screen.findAllByText("DeepSeek")).length).toBeGreaterThan(0);

    fireEvent.change(await screen.findByLabelText("Provider ID"), { target: { value: "qwen" } });
    fireEvent.change(screen.getByLabelText("名称"), { target: { value: "Qwen" } });
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
    });
    fireEvent.change(screen.getByLabelText("默认模型"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "保存上游" }));

    await waitFor(() => {
      expect(apiMock.saveModelProvider).toHaveBeenCalledWith({
        provider: {
          id: "qwen",
          name: "Qwen",
          kind: "openai-compatible",
          baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
          apiKey: "",
          defaultModel: "",
          enabled: true,
        },
        makeDefault: true,
      });
    });
  });

  it("saves and starts the local relay", async () => {
    apiMock.saveModelRelayConfig.mockResolvedValue({
      enabled: true,
      running: false,
      port: 17431,
      baseUrl: "http://127.0.0.1:17431",
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
    });
    apiMock.startModelRelay.mockResolvedValue({
      enabled: true,
      running: true,
      port: 17431,
      baseUrl: "http://127.0.0.1:17431",
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
    });
    apiMock.restartModelRelay.mockResolvedValue({
      enabled: true,
      running: true,
      port: 17431,
      baseUrl: "http://127.0.0.1:17431",
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
    });
    apiMock.stopModelRelay.mockResolvedValue({
      enabled: false,
      running: false,
      port: 17431,
      baseUrl: "http://127.0.0.1:17431",
      configPath: "C:/Users/example/AppData/Roaming/AI Strategist/model-gateway.json",
    });
    apiMock.modelRelayLogs.mockResolvedValue([
      {
        timestampMs: 1,
        method: "GET",
        path: "/v1/models",
        providerId: "deepseek",
        status: 200,
        latencyMs: 12,
      },
    ]);

    render(<ModelManagementPage />);

    expect(await screen.findByText("固定端口")).toBeInTheDocument();
    expect(screen.getByText("17431")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "启动模型桶" }));

    await waitFor(() => {
      expect(apiMock.saveModelRelayConfig).toHaveBeenCalledWith({
        port: 17431,
        enabled: true,
        managementToken: "",
      });
      expect(apiMock.startModelRelay).toHaveBeenCalled();
    });
    expect(await screen.findByText("运行中")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "复制 Base URL" }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith("http://127.0.0.1:17431"));

    fireEvent.click(screen.getByRole("button", { name: "刷新日志" }));
    expect(await screen.findByText("/v1/models")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重启" }));
    await waitFor(() => expect(apiMock.restartModelRelay).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "停止" }));
    await waitFor(() => expect(apiMock.stopModelRelay).toHaveBeenCalled());
  });
});
