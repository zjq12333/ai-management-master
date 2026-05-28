<p align="center">
  <img src="assets/app-icon-composed.png" alt="AI Strategist" width="128" height="128" />
</p>

<h1 align="center">AI Strategist Desktop</h1>

<p align="center">
  面向本地 Codex Desktop 的启动与修复桌面壳。当前主线是 <b>启动与修复</b>，不是早期的账号轮换或会话树产品线。
</p>

<p align="center">
  <a href="README-en.md">English</a> | <b>简体中文</b>
</p>

## 当前定位

`ai-strategist-desktop/` 是 AI Strategist 的 Tauri 前端工程。它负责把本地 Codex Desktop 的启动、检查、修复证据集中到一个稳定桌面界面里。

当前主线目标：

- 保持 `启动与修复` 工作流稳定。
- 支持官方账号、API 通道、混合模式三种启动路径。
- 在启动前展示 provider、聊天桶、插件和运行状态证据。
- 将 Python 桥接脚本和 Tauri 命令桥接逐步产品化，减少对开发机环境的依赖。

暂不作为当前主线扩展：

- 多账号轮换。
- 会话树管理。
- 智能模型路由。
- 大而全的 Codex 管理台。

这些方向可以作为历史参考或未来候选，但不能覆盖当前 `启动与修复` 主线。

## 常用命令

从仓库根目录运行完整验证：

```powershell
.\Verify-AI-Strategist.ps1
```

桌面端单独运行：

```powershell
pnpm --dir ai-strategist-desktop dev
pnpm --dir ai-strategist-desktop build
pnpm --dir ai-strategist-desktop test
pnpm --dir ai-strategist-desktop tauri dev
```

Tauri/Rust 侧测试：

```powershell
cargo test --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml
```

Python 桥接测试在仓库根目录执行：

```powershell
python -m pytest
```

## 关键目录

- `src/main-app.tsx`: 当前桌面主界面挂载。
- `src/components/login-repair/`: `启动与修复` 页面。
- `src/components/enhancer/`: handoff 和增强器相关前端辅助逻辑。
- `src-tauri/src/commands/`: Tauri 命令桥接。
- `src-tauri/resources/`: 桌面端运行时资源。

## 文档入口

- 根项目说明：`../README.md`
- 文档地图：`../docs/README.md`
- 当前执行计划：`../docs/plans/EXECUTION_PLAN.md`
- 产品化检查：`../docs/plans/PRODUCTIZATION_CHECKLIST.md`
- 发布检查：`../docs/release/V0_1_RELEASE_CHECKLIST.md`
