# AI Strategist

AI Strategist 是面向本地 Codex Desktop 的桌面启动与修复工具。当前主界面采用 Tauri 版本，核心入口叫 **启动与修复**。

它当前的主线目标有两层：

- 把 Codex 的启动、检查、修复集中到一个稳定桌面界面里；
- 把现有工具从“依赖开发机环境的脚本集合”收敛成“别人下载就能用的桌面产品”。

## 当前产品形态

- 应用名：`AI Strategist`
- 主功能页：`启动与修复`
- 导航方式：顶部功能导航；左侧不放导航内容
- 当前桌面产物：
  - `AI Strategist.exe`
  - `AI Strategist_1.0.0_x64-setup.exe`

## 启动与修复包含的能力

### 三种启动模式

1. **官方账号启动**
   - 使用 Codex Desktop 官方登录态启动。
   - 目标是插件可用、聊天可见。

2. **API 供应商启动**
   - 使用 API provider / relay / proxy 通道启动。
   - 目标是模型请求走指定 provider，并让聊天记录对齐到对应 provider 桶。
   - 当前要求：必须显式填写 provider 信息，不再静默回退旧配置。

3. **混合模式启动**
   - 保留官方登录态，同时使用 relay/API 通道。
   - 目标是插件可用，同时模型请求走中转通道。
   - 当前要求：必须显式填写 hybrid 所需 provider 信息，不再静默回退旧配置。

### 修复能力

- 检查 `config.toml` 当前 `model_provider`
- 检查 `codex-threadripper status` 的目标 provider 和待对齐数量
- 统计 `state_5.sqlite` 中线程 provider 分布
- 在用户触发修复时，对隐藏聊天/错桶聊天执行对齐
- 保存运行证据到 `reports/`，便于回看和排查

## 推荐使用方式

优先使用桌面上的 Tauri 版本：

```text
AI Strategist.exe
```

进入应用后：

1. 打开顶部导航里的 `启动与修复`
2. 查看当前状态卡片：登录状态、模型通道、聊天桶状态、插件可用性
3. 如果使用 API / Hybrid，先填写本次 provider 信息
4. 选择启动方式：
   - `官方账号启动`
   - `API 供应商启动`
   - `混合模式启动`
5. 如提示 Codex 正在运行，先关闭 Codex Desktop / codex CLI，再继续
6. 启动或修复完成后，查看页面结果和 `reports/` 中的证据文件

## 产品化方向

当前仓库已经明确：后续不能继续依赖“用户机器刚好已经配置正确”的环境。

产品化改造原则：

- 不依赖用户自己的 `PATH`
- 不依赖 `WindowsApps` 里的默认 `codex.exe`
- 不假设用户已安装 Python / Git / threadripper
- 主流程必须自带运行时、自带依赖、自检并可降级

对应文档见：

- 文档地图：`docs/README.md`
- 产品化检查：`docs/plans/PRODUCTIZATION_CHECKLIST.md`
- 当前执行计划：`docs/plans/EXECUTION_PLAN.md`
- v0.1 发布检查：`docs/release/V0_1_RELEASE_CHECKLIST.md`

本地统一验证：

```powershell
.\Verify-AI-Strategist.ps1
```

## 旧 Tkinter 入口

旧的 Python/Tkinter 工具仍保留为参考和回退入口：

```text
Run-CodexMaintenanceGUI.vbs
```

后续主线以 Tauri 桌面应用为准；Tkinter 入口不再作为主要产品界面继续扩展。

## 适合处理的问题

- 切换 API 供应商后，历史聊天突然不见了
- 官方账号能看到聊天，但非官方通道看不到
- 想在启动 Codex 前先确认 provider、聊天桶和插件状态
- 想把启动、检查、修复证据集中在一个桌面界面里完成

## 当前功能范围

目前已经可用：

- 顶部功能导航；无左侧导航
- `启动与修复` 页面
- 官方 / API / 混合三种启动模式
- API / Hybrid provider 显式输入与校验
- 启动前状态检查
- 真实修复入口
- Codex 运行中拦截提示
- 运行结果卡片
- 桌面 exe 与安装包产物

暂时保留但后续再评估的模块：

- 概览
- 自定义指令
- MCP
- Skills
- 维护
- 设置

这些模块不是当前主线，当前主线只要求 `启动与修复` 能稳定承接三种启动模式和修复能力。 
