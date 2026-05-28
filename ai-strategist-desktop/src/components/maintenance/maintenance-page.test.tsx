import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import { MaintenancePage } from "@/components/maintenance/maintenance-page";

vi.mock("@/lib/api", () => ({
  api: {
    diagnose: vi.fn(),
    clean: vi.fn(),
    cleanupDesktopHistoryBackups: vi.fn(),
    rebuildRegistry: vi.fn(),
    restartCodex: vi.fn(),
    exportDiagnosticsBundle: vi.fn(),
    firstRunSelfCheck: vi.fn(),
    openPath: vi.fn(),
  },
}));

function renderMaintenancePage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MaintenancePage />
    </QueryClientProvider>,
  );
}

describe("MaintenancePage", () => {
  it("does not expose archived chat deletion because Codex handles it natively", () => {
    renderMaintenancePage();

    expect(screen.queryByText("归档聊天")).not.toBeInTheDocument();
    expect(screen.queryByText("预览归档聊天")).not.toBeInTheDocument();
    expect(screen.queryByText("删除归档聊天")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认删除" })).not.toBeInTheDocument();
  });
});
