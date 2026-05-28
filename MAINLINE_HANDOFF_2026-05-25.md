# AI Strategist 主线项目移交

更新时间：2026-05-25  
项目目录：`D:\我的空间\工作\pilot文件夹\AI-Strategist`

## 给接手人的简单话

这个项目现在的主线不是“按模型厂商或 provider 桶去对齐聊天”，而是做一个本地桌面工具：用户打开 **AI Strategist**，进入 **启动与修复**，不管模型叫什么、属于哪家厂商，工具都尽量把聊天记录恢复到它本来应该待的 workspace/session 位置。

`codex-threadripper` 现在只应被理解为兼容性诊断工具，不是聊天归属的主规则。真正的恢复主线在 `repair_codex_desktop_history.py`：根据 Codex Desktop 的历史、cwd、session 文件、全局 state 和 session index 来恢复聊天。

下一位接手人请先看这份文件，再看：

- `PRODUCTIZATION_CHECKLIST.md`
- `V0_1_RELEASE_CHECKLIST.md`
- `EXECUTION_PLAN.md`
- `RUNTIME_BUNDLING_PLAN.md`
- `README.md`

不要从零重新判断产品方向；当前方向已经明确。

## 项目一句话

**AI Strategist** 是一个面向本地 Codex Desktop 的 Tauri 桌面应用，当前核心能力是 **启动与修复**：检查 Codex 状态、选择启动模式、执行聊天恢复、记录证据报告，并逐步产品化为“下载就能用”的 Windows 桌面产品。

## 当前产品定位

目标用户：

- 使用 Codex Desktop / codex CLI 的本地用户
- 遇到聊天记录不可见、workspace 归属错误、session index 丢失、官方/API/Hybrid 启动状态不清楚的用户
- 不希望手工理解 `.codex`、SQLite、provider、session 文件和 runtime PATH 的非工程用户

当前重点：

- 不是做完整 AI 管理平台
- 不是重写 Codex Desktop
- 不是把旧 Tkinter 工具整体搬进新壳
- 是把“启动、检查、修复、证据报告”收敛成一个稳定桌面工作流

## 技术栈与目录

主要技术：

- 桌面壳：Tauri 2
- 前端：React 18、TypeScript、Vite、Tailwind、Radix UI、TanStack Query
- 桥接层：Rust Tauri command 调 Python bridge
- 修复逻辑：Python 操作 Codex Desktop 本地文件和 SQLite
- 测试：Vitest、pytest、cargo test

关键目录和文件：

- `ai-strategist-desktop/`
  - Tauri + React 桌面应用
- `ai-strategist-desktop/src/components/login-repair/login-repair-page.tsx`
  - 当前主线页面：启动与修复
- `ai-strategist-desktop/src/lib/api.ts`
  - 前端调用 Tauri command 的 API 层
- `ai-strategist-desktop/src/types/prelaunch.ts`
  - 启动/修复相关 TS 类型
- `ai-strategist-desktop/src-tauri/src/commands/prelaunch.rs`
  - Tauri 侧启动/修复命令桥
- `ai-strategist-desktop/src-tauri/src/platform/runtime_resolver.rs`
  - runtime / helper binary 解析器雏形
- `prelaunch_bridge.py`
  - Python bridge CLI，负责启动前流程编排
- `prelaunch_manager.py`
  - provider 配置、状态采集、Codex 进程检查、threadripper 状态读取等辅助逻辑
- `repair_codex_desktop_history.py`
  - 聊天恢复核心逻辑
- `tests/test_prelaunch_bridge.py`
  - Python bridge 和恢复策略测试
- `reports/`
  - 每次启动/修复的运行证据输出目录

## 当前主流程

用户进入桌面应用后，主线页面是 **启动与修复**。

页面包含：

- 官方账号启动
- API 供应商启动
- 混合登录
- 修复恢复
- 高级恢复选项
- 当前状态卡片
- 最近一次执行结果
- 归属分析摘要

当前流程：

1. 读取启动前状态：
   - auth mode
   - config model_provider
   - provider distribution
   - threadripper status 里的兼容差异行数
2. 用户选择启动或修复。
3. 如果 Codex Desktop / codex CLI 正在运行，先拦截并提示关闭。
4. API / Hybrid 启动必须显式填写 provider 信息，不允许静默复用旧配置。
5. 修复前会备份相关文件。
6. 修复后写入 session index / state，并输出 `reports/` 证据。
7. UI 展示恢复线程数、恢复 workspace 数、跳过线程数、主要 workspace、主要跳过原因。

## 已完成

### 1. 产品主线收敛

