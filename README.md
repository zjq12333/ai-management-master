# Codex Desktop 历史记录修复工具

这是一个给 **Codex Desktop 左侧历史记录不可见、会话被隐藏、工作区位置错乱** 准备的一键修复工具。

它适合这样的情况：

- Codex Desktop 左侧看不到以前的对话；
- 会话还在本机 `.codex` 目录里，但桌面端不显示；
- 切换过模型渠道或 `model_provider` 后，历史记录消失；
- 一些没有实际对话的空文件夹被错误导入到左侧工作区列表。

本工具不会删除你的对话文件，也不会删除 rollout 记录。

## 最简单用法：双击运行

从 GitHub 下载本仓库后：

1. 解压到任意文件夹；
2. 双击 `Run-CodexDesktopHistoryRepair.cmd`；
3. 看到提示后按 `Y` 确认运行。

运行过程中，Codex Desktop 可能会被关闭并重新打开，这是正常现象。因为桌面端打开时可能会把内存里的旧状态写回文件，所以正式修复前需要先关闭它。

如果你只想先看看会修复什么，不想真正写入文件，可以双击：

```text
Preview-CodexDesktopHistoryRepair.cmd
```

预览模式不会关闭 Codex，也不会修改任何文件。

## 文件说明

- `Run-CodexDesktopHistoryRepair.cmd`：双击运行的正式修复入口。
- `Preview-CodexDesktopHistoryRepair.cmd`：双击运行的预览入口。
- `Repair-CodexDesktopHistory.ps1`：PowerShell 主启动脚本。
- `repair_codex_desktop_history.py`：实际修复 Codex Desktop 状态和 SQLite 数据的核心脚本。

## 它会做什么

正式修复时，工具会：

1. 检查并尽量安装 `codex-threadripper`；
2. 执行 `codex-threadripper --codex-home <home> sync`，把历史线程同步到当前配置的模型渠道桶；
3. 关闭 Codex Desktop；
4. 备份关键状态文件：
   - `%USERPROFILE%\.codex\state_5.sqlite`
   - `%USERPROFILE%\.codex\.codex-global-state.json`
5. 取消隐藏被归档的线程；
6. 恢复每条对话原本所在的工作区位置；
7. 跳过没有用户对话的空线程，避免把“暂无对话”的文件夹导入左侧工作区列表；
8. 重新打开 Codex Desktop。

## PowerShell 用法

如果你更喜欢命令行，也可以在仓库目录里运行：

```powershell
.\Repair-CodexDesktopHistory.ps1
```

只预览，不修改：

```powershell
.\Repair-CodexDesktopHistory.ps1 -DryRun
```

修复完成后不自动重启 Codex Desktop：

```powershell
.\Repair-CodexDesktopHistory.ps1 -NoRestart
```

跳过 `codex-threadripper` 的 npm 安装步骤，只使用本机已有命令：

```powershell
.\Repair-CodexDesktopHistory.ps1 -SkipThreadripperInstall
```

控制 projectless 会话桶的写入方式：

```powershell
.\Repair-CodexDesktopHistory.ps1 -ProjectlessMode current-only
.\Repair-CodexDesktopHistory.ps1 -ProjectlessMode all
.\Repair-CodexDesktopHistory.ps1 -ProjectlessMode none
```

默认是 `current-only`，通常能让恢复出来的会话留在各自原本的工作区分组里。

## 备份位置

每次正式修复都会在 `%USERPROFILE%\.codex` 下生成带时间戳的备份文件，例如：

```text
.codex-global-state.json.backup_desktop_repair_YYYYMMDD-HHMMSS
state_5.sqlite.backup_desktop_repair_YYYYMMDD-HHMMSS
```

如果修复结果不符合预期，可以用这些备份文件手动恢复。

## 注意事项

- 正式修复会关闭 Codex Desktop，请在能接受重启的时候运行。
- 工具不会删除对话、不会删除 rollout 文件。
- 工具会跳过没有用户消息的空线程，避免导入暂无对话的文件夹。
- 如果 Windows 弹出安全提示，选择允许运行即可；这是本地脚本，没有联网上传你的对话内容。
