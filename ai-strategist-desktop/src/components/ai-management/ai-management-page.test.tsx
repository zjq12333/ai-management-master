import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AIManagementPage } from "@/components/ai-management/ai-management-page";
import { appNavItems } from "@/components/layout/sidebar";
import i18n from "@/lib/i18n";
import { ALL_APP_ROUTES } from "@/types/navigation";

vi.mock("@/components/mcp/mcp-page", () => ({
  McpPage: () => <div>MCP content</div>,
}));

vi.mock("@/components/skills/skills-page", () => ({
  SkillsPage: () => <div>Skills content</div>,
}));

describe("AIManagementPage", () => {
  beforeEach(() => {
    i18n.changeLanguage("zh");
  });

  it("consolidates AI management modules into one top-level route", () => {
    expect(ALL_APP_ROUTES).toContain("aiManagement");
    expect(ALL_APP_ROUTES).not.toContain("customInstructions");
    expect(ALL_APP_ROUTES).not.toContain("mcp");
    expect(ALL_APP_ROUTES).not.toContain("skills");

    expect(appNavItems.map((item) => item.route)).toEqual([
      "overview",
      "loginRepair",
      "enhancer",
      "aiManagement",
      "modelManagement",
      "maintenance",
      "settings",
    ]);
    expect(appNavItems.map((item) => item.labelKey)).toContain("nav.aiManagement");
  });

  it("keeps launch and repair outside AI management", () => {
    render(<AIManagementPage />);

    expect(screen.queryByRole("tab", { name: "启动与修复" })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "MCP 管理" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Skills 管理" })).toBeInTheDocument();
    expect(screen.getByText("MCP content")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Skills 管理" }));

    expect(screen.getByText("Skills content")).toBeInTheDocument();
  });
});
