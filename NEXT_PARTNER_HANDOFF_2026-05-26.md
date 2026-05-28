# AI Strategist 下一位接手交接包

更新时间：2026-05-26 12:48:49  
项目目录：`D:\我的空间\工作\pilot文件夹\AI-Strategist`

## 复制给下一位伙伴的口令

```text
请先阅读以下文件，不要从零重新分析，也不要先改产品方向：

1. D:\我的空间\工作\pilot文件夹\AI-Strategist\NEXT_PARTNER_HANDOFF_2026-05-26.md
2. D:\我的空间\工作\pilot文件夹\AI-Strategist\ENHANCER_HANDOFF_2026-05-25.md
3. D:\我的空间\工作\pilot文件夹\AI-Strategist\MAINLINE_HANDOFF_2026-05-25.md
4. D:\我的空间\工作\pilot文件夹\AI-Strategist\PRODUCTIZATION_CHECKLIST.md
5. D:\我的空间\工作\pilot文件夹\AI-Strategist\EXECUTION_PLAN.md

当前目标不是重新设计，而是继续修 AI Strategist 的增强启动链，让“增强登录 / 混合登录”真正把 Codex 拉起来，并保留增强功能入口。

已知用户反馈：
- 现在还是拉不起 Codex，表现是闪两下就退。
- 用户明确要求：对标 D:\CodexPlusPlus，能抄的实现思路就抄，不要自己再发散。
- 增强功能菜单已经有了，重点是底层启动 / 注入 / 接管链路要真正可用。
- 不要在开发过程中擅自杀掉用户正在工作的 Codex 进程；真实破坏性测试前先说明。

你接手后先做这几件事：
1. 对照 D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\launcher.py 和 watcher.py，检查我们 enhancer_runtime.py / enhancer_runtime_watcher.py / prelaunch_manager.py 的启动、CDP 探测、失败清理、再次接管是否还有缺口。
2. 重点排查“已写入 / 已注入参数，但 Codex 没真正拉起或很快退出”的链路，不要只看静态代码，要把失败点收敛到具体一环。
3. 检查增强运行时是否错误依赖了当前环境的 python、WindowsApps、AppUserModelID、AppID 或路径形式。
4. 只有在必须进入真实测试时再停下来让用户测。

不要做：
- 不要重新讨论是否要做增强功能菜单，已经做了。
- 不要把功能改回“在我们的 UI 上直接移动聊天”，用户要的是在 Codex 内点击图标处理。
- 不要用我的机器路径写死产品逻辑。
- 不要把问题又扩展成大范围重构或新功能设计。
```

## 当前产品判断

- `启动与修复` 仍是主线。
- `增强功能` 已经作为与 `启动与修复` 同级的顶部菜单存在。
- 用户要的不是我们 UI 直接代替 Codex 操作，而是：
  - 在 `增强功能` 里给开关；
  - 开启后，增强启动链把能力注入到 Codex 自己的界面里；
  - 用户在 Codex 里点图标完成“聊天信息搬家 / 一键移交任务”。

## 已完成到哪里

### 1. 增强功能入口已存在

- 顶部菜单已有 `增强功能`
- 页面已有这些开关：
  - `聊天信息搬家`
  - `一键移交任务`
  - `隐藏 Codex 官方额度提醒`

相关文件：

- `ai-strategist-desktop/src/components/enhancer/enhancer-page.tsx`
- `ai-strategist-desktop/src/components/login-repair/login-repair-page.tsx`
- `ai-strategist-desktop/src-tauri/src/commands/enhancer.rs`

### 2. 启动链已按对标方向拆层

新增/已接入：

- `codex_desktop_app_paths.py`
- `codex_desktop_launcher.py`
- `enhancer_runtime.py`
- `enhancer_runtime_watcher.py`

当前结构含义：

- `codex_desktop_app_paths.py`
  - 做 Codex Desktop 路径 / AppID / AUMID 探测
- `codex_desktop_launcher.py`
  - 做增强启动、CDP 重试、失败清理、stale runtime 清理
- `enhancer_runtime.py`
  - 做增强 runtime 启动、注入、bridge、页面监听
- `enhancer_runtime_watcher.py`
  - 做 watcher 风格的 grace / takeover / cooldown / backoff

