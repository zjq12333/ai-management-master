import type { CSSProperties, ReactNode } from "react";
import { Minus, Square, X } from "lucide-react";
import { api } from "@/lib/api";

interface SiteHeaderProps {
  children: ReactNode;
}

export function SiteHeader({ children }: SiteHeaderProps) {
  const handleMinimize = () => {
    void api.windowControl("minimize");
  };

  const handleToggleMaximize = () => {
    void api.windowControl("toggleMaximize");
  };

  const handleClose = () => {
    void api.windowControl("hide");
  };

  return (
    <header
      className="flex h-12 shrink-0 items-center gap-4 border-b bg-background/95 pl-4"
      data-tauri-drag-region
    >
      <div className="flex shrink-0 items-center gap-3">
        <img
          src="/app-icon.png"
          alt="AI Strategist"
          className="h-7 w-7 select-none rounded-[8px] object-cover"
          draggable={false}
        />
        <span className="text-sm font-semibold">AI Strategist</span>
      </div>
      <div className="min-w-0 flex-1">
        {children}
      </div>
      <div
        className="flex h-full shrink-0 items-stretch"
        style={{ WebkitAppRegion: "no-drag" } as CSSProperties}
      >
        <WindowControlButton ariaLabel="最小化" onClick={handleMinimize}>
          <Minus className="h-4 w-4" strokeWidth={1.75} />
        </WindowControlButton>
        <WindowControlButton ariaLabel="最大化" onClick={handleToggleMaximize}>
          <Square className="h-3.5 w-3.5" strokeWidth={1.75} />
        </WindowControlButton>
        <WindowControlButton ariaLabel="关闭" onClick={handleClose} danger>
          <X className="h-4 w-4" strokeWidth={1.75} />
        </WindowControlButton>
      </div>
    </header>
  );
}

function WindowControlButton({
  ariaLabel,
  children,
  danger = false,
  onClick,
}: {
  ariaLabel: string;
  children: ReactNode;
  danger?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      className={
        danger
          ? "no-drag flex w-11 items-center justify-center text-muted-foreground transition-colors hover:bg-red-500 hover:text-white"
          : "no-drag flex w-11 items-center justify-center text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      }
    >
      {children}
    </button>
  );
}
