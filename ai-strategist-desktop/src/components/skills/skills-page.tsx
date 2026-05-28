import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { BentoCard } from "@/components/ui/bento-card";
import { Button } from "@/components/ui/button";
import { SegmentedOptions } from "@/components/ui/segmented-options";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "@/hooks/use-toast";
import { formatDateTime } from "@/lib/format-time";
import {
  Sparkles,
  Languages,
  Upload,
  Trash2,
  RotateCcw,
  Archive,
  Copy,
} from "lucide-react";

type Tab = "installed" | "backups";

export function SkillsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("installed");
  const [removing, setRemoving] = useState<string | null>(null);
  const [deletingBackup, setDeletingBackup] = useState<string | null>(null);
  const [showOriginal, setShowOriginal] = useState<Record<string, boolean>>({});

  const skillsQuery = useQuery({
    queryKey: ["installed-skills"],
    queryFn: () => api.loadInstalledSkills(),
    staleTime: Infinity,
  });

  const backupsQuery = useQuery({
    queryKey: ["skill-backups"],
    queryFn: () => api.loadSkillBackups(),
    enabled: tab === "backups",
  });

  const translationsQuery = useQuery({
    queryKey: ["skill-translations"],
    queryFn: () => api.loadSkillTranslations(),
    staleTime: Infinity,
  });

  const importMutation = useMutation({
    mutationFn: async () => {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const path = await open({ directory: true });
      if (typeof path === "string") return api.importSkill(path);
      throw new Error("cancelled");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["installed-skills"] }),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => api.removeSkill(id),
    onSuccess: () => {
      setRemoving(null);
      queryClient.invalidateQueries({ queryKey: ["installed-skills"] });
      queryClient.invalidateQueries({ queryKey: ["skill-backups"] });
    },
  });

  const restoreMutation = useMutation({
    mutationFn: (id: string) => api.restoreSkillBackup(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["installed-skills"] });
      queryClient.invalidateQueries({ queryKey: ["skill-backups"] });
    },
  });

  const deleteBackupMutation = useMutation({
    mutationFn: (id: string) => api.deleteSkillBackup(id),
    onSuccess: () => {
      setDeletingBackup(null);
      queryClient.invalidateQueries({ queryKey: ["skill-backups"] });
    },
  });

  const translationMutation = useMutation({
    mutationFn: () => {
      const items = (skillsQuery.data?.data.items ?? [])
        .filter((skill) => !!skill.summary?.trim())
        .map((skill) => ({ id: skill.id, text: skill.summary!.trim() }));
      if (items.length === 0) {
        throw new Error("no-text");
      }
      return api.translateSkillSummaries(null, items);
    },
    onSuccess: (result) => {
      queryClient.setQueryData(["skill-translations"], result);
      if (result.data.failedCount > 0 && result.data.translatedCount === 0) {
        toast({ title: t("skills.translationFailed"), variant: "destructive" });
      } else if (result.data.translatedCount > 0 || Object.keys(result.data.translations).length > 0) {
        toast({ title: t("skills.translationSuccess"), variant: "default" });
      } else {
        toast({ title: t("skills.translationNoText"), variant: "default" });
      }
    },
    onError: (error) => {
      if (error instanceof Error && error.message === "no-text") {
        toast({ title: t("skills.translationNoText"), variant: "default" });
        return;
      }
      toast({ title: t("skills.translationFailed"), variant: "destructive" });
    },
  });

  const skills = skillsQuery.data?.data.items ?? [];
  const backups = backupsQuery.data?.data.items ?? [];
  const skillsRootPath = skillsQuery.data?.data.rootPath ?? "";
  const backupsRootPath = backupsQuery.data?.data.rootPath ?? "";
  const translations = translationsQuery.data?.data.translations ?? {};

  const translateSummaries = () => {
    translationMutation.mutate();
  };

  const displaySummary = (skill: (typeof skills)[number]) => {
    const entry = translations[skill.id];
    const canShowTranslation =
      !!skill.summary && !!entry?.zh && entry.source.trim() === skill.summary.trim();
    return {
      text: canShowTranslation && !showOriginal[skill.id] ? entry.zh : skill.summary,
      hasTranslation: canShowTranslation,
      showingOriginal: !!showOriginal[skill.id],
    };
  };

  const copyPath = (path: string) => {
    navigator.clipboard.writeText(path);
    toast({
      title: t("skills.pathCopied"),
      description: t("skills.pathCopiedDesc"),
      variant: "default",
    });
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <p className="max-w-md text-sm text-muted-foreground">{t("skills.description")}</p>
        <div className="flex items-center gap-2">
          <SegmentedOptions
            items={[
              { value: "installed", label: t("skills.installed") },
              { value: "backups", label: t("skills.backups") },
            ]}
            value={tab}
            onChange={(value) => setTab(value as Tab)}
          />
          {tab === "installed" && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => translateSummaries()}
              disabled={translationMutation.isPending || skills.length === 0}
            >
              <Languages className="h-3.5 w-3.5" />
              {translationMutation.isPending
                ? t("skills.translatingSummaries")
                : t("skills.translateSummaries")}
            </Button>
          )}
          <Button size="sm" onClick={() => importMutation.mutate()} disabled={importMutation.isPending}>
            <Upload className="h-3.5 w-3.5" />
            {t("skills.import")}
          </Button>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4">
        <BentoCard compact>
          <span className="text-xs text-muted-foreground">{t("skills.skillCount")}</span>
          <span className="mt-1 text-lg font-semibold">{skills.length}</span>
        </BentoCard>
        <BentoCard compact>
          <span className="text-xs text-muted-foreground">{t("skills.backupCount")}</span>
          <span className="mt-1 text-lg font-semibold">{backups.length}</span>
        </BentoCard>
        <BentoCard compact>
          <span className="text-xs text-muted-foreground">{t("skills.rootPath")}</span>
          <button
            className="mt-1 flex w-full items-center gap-1.5 text-left"
            title={skillsRootPath}
            onClick={() => copyPath(skillsRootPath)}
          >
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{skillsRootPath}</span>
            <Copy className="h-3 w-3 shrink-0 text-muted-foreground" />
          </button>
        </BentoCard>
        <BentoCard compact>
          <span className="text-xs text-muted-foreground">{t("skills.backupRootPath")}</span>
          <button
            className="mt-1 flex w-full items-center gap-1.5 text-left"
            title={backupsRootPath}
            onClick={() => copyPath(backupsRootPath)}
          >
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{backupsRootPath}</span>
            <Copy className="h-3 w-3 shrink-0 text-muted-foreground" />
          </button>
        </BentoCard>
      </div>

      {/* List content */}
      {tab === "installed" ? (
        skills.length === 0 ? (
          <BentoCard>
            <div className="flex h-48 flex-col items-center justify-center">
              <Sparkles className="h-10 w-10 text-muted-foreground/40" />
              <p className="mt-3 text-sm text-muted-foreground">{t("skills.empty")}</p>
            </div>
          </BentoCard>
        ) : (
          <BentoCard className="p-0">
            <div className="divide-y divide-border">
              {skills.map((skill) => {
                const summary = displaySummary(skill);
                return (
                  <div
                    key={skill.id}
                    className="group flex items-center justify-between px-5 py-4 transition-colors hover:bg-accent"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-[14px] font-semibold">{skill.title || skill.name}</p>
                      {summary.text && (
                        <div className="mt-1.5 flex min-w-0 items-center gap-2">
                          <p className="min-w-0 flex-1 truncate text-[13px] text-muted-foreground">
                            {summary.text}
                          </p>
                          {summary.hasTranslation && (
                            <Button
                              variant="ghost"
                              size="xs"
                              className="h-6 shrink-0 px-2 text-[11px] text-muted-foreground"
                              onClick={() =>
                                setShowOriginal((prev) => ({
                                  ...prev,
                                  [skill.id]: !summary.showingOriginal,
                                }))
                              }
                            >
                              {summary.showingOriginal
                                ? t("skills.showTranslation")
                                : t("skills.showOriginal")}
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="ml-4 flex shrink-0 items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                      <Button
                        variant="outline"
                        size="icon-sm"
                        onClick={() => setRemoving(skill.id)}
                        className="text-muted-foreground hover:bg-destructive hover:text-white hover:border-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </BentoCard>
        )
      ) : backups.length === 0 ? (
        <BentoCard>
          <div className="flex h-48 flex-col items-center justify-center">
            <Archive className="h-10 w-10 text-muted-foreground/40" />
            <p className="mt-3 text-sm text-muted-foreground">{t("skills.noBackups")}</p>
          </div>
        </BentoCard>
      ) : (
        <BentoCard className="p-0">
          <div className="divide-y divide-border">
            {backups.map((backup) => (
              <div
                key={backup.id}
                className="group flex items-center justify-between px-5 py-4 transition-colors hover:bg-accent"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold">{backup.title || backup.name}</p>
                  <p className="mt-1.5 text-[13px] text-muted-foreground">
                    {formatDateTime(backup.createdAt)} · {backup.relativePath}
                  </p>
                </div>
                <div className="ml-4 flex shrink-0 items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                  <Button variant="outline" size="sm" onClick={() => restoreMutation.mutate(backup.id)} disabled={restoreMutation.isPending}>
                    <RotateCcw className="h-3.5 w-3.5" />
                    {t("skills.restore")}
                  </Button>
                  <Button
                    variant="outline"
                    size="icon-sm"
                    onClick={() => setDeletingBackup(backup.id)}
                    className="text-muted-foreground hover:bg-destructive hover:text-white hover:border-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </BentoCard>
      )}

      {/* Remove skill confirm dialog */}
      <AlertDialog open={removing !== null} onOpenChange={(v) => !v && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("skills.remove")}</AlertDialogTitle>
            <AlertDialogDescription>{t("skills.confirmRemove")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => removing && removeMutation.mutate(removing)}
            >
              {t("skills.remove")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete backup confirm dialog */}
      <AlertDialog open={deletingBackup !== null} onOpenChange={(v) => !v && setDeletingBackup(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("skills.deleteBackup")}</AlertDialogTitle>
            <AlertDialogDescription>{t("skills.confirmDeleteBackup")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deletingBackup && deleteBackupMutation.mutate(deletingBackup)}
            >
              {t("skills.deleteBackup")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

    </div>
  );
}
