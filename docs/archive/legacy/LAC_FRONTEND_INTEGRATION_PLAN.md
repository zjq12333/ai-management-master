# 已废弃：不要按本文继续实施

本文档位于旧的 `AI管理大师文件夹 / ai-strategist-desktop` 工作区，包含 `ai-strategist-desktop` 路径，已确认不应作为当前 LAC 前端接入依据。

后续 LAC 前端接入必须先确认真实前端仓库路径，例如 AionUi 本地 checkout；不得再根据本文档修改 `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop`。

---

# LAC 前端接入实施方案

## 0. 当前共识

本方案用于指导 **AI Strategist / AI 军师前端** 接入 **LAC 内核能力**。

当前阶段只讨论和推进 **只读接入**，不做大合并、不重构、不改变 LAC 路由策略。

核心判断：

- LAC 是内核 / 能力本体。
- AI 军师 / AI Strategist 是产品化前端和交互名称。
- 当前前端先承接 LAC 状态与自评能力。
- 另一条环境治理线继续处理 Codex 启动、登录、修复、provider 等问题。
- 本线重点是 LAC 前端接入，不混入环境治理实现。

## 1. 本轮目标

把 LAC 的只读自评结果接入 AI Strategist 前端，让前端可以展示 LAC 当前状态。

第一轮只接：

```text
GET /control/lac-control-space
```

不接写操作，不接高风险控制动作。

## 2. 页面承接位置

首版承接页：

```text
ai-strategist-desktop/src/components/overview/overview-page.tsx
```

也就是 **Overview / 仪表盘**。

原因：

- 不干扰当前主线页 `启动与修复`。
- LAC 状态属于总览信息，适合放在仪表盘。
- LAC 不在线时可以自然降级。
- 不会影响官方启动、API 启动、Hybrid 启动、修复恢复等主流程。

首版不建议接入：

```text
ai-strategist-desktop/src/components/login-repair/login-repair-page.tsx
```

原因：

- `启动与修复` 是当前稳定主线。
- 把 LAC 状态绑进主操作链会增加耦合。
- LAC 不在线不应该阻塞启动/修复。

## 3. 数据源映射

### 3.1 主数据源

```text
http://127.0.0.1:20128/control/lac-control-space
```

### 3.2 展示字段

前端首版展示摘要即可，不展示完整原始 JSON。

建议展示：

| 字段组 | 前端含义 |
| --- | --- |
| `availability` | LAC 是否可用、失败检查项 |
| `latency` | 最近请求数量、平均/最小/最大耗时 |
| `routing_quality` | 普通聊天策略、advisory、semantic router、cache lookup 状态 |
| `safety` | memory/router 是否进入普通聊天路径、cache write 是否开启 |
| `memory_quality` | memory backend、local cache 条目、memory candidates 数量 |
| `cost_control` | budget policy 是否开启、默认 profile、近期 profile 使用 |
| `execution_reliability` | 最近非 2xx 数量、最近状态码 |
| `gaps` | 当前已知缺口 |

## 4. 桥接方式

### 4.1 推荐链路

采用 Tauri 只读命令桥，而不是前端直接 fetch。

```text
React Overview
  -> api.lacControlSpaceStatus()
  -> Tauri invoke("lac_control_space_status")
  -> Rust reqwest GET http://127.0.0.1:20128/control/lac-control-space
  -> 返回结构化 JSON
```

### 4.2 选择 Tauri 桥的原因

- AI Strategist 当前项目习惯是通过 `invoke` 调用本地能力。
- 后续端口、路径、鉴权、启动方式变化时，只需要改 Rust 桥接层。
- 前端保持桌面应用的命令接口风格。
- 可以统一处理 LAC 不在线、超时、HTTP 错误等降级情况。

### 4.3 桥接要求

- 只读。
- 短超时，建议 1.5 秒到 2 秒。
- LAC 不可达时返回结构化错误，不让页面崩溃。
- 不修改 LAC 配置。
- 不修改 CLIProxyAPI 配置或 key。
- 不改变普通聊天默认直通 CLIProxyAPI 的行为。

### 4.4 返回结构

建议桥接返回：

```ts
{
  ok: boolean
  reachable: boolean
  endpoint: string
  status_code: number | null
  error: string | null
  snapshot: LacControlSpaceSnapshot | null
}
```

## 5. 最小改动文件清单

### 5.1 Tauri / Rust

```text
ai-strategist-desktop/src-tauri/src/commands/lac.rs
ai-strategist-desktop/src-tauri/src/commands/mod.rs
ai-strategist-desktop/src-tauri/src/lib.rs
```

