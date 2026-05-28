# AI Strategist 增强器阶段交接

更新时间：2026-05-25  
项目目录：`D:\我的空间\工作\pilot文件夹\AI-Strategist`

## 接手口令

新窗口请先阅读：

- `ENHANCER_HANDOFF_2026-05-25.md`
- `MAINLINE_HANDOFF_2026-05-25.md`
- `PRODUCTIZATION_CHECKLIST.md`
- `EXECUTION_PLAN.md`

不要从零重新分析产品方向。当前方向已经更新：

1. `启动与修复` 仍然是主线入口
2. 下一阶段开始开发“增强器功能”
3. 参考对象是 `D:\CodexPlusPlus`
4. 但 AI Strategist 不是照抄 Codex++，而是按我们自己的产品边界做取舍

## 一句话说明

AI Strategist 现在进入第二阶段：在保留“启动与修复”主线的前提下，开始增加类似 Codex++ 的增强器能力，让用户在稳定启动、恢复会话之后，继续获得更强的使用体验。

## 当前产品判断

### 已确认不变的主线

- AI Strategist 不是单纯 provider 桶同步工具
- 会话恢复主规则仍然是：
  - 恢复到该待的 workspace / session
  - provider 只做启动通道和兼容性诊断
- `启动与修复` 仍是当前主入口
- 产品化、runtime、自检、干净机器可运行仍然要继续做

### 新增方向

在上面的前提下，AI Strategist 可以开始增加“增强器能力”。

这意味着：

- 不只是“能启动、能修复”
- 还要逐步提供一些“Codex 原生没有、但用户很需要”的增强功能

参考对象：

`D:\CodexPlusPlus`

它的核心思路是：

- 外部启动 Codex
- 通过 CDP 注入前端脚本
- 配合本地 helper server
- 增强原始 Codex Desktop 的能力

这个方向值得研究，但不能整包照搬。

## Codex++ 和 AI Strategist 的关系

### Codex++ 的定位

Codex++ 更像：

- Codex App 的外挂增强器
- 通过注入补齐删除、导出、插件解锁、timeline、provider sync 等能力

### AI Strategist 的定位

AI Strategist 更像：

- 围绕 Codex 的启动、修复、恢复、状态控制和产品化桌面壳

### 现在的新关系

下一阶段建议把 AI Strategist 理解为：

**“启动与修复控制台 + 可控的增强器能力”**

也就是说：

- AI Strategist 保留自己的主线
- 但适度吸收 Codex++ 里真正高价值的增强功能

不是做成第二个 Codex++，而是做成更完整的本地 Codex 工作台。

## 适合借鉴的增强能力

以下能力值得作为候选：

### 1. 会话删除 / 撤销

价值高，用户痛点明确。

可借鉴内容：

- 本地 SQLite 删除
- rollout 文件备份
- 撤销令牌和恢复逻辑
- 删除前确认

注意：

- 必须放在 AI Strategist 的安全边界里
- 必须先备份
- 必须明确删除作用域

### 2. Markdown 导出

价值高，风险相对低。

可借鉴内容：

- 从 rollout 导出用户/助手消息
- 标题清洗
- 时间戳渲染
- 导出文件命名规则

这类功能很适合尽早并入。

### 3. 会话移动 / workspace 归属调整

这和 AI Strategist 当前主线高度相关。

可借鉴内容：

- 修改 `threads.cwd`
- 修改 rollout 的 `session_meta.cwd`
- 提供“移动到 project/workspace”的交互

这类能力比 provider sync 更符合我们现在的产品思路。

### 4. 对话 Timeline

这是体验增强项，不是主线必需，但价值不错。

适合后置：

- 在会话恢复和产品化更稳之后再做

### 5. 后端状态面板 / helper 状态

AI Strategist 未来如果也走增强器注入链，这类可视化状态会很有用。

## 不要直接照搬的部分

### 1. 不要把 provider sync 重新变成主规则

Codex++ 的 provider sync 重点是：

- 切换 provider 后，让历史会话继续显示

但 AI Strategist 现在已经明确：

- provider 不是会话归属主规则
- workspace/session 才是主规则

所以：

- 可以研究它的 metadata 修复方式
- 不能把它重新抬回“按 provider 决定归属”的产品逻辑

