# AI Strategist 交接文件

> Archive note: this file is preserved as historical context. Use `README.md`
> and `docs/README.md` as the current documentation entry points.

## 项目位置

- 本地目录：`D:\我的空间\工作\pilot文件夹\AI-Strategist`
- GitHub：`https://github.com/zjq12333/ai-management-master`
- 当前分支：`main`
- 当前桌面应用目录：`ai-strategist-desktop/`

## 当前目标

把现有工具收敛成 **AI Strategist** 的桌面应用，其中当前主线页面叫 **启动与修复**。

当前目标已经不是单纯“把旧工具迁到新壳”，而是双主线并行：

1. 让 `启动与修复` 主流程稳定可用。
2. 把项目改造成“别人下载就能用”的桌面产品，而不是依赖开发机环境的工具集合。

核心流程：

1. 用户打开 AI Strategist。
2. 顶部导航进入 `启动与修复`。
3. 用户选择三种启动模式之一：
   - 官方账号启动
   - API 供应商启动
   - 混合模式启动
4. 如果是 API / Hybrid，用户必须先填写本次 provider 信息。
5. 工具检查当前登录态、模型通道、threadripper 目标和聊天 provider 分布。
6. 工具按用户动作执行启动或修复。
7. 工具输出页面结果，并把证据保存在 `reports/`。

## 当前 UI 原则

- 左侧不要放任何导航或任务入口。
- 所有主要模块入口放在顶部导航。
- `启动与修复` 是三种启动模式和修复能力的承载页。
- 其他模块暂时保留，后续再决定是否继续使用。
- 当前不是把旧项目整体搬入新壳，而是把“启动与修复”功能模块迁移到现有 Tauri 应用里。

## 当前状态（2026-05-24）

- Tauri 应用已改名为 `AI Strategist`。
- 包名：`ai-strategist`。
- Tauri productName：`AI Strategist`。
- Tauri identifier：`dev.ai.strategist`。
- 主界面已使用顶部功能导航。
- `启动与修复` 页面已承接：
  - 官方启动
  - API 启动
  - 混合启动
  - 真实修复
  - Codex 运行中拦截提示
  - 运行结果展示
- API / Hybrid 已恢复 provider 显式输入，不再静默吃旧配置。
- 桌面已存在产物：
  - `AI Strategist.exe`
  - `AI Strategist_1.0.0_x64-setup.exe`
- 旧桌面快捷方式 `legacy desktop shortcut` 已删除。

## 已完成

- 新 Tauri shell 可构建并打包。
- 应用品牌从旧名称同步为 `AI Strategist`。
- 主导航迁移到顶部；左侧无导航。
- `启动与修复` 作为当前主线页面。
- 三种启动模式迁入当前页面。
- 修复功能迁入当前页面。
- API / Hybrid provider 输入与桥接链已恢复。
- 保留概览、自定义指令、MCP、Skills、维护、设置等其他模块，暂不删除。
- 已完成发布前源码路径旧品牌扫描：`ai-strategist-desktop/src`、`src-tauri/src`、capabilities、gen、package/config/lock 等路径无旧品牌命中。
- 已确认默认 `WindowsApps` `codex` 入口不可用，本机已加长期 shim 绕过。

## 当前关键风险

1. 产品仍有外部环境依赖残留。
   - `git` 当前机器不可用。
   - `codex-threadripper` 当前机器未发现。
   - `apply_patch` 默认链路仍受 `WindowsApps` 入口限制。
2. 运行时和辅助工具还未正式产品内置。
3. 首启自检、自动修复、运行时分发还未完成。

## 关键文件

- `ai-strategist-desktop/src/main-app.tsx`
  - Tauri 主应用布局；顶部导航挂载点。
- `ai-strategist-desktop/src/components/layout/sidebar.tsx`
  - 当前导出 `TopFeatureNav`；文件名仍是历史名称，但实际渲染顶部导航。
- `ai-strategist-desktop/src/components/login-repair/login-repair-page.tsx`
  - 当前 `启动与修复` 页面。
- `ai-strategist-desktop/src-tauri/src/commands/prelaunch.rs`
  - Tauri 侧启动/修复命令桥接。
- `prelaunch_bridge.py`
  - Python 桥接入口。
- `prelaunch_manager.py`
  - provider 配置与证据采集辅助模块。
- `repair_codex_desktop_history.py`
  - 聊天恢复核心逻辑。
- `tests/test_prelaunch_bridge.py`
  - Python 桥接测试。
- `docs/plans/PRODUCTIZATION_CHECKLIST.md`
  - 桌面产品化改造清单。

## 验证命令

当前已验证可用：

```powershell
pnpm --dir ai-strategist-desktop test prelaunch-page
pnpm --dir ai-strategist-desktop build
python -m unittest tests.test_prelaunch_bridge -v
cargo test --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml prelaunch
```

## 当前文档同步状态

- `README.md` 已更新为当前产品说明。
- Historical handoff files now live under `docs/archive/handoffs/`.
- `docs/README.md` is the current documentation map.
- `docs/plans/EXECUTION_PLAN.md` describes the current active plan.
- `docs/plans/PRODUCTIZATION_CHECKLIST.md` is the productization checklist.

## 下一步建议

1. 把产品化改造清单拆成可执行任务，而不是继续零散修环境。
2. 优先做运行时解析器、内部依赖分发、首启自检。
3. 再决定哪些能力必须内置，哪些能力允许降级。
4. 发布前验证必须在干净机器上跑，不再只在当前开发机验证。

## 新窗口接力口令

This file is archived. For new work, start from `README.md`, `docs/README.md`,
`docs/plans/EXECUTION_PLAN.md`, and `docs/plans/PRODUCTIZATION_CHECKLIST.md`.
