import { useEffect, useMemo, useState } from "react";
import { DatabaseZap, RefreshCw, Save, ServerCog } from "lucide-react";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type {
  ModelGatewaySnapshot,
  ModelProviderConfig,
  ModelProviderHealthPayload,
  ModelProviderKind,
  ModelRelayLogEntry,
  ModelRelayStatusPayload,
  ModelRouteConfig,
  UpstreamModel,
} from "@/types/model-management";

const emptyProvider: ModelProviderConfig = {
  id: "",
  name: "",
  kind: "openai-compatible",
  baseUrl: "",
  apiKey: "",
  defaultModel: "",
  enabled: true,
};

const emptyRoute: ModelRouteConfig = {
  id: "",
  modelPattern: "",
  providerId: "",
  enabled: true,
};

export function ModelManagementPage() {
  const [snapshot, setSnapshot] = useState<ModelGatewaySnapshot | null>(null);
  const [form, setForm] = useState<ModelProviderConfig>(emptyProvider);
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [models, setModels] = useState<UpstreamModel[]>([]);
  const [health, setHealth] = useState<ModelProviderHealthPayload | null>(null);
  const [relay, setRelay] = useState<ModelRelayStatusPayload | null>(null);
  const [relayLogs, setRelayLogs] = useState<ModelRelayLogEntry[]>([]);
  const [relayPort, setRelayPort] = useState("17431");
  const [relayToken, setRelayToken] = useState("");
  const [routeForm, setRouteForm] = useState<ModelRouteConfig>(emptyRoute);
  const [status, setStatus] = useState("");
  const [fetchingModels, setFetchingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);
  const [relayBusy, setRelayBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .modelGatewaySnapshot()
      .then((payload) => {
        if (cancelled) return;
        setSnapshot(payload);
        setRelayPort(String(payload.relay.port));
        setRelayToken(payload.relay.managementToken ?? "");
        setRouteForm((current) => ({
          ...current,
          providerId: current.providerId || payload.defaultProviderId || payload.providers[0]?.id || "",
        }));
        const first = payload.providers.find((provider) => provider.id === payload.defaultProviderId) ?? payload.providers[0];
        if (first) {
          setSelectedProviderId(first.id);
          setForm({ ...emptyProvider, ...first, apiKey: first.apiKey ?? "", defaultModel: first.defaultModel ?? "" });
        }
        return api.modelRelayStatus();
      })
      .then((payload) => {
        if (cancelled || !payload) return;
        setRelay(payload);
        setRelayPort(String(payload.port));
        return api.modelRelayLogs();
      })
      .then((payload) => {
        if (cancelled || !payload) return;
        setRelayLogs(payload);
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : String(error)));
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedProvider = useMemo(
    () => snapshot?.providers.find((provider) => provider.id === selectedProviderId),
    [selectedProviderId, snapshot],
  );

  const updateForm = (patch: Partial<ModelProviderConfig>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const selectProvider = (providerId: string) => {
    const provider = snapshot?.providers.find((item) => item.id === providerId);
    setSelectedProviderId(providerId);
    if (provider) {
      setForm({ ...emptyProvider, ...provider, apiKey: provider.apiKey ?? "", defaultModel: provider.defaultModel ?? "" });
      setModels([]);
      setHealth(null);
      setStatus("");
    }
  };

  const saveProvider = async () => {
    setSaving(true);
    setStatus("");
    try {
      const payload = await api.saveModelProvider({ provider: form, makeDefault: true });
      setSnapshot(payload);
      setSelectedProviderId(form.id);
      setStatus("上游配置已保存");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  const setDefaultProvider = async () => {
    const providerId = selectedProvider?.id || form.id;
    if (!providerId) {
      setStatus("请先选择或保存一个上游");
      return;
    }
    setSaving(true);
    setStatus("");
    try {
      const payload = await api.setDefaultModelProvider(providerId);
      setSnapshot(payload);
      setSelectedProviderId(providerId);
      setStatus("默认上游已更新");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  const deleteProvider = async () => {
    const providerId = selectedProvider?.id;
    if (!providerId) {
      setStatus("请先选择一个已保存的上游");
      return;
    }
    setSaving(true);
    setStatus("");
    try {
      const payload = await api.deleteModelProvider(providerId);
      setSnapshot(payload);
      const next = payload.providers.find((provider) => provider.id === payload.defaultProviderId) ?? payload.providers[0];
      setSelectedProviderId(next?.id ?? "");
      setForm(next ? { ...emptyProvider, ...next, apiKey: next.apiKey ?? "", defaultModel: next.defaultModel ?? "" } : emptyProvider);
      setModels([]);
      setHealth(null);
      setStatus("上游已删除");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  const checkHealth = async () => {
    const providerId = selectedProvider?.id || form.id;
    if (!providerId) {
      setStatus("请先选择或保存一个上游");
      return;
    }
    setChecking(true);
    setStatus("");
    try {
      const payload = await api.checkModelProviderHealth(providerId);
      setHealth(payload);
      setStatus(
        payload.ok
          ? `健康检查通过：${payload.modelCount} 个模型，${payload.latencyMs}ms`
          : payload.error ?? "健康检查失败",
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setChecking(false);
    }
  };

  const saveRelayConfig = async () => {
    setRelayBusy(true);
    setStatus("");
    try {
      const payload = await api.saveModelRelayConfig({
        port: relay?.port ?? snapshot?.relay.port ?? 17431,
        enabled: relay?.enabled ?? false,
        autoStart: snapshot?.relay.autoStart ?? false,
        managementToken: relayToken,
      });
      setRelay(payload);
      setRelayPort(String(payload.port));
      setStatus("模型桶访问 Token 已保存");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setRelayBusy(false);
    }
  };

  const startRelay = async () => {
    setRelayBusy(true);
    setStatus("");
    try {
      await api.saveModelRelayConfig({
        port: relay?.port ?? snapshot?.relay.port ?? 17431,
        enabled: true,
        managementToken: relayToken,
      });
      const payload = await api.startModelRelay();
      setRelay(payload);
      setRelayPort(String(payload.port));
      setStatus(`本地 Relay 已启动：${payload.baseUrl}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setRelayBusy(false);
    }
  };

  const stopRelay = async () => {
    setRelayBusy(true);
    setStatus("");
    try {
      const payload = await api.stopModelRelay();
      setRelay(payload);
      setRelayPort(String(payload.port));
      setStatus("本地 Relay 已停止");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setRelayBusy(false);
    }
  };

  const restartRelay = async () => {
    setRelayBusy(true);
    setStatus("");
    try {
      const payload = await api.restartModelRelay();
      setRelay(payload);
      setRelayPort(String(payload.port));
      setStatus(`本地 Relay 已重启：${payload.baseUrl}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setRelayBusy(false);
    }
  };

  const refreshRelayLogs = async () => {
    try {
      const payload = await api.modelRelayLogs();
      setRelayLogs(payload);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    }
  };

  const copyRelayBaseUrl = async () => {
    const baseUrl = relay?.baseUrl ?? `http://127.0.0.1:${relayPort || "17431"}`;
    try {
      await navigator.clipboard.writeText(baseUrl);
      setStatus(`已复制 Base URL：${baseUrl}`);
    } catch {
      setStatus(`Base URL：${baseUrl}`);
    }
  };

  const updateRouteForm = (patch: Partial<ModelRouteConfig>) => {
    setRouteForm((current) => ({ ...current, ...patch }));
  };

  const saveRoute = async () => {
    setSaving(true);
    setStatus("");
    try {
      const route = {
        ...routeForm,
        id: routeForm.id || `route-${routeForm.modelPattern.replace(/[^a-zA-Z0-9_-]/g, "-")}`,
      };
      const payload = await api.saveModelRoute({ route });
      setSnapshot(payload);
      setRouteForm({
        ...emptyRoute,
        providerId: payload.defaultProviderId || payload.providers[0]?.id || "",
      });
      setStatus("模型路由已保存");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  const deleteRoute = async (routeId: string) => {
    setSaving(true);
    setStatus("");
    try {
      const payload = await api.deleteModelRoute(routeId);
      setSnapshot(payload);
      setStatus("模型路由已删除");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  const fetchModels = async () => {
    const providerId = selectedProvider?.id || form.id;
    if (!providerId) {
      setStatus("请先选择或保存一个上游");
      return;
    }
    setFetchingModels(true);
    setStatus("");
    try {
      const payload = await api.listUpstreamModels(providerId);
      setModels(payload.models);
      setStatus(payload.ok ? `已从 ${payload.endpoint} 拉取 ${payload.models.length} 个模型` : payload.error ?? "拉取失败");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setFetchingModels(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-5 p-6">
      <PageHeader title="模型管理" />

      <section className="grid min-h-0 flex-1 grid-cols-[minmax(220px,280px)_minmax(0,1fr)] gap-4">
        <aside className="flex min-h-0 flex-col rounded-md border bg-card">
          <div className="flex items-center gap-2 border-b px-4 py-3">
            <ServerCog className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">上游 API</span>
          </div>
          <div className="min-h-0 flex-1 space-y-2 overflow-auto p-3">
            {snapshot?.providers.length ? (
              snapshot.providers.map((provider) => (
                <button
                  key={provider.id}
                  type="button"
                  onClick={() => selectProvider(provider.id)}
                  className="flex w-full flex-col gap-1 rounded-md border px-3 py-2 text-left transition-colors hover:bg-muted/70 data-[active=true]:border-primary data-[active=true]:bg-primary/10"
                  data-active={provider.id === selectedProviderId}
                >
                  <span className="flex items-center justify-between gap-2 text-sm font-medium">
                    {provider.name || provider.id}
                    {provider.id === snapshot.defaultProviderId ? <Badge variant="secondary">默认上游</Badge> : null}
                  </span>
                  <span className="truncate text-xs text-muted-foreground">{provider.baseUrl}</span>
                </button>
              ))
            ) : (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">还没有配置上游 API</div>
            )}
          </div>
        </aside>

        <main className="min-h-0 space-y-4 overflow-auto">
          <section className="rounded-md border bg-card p-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-3">
              <div className="flex items-center gap-2">
                <DatabaseZap className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">本地模型桶</span>
                <Badge variant={relay?.running ? "secondary" : "outline"}>
                  {relay?.running ? "运行中" : "未启动"}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" onClick={copyRelayBaseUrl}>
                  复制 Base URL
                </Button>
                <Button type="button" variant="outline" onClick={saveRelayConfig} disabled={relayBusy}>
                  保存 Token
                </Button>
                <Button type="button" onClick={startRelay} disabled={relayBusy}>
                  {relayBusy ? "处理中" : "启动模型桶"}
                </Button>
                <Button type="button" variant="outline" onClick={restartRelay} disabled={relayBusy || !relay?.running}>
                  重启
                </Button>
                <Button type="button" variant="outline" onClick={stopRelay} disabled={relayBusy || !relay?.running}>
                  停止
                </Button>
              </div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-[180px_minmax(0,1fr)]">
              <div className="space-y-2">
                <Label>固定端口</Label>
                <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm font-medium">{relayPort}</div>
                <div className="text-xs text-muted-foreground">端口由启动与修复统一管理，模型管理只使用这个本地桶。</div>
              </div>
              <div className="space-y-2">
                <Label>Base URL</Label>
                <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm font-medium">
                  {relay?.baseUrl ?? `http://127.0.0.1:${relayPort || "17431"}`}
                </div>
                <div className="text-xs text-muted-foreground">
                  Codex、Claude Code、Continue、Cursor 统一接这个 Base URL；provider 和路由由模型桶接管。
                </div>
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="relay-token">访问 Token</Label>
                <Input
                  id="relay-token"
                  type="password"
                  value={relayToken}
                  placeholder="留空表示仅本机端口保护"
                  onChange={(event) => setRelayToken(event.target.value)}
                />
              </div>
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium">请求日志</span>
                <Button type="button" variant="outline" size="sm" onClick={refreshRelayLogs}>
                  刷新日志
                </Button>
              </div>
              {relayLogs.length ? (
                <div className="max-h-40 space-y-2 overflow-auto">
                  {relayLogs
                    .slice()
                    .reverse()
                    .map((entry) => (
                      <div
                        key={`${entry.timestampMs}-${entry.method}-${entry.path}`}
                        className="grid gap-2 rounded-md border px-3 py-2 text-xs md:grid-cols-[80px_minmax(0,1fr)_80px_80px]"
                      >
                        <span className="font-medium">{entry.method}</span>
                        <span className="truncate">{entry.path}</span>
                        <span>{entry.status}</span>
                        <span className="text-muted-foreground">{entry.latencyMs}ms</span>
                      </div>
                    ))}
                </div>
              ) : (
                <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                  暂无请求。启动模型桶后，请求 /health、/v1/models 或 /v1/chat/completions 会出现在这里。
                </div>
              )}
            </div>
          </section>

          <section className="rounded-md border bg-card p-4">
            <div className="flex items-center justify-between gap-3 border-b pb-3">
              <div className="flex items-center gap-2">
                <ServerCog className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">模型路由</span>
              </div>
              <Button type="button" onClick={saveRoute} disabled={saving || !routeForm.modelPattern || !routeForm.providerId}>
                保存路由
              </Button>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1fr)_220px]">
              <div className="space-y-2">
                <Label htmlFor="route-pattern">模型匹配</Label>
                <Input
                  id="route-pattern"
                  value={routeForm.modelPattern}
                  placeholder="qwen-* / deepseek-chat / *"
                  onChange={(event) => updateRouteForm({ modelPattern: event.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>目标上游</Label>
                <Select value={routeForm.providerId} onValueChange={(providerId) => updateRouteForm({ providerId })}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择 provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {snapshot?.providers.map((provider) => (
                      <SelectItem key={provider.id} value={provider.id}>
                        {provider.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {snapshot?.modelRoutes?.length ? (
                snapshot.modelRoutes.map((route) => (
                  <div key={route.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <Badge variant={route.enabled ? "secondary" : "outline"}>{route.enabled ? "启用" : "停用"}</Badge>
                      <span className="font-medium">{route.modelPattern}</span>
                      <span className="text-muted-foreground">→ {route.providerId}</span>
                    </div>
                    <Button type="button" variant="outline" size="sm" onClick={() => deleteRoute(route.id)} disabled={saving}>
                      删除
                    </Button>
                  </div>
                ))
              ) : (
                <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                  尚未配置模型路由。未匹配时会使用默认上游。
                </div>
              )}
            </div>
          </section>

          <section className="rounded-md border bg-card p-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="provider-id">Provider ID</Label>
                <Input id="provider-id" value={form.id} onChange={(event) => updateForm({ id: event.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="provider-name">名称</Label>
                <Input id="provider-name" value={form.name} onChange={(event) => updateForm({ name: event.target.value })} />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="provider-base-url">Base URL</Label>
                <Input
                  id="provider-base-url"
                  value={form.baseUrl}
                  placeholder="https://api.example.com/v1"
                  onChange={(event) => updateForm({ baseUrl: event.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="provider-kind">协议类型</Label>
                <Select value={form.kind} onValueChange={(value) => updateForm({ kind: value as ModelProviderKind })}>
                  <SelectTrigger id="provider-kind">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="openai-compatible">OpenAI-compatible</SelectItem>
                    <SelectItem value="responses">Responses API</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="provider-default-model">默认模型</Label>
                <Input
                  id="provider-default-model"
                  value={form.defaultModel ?? ""}
                  onChange={(event) => updateForm({ defaultModel: event.target.value })}
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="provider-api-key">API Key</Label>
                <Input
                  id="provider-api-key"
                  type="password"
                  value={form.apiKey ?? ""}
                  onChange={(event) => updateForm({ apiKey: event.target.value })}
                />
              </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-sm">
                <Switch checked={form.enabled} onCheckedChange={(checked) => updateForm({ enabled: checked })} />
                启用这个上游
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" onClick={checkHealth} disabled={checking}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {checking ? "检查中" : "健康检查"}
                </Button>
                <Button type="button" variant="outline" onClick={fetchModels} disabled={fetchingModels}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {fetchingModels ? "拉取中" : "拉取模型"}
                </Button>
                <Button type="button" variant="outline" onClick={setDefaultProvider} disabled={saving || !selectedProvider}>
                  设为默认
                </Button>
                <Button type="button" variant="outline" onClick={deleteProvider} disabled={saving || !selectedProvider}>
                  删除上游
                </Button>
                <Button type="button" onClick={saveProvider} disabled={saving}>
                  <Save className="mr-2 h-4 w-4" />
                  {saving ? "保存中" : "保存上游"}
                </Button>
              </div>
            </div>
          </section>

          <section className="rounded-md border bg-card">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div className="flex items-center gap-2">
                <DatabaseZap className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">上游模型</span>
              </div>
              {snapshot?.configPath ? <span className="max-w-[50%] truncate text-xs text-muted-foreground">{snapshot.configPath}</span> : null}
            </div>
            <div className="space-y-2 p-4">
              {health ? (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <Badge variant={health.ok ? "secondary" : "destructive"}>
                      {health.ok ? "健康" : "异常"}
                    </Badge>
                    <span className="font-medium">{health.providerId}</span>
                  </div>
                  <span className="text-muted-foreground">
                    {health.modelCount} 个模型 · {health.latencyMs}ms
                  </span>
                </div>
              ) : null}
              {models.length ? (
                models.map((model) => (
                  <div key={model.id} className="flex items-center justify-between rounded-md border px-3 py-2">
                    <span className="text-sm font-medium">{model.id}</span>
                    {model.ownedBy ? <span className="text-xs text-muted-foreground">{model.ownedBy}</span> : null}
                  </div>
                ))
              ) : (
                <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">点击“拉取模型”检查上游 API。</div>
              )}
              {status ? <div className="text-sm text-muted-foreground">{status}</div> : null}
            </div>
          </section>
        </main>
      </section>
    </div>
  );
}
