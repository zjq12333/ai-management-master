import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import {
  Bot,
  LayoutDashboard,
  LogIn,
  Settings,
  Sparkles,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { Route } from "@/types/navigation";

export const appNavItems: {
  route: Route;
  icon: LucideIcon;
  labelKey: string;
  fallbackLabel?: string;
}[] = [
  { route: "overview", icon: LayoutDashboard, labelKey: "nav.overview" },
  { route: "loginRepair", icon: LogIn, labelKey: "nav.loginRepair" },
  { route: "enhancer", icon: Sparkles, labelKey: "nav.enhancer", fallbackLabel: "增强功能" },
  { route: "aiManagement", icon: Sparkles, labelKey: "nav.aiManagement" },
  { route: "modelManagement", icon: Bot, labelKey: "nav.modelManagement" },
  { route: "maintenance", icon: Wrench, labelKey: "nav.maintenance" },
  { route: "settings", icon: Settings, labelKey: "nav.settings" },
];

const hiddenNavRoutes = new Set<Route>([]);

interface TopFeatureNavProps {
  activeRoute: Route;
  onNavigate: (route: Route) => void;
}

export function TopFeatureNav({ activeRoute, onNavigate }: TopFeatureNavProps) {
  const { t } = useTranslation();
  const noDragStyle = { WebkitAppRegion: "no-drag" } as CSSProperties;

  return (
    <div className="flex min-w-0 items-center gap-2 overflow-x-auto" style={noDragStyle}>
      {appNavItems
        .filter((item) => !hiddenNavRoutes.has(item.route))
        .map(({ route, icon: Icon, labelKey, fallbackLabel }) => {
          const isActive = activeRoute === route;
          const label = t(labelKey, {
            defaultValue: fallbackLabel ?? labelKey,
          });
          return (
            <button
              key={route}
              type="button"
              onClick={() => onNavigate(route)}
              style={noDragStyle}
              className={cn(
                "flex h-8 shrink-0 items-center gap-2 rounded-[10px] px-3 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" strokeWidth={1.75} />
              <span className="whitespace-nowrap">{label}</span>
            </button>
          );
        })}
    </div>
  );
}