- 应用名称已统一为 `AI Strategist`
- Tauri `productName` 是 `AI Strategist`
- package name 是 `ai-strategist`
- Tauri identifier 是 `dev.ai.strategist`
- 当前主线页面叫 `启动与修复`
- 左侧导航已移除，主导航在顶部
- 旧 Tkinter 工具保留为参考/回退，不再作为主线扩展对象

### 2. 启动与修复 UI

- 已有官方/API/混合三种启动卡片
- 已有修复恢复卡片
- 已有 Codex 运行中拦截弹窗
- 已有 provider 输入表单
- API / Hybrid 已要求显式 provider 输入
- 已有隐藏官方额度提醒开关
- 已有结果卡片和归属分析摘要
- 已有高级恢复开关：
  - 包含归档聊天
  - 允许缺失 cwd
  - 允许空 workspace
  - 允许缺失 session
  - 恢复到 projectless
  - 取消归档选中聊天

### 3. 恢复逻辑

- `repair_codex_desktop_history.py` 已支持按 workspace/session 归属恢复
- 修复结果包含 `thread_attributions`
- 归属逻辑已覆盖：
  - 同 provider 跨 workspace 不能混在一起
  - 同 workspace 下不同 provider 可以一起归属到该 workspace
  - 默认跳过 archived/deleted/空 workspace/缺失 session 等不安全记录
  - 高级恢复可放宽筛选策略
- 支持 `projectless-mode`
- 支持 `unarchive-selected`
- 支持备份后再修改

### 4. provider / threadripper 定位调整

- `prelaunch_bridge.py` 的启动流程已经调整为：
  1. repair history
  2. configure provider
  3. provider compatibility check
  4. launch
- `codex-threadripper sync` 不再作为自动主线动作
- threadripper 当前只做兼容性检查
- UI 文案从“待同步行数”调整为“兼容差异行数”
- 这符合产品思路：聊天要回到该待的 workspace/session，不是按模型名或厂商来决定归属

### 5. runtime resolver 初步接入

- `runtime_resolver.rs` 已存在
- Tauri prelaunch command 已通过 resolver 解析 Python runtime
- Tauri prelaunch command 会解析 `codex-threadripper.exe` / `codex-threadripper`
- 解析到 threadripper 后，通过 `AI_STRATEGIST_THREADRIPPER` 注入 Python bridge
- Python `prelaunch_manager.threadripper_command()` 优先使用该环境变量

### 6. 测试与验证

最近一次完整验证结果：

```powershell
python -m pytest -q
# 29 passed, 3 subtests passed

pnpm test
# 18 passed

pnpm build
# passed

cargo test commands::prelaunch
# 4 passed

cargo test
# 9 passed
```

构建提示：

- Vite 有一个关于 `@tauri-apps/api/core` 动态导入分块的提示，不是失败。
- Rust 目前有若干既有 unused warnings，不是本次高级恢复引入的阻塞问题。

## 还没完成

### 1. 产品化还没完成

这是最大缺口。当前开发机能跑，不等于用户下载安装就能跑。

未完成项来自 `PRODUCTIZATION_CHECKLIST.md`：

- 还没有完成“单一内部 runtime resolver”覆盖所有主线调用
- 还没有停止所有 bare command 调用
- 还没有 bundle / product-manage Codex CLI
- 还没有 bundle Python runtime 或把 Python bridge 打包成不依赖系统 Python 的形式
- 还没有明确 `codex-threadripper` 是必需还是可降级
- 还没有干净 Windows 机器验收
- 还没有稳定 diagnostics bundle 导出
- 还没有完整 first-run repair 流程

### 2. runtime 解析仍只是雏形

已有：

- Python resolver
- Codex CLI resolver
- helper binary resolver
- Codex Desktop exe resolver

但还没全部接入：

- 有些模块可能仍然通过 PATH 或默认命令名找工具
- diagnostics 里还没完整展示每个 runtime 实际来自哪里
- installer 里还没真正带上这些 runtime

### 3. Git 环境刚修了一部分

本机 Git 安装在：

```text
D:\Git\cmd\git.exe
```

已经把 `D:\Git\cmd` 加到当前 Windows 用户 Path。新开的 PowerShell / Codex 应该能直接运行 `git`，旧会话可能仍需重启。

注意：当前 repo 有大量已有改动和未跟踪文件，不要误删。

当前 `git status --short` 曾显示：

```text
 M CodexMaintenanceGUI.py
 M README.md
 M repair_codex_desktop_history.py
?? ai-strategist-desktop/
?? prelaunch_bridge.py
?? prelaunch_manager.py
?? tests/
?? reports/
...
```

