import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EnhancerPage } from "@/components/enhancer/enhancer-page";
import { appNavItems } from "@/components/layout/sidebar";
import { ALL_APP_ROUTES } from "@/types/navigation";

const {
  getEnhancerSettingsMock,
  setChatInfoMoveEnabledMock,
  setOneClickHandoffEnabledMock,
  setHideOfficialQuotaNoticeEnabledMock,
  setMustInstallPluginsEnabledMock,
  switchProps,
} = vi.hoisted(() => ({
  getEnhancerSettingsMock: vi.fn(),
  setChatInfoMoveEnabledMock: vi.fn(),
  setOneClickHandoffEnabledMock: vi.fn(),
  setHideOfficialQuotaNoticeEnabledMock: vi.fn(),
  setMustInstallPluginsEnabledMock: vi.fn(),
  switchProps: [] as Array<{
    checked: boolean;
    disabled?: boolean;
    onCheckedChange?: (next: boolean) => void;
    "aria-label"?: string;
  }>,
}));

vi.mock("@/lib/api", () => ({
  api: {
    getEnhancerSettings: getEnhancerSettingsMock,
    setChatInfoMoveEnabled: setChatInfoMoveEnabledMock,
    setOneClickHandoffEnabled: setOneClickHandoffEnabledMock,
    setHideOfficialQuotaNoticeEnabled: setHideOfficialQuotaNoticeEnabledMock,
    setMustInstallPluginsEnabled: setMustInstallPluginsEnabledMock,
  },
}));

vi.mock("@/components/ui/switch", () => ({
  Switch: (props: {
    checked: boolean;
    disabled?: boolean;
    onCheckedChange?: (next: boolean) => void;
    "aria-label"?: string;
  }) => {
    switchProps.push(props);
    return (
      <button
        type="button"
        role="switch"
        aria-label={props["aria-label"]}
        aria-checked={props.checked}
        disabled={props.disabled}
      />
    );
  },
}));

beforeEach(() => {
  switchProps.length = 0;
  getEnhancerSettingsMock.mockReset();
  getEnhancerSettingsMock.mockResolvedValue({
    chatInfoMoveEnabled: false,
    oneClickHandoffEnabled: false,
    hideOfficialQuotaNoticeEnabled: false,
    mustInstallPluginsEnabled: false,
  });
  setChatInfoMoveEnabledMock.mockReset();
  setChatInfoMoveEnabledMock.mockResolvedValue({
    chatInfoMoveEnabled: true,
    oneClickHandoffEnabled: false,
    hideOfficialQuotaNoticeEnabled: false,
    mustInstallPluginsEnabled: false,
  });
  setOneClickHandoffEnabledMock.mockReset();
  setOneClickHandoffEnabledMock.mockResolvedValue({
    chatInfoMoveEnabled: false,
    oneClickHandoffEnabled: true,
    hideOfficialQuotaNoticeEnabled: false,
    mustInstallPluginsEnabled: false,
  });
  setHideOfficialQuotaNoticeEnabledMock.mockReset();
  setHideOfficialQuotaNoticeEnabledMock.mockResolvedValue({
    chatInfoMoveEnabled: false,
    oneClickHandoffEnabled: false,
    hideOfficialQuotaNoticeEnabled: true,
    mustInstallPluginsEnabled: false,
  });
  setMustInstallPluginsEnabledMock.mockReset();
  setMustInstallPluginsEnabledMock.mockResolvedValue({
    chatInfoMoveEnabled: false,
    oneClickHandoffEnabled: false,
    hideOfficialQuotaNoticeEnabled: false,
    mustInstallPluginsEnabled: true,
  });
});

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <EnhancerPage />
    </QueryClientProvider>,
  );
}

describe("EnhancerPage", () => {
  it("renders enhancer toggles", async () => {
    renderPage();

    expect(await screen.findByText("聊天信息搬家")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "聊天信息搬家" })).toBeInTheDocument();
    expect(screen.getByText("一键移交任务")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "一键移交任务" })).toBeInTheDocument();
    expect(screen.getByText("隐藏 Codex 官方额度提醒")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "隐藏 Codex 官方额度提醒" })).toBeInTheDocument();
    expect(screen.getByText("必须装")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "必须装" })).toBeInTheDocument();
    expect(getEnhancerSettingsMock).toHaveBeenCalledTimes(1);
  });

  it("saves the chat move toggle state", async () => {
    renderPage();

    await screen.findByText("聊天信息搬家");
    const toggle = switchProps.find((item) => item["aria-label"] === "聊天信息搬家");
    expect(toggle?.onCheckedChange).toBeTypeOf("function");
    act(() => {
      toggle?.onCheckedChange?.(true);
    });

    await waitFor(() => {
      expect(setChatInfoMoveEnabledMock).toHaveBeenCalledWith(true);
    });
  });

  it("saves the one-click handoff toggle state", async () => {
    renderPage();

    await screen.findByText("一键移交任务");
    const toggle = switchProps.find((item) => item["aria-label"] === "一键移交任务");
    expect(toggle?.onCheckedChange).toBeTypeOf("function");
    act(() => {
      toggle?.onCheckedChange?.(true);
    });

    await waitFor(() => {
      expect(setOneClickHandoffEnabledMock).toHaveBeenCalledWith(true);
    });
  });

  it("saves the quota notice toggle state", async () => {
    renderPage();

    await screen.findByText("隐藏 Codex 官方额度提醒");
    const toggle = switchProps.find((item) => item["aria-label"] === "隐藏 Codex 官方额度提醒");
    expect(toggle?.onCheckedChange).toBeTypeOf("function");
    act(() => {
      toggle?.onCheckedChange?.(true);
    });

    await waitFor(() => {
      expect(setHideOfficialQuotaNoticeEnabledMock).toHaveBeenCalledWith(true);
    });
  });

  it("saves the must-install plugin toggle state", async () => {
    renderPage();

    await screen.findByText("必须装");
    const toggle = switchProps.find((item) => item["aria-label"] === "必须装");
    expect(toggle?.onCheckedChange).toBeTypeOf("function");
    act(() => {
      toggle?.onCheckedChange?.(true);
    });

    await waitFor(() => {
      expect(setMustInstallPluginsEnabledMock).toHaveBeenCalledWith(true);
    });
  });

  it("registers enhancer as a top-level route", () => {
    expect(ALL_APP_ROUTES).toContain("enhancer");
    expect(appNavItems.map((item) => item.route)).toContain("enhancer");
    expect(appNavItems.find((item) => item.route === "enhancer")?.labelKey).toBe("nav.enhancer");
  });
});
