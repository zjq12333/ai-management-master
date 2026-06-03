import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellOff, FolderSync, Send } from "lucide-react";

import { BentoCard } from "@/components/ui/bento-card";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import type { EnhancerSettingsPayload } from "@/types/enhancer";

type EnhancerFeatureCard = {
  key: keyof EnhancerSettingsPayload;
  title: string;
  description: string;
  detail: string;
  icon: typeof FolderSync;
  accentClassName: string;
  save: (enabled: boolean) => Promise<EnhancerSettingsPayload>;
};

const featureCards: EnhancerFeatureCard[] = [
  {
    key: "chatInfoMoveEnabled",
    title: "聊天信息搬家",
    description: "开启后，Codex 侧边栏会出现聊天归属调整入口，由用户自己在 Codex 内完成归属切换。",
    detail: "当前实现只调整聊天归属元数据，不搬动聊天文件。",
    icon: FolderSync,
    accentClassName: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    save: (enabled) => api.setChatInfoMoveEnabled(enabled),
  },
  {
    key: "oneClickHandoffEnabled",
    title: "一键移交任务",
    description: "开启后，Codex 会话操作里会提供任务移交入口，直接拉起同 workspace 的新对话接管任务。",
    detail: "会先生成 handoff 文件，再把接管提示自动送进对应 workspace 的新对话。",
    icon: Send,
    accentClassName: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
    save: (enabled) => api.setOneClickHandoffEnabled(enabled),
  },
  {
    key: "hideOfficialQuotaNoticeEnabled",
    title: "隐藏 Codex 官方额度提醒",
    description: "开启后，启动与修复里的增强登录会被锁住，请改用 API 供应商启动或混合登录。",
    detail: "这是增强功能总开关的一部分，避免在登录页单独出现策略开关。",
    icon: BellOff,
    accentClassName: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    save: (enabled) => api.setHideOfficialQuotaNoticeEnabled(enabled),
  },
];

export function EnhancerPage() {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery<EnhancerSettingsPayload>({
    queryKey: ["enhancer-settings"],
    queryFn: () => api.getEnhancerSettings(),
  });

  const saveMutation = useMutation({
    mutationFn: ({ save, enabled }: { save: EnhancerFeatureCard["save"]; enabled: boolean }) => save(enabled),
    onSuccess: (payload) => {
      queryClient.setQueryData(["enhancer-settings"], payload);
    },
  });

  const settings = saveMutation.data ?? settingsQuery.data ?? {
    chatInfoMoveEnabled: false,
    oneClickHandoffEnabled: false,
    hideOfficialQuotaNoticeEnabled: false,
  };

  return (
    <div className="space-y-6">
      {featureCards.map((feature) => {
        const Icon = feature.icon;
        return (
          <BentoCard key={feature.key} className="space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex min-w-0 gap-3">
                <div className={`rounded-xl p-2 ${feature.accentClassName}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0 space-y-1">
                  <div className="text-sm font-semibold">{feature.title}</div>
                  <p className="text-sm leading-5 text-muted-foreground">{feature.description}</p>
                  <p className="text-xs leading-5 text-muted-foreground">{feature.detail}</p>
                </div>
              </div>
              <Switch
                checked={settings[feature.key]}
                onCheckedChange={(enabled) => saveMutation.mutate({ save: feature.save, enabled })}
                disabled={settingsQuery.isLoading || saveMutation.isPending}
                aria-label={feature.title}
              />
            </div>
          </BentoCard>
        );
      })}
    </div>
  );
}