用途：

- 新增 `lac_control_space_status` 只读命令。
- 注册 `lac` command module。
- 注册 Tauri invoke handler。

### 5.2 前端类型与 API

```text
ai-strategist-desktop/src/types/lac.ts
ai-strategist-desktop/src/lib/api.ts
```

用途：

- 定义 `LacControlSpaceSnapshot`。
- 定义 `LacControlSpaceStatusPayload`。
- 暴露 `api.lacControlSpaceStatus()`。

### 5.3 前端页面

```text
ai-strategist-desktop/src/components/overview/overview-page.tsx
```

用途：

- 使用 React Query 读取 LAC 状态。
- 显示只读摘要卡片。
- LAC 不可达时显示降级提示。

## 6. 前端展示建议

在 Overview 页添加一个独立卡片，例如：

```text
LAC 内核状态
```

卡片内容首版建议：

- 可达状态：在线 / 不可达
- health 状态：ok / warn / unknown
- 普通聊天策略：direct_relay / 其他
- 本地缓存读取：开 / 关
- relay-response 写入：开 / 关
- 最近请求数
- 平均耗时
- gaps 数量和前几个 gap

不建议首版展示：

- 完整 telemetry 原文
- 完整 prompt
- secrets
- 复杂配置编辑器
- 写操作按钮

## 7. 降级策略

如果 LAC 不在线：

前端显示：

```text
LAC 当前不可达
endpoint: http://127.0.0.1:20128/control/lac-control-space
error: <错误摘要>
```

并且：

- Overview 页面不崩溃。
- 顶部导航不受影响。
- `启动与修复` 页面不受影响。
- 其他模块不受影响。

## 8. 验证方案

### 8.1 前端测试

```powershell
rtk pnpm --dir ai-strategist-desktop test
```

需要验证：

- LAC 可达时，Overview 显示摘要。
- LAC 不可达时，Overview 显示降级状态。
- 现有 `启动与修复` 测试不受影响。

### 8.2 前端构建

```powershell
rtk pnpm --dir ai-strategist-desktop build
```

### 8.3 Rust / Tauri 测试

```powershell
rtk cargo test --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml
```

### 8.4 LAC 后端基线

在 LAC 项目中：

```powershell
rtk python scripts\check_lac_live.py
rtk python -m pytest -q
```

当前已知 LAC 基线：

```text
health check: 16/16 OK
pytest: 172 passed
```

## 9. 本轮明确不做

本轮不做以下事项：

- 不把 LAC 状态接入 `启动与修复` 主流程。
- 不新增 LAC 写操作按钮。
- 不改 LAC 路由策略。
- 不启用 semantic router 默认路径。
- 不启用 advisory context 默认路径。
- 不启用 relay-response cache writes。
- 不修改 CLIProxyAPI key/config/auth。
- 不把两个项目做大规模代码合并。
- 不重构 AI Strategist 页面结构。

## 10. 当前风险点

### 10.1 AI Strategist worktree 不干净

当前项目里已有大量未跟踪内容和历史改动。

处理原则：

- 不做 reset。
- 不做 clean。
- 不回滚用户已有改动。
- 本轮只改最小范围。

### 10.2 LAC 不应成为前端硬依赖

LAC 是内核能力，但当前接入必须可降级。

原则：

- LAC 在线：展示能力状态。
- LAC 离线：显示不可达。
- AI Strategist 仍可打开和执行环境治理能力。

### 10.3 当前接入口径仍需用户确认

本方案是第一版接入方案。继续实现前，应先确认：

1. 是否把首版展示放在 Overview。
2. 是否同意首版只读。
3. 是否同意走 Tauri command bridge。
4. 是否暂不接入 `启动与修复` 主流程。

## 11. 讨论顺序

后续按以下顺序逐步讨论：

1. **页面位置**：Overview 是否合适？
2. **桥接方式**：Tauri command bridge 是否合适？
3. **展示字段**：首版卡片显示哪些字段？
4. **降级策略**：LAC 不在线时怎么显示？
5. **验证标准**：哪些测试必须过？
6. **实施边界**：是否继续保持只读？
7. **下一阶段**：只读稳定后，哪些控制动作可以接？

## 12. 当前未完成事项

截至本文档创建时：

- 已有后端 LAC endpoint：`GET /control/lac-control-space`。
- 已开始草拟 Tauri 只读桥接文件。
- 尚未完成完整前端接入。
- 尚未完成最终测试。
- 继续实现前，应先按本文档和用户确认下一步。