### 2. 不要一上来复制整套 CDP 注入体系

Codex++ 的核心价值很大，但复杂度也高：

- CDP
- debug port
- 注入脚本
- DOM selector
- helper bridge

AI Strategist 现在不应该第一步就全量复制。

建议顺序：

1. 先选功能
2. 再定交互
3. 最后决定是否必须注入

### 3. 不要让增强器反过来吞掉主线

AI Strategist 当前仍然必须优先保证：

- 启动与修复
- 恢复逻辑
- 产品化

增强器功能不能把这些工作打断。

## 建议的增强器开发顺序

### 第一批：低风险高价值

建议优先做：

1. Markdown 导出
2. 会话删除 + 撤销
3. 会话移动 / workspace 调整

原因：

- 都有明确用户价值
- 和 AI Strategist 当前的数据层主线兼容
- 不一定一开始就要大规模前端注入

### 第二批：中风险增强

可继续评估：

4. 会话排序辅助 / 时间信息展示
5. 状态面板
6. 简化版 Timeline

### 第三批：高复杂度增强

最后再决定：

7. 插件入口解锁
8. 特定安装限制绕过
9. 完整前端注入菜单系统

这些能力依赖上游 UI 结构，很容易脆。

## 当前建议的工程策略

### 路线 A：先做本地数据能力

优先把增强器功能做成：

- AI Strategist 自己的桌面页面
- Tauri command
- Python / Rust 后端操作

优点：

- 复用现有壳
- 风险低
- 可测试性更好

适合：

- 删除
- 撤销
- 导出
- workspace 调整

### 路线 B：必要时再做注入能力

如果某些增强能力必须在 Codex 原窗口里交互，才考虑：

- 借鉴 Codex++ 的 CDP 注入模式

但要做成 AI Strategist 自己的受控模块，不要直接复制糊上去。

## 立即任务

新窗口接手后的下一步任务，就是：

**规划并开始开发 AI Strategist 的增强器功能，参考对象是 Codex++。**

建议第一轮输出是文档和设计，不要直接大规模写代码。

### 第一轮要完成的内容

1. 列出 Codex++ 所有增强能力
2. 按三类分类：
   - 立即适合 AI Strategist
   - 适合后置
   - 不适合引入
3. 给出 AI Strategist 第一批增强器 MVP
4. 定义这些功能是：
   - 桌面壳内做
   - 还是必须注入 Codex 页面
5. 定义每个功能的安全边界和备份策略

## 建议产出物

建议新窗口优先产出这些文档：

1. `ENHANCER_FEATURE_MATRIX.md`
   - Codex++ 功能盘点
   - AI Strategist 适配判断

2. `ENHANCER_MVP_PLAN.md`
   - 第一批增强器功能
   - 优先级
   - 风险
   - 技术路线

3. `ENHANCER_ARCHITECTURE_OPTIONS.md`
   - 壳内实现 vs 注入实现
   - 各自优缺点

## 当前已知参考文件

AI Strategist 侧：

- `ai-strategist-desktop/src/components/login-repair/login-repair-page.tsx`
- `ai-strategist-desktop/src-tauri/src/commands/prelaunch.rs`
- `prelaunch_bridge.py`
- `repair_codex_desktop_history.py`
- `MAINLINE_HANDOFF_2026-05-25.md`

Codex++ 侧重点参考：

- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\README.md`
- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\launcher.py`
- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\cdp.py`
- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\helper_server.py`
- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\storage_adapter.py`
- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\markdown_exporter.py`
- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\provider_sync.py`
- `D:\CodexPlusPlus\CodexPlusPlus\CodexPlusPlus\codex_session_delete\inject\renderer-inject.js`

## 给接手人的简单话

你接下来不是继续只盯着“启动与修复”了，而是要开始做 AI Strategist 的增强器阶段。

参考对象就是 Codex++，但不要照抄。

先做功能矩阵和 MVP 方案，优先挑：

- Markdown 导出
- 删除 / 撤销
- workspace 调整

这三类最值得先做。

记住边界：

- AI Strategist 的主线还是启动、修复、恢复、产品化
- provider 不再是会话归属主规则
- 增强器功能不能把主线带偏
