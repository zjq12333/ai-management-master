import { ClipboardCheck, LayoutDashboard, PanelsTopLeft, ShieldCheck } from "lucide-react";

import { BentoCard } from "@/components/ui/bento-card";

const overviewCards = [
  {
    title: "顶部导航",
    desc: "主要功能入口统一放在顶部，左侧不再承载导航内容。",
    icon: PanelsTopLeft,
  },
  {
    title: "其他模块保留",
    desc: "自定义指令、MCP、Skills、维护和设置暂时继续保留。",
    icon: ClipboardCheck,
  },
  {
    title: "执行证据",
    desc: "涉及启动、修复等动作的证据只在对应模块内展示。",
    icon: ShieldCheck,
  },
];

export function OverviewPage() {
  return (
    <div className="space-y-6">
      <BentoCard className="overflow-hidden">
        <div className="flex items-start gap-4">
          <div className="rounded-2xl bg-primary/10 p-3 text-primary">
            <LayoutDashboard className="h-6 w-6" />
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Dashboard
            </div>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight">仪表盘</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              这里只保留总览信息。登录、启动、修复等具体操作不放在仪表盘内，统一通过顶部对应入口进入。
            </p>
          </div>
        </div>
      </BentoCard>

      <div className="grid gap-4 md:grid-cols-3">
        {overviewCards.map(({ title, desc, icon: Icon }) => (
          <BentoCard key={title}>
            <div className="flex items-start gap-3">
              <div className="rounded-xl bg-primary/10 p-2 text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-semibold">{title}</div>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">{desc}</p>
              </div>
            </div>
          </BentoCard>
        ))}
      </div>
    </div>
  );
}
