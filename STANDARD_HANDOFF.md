# AI Strategist 新窗口标准工作移交手册

> 用途：开新窗口后，让接手会话直接从当前真实状态继续，不要重新从零分析。

## 0. 接手口令

新窗口请直接说：

```text
请先阅读 STANDARD_HANDOFF.md、HANDOFF.md、EXECUTION_PLAN.md、PRODUCTIZATION_CHECKLIST.md、AI_STRATEGIST_CLONE_HANDOFF.md，不要重新从零分析。按当前计划继续：维护 `启动与修复` 主流程，同时推进产品化改造；不要依赖 WindowsApps 默认 codex 入口，不要把环境幸运当成产品能力。
```

## 1. 项目基本信息

- 项目目录：`D:\我的空间\工作\pilot文件夹\AI-Strategist`
- 当前产品名：`AI Strategist`
- 当前主线页面：`启动与修复`
- 当前桌面应用目录：`ai-strategist-desktop/`
- 当前桌面产物：
  - `AI Strategist.exe`
  - `AI Strategist_1.0.0_x64-setup.exe`

## 2. 当前硬性要求

这些要求不能改、不能绕过：

1. **左侧不要有任何导航或任务入口。**
2. 所有模块入口都要放在顶部。
3. 当前页面名称叫 **启动与修复**。
4. 当前迁移的是旧工具里的“三种启动模式 + 修复功能模块”，不是把旧工具整体搬进来。
5. API / Hybrid 启动必须显式填写 provider，不允许静默回退旧配置。
6. 文档同步、UI 打磨、运行时产品化要分清阶段，不要混着乱改。
7. 不要把“当前开发机正好能跑”误当成“产品已经通用”。

## 3. 当前已经完成的事

### 3.1 产品与文档

已完成：

- `README.md` 已更新为当前产品说明。
- `HANDOFF.md` 已更新为当前 Tauri 主线与产品化主线交接。
- `EXECUTION_PLAN.md` 已更新为当前计划。
- `AI_STRATEGIST_CLONE_HANDOFF.md` 保持为历史来源说明。
- `PRODUCTIZATION_CHECKLIST.md` 已新增为产品化改造主清单。
- `V0_1_RELEASE_CHECKLIST.md` 仍保留 v0.1 发布门槛清单。

### 3.2 应用状态

已确认：

- Tauri 应用已改名为 `AI Strategist`。
- package name 是 `ai-strategist`。
- Tauri identifier 是 `dev.ai.strategist`。
- 主界面使用顶部导航。
- `启动与修复` 页面承接：
  - 官方账号启动
  - API 供应商启动
  - 混合模式启动
  - 修复功能
- API / Hybrid provider 输入已恢复。
- 旧桌面快捷方式 `legacy desktop shortcut` 已删除。
- 桌面仍存在新的 exe 和 setup 产物。

### 3.3 环境侧最近结论

已确认：

- 默认 `WindowsApps` `codex.exe` 入口不可直接执行。
- 用户级长期修复 shim 已建立：
  - `C:\Users\Administrator\AppData\Local\OpenAI\Codex\shim\codex.cmd`
- 直接可执行的本地 Codex CLI 副本存在于：
  - `C:\Users\Administrator\AppData\Local\OpenAI\Codex\bin\...\codex.exe`
- `git` 当前 shell 不可用。
- `codex-threadripper` 当前未发现。

## 4. 当前不能混淆的事

新窗口默认不要把下面几类问题混成一件事：

- 不要把“界面主线修复”混成“产品化已经完成”。
- 不要把“当前机器有 shim 可用”混成“安装包对别人已经通用”。
- 不要把“用户 PATH 正确”当成产品前提。
- 不要把“外部工具缺失”留给终端用户手工补环境。

## 5. 当前计划

### 计划 1：保持主流程稳定

继续保证：

- `启动与修复` 页稳定
- 三种启动模式稳定
- API / Hybrid 必须显式填写 provider
- 修复恢复链不退化
- 结果写入 `reports/`

### 计划 2：产品化改造执行

按 `PRODUCTIZATION_CHECKLIST.md` 推进：

- 运行时解析器
- 内部依赖分发
- 首启自检
- 降级策略
- 干净机器验收

### 计划 3：验证命令

当前已验证可用：

```powershell
pnpm --dir ai-strategist-desktop test prelaunch-page
pnpm --dir ai-strategist-desktop build
python -m unittest tests.test_prelaunch_bridge -v
cargo test --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml prelaunch
```

## 6. 关键文件索引

- `STANDARD_HANDOFF.md`
  - 当前这份标准工作移交手册。
- `HANDOFF.md`
  - 当前 Tauri 主线与产品化主线交接。
- `EXECUTION_PLAN.md`
  - 当前计划和阶段拆分。
- `PRODUCTIZATION_CHECKLIST.md`
  - 当前产品化改造清单。
- `AI_STRATEGIST_CLONE_HANDOFF.md`
  - 历史来源说明，不再作为当前产品目标。
- `V0_1_RELEASE_CHECKLIST.md`
  - 发布检查清单。
- `README.md`
  - 用户向说明。
- `ai-strategist-desktop/src/components/login-repair/login-repair-page.tsx`
  - 当前 `启动与修复` 页面。
- `ai-strategist-desktop/src-tauri/src/commands/prelaunch.rs`
  - Tauri 侧启动/修复命令桥接。
- `prelaunch_bridge.py`
  - Python 桥接入口。
- `prelaunch_manager.py`
  - provider 配置和证据采集辅助模块。
- `repair_codex_desktop_history.py`
  - 聊天恢复核心逻辑。

## 7. 当前状态一句话总结

当前项目已经从旧名称/旧壳说明收敛到 **AI Strategist**；主线是顶部导航下的 **启动与修复** 页面，承接三种启动模式和修复功能。同时，项目已经进入“产品化改造”阶段，目标是不再依赖开发机环境，而是走向可分发、可首启自检、可在干净机器上运行的桌面产品。