说明很多当前主线文件在 Git 看来仍是未跟踪。接手人要先整理 `.gitignore`、确认哪些文件应该纳入版本，再考虑提交。

### 4. v0.1 发布门槛未全部满足

`V0_1_RELEASE_CHECKLIST.md` 已经标出关键延期项：

- binary 还不是完全环境独立
- mainline workflow 还未彻底摆脱用户 PATH
- mainline workflow 还未彻底摆脱 `WindowsApps` 默认 `codex.exe`
- mainline workflow 还不能保证不需要用户预装 Python/Git/helper tools
- clean-machine install acceptance 未完成

### 5. 非主线模块还没最终裁剪

当前仍保留：

- 概览
- AI 管理
- 维护
- 设置

旧文档里提到的 MCP、Skills、自定义指令等模块是否继续保留，需要另行判断。当前主线不要被这些模块牵走。

## 后续计划

### 第一优先级：巩固恢复主线

目标：确保“恢复到该待的地方”稳定，而不是回到 provider 桶思路。

建议动作：

1. 为高级恢复增加更多真实样本测试：
   - archived + unarchive
   - missing cwd
   - empty cwd
   - missing session
   - projectless all / current-only / none
2. 增加端到端样本 fixture：
   - SQLite threads
   - `.codex-global-state.json`
   - `session_index.jsonl`
3. 对恢复结果生成更清晰的用户报告：
   - 哪些恢复到 workspace
   - 哪些放到 projectless
   - 哪些跳过
   - 为什么跳过

### 第二优先级：runtime 产品化

按 `PRODUCTIZATION_CHECKLIST.md` 和 `RUNTIME_BUNDLING_PLAN.md` 做。

执行顺序：

1. 盘点所有 bare command 调用
2. 把 Codex CLI / Codex Desktop / Python / helper binary 都走 `runtime_resolver.rs`
3. 给 resolver 返回结构加 diagnostics 字段
4. UI 或 diagnostics 页面展示 runtime 来源
5. 明确 `codex-threadripper`：
   - 如果主线需要，就打包
   - 如果只是诊断，就缺失时降级，不影响修复承诺
6. 设计 product-managed runtime 目录
7. Installer 集成 runtime

### 第三优先级：首启自检与修复

目标：用户第一次打开时，不应该看到开发者错误。

首启检查应覆盖：

- Codex Desktop 是否安装
- Codex CLI 是否可用
- Python bridge runtime 是否可用
- `.codex` 是否存在
- `config.toml` / `auth.json` / `state_5.sqlite` 是否可读
- 是否能写 reports 和 backup
- helper tools 是否可用或降级

UI 只给三种结果：

- ready
- repaired automatically
- blocked with explicit next action

### 第四优先级：发布验收

发布前必须做：

1. 干净 Windows 机器安装
2. 不预装 Python / Node / Rust / Git
3. 打开 `AI Strategist.exe`
4. 进入 `启动与修复`
5. 跑官方/API/Hybrid/修复四条路径
6. 确认每条路径都有报告
7. 确认失败时能导出诊断

## 接手时不要做的事

- 不要把 `codex-threadripper sync` 重新放回自动主线
- 不要按 provider/model 名决定聊天最终归属
- 不要假设用户电脑有 Python、Git、Node、Rust
- 不要把当前开发机测试通过当成发布完成
- 不要删除未跟踪文件，除非先确认它不是当前主线文件
- 不要把 `ai-strategist-desktop/src/components/layout/sidebar.tsx` 误判为左侧导航；它现在实际导出顶部导航 `TopFeatureNav`

## 推荐接手命令

进入项目：

```powershell
cd "D:\我的空间\工作\pilot文件夹\AI-Strategist"
```

检查 Git：

```powershell
git --version
git status --short
```

如果 `git` 仍不可用，用绝对路径：

```powershell
& "D:\Git\cmd\git.exe" status --short
```

验证主线：

```powershell
python -m pytest -q
pnpm --dir ai-strategist-desktop test
pnpm --dir ai-strategist-desktop build
cargo test --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml
```

## 当前工作状态总结

项目现在已经完成了从“旧脚本/旧壳思路”到 “AI Strategist 启动与修复主线” 的关键转向。当前最重要的业务判断是：

**聊天恢复的主规则是 workspace/session 归属，不是 provider 桶。**

现阶段已经能在开发环境里跑通 UI、Python bridge、Rust command 和测试。但它还不是一个真正可广泛分发的成品，因为 runtime、helper、首启自检、干净机器验收还没完成。

下一步应该继续做产品化，不要再回头纠缠模型名字或厂商桶。
