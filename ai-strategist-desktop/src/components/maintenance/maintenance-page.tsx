import { useState, useCallback } from "react";
import { flushSync } from "react-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { BentoCard } from "@/components/ui/bento-card";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import {
  Stethoscope,
  Trash2,
  RotateCw,
  RotateCcw,
  Files,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import type {
  DiagnosePayload,
  DiagnosticsBundlePayload,
  FirstRunCheckStatusPayload,
  RuntimeResolutionEntry,
} from "@/types";

const MIN_FEEDBACK_MS = 800;

interface ActionResult {
  type: "success" | "error";
  message: string;
}

function RuntimeRow({
  label,
  runtime,
}: {
  label: string;
  runtime: RuntimeResolutionEntry | null;
}) {
  if (!runtime) {
    return (
      <div className="rounded-lg border border-dashed border-border/80 px-3 py-2 text-xs text-muted-foreground">
        <span className="font-medium">{label}:</span> unavailable
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/70 bg-background/70 px-3 py-2 text-xs">
      <div className="font-medium text-foreground">{label}</div>
      <div className="mt-1 break-all text-muted-foreground">{runtime.path}</div>
      <div className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground/80">{runtime.source}</div>
    </div>
  );
}

export function MaintenancePage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [results, setResults] = useState<Record<string, ActionResult>>({});
  const [runningKeys, setRunningKeys] = useState<Record<string, boolean>>({});
  const [restartConfirmOpen, setRestartConfirmOpen] = useState(false);
  const [diagnosePayload, setDiagnosePayload] = useState<DiagnosePayload | null>(null);
  const [selfCheckPayload, setSelfCheckPayload] = useState<FirstRunCheckStatusPayload | null>(null);
  const [diagnosticsBundle, setDiagnosticsBundle] = useState<DiagnosticsBundlePayload | null>(null);

  const setActionResult = (key: string, result: ActionResult) => {
    setResults((prev) => ({ ...prev, [key]: result }));
  };

  const diagnoseMutation = useMutation({
    mutationFn: () => api.diagnose(),
    onSuccess: (res) => {
      const d = res.data;
      setDiagnosePayload(d);
      setActionResult("diagnose", {
        type: "success",
        message: t("maintenance.diagnoseResult", {
          os: d.platform.os,
          arch: d.platform.arch,
          version: d.coreVersion,
          count: d.registryState.accountCount,
        }),
      });
    },
    onError: (err) => setActionResult("diagnose", { type: "error", message: String(err) }),
  });

  const cleanMutation = useMutation({
    mutationFn: () => api.clean(),
    onSuccess: (res) => {
      queryClient.invalidateQueries();
      const d = res.data;
      setActionResult("clean", {
        type: "success",
        message: t("maintenance.cleanResult", {
          authBackups: d.authBackupsRemoved,
          registryBackups: d.registryBackupsRemoved,
          staleEntries: d.staleEntriesRemoved,
        }),
      });
    },
    onError: (err) => setActionResult("clean", { type: "error", message: String(err) }),
  });

  const cleanupBackupsMutation = useMutation({
    mutationFn: () => api.cleanupDesktopHistoryBackups(10),
    onSuccess: (res) => {
      const d = res.data;
      setActionResult("cleanupBackups", {
        type: d.errors.length ? "error" : "success",
        message: t("maintenance.cleanupBackupsResult", {
          removed: d.removed,
          kept: d.kept,
          errors: d.errors.length,
        }),
      });
    },
    onError: (err) => setActionResult("cleanupBackups", { type: "error", message: String(err) }),
  });

  const rebuildMutation = useMutation({
    mutationFn: () => api.rebuildRegistry(),
    onSuccess: (res) => {
      queryClient.invalidateQueries();
      setActionResult("rebuild", {
        type: "success",
        message: t("maintenance.rebuildResult", { count: res.data.accountCount }),
      });
    },
    onError: (err) => setActionResult("rebuild", { type: "error", message: String(err) }),
  });

  const restartMutation = useMutation({
    mutationFn: () => api.restartCodex(),
    onSuccess: () => setActionResult("restart", { type: "success", message: t("maintenance.codexRestarted") }),
    onError: (err) => setActionResult("restart", { type: "error", message: String(err) }),
  });

  const diagnosticsBundleMutation = useMutation({
    mutationFn: () => api.exportDiagnosticsBundle(),
    onSuccess: (res) => {
      const data = res.data;
      setDiagnosticsBundle(data);
      setActionResult("diagnosticsBundle", {
        type: "success",
        message: `Diagnostics bundle exported: ${data.bundlePath}`,
      });
    },
    onError: (err) => setActionResult("diagnosticsBundle", { type: "error", message: String(err) }),
  });

  const firstRunSelfCheckMutation = useMutation({
    mutationFn: () => api.firstRunSelfCheck(),
    onSuccess: (res) => {
      const data = res.data;
      setSelfCheckPayload(data);
      setActionResult("selfCheck", {
        type: data.state === "ready" ? "success" : "error",
        message: data.summary,
      });
    },
    onError: (err) => setActionResult("selfCheck", { type: "error", message: String(err) }),
  });

  const runAction = useCallback(async (key: string, mutateAsync: () => Promise<unknown>) => {
    if (runningKeys[key]) return;
    flushSync(() => setRunningKeys((prev) => ({ ...prev, [key]: true })));
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

    const startedAt = Date.now();
    try {
      await mutateAsync();
    } finally {
      const elapsed = Date.now() - startedAt;
      if (elapsed < MIN_FEEDBACK_MS) {
        await new Promise((r) => setTimeout(r, MIN_FEEDBACK_MS - elapsed));
      }
      setRunningKeys((prev) => ({ ...prev, [key]: false }));
    }
  }, [runningKeys]);

  const handleRestartClick = () => {
    setRestartConfirmOpen(true);
  };

  const handleRestartConfirm = () => {
    setRestartConfirmOpen(false);
    runAction("restart", () => restartMutation.mutateAsync());
  };

  const openDiagnosticsBundle = async () => {
    if (!diagnosticsBundle?.bundlePath) return;
    await api.openPath(diagnosticsBundle.bundlePath);
  };

  const actions: {
    key: string;
    icon: typeof Stethoscope;
    iconColor: string;
    label: string;
    description: string;
    actionLabel: string;
    loadingLabel: string;
    onAction: () => void;
    variant?: "destructive";
    secondaryActionLabel?: string;
    secondaryLoadingLabel?: string;
    onSecondaryAction?: () => void;
    secondaryDisabled?: boolean;
    secondaryVariant?: "destructive";
  }[] = [
    {
      key: "diagnose",
      icon: Stethoscope,
      iconColor: "text-blue-500",
      label: t("maintenance.diagnose"),
      description: t("maintenance.diagnoseDesc"),
      actionLabel: t("maintenance.diagnoseAction"),
      loadingLabel: t("maintenance.diagnosing"),
      onAction: () => runAction("diagnose", () => diagnoseMutation.mutateAsync()),
    },
    {
      key: "selfCheck",
      icon: Stethoscope,
      iconColor: "text-emerald-500",
      label: t("maintenance.selfCheck"),
      description: t("maintenance.selfCheckDesc"),
      actionLabel: t("maintenance.selfCheckAction"),
      loadingLabel: t("maintenance.running"),
      onAction: () => runAction("selfCheck", () => firstRunSelfCheckMutation.mutateAsync()),
    },
    {
      key: "diagnosticsBundle",
      icon: Files,
      iconColor: "text-slate-500",
      label: "Diagnostics Bundle",
      description: "Export app version, runtime resolution, helper availability, and permission-check results.",
      actionLabel: "Export",
      loadingLabel: t("maintenance.running"),
      onAction: () => runAction("diagnosticsBundle", () => diagnosticsBundleMutation.mutateAsync()),
    },
    {
      key: "clean",
      icon: Trash2,
      iconColor: "text-amber-500",
      label: t("maintenance.clean"),
      description: t("maintenance.cleanDesc"),
      actionLabel: t("maintenance.cleanAction"),
      loadingLabel: t("maintenance.cleaning"),
      onAction: () => runAction("clean", () => cleanMutation.mutateAsync()),
    },
    {
      key: "cleanupBackups",
      icon: Files,
      iconColor: "text-cyan-500",
      label: t("maintenance.cleanupBackups"),
      description: t("maintenance.cleanupBackupsDesc"),
      actionLabel: t("maintenance.cleanupBackupsAction"),
      loadingLabel: t("maintenance.cleaning"),
      onAction: () => runAction("cleanupBackups", () => cleanupBackupsMutation.mutateAsync()),
    },
    {
      key: "rebuild",
      icon: RotateCw,
      iconColor: "text-violet-500",
      label: t("maintenance.rebuild"),
      description: t("maintenance.rebuildDesc"),
      actionLabel: t("maintenance.rebuildAction"),
      loadingLabel: t("maintenance.rebuilding"),
      onAction: () => runAction("rebuild", () => rebuildMutation.mutateAsync()),
    },
    {
      key: "restart",
      icon: RotateCcw,
      iconColor: "text-red-500",
      label: t("maintenance.restartCodex"),
      description: t("maintenance.restartCodexDesc"),
      actionLabel: t("maintenance.restartCodexAction"),
      loadingLabel: t("maintenance.running"),
      onAction: handleRestartClick,
      variant: "destructive",
    },
  ];

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">{t("maintenance.description")}</p>

      {diagnosePayload && (
        <BentoCard className="space-y-4 p-5">
          <div>
            <div className="text-sm font-semibold">{t("maintenance.runtimeDiagnosticsTitle")}</div>
            <p className="mt-1 text-xs text-muted-foreground">
              {diagnosePayload.firstRunCheck.summary}
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <RuntimeRow label="Python" runtime={diagnosePayload.runtimes.python} />
            <RuntimeRow label="Codex CLI" runtime={diagnosePayload.runtimes.codexCli} />
            <RuntimeRow label="Codex Desktop" runtime={diagnosePayload.runtimes.codexDesktop} />
            <RuntimeRow label="Threadripper" runtime={diagnosePayload.runtimes.threadripper} />
          </div>
          <div className="rounded-lg border border-border/70 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{t("maintenance.firstRunCheckStatus")}:</span>{" "}
            {diagnosePayload.firstRunCheck.state}
            {diagnosePayload.firstRunCheck.actionLabel ? ` - ${diagnosePayload.firstRunCheck.actionLabel}` : ""}
          </div>
        </BentoCard>
      )}

      {selfCheckPayload && (
        <BentoCard className="space-y-4 p-5">
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <span className="rounded-full border border-border/70 px-2.5 py-1 font-medium text-foreground">
              {selfCheckPayload.state}
            </span>
            <span className="text-muted-foreground">
              repaired {selfCheckPayload.repairedCount} - blocked {selfCheckPayload.blockedCount}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{selfCheckPayload.summary}</p>
          <div className="grid gap-3 md:grid-cols-2">
            {selfCheckPayload.checks.map((check) => (
              <div key={check.key} className="rounded-lg border border-border/70 bg-background/70 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-foreground">{check.label}</span>
                  <span className="uppercase tracking-wide text-muted-foreground/80">{check.state}</span>
                </div>
                <div className="mt-1 break-all text-muted-foreground">{check.detail}</div>
              </div>
            ))}
          </div>
        </BentoCard>
      )}

      {diagnosticsBundle && (
        <BentoCard className="space-y-3 p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold">Diagnostics Bundle</div>
            <Button variant="outline" size="sm" onClick={openDiagnosticsBundle}>Open</Button>
          </div>
          <div className="text-xs text-muted-foreground break-all">{diagnosticsBundle.bundlePath}</div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-border/70 bg-background/70 px-3 py-2 text-xs">
              <div className="font-medium text-foreground">Python runtime used</div>
              <div className="mt-1 break-all text-muted-foreground">{diagnosticsBundle.pythonRuntimePathUsed}</div>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/70 px-3 py-2 text-xs">
              <div className="font-medium text-foreground">Codex path used</div>
              <div className="mt-1 break-all text-muted-foreground">{diagnosticsBundle.codexPathUsed ?? "unavailable"}</div>
            </div>
          </div>
        </BentoCard>
      )}
      <BentoCard className="p-0">
        <div className="divide-y divide-border">
          {actions.map(({ key, icon: Icon, iconColor, label, description, actionLabel, loadingLabel, onAction, variant, secondaryActionLabel, secondaryLoadingLabel, onSecondaryAction, secondaryDisabled, secondaryVariant }) => {
            const result = results[key];
            const busy = !!runningKeys[key];
            const primaryBusy = busy;
            const secondaryBusy = false;
            return (
              <div key={key} className="px-5 py-4 transition-colors hover:bg-accent">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <Icon className={cn("h-[18px] w-[18px] shrink-0", iconColor)} />
                    <div className="min-w-0">
                      <span className="text-[14px] font-semibold">{label}</span>
                      <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{description}</p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={onAction}
                      disabled={primaryBusy || secondaryBusy}
                      className={cn(variant === "destructive" ? "text-muted-foreground hover:border-destructive hover:bg-destructive hover:text-white" : "")}
                    >
                      {primaryBusy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                      {primaryBusy ? loadingLabel : actionLabel}
                    </Button>
                    {secondaryActionLabel && onSecondaryAction && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={onSecondaryAction}
                        disabled={secondaryBusy || primaryBusy || secondaryDisabled}
                        className={cn(
                          secondaryVariant === "destructive"
                            ? "text-muted-foreground hover:border-destructive hover:bg-destructive hover:text-white disabled:hover:border-input disabled:hover:bg-transparent disabled:hover:text-muted-foreground"
                            : ""
                        )}
                      >
                        {secondaryBusy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                        {secondaryBusy ? secondaryLoadingLabel : secondaryActionLabel}
                      </Button>
                    )}
                  </div>
                </div>
                {result && (
                  <div
                    className={cn(
                      "mt-3 flex items-start gap-2 rounded-xl border px-3 py-2 text-xs",
                      result.type === "success"
                        ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-700 dark:text-emerald-400"
                        : "border-destructive/20 bg-destructive/5 text-destructive"
                    )}
                  >
                    {result.type === "success" ? (
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    )}
                    <span>{result.message}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </BentoCard>

      <AlertDialog open={restartConfirmOpen} onOpenChange={setRestartConfirmOpen}>
        <AlertDialogContent className="max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle>{t("maintenance.restartConfirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("maintenance.restartConfirmDesc")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRestartConfirm}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {t("maintenance.restartCodexAction")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
