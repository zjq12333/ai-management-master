# AI管理大师

AI管理大师是一个面向本地 Codex Desktop 使用场景的小工具，当前第一阶段主要提供聊天记录搜索、恢复、隐藏聊天识别修复和图形界面操作。

当前版本按“安全恢复”设计：默认只恢复真实、可见、仍然有对应文件和工作区的聊天记录，不会把已删除工作区、空文件夹、归档会话或无用户消息的空线程重新塞回桌面端。

## 安全默认行为

默认会恢复：

- 有用户消息的会话；
- 未归档的会话；
- SQLite 中有对应 rollout/session 文件的会话；
- `cwd` 仍然存在的会话；
- `cwd` 存在且不是空文件夹的会话。

默认会跳过：

- 已归档会话；
- 被删除的工作区目录；
- 空工作区目录；
- 没有用户消息的空线程；
- 找不到 rollout/session 文件的线程。

工具不会删除你的聊天文件，也不会删除 rollout 文件。正式运行前会自动备份关键状态文件。

## 最简单用法

打开图形界面：

```text
Run-CodexMaintenanceGUI.cmd
```

如果你不想看到任何黑色命令行窗口，可以双击：

```text
Run-CodexMaintenanceGUI.vbs
```

GUI 会自动搜索常见 Codex 数据目录，并提供下拉选择和“找不到再点...”按钮。小白用户通常只需要：

1. 打开 GUI；
2. 确认顶部显示“有效 Codex 数据目录”；
3. 点击“搜索聊天记录”；
4. 确认可恢复数量；
5. 关闭 Codex Desktop；
6. 点击旁边的“恢复聊天记录”。

主界面默认是小白模式，不需要选择恢复规则。工具会在后端自动使用安全默认规则搜索：

- 不包含归档会话；
- 不包含已删除工作区；
- 不包含空工作区；
- 不包含缺失 session 的线程；
- 不包含无用户消息的空线程。

高级用户可以点“高级设置”，手动打开归档、已删除工作区、空工作区等恢复选项。每个勾选项旁边都有说明，会写清楚打开后会发生什么。

GUI 左侧已经预留这些功能入口：

- 历史恢复：当前已实现，主按钮是“搜索聊天记录”；
- 历史诊断：预留；
- 脏数据清理：预留；
- 聊天导出：预留；
- 备份恢复：预留。

## GUI 设计

GUI 是一个轻量壳，不重写底层修复逻辑。它只负责：

- 自动检测和校验 Codex Home；
- 展示安全恢复选项；
- 调用 `repair_codex_desktop_history.py`；
- 展示 dry-run 摘要和日志；
- 为后续诊断、清理、导出、备份恢复功能预留入口。

路径检测会检查目录里是否存在：

- `state_5.sqlite`
- `.codex-global-state.json`

缺少任意一个都会显示为无效目录，并阻止修复。

## 命令行用法

预览，不写入任何文件：

```text
Preview-CodexDesktopHistoryRepair.cmd
```

正式修复：

```text
Run-CodexDesktopHistoryRepair.cmd
```

正式修复时脚本会提示你先关闭 Codex Desktop，然后按 Enter 继续。它不会强制杀掉 `Codex` 或 `codex` 进程，避免误关正在工作的 CLI/API 会话。

## PowerShell 用法

在仓库目录运行：

```powershell
.\Repair-CodexDesktopHistory.ps1 -DryRun
```

正式修复：

```powershell
.\Repair-CodexDesktopHistory.ps1
```

同时尝试修复隐藏聊天识别：

```powershell
.\Repair-CodexDesktopHistory.ps1 -SyncProvider
```

`-SyncProvider` 只会调用本机已有的 `codex-threadripper`。如果没有安装，它会跳过，不会自动联网安装。

允许脚本安装 `codex-threadripper`：

```powershell
.\Repair-CodexDesktopHistory.ps1 -SyncProvider -InstallThreadripper
```

## 高级开关

默认不建议打开这些开关，除非你明确知道自己要恢复什么。

```powershell
# 包含已归档会话，但不改变归档标记
.\Repair-CodexDesktopHistory.ps1 -IncludeArchived

# 包含已归档会话，并只取消这些被选中会话的归档标记
.\Repair-CodexDesktopHistory.ps1 -IncludeArchived -UnarchiveSelected

# 允许恢复 cwd 已不存在的会话
.\Repair-CodexDesktopHistory.ps1 -AllowMissingCwd

# 允许恢复 cwd 存在但为空的会话
.\Repair-CodexDesktopHistory.ps1 -AllowEmptyCwd

# 允许恢复找不到 rollout/session 文件的会话
.\Repair-CodexDesktopHistory.ps1 -AllowMissingSession

# 不运行 provider 状态检查或同步
.\Repair-CodexDesktopHistory.ps1 -NoProviderSync
```

Projectless 桶控制：

```powershell
.\Repair-CodexDesktopHistory.ps1 -ProjectlessMode none
.\Repair-CodexDesktopHistory.ps1 -ProjectlessMode current-only
.\Repair-CodexDesktopHistory.ps1 -ProjectlessMode all
```

默认是 `none`，也就是不把恢复出来的线程额外放入 projectless 区域，尽量只按原始工作区归类。

## 修复隐藏聊天识别说明

本工具不硬编码 `codexzh`、`OpenAI` 或任何固定 provider。

正常情况下不用打开这个功能。工具本身会搜索所有来源的聊天记录。

只有在“搜索和恢复都做了，但桌面端仍然看不到聊天”时，再尝试打开它。它的作用是把旧聊天里残留的模型来源标记，修正成当前 Codex Desktop 更容易识别的形式，但不会修改聊天内容。

如果你使用 `-SyncProvider`，脚本只负责调用：

```powershell
codex-threadripper --codex-home <你的 .codex 路径> sync
```

实际同步到哪个 provider，由你本机当前 Codex 配置和 `codex-threadripper` 决定。

## 备份和报告

正式修复会在：

```text
%USERPROFILE%\.codex\desktop_history_repair_backups\<时间戳>\
```

备份这些文件：

- `state_5.sqlite`
- `state_5.sqlite-wal`
- `state_5.sqlite-shm`
- `.codex-global-state.json`
- `session_index.jsonl`

同一目录下还会生成：

```text
repair-report.json
```

报告里包含本次选中的会话数量、跳过原因、provider 分布和跳过样例。

## 文件说明

- `CodexMaintenanceGUI.py`：图形界面壳和功能导航。
- `Run-CodexMaintenanceGUI.cmd`：双击打开 GUI。
- `Run-CodexMaintenanceGUI.vbs`：无黑色命令行窗口的 GUI 启动入口。
- `repair_codex_desktop_history.py`：核心修复逻辑。
- `Repair-CodexDesktopHistory.ps1`：PowerShell 启动器和参数入口。
- `Preview-CodexDesktopHistoryRepair.cmd`：双击预览。
- `Run-CodexDesktopHistoryRepair.cmd`：双击正式修复。