### 3. 当前启动策略已经改过

- `official` 现在是“增强登录”
  - 保留原始聊天和登录态
  - 不自动恢复聊天归属
  - 直接走增强链
- `hybrid` 也走增强链
- `api` 在增强功能开启时也可走增强链，否则普通启动

### 4. 快捷方式已补统一更新入口

新增：

- `Update-AI-Strategist-Shortcut.ps1`

更新：

- `Launch-AI-Strategist.cmd`

现在启动器会尝试静默刷新桌面 `AI Strategist.lnk`，避免又指到旧入口。

## 当前仍然没解决的核心问题

用户最新明确反馈：

- 还是拉不起 Codex
- 现象是“闪两下就退”
- 之前很多次属于“信息写入了，但没真正拉起 Codex，只能靠对标工具恢复聊天后启动”

也就是说：

- AI Strategist 自己的 UI 外壳并不是当前主问题
- 主问题仍然是 **Codex Desktop 被增强链拉起、保持存活、CDP 可用、注入成功** 这一整条链

## 这轮已经做过但只做了静态验证

做过：

- `python -m py_compile enhancer_runtime.py enhancer_runtime_watcher.py prelaunch_manager.py prelaunch_bridge.py codex_desktop_app_paths.py codex_desktop_launcher.py`
- `python -m pytest tests\test_enhancer_runtime_watcher.py tests\test_prelaunch_bridge.py -q -k "watcher or retry or quota or hybrid or api or official or desktop_codex_running_processes or find_codex_desktop_exe or launch_codex_desktop_with_enhancer"`
- PowerShell 脚本语法检查：`Update-AI-Strategist-Shortcut.ps1`

结果：

- 相关静态检查通过
- 但 **没有完成真实环境下的成功拉起验证**

所以不要误判成“已经修好”，现在只是代码结构比之前更接近对标项目。

## 下一位最该盯住的地方

### A. 真实失败点定位

优先确认是哪一种：

1. Codex 根本没被正确启动
2. Codex 启动后很快退出
3. Codex 活着，但 CDP 端口没起来
4. CDP 起来了，但页面目标没抓到
5. 注入后 bridge/renderer 异常导致页面或进程退出
6. takeover / cleanup 逻辑把本来起来的进程又清掉了

### B. 和对标项目逐项比对

重点比对：

- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\launcher.py`
- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\watcher.py`

不要只看函数名，要看这些行为是否一致：

- stale launcher 清理
- stale Codex 进程清理
- AppX 激活后的等待窗口
- CDP 未起来时的 retry 策略
- 失败后的彻底 cleanup
- 再次 takeover 的触发条件

### C. 环境依赖风险

继续检查：

- 是否仍错误依赖当前 shell 的 Python
- 是否仍错误依赖 `WindowsApps` 的 `Codex.exe`
- 是否 AUMID / AppID / exe path 的推断不稳定
- 是否 `pythonw/python` 启动 enhancer_runtime.py 的方式本身有问题

## 禁止误走的路

- 不要重新回到 provider sync 主导产品逻辑
- 不要把“聊天搬家”做成我们面板里直接操作
- 不要继续只做 UI 微调
- 不要写死开发机路径来“修复”
- 不要把这次接手扩展成全仓大重构

## 真实接手前建议先跑

```powershell
cd "D:\我的空间\工作\pilot文件夹\AI-Strategist"
python -m py_compile enhancer_runtime.py enhancer_runtime_watcher.py prelaunch_manager.py prelaunch_bridge.py codex_desktop_app_paths.py codex_desktop_launcher.py
python -m pytest tests\test_enhancer_runtime_watcher.py tests\test_prelaunch_bridge.py -q
```

如果要看当前工作树：

```powershell
git status --short
```

## 当前工作树提醒

- 当前 repo 是脏工作树
- 有很多未跟踪文件和历史修改
- 不要用破坏性 git 命令
- 不要误删 `ai-strategist-desktop/`、`tests/`、`reports/`、文档链文件

## 给下一位的结论

这不是“重新规划”任务了。  
这是一个很具体的修复任务：

**把 AI Strategist 的增强启动链修到和对标项目一样能稳定把 Codex 拉起来，然后再保留我们自己的增强功能菜单和新增功能。**
