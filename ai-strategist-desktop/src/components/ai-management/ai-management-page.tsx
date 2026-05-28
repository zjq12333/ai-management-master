import { useState } from "react";
import { FileCode2, Server, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";

import { CustomInstructionsPage } from "@/components/custom-instructions/custom-instructions-page";
import { McpPage } from "@/components/mcp/mcp-page";
import { SkillsPage } from "@/components/skills/skills-page";
import { cn } from "@/lib/utils";

type AIManagementSection = "strategyTemplates" | "mcp" | "skills";

const sections: {
  value: AIManagementSection;
  labelKey: string;
  icon: typeof FileCode2;
}[] = [
  { value: "strategyTemplates", labelKey: "aiManagement.strategyTemplates", icon: FileCode2 },
  { value: "mcp", labelKey: "nav.mcp", icon: Server },
  { value: "skills", labelKey: "nav.skills", icon: Sparkles },
];

export function AIManagementPage() {
  const { t } = useTranslation();
  const [activeSection, setActiveSection] = useState<AIManagementSection>("strategyTemplates");

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{t("aiManagement.title")}</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">{t("aiManagement.description")}</p>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <div
          role="tablist"
          aria-label={t("aiManagement.title")}
          className="inline-flex h-auto w-fit flex-wrap justify-start gap-1 rounded-2xl bg-muted/70 p-1.5 text-muted-foreground"
        >
          {sections.map(({ value, labelKey, icon: Icon }) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={activeSection === value}
              onClick={() => setActiveSection(value)}
              className={cn(
                "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl px-4 py-2 text-sm font-medium transition-colors",
                activeSection === value
                  ? "bg-card text-foreground shadow"
                  : "hover:bg-card/60 hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" strokeWidth={1.8} />
              {t(labelKey)}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-auto">
          {activeSection === "strategyTemplates" && <CustomInstructionsPage />}
          {activeSection === "mcp" && <McpPage />}
          {activeSection === "skills" && <SkillsPage />}
        </div>
      </div>
    </div>
  );
}
