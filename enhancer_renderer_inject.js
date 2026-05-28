(() => {
  const rowSelector = "[data-app-action-sidebar-thread-id]";
  const projectSelector = "[data-app-action-sidebar-project-row]";
  const styleId = "ai-strategist-enhancer-style";
  const actionGroupClass = "ai-strategist-session-actions";
  const actionButtonClass = "ai-strategist-session-action-button";
  const actionMenuOverlayClass = "ai-strategist-session-action-menu-overlay";
  const actionMenuPanelClass = "ai-strategist-session-action-menu-panel";
  const moveOverlayClass = "ai-strategist-move-overlay";
  const movePanelClass = "ai-strategist-move-panel";
  const toastClass = "ai-strategist-toast";
  const pluginNavButtonSelector = 'nav[role="navigation"] button.h-token-nav-row.w-full';
  const pluginSvgPathSelector = 'svg path[d^="M7.94562 14.0277"]';
  const projectionStorageKey = "__ai_strategist_project_move_projection_v1__";
  const projectionTtlMs = 60_000;
  const refreshDelaysMs = [200, 900, 2200];
  const defaultSettings = {
    chatInfoMoveEnabled: false,
    oneClickHandoffEnabled: false,
    mustInstallPluginsEnabled: false,
  };

  function enhancerSettings() {
    const raw = window.__aiStrategistEnhancerSettings;
    if (!raw || typeof raw !== "object") {
      return { ...defaultSettings };
    }
    return {
      ...defaultSettings,
      ...raw,
    };
  }

  function ensureBridge() {
    return typeof window.__aiStrategistEnhancerBridge === "function";
  }

  function postJson(path, payload) {
    if (!ensureBridge()) {
      return Promise.reject(new Error("Enhancer bridge unavailable"));
    }
    return window.__aiStrategistEnhancerBridge(path, payload);
  }

  function visibleText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function hasAnyText(value, needles) {
    const text = visibleText(value).toLowerCase();
    return needles.some((needle) => text.includes(needle.toLowerCase()));
  }

  function reactFiberFrom(element) {
    const fiberKey = Object.keys(element).find((key) => key.startsWith("__reactFiber"));
    return fiberKey ? element[fiberKey] : null;
  }

  function authContextValueFrom(element) {
    for (let fiber = reactFiberFrom(element); fiber; fiber = fiber.return) {
      for (const value of [fiber.memoizedProps?.value, fiber.pendingProps?.value]) {
        if (value && typeof value === "object" && typeof value.setAuthMethod === "function" && "authMethod" in value) {
          return value;
        }
      }
    }
    return null;
  }

  function spoofChatGPTAuthMethod(element) {
    const auth = authContextValueFrom(element);
    if (!auth || auth.authMethod === "chatgpt") return false;
    auth.setAuthMethod("chatgpt");
    return true;
  }

  function pluginInstallCandidates() {
    return Array.from(document.querySelectorAll([
      "button:disabled.w-full.justify-center",
      "[role='button'][aria-disabled='true'].cursor-not-allowed",
    ].join(",")));
  }

  function pluginEntryButton() {
    const byIcon = document.querySelector(`${pluginNavButtonSelector} ${pluginSvgPathSelector}`)?.closest("button");
    if (byIcon) return byIcon;
    return Array.from(document.querySelectorAll(pluginNavButtonSelector)).find((button) => {
      const text = visibleText(button.textContent);
      return text === "插件" || text === "Plugins" || text === "插件 - 已解锁" || text === "Plugins - Unlocked";
    }) || null;
  }

  function labelUnlockedPluginEntry(button) {
    const labelTextNode = Array.from(button.querySelectorAll("span, div")).reverse()
      .flatMap((node) => Array.from(node.childNodes))
      .find((node) => node.nodeType === 3 && ["插件", "Plugins", "插件 - 已解锁", "Plugins - Unlocked"].includes(visibleText(node.nodeValue)));
    if (!labelTextNode) return;
    const current = visibleText(labelTextNode.nodeValue);
    labelTextNode.nodeValue = current.startsWith("Plugins") ? "Plugins - Unlocked" : "插件 - 已解锁";
  }

  function enablePluginEntry() {
    if (!enhancerSettings().mustInstallPluginsEnabled) return;
    const pluginButton = pluginEntryButton();
    if (!pluginButton) return;
    spoofChatGPTAuthMethod(pluginButton);
    pluginButton.disabled = false;
    pluginButton.removeAttribute("disabled");
    pluginButton.style.display = "";
    pluginButton.querySelectorAll("*").forEach((node) => {
      node.style.display = "";
    });
    labelUnlockedPluginEntry(pluginButton);
    const reactPropsKey = Object.keys(pluginButton).find((key) => key.startsWith("__reactProps"));
    if (reactPropsKey) {
      pluginButton[reactPropsKey].disabled = false;
    }
    if (pluginButton.dataset.aiStrategistPluginEnabled === "true") return;
    pluginButton.dataset.aiStrategistPluginEnabled = "true";
    pluginButton.addEventListener("click", () => {
      spoofChatGPTAuthMethod(pluginButton);
    }, true);
  }

  function installButtonLabel(element) {
    return visibleText(element.textContent);
  }

  function pluginInstallSurfaceVisible() {
    const selectors = [
      "[role='dialog']",
      "[data-radix-dialog-content]",
      "main",
      "[data-testid*='plugin']",
      "[data-testid*='connector']",
    ];
    const surfaces = Array.from(document.querySelectorAll(selectors.join(",")));
    return surfaces.some((surface) => {
      const text = visibleText(surface.textContent || "");
      return (
        hasAnyText(text, ["install", "app unavailable", "connector unavailable", "安装", "应用不可用", "插件安装失败"])
        && hasAnyText(text, ["plugin", "connector", "chrome", "openai-bundled", "插件", "连接器"])
      );
    });
  }

  function looksLikeInstallControl(button) {
    return hasAnyText(installButtonLabel(button), ["install", "安装", "必须装"]);
  }

  function unblockPluginInstallButton(button) {
    button.disabled = false;
    button.removeAttribute("disabled");
    button.removeAttribute("aria-disabled");
    button.classList.remove("disabled", "opacity-50", "cursor-not-allowed", "pointer-events-none");
    button.style.pointerEvents = "auto";
    button.tabIndex = 0;
    button.dataset.aiStrategistMustInstallUnlocked = "true";
    const reactPropsKey = Object.keys(button).find((key) => key.startsWith("__reactProps"));
    if (reactPropsKey) {
      button[reactPropsKey].disabled = false;
      button[reactPropsKey]["aria-disabled"] = false;
    }
  }

  function labelMustInstallButton(button) {
    const textNode = Array.from(button.childNodes).find((node) => {
      const text = visibleText(node.nodeValue);
      return node.nodeType === 3 && hasAnyText(text, ["install", "add", "安装", "添加", "必须装"]);
    });
    if (textNode) {
      textNode.nodeValue = "必须装";
      return;
    }
    const labelNode = Array.from(button.querySelectorAll("span, div")).find((node) => {
      return hasAnyText(node.textContent, ["install", "add", "安装", "添加", "必须装"]);
    });
    if (labelNode) {
      labelNode.textContent = "必须装";
    }
  }

  function unlockMustInstallPluginButtons() {
    if (!enhancerSettings().mustInstallPluginsEnabled) return;
    if (!pluginInstallSurfaceVisible()) return;
    spoofChatGPTAuthMethod(document.body);
    pluginInstallCandidates().forEach((button) => {
      if (!looksLikeInstallControl(button)) return;
      unblockPluginInstallButton(button);
      labelMustInstallButton(button);
    });
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function normalizeWorkspacePath(value) {
    return String(value || "")
      .replace(/^\\\\\?\\/, "")
      .replace(/\//g, "\\")
      .replace(/\\+$/, "")
      .trim()
      .toLowerCase();
  }

  function sameWorkspacePath(left, right) {
    const normalizedLeft = normalizeWorkspacePath(left);
    const normalizedRight = normalizeWorkspacePath(right);
    return !!normalizedLeft && !!normalizedRight && normalizedLeft === normalizedRight;
  }

  function displayProjectName(path) {
    const trimmed = String(path || "").replace(/[\\/]+$/, "").trim();
    return trimmed.split(/[\\/]+/).filter(Boolean).pop() || trimmed || "未命名项目";
  }

  function numericTimestamp(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
  }

  function timestampMsFromPayload(payload) {
    return numericTimestamp(payload?.updated_at_ms) || numericTimestamp(payload?.updated_at) * 1000 || numericTimestamp(payload?.created_at_ms);
  }

  function sessionRows() {
    return Array.from(document.querySelectorAll(rowSelector));
  }

  function sessionKey(sessionId) {
    return String(sessionId || "").replace(/^local:/, "").trim();
  }

  function threadIdVariants(sessionId) {
    const bare = sessionKey(sessionId);
    return bare ? [bare, `local:${bare}`] : [];
  }

  function sessionRefFromRow(row) {
    const href = row.getAttribute("href") || row.querySelector("a")?.getAttribute("href") || "";
    const idMatch =
      href.match(/(?:session|conversation|thread)[=/:-]([A-Za-z0-9_.-]+)/i) ||
      href.match(/([A-Za-z0-9_.-]{8,})$/);
    const sessionId =
      row.getAttribute("data-app-action-sidebar-thread-id") ||
      row.getAttribute("data-session-id") ||
      (idMatch && idMatch[1]) ||
      "";
    const titleNode = row.querySelector("[data-thread-title], .truncate.select-none, .truncate.text-base");
    const title = visibleText(titleNode?.textContent || row.textContent || "Untitled session").slice(0, 160);
    return { session_id: sessionId, title };
  }

  function rowListItem(row) {
    return row.closest?.('[role="listitem"]') || row;
  }

  function threadRowFromListItem(item) {
    if (!item) return null;
    if (item.matches?.(rowSelector)) return item;
    return item.querySelector?.(rowSelector) || null;
  }

  function projectListItem(row) {
    return row?.closest?.('[role="listitem"][aria-label]') || row?.closest?.('[role="listitem"]') || row || null;
  }

  function projectsSection() {
    return document.querySelector('[data-app-action-sidebar-section-heading="Projects"]');
  }

  function chatsSection() {
    return document.querySelector('[data-app-action-sidebar-section-heading="Chats"]');
  }

  function chatsThreadList() {
    return chatsSection()?.querySelector?.('[role="list"]') || null;
  }

  function rowIsInChats(row) {
    return !!(row && chatsSection()?.contains(row));
  }

  function rowPinned(row) {
    return row?.getAttribute?.("data-app-action-sidebar-thread-pinned") === "true" ||
      rowListItem(row)?.getAttribute?.("data-app-action-sidebar-thread-pinned") === "true";
  }

  function nativeProjectTargets() {
    const section = projectsSection();
    const seen = new Set();
    return Array.from(document.querySelectorAll(projectSelector)).flatMap((row) => {
      if (section && !section.contains(row)) return [];
      const path = row.getAttribute("data-app-action-sidebar-project-id") || "";
      const normalizedPath = normalizeWorkspacePath(path);
      if (!normalizedPath || seen.has(normalizedPath)) return [];
      seen.add(normalizedPath);
      const label =
        row.getAttribute("data-app-action-sidebar-project-label") ||
        row.getAttribute("aria-label") ||
        displayProjectName(path);
      return [{
        kind: "project",
        label: String(label || displayProjectName(path)),
        description: path,
        path,
        normalizedPath,
        row,
        listItem: projectListItem(row),
      }];
    });
  }

  function projectMoveTargets() {
    return [
      { kind: "projectless", label: "普通对话", description: "不属于任何项目", path: "", normalizedPath: "" },
      ...nativeProjectTargets().map((target) => ({
        kind: "project",
        label: target.label,
        description: target.description,
        path: target.path,
        normalizedPath: target.normalizedPath,
      })),
    ];
  }

  function targetPath(target) {
    return target?.path || target?.targetCwd || "";
  }

  function targetLabel(target) {
    return target?.label || target?.targetLabel || displayProjectName(targetPath(target));
  }

  function projectItemMatchesTarget(projectItem, target) {
    const projectRow = projectItem?.matches?.(projectSelector) ? projectItem : projectItem?.querySelector?.(projectSelector);
    const projectPath = projectRow?.getAttribute?.("data-app-action-sidebar-project-id") || "";
    if (projectPath && sameWorkspacePath(projectPath, targetPath(target))) return true;
    const actualLabel = visibleText(projectRow?.getAttribute?.("data-app-action-sidebar-project-label") || projectItem?.getAttribute?.("aria-label") || "");
    return !!actualLabel && actualLabel === visibleText(targetLabel(target));
  }

  function findProjectListItem(target) {
    const nativeTarget = nativeProjectTargets().find((project) => sameWorkspacePath(project.path, targetPath(target)));
    if (nativeTarget?.listItem) return nativeTarget.listItem;
    const section = projectsSection();
    if (!section) return null;
    return Array.from(section.querySelectorAll('[role="listitem"][aria-label], [role="listitem"]')).find((item) => projectItemMatchesTarget(item, target)) || null;
  }

  function projectMoveInjectedList(projectItem) {
    let list = projectItem.querySelector?.('[data-ai-strategist-injected-project-list="true"]');
    if (!list) {
      const host = Array.from(projectItem.children || []).find((node) => String(node.className || "").includes("overflow-hidden")) || projectItem;
      list = document.createElement("div");
      list.setAttribute("role", "list");
      list.setAttribute("data-ai-strategist-injected-project-list", "true");
      list.className = "flex flex-col";
      host.appendChild(list);
    }
    return list;
  }

  function projectThreadList(projectItem, target) {
    const targetCwd = targetPath(target);
    const lists = Array.from(projectItem.querySelectorAll?.("[data-app-action-sidebar-project-list-id]") || []);
    return lists.find((list) => sameWorkspacePath(list.getAttribute("data-app-action-sidebar-project-list-id"), targetCwd)) ||
      lists[0] ||
      projectMoveInjectedList(projectItem);
  }

  function sortMsForRow(row, ref = sessionRefFromRow(row), target = null) {
    return numericTimestamp(target?.sortMs) ||
      numericTimestamp(row.dataset.aiStrategistSortMs) ||
      numericTimestamp(rowListItem(row).dataset.aiStrategistSortMs) ||
      numericTimestamp(ref?.updated_at_ms);
  }

  function sortRowsInList(list) {
    const items = Array.from(list.children);
    const rows = items
      .map((item) => ({ item, row: threadRowFromListItem(item) }))
      .filter((entry) => !!entry.row);
    rows.sort((left, right) => {
      const leftPinned = rowPinned(left.row);
      const rightPinned = rowPinned(right.row);
      if (leftPinned !== rightPinned) return leftPinned ? -1 : 1;
      const leftRef = sessionRefFromRow(left.row);
      const rightRef = sessionRefFromRow(right.row);
      const leftSort = sortMsForRow(left.row, leftRef);
      const rightSort = sortMsForRow(right.row, rightRef);
      if (leftSort !== rightSort) return rightSort - leftSort;
      return sessionKey(rightRef.session_id).localeCompare(sessionKey(leftRef.session_id));
    });
    rows.forEach(({ item }) => list.appendChild(item));
  }

  function insertRowItemByTime(list, row, target) {
    const item = rowListItem(row);
    const ref = sessionRefFromRow(row);
    const sortMs = numericTimestamp(target?.sortMs) || sortMsForRow(row, ref);
    row.dataset.aiStrategistSortMs = String(sortMs || 0);
    item.dataset.aiStrategistSortMs = String(sortMs || 0);
    list.appendChild(item);
    sortRowsInList(list);
  }

  function moveRowToProjectList(row, target) {
    const projectItem = findProjectListItem(target);
    if (!projectItem) return false;
    const list = projectThreadList(projectItem, target);
    if (!list) return false;
    insertRowItemByTime(list, row, target);
    row.dataset.aiStrategistMoveTargetKind = "project";
    row.dataset.aiStrategistMoveTargetCwd = targetPath(target);
    rowListItem(row).dataset.aiStrategistMoveTargetKind = "project";
    rowListItem(row).dataset.aiStrategistMoveTargetCwd = targetPath(target);
    return true;
  }

  function moveRowToChats(row, target = null) {
    const list = chatsThreadList();
    if (!list) return false;
    insertRowItemByTime(list, row, target);
    row.dataset.aiStrategistMoveTargetKind = "projectless";
    delete row.dataset.aiStrategistMoveTargetCwd;
    rowListItem(row).dataset.aiStrategistMoveTargetKind = "projectless";
    delete rowListItem(row).dataset.aiStrategistMoveTargetCwd;
    return true;
  }

  function rowIsUnderTarget(row, target) {
    if (!row || !target) return false;
    if (target.kind === "projectless" || target.targetKind === "projectless") {
      return rowIsInChats(row);
    }
    const item = row.closest?.('[role="listitem"][aria-label]') || rowListItem(row)?.parentElement?.closest?.('[role="listitem"][aria-label]');
    return !!item && projectItemMatchesTarget(item, target);
  }

  function readProjectMoveProjection() {
    try {
      const raw = JSON.parse(localStorage.getItem(projectionStorageKey) || "{}");
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
      const now = Date.now();
      const projection = {};
      for (const [key, value] of Object.entries(raw)) {
        if (!value || typeof value !== "object") continue;
        if (typeof value.at === "number" && now - value.at > projectionTtlMs) continue;
        const sessionId = sessionKey(value.sessionId || key);
        if (!sessionId) continue;
        const targetKind = value.targetKind === "projectless" ? "projectless" : "project";
        const targetCwd = String(value.targetCwd || value.path || "");
        if (targetKind === "project" && !targetCwd) continue;
        projection[sessionId] = {
          sessionId,
          targetKind,
          targetCwd,
          targetLabel: String(value.targetLabel || value.label || (targetKind === "projectless" ? "普通对话" : displayProjectName(targetCwd))),
          sortMs: numericTimestamp(value.sortMs),
          at: typeof value.at === "number" ? value.at : now,
        };
      }
      return projection;
    } catch {
      return {};
    }
  }

  function writeProjectMoveProjection(projection) {
    try {
      localStorage.setItem(projectionStorageKey, JSON.stringify(projection || {}));
    } catch {}
  }

  function saveProjectMoveProjection(ref, target, sortMs) {
    const key = sessionKey(ref.session_id);
    if (!key) return;
    const projection = readProjectMoveProjection();
    projection[key] = {
      sessionId: key,
      targetKind: target.kind === "projectless" ? "projectless" : "project",
      targetCwd: target.path || "",
      targetLabel: target.label || (target.kind === "projectless" ? "普通对话" : displayProjectName(target.path)),
      sortMs: numericTimestamp(sortMs),
      at: Date.now(),
    };
    writeProjectMoveProjection(projection);
  }

  function clearProjectMoveProjection(ref) {
    const projection = readProjectMoveProjection();
    const keys = threadIdVariants(ref.session_id).map(sessionKey).filter(Boolean);
    let changed = false;
    keys.forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(projection, key)) {
        delete projection[key];
        changed = true;
      }
    });
    if (changed) writeProjectMoveProjection(projection);
  }

  function applyProjectMoveProjection() {
    const projection = readProjectMoveProjection();
    sessionRows().forEach((row) => {
      const ref = sessionRefFromRow(row);
      const target = projection[sessionKey(ref.session_id)];
      if (!target) {
        delete row.dataset.aiStrategistMoveTargetKind;
        delete row.dataset.aiStrategistMoveTargetCwd;
        delete rowListItem(row).dataset.aiStrategistMoveTargetKind;
        delete rowListItem(row).dataset.aiStrategistMoveTargetCwd;
        return;
      }
      if (rowIsUnderTarget(row, target)) return;
      const moved = target.targetKind === "projectless"
        ? moveRowToChats(row, target)
        : moveRowToProjectList(row, { kind: "project", path: target.targetCwd, label: target.targetLabel, sortMs: target.sortMs });
      if (moved && Date.now() - target.at > 5_000) {
        clearProjectMoveProjection(ref);
      }
    });
  }

  async function applyChatsSortCorrection() {
    const list = chatsThreadList();
    if (!list) return;
    const rows = Array.from(list.children).map(threadRowFromListItem).filter(Boolean);
    if (rows.length < 2) return;
    const refs = rows.map(sessionRefFromRow).filter((ref) => ref.session_id);
    try {
      const result = await postJson("/thread-sort-keys", { sessions: refs });
      if (result?.status === "ok" && Array.isArray(result?.sort_keys)) {
        const byId = new Map();
        result.sort_keys.forEach((item) => {
          byId.set(sessionKey(item?.session_id), item);
        });
        rows.forEach((row) => {
          const ref = sessionRefFromRow(row);
          const payload = byId.get(sessionKey(ref.session_id));
          const sortMs = timestampMsFromPayload(payload);
          if (sortMs) {
            row.dataset.aiStrategistSortMs = String(sortMs);
            rowListItem(row).dataset.aiStrategistSortMs = String(sortMs);
          }
        });
      }
    } catch {}
    sortRowsInList(list);
  }

  function refreshAfterProjectMove() {
    applyProjectMoveProjection();
    applyChatsSortCorrection().catch(() => {});
    refreshDelaysMs.forEach((delay) => {
      setTimeout(() => {
        applyProjectMoveProjection();
        applyChatsSortCorrection().catch(() => {});
      }, delay);
    });
  }

  function showToast(message) {
    document.querySelectorAll(`.${toastClass}`).forEach((node) => node.remove());
    const toast = document.createElement("div");
    toast.className = toastClass;
    toast.textContent = String(message || "");
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
  }

  function closeSessionActionMenus() {
    document.querySelectorAll(`.${actionMenuOverlayClass}`).forEach((node) => node.remove());
  }

  function closeMoveOverlay() {
    document.querySelectorAll(`.${moveOverlayClass}`).forEach((node) => node.remove());
  }

  function actionItems() {
    const settings = enhancerSettings();
    const items = [];
    if (settings.chatInfoMoveEnabled) {
      items.push({ kind: "move", label: "聊天信息搬家" });
    }
    if (settings.oneClickHandoffEnabled) {
      items.push({ kind: "handoff", label: "一键移交任务" });
    }
    return items;
  }

  function hasActionsEnabled() {
    return actionItems().length > 0;
  }

  function isNativeProjectTarget(target) {
    return target?.kind === "project" && nativeProjectTargets().some((project) => sameWorkspacePath(project.path, target.path));
  }

  async function moveSessionToProjectless(ref) {
    if (!ref.session_id) throw new Error("未找到会话 ID");
    const result = await postJson("/thread-projectless", { session_id: ref.session_id, enabled: true });
    if (result?.status !== "moved") {
      throw new Error(result?.message || "移动到普通对话失败");
    }
    return result;
  }

  async function moveSessionToProject(ref, target) {
    if (!ref.session_id) throw new Error("未找到会话 ID");
    if (!target?.path) throw new Error("目标项目路径为空");
    if (!isNativeProjectTarget(target)) throw new Error("目标项目不在 Codex 项目列表中");
    const result = await postJson("/move-thread-workspace", { ...ref, target_cwd: target.path });
    if (result?.status !== "moved") {
      throw new Error(result?.message || "移动到项目失败");
    }
    await postJson("/thread-projectless", { session_id: ref.session_id, enabled: false }).catch(() => null);
    return result;
  }

  async function applyProjectMove(row, target) {
    const ref = sessionRefFromRow(row);
    let result;
    if (target.kind === "projectless") {
      result = await moveSessionToProjectless(ref);
    } else {
      result = await moveSessionToProject(ref, target);
    }
    const sortMs = timestampMsFromPayload(result) || sortMsForRow(row, ref);
    row.dataset.aiStrategistSortMs = String(sortMs || 0);
    rowListItem(row).dataset.aiStrategistSortMs = String(sortMs || 0);
    saveProjectMoveProjection(ref, { ...target, sortMs }, sortMs);
    if (target.kind === "projectless") {
      moveRowToChats(row, { ...target, sortMs });
      showToast(`已移动到普通对话：${ref.title || ref.session_id}`);
    } else {
      moveRowToProjectList(row, { ...target, sortMs });
      showToast(`已移动到 ${target.label}`);
    }
    refreshAfterProjectMove();
  }

  function openMoveOverlay(row) {
    closeMoveOverlay();
    const ref = sessionRefFromRow(row);
    const targets = projectMoveTargets();
    const overlay = document.createElement("div");
    overlay.className = moveOverlayClass;
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) closeMoveOverlay();
    });

    const panel = document.createElement("div");
    panel.className = movePanelClass;
    panel.innerHTML = `
      <div class="ai-strategist-move-header">
        <div class="ai-strategist-move-title">移动“${escapeHtml(ref.title || ref.session_id)}”</div>
      </div>
      <div class="ai-strategist-move-list"></div>
    `;

    const list = panel.querySelector(".ai-strategist-move-list");
    if (!targets.length) {
      const empty = document.createElement("div");
      empty.className = "ai-strategist-move-item-path";
      empty.textContent = "当前没有可用目标。";
      list.appendChild(empty);
    }

    targets.forEach((target) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ai-strategist-move-item";
      button.innerHTML = `
        <div class="ai-strategist-move-item-title">${escapeHtml(target.label)}</div>
        <div class="ai-strategist-move-item-path">${escapeHtml(target.description || " ")}</div>
      `;
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          closeMoveOverlay();
          await applyProjectMove(row, target);
        } catch (error) {
          showToast(error instanceof Error ? error.message : "聊天归属更新失败");
        } finally {
          button.disabled = false;
        }
      });
      list.appendChild(button);
    });

    overlay.appendChild(panel);
    document.body.appendChild(overlay);
  }

  function looksLikeNewChatControl(node) {
    const label = visibleText(node?.getAttribute?.("aria-label") || node?.getAttribute?.("title") || node?.textContent);
    if (!label) return false;
    return /^(新建对话|新对话|新聊天|新任务|New chat|New conversation|New task)$/i.test(label) ||
      /开始新对话|新建|新对话|新聊天|新任务|new chat|new conversation|new task|start new/i.test(label);
  }

  function findProjectScopedNewChatControl(cwd) {
    const target = nativeProjectTargets().find((project) => sameWorkspacePath(project.path, cwd));
    if (!target) return null;
    const containers = [target.listItem, target.row, target.row?.parentElement].filter(Boolean);
    for (const container of containers) {
      const match = Array.from(container.querySelectorAll("a, button")).find((node) => {
        const rect = node.getBoundingClientRect();
        return looksLikeNewChatControl(node) && rect.width > 0 && rect.height > 0;
      });
      if (match) return match;
    }
    return null;
  }

  function findNewChatControl(cwd = "") {
    const scoped = cwd ? findProjectScopedNewChatControl(cwd) : null;
    if (scoped) return scoped;
    if (cwd) return null;
    const selectorCandidates = [
      "[data-testid*='new'][data-testid*='chat']",
      "[data-testid*='new'][data-testid*='thread']",
      "[aria-label*='New chat']",
      "[aria-label*='New conversation']",
      "[aria-label*='新建']",
      "[aria-label*='新对话']",
      "[title*='New chat']",
      "[title*='新建']",
    ];
    for (const selector of selectorCandidates) {
      const node = document.querySelector(selector);
      const control = node?.matches?.("a, button") ? node : node?.closest?.("a, button");
      if (!control) continue;
      const rect = control.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) return control;
    }
    return Array.from(document.querySelectorAll("a, button")).find((node) => {
      const rect = node.getBoundingClientRect();
      return looksLikeNewChatControl(node) && rect.width > 0 && rect.height > 0;
    }) || null;
  }

  function findComposer() {
    const candidates = Array.from(document.querySelectorAll("textarea, [contenteditable='true'], [role='textbox']"));
    return candidates.find((node) => {
      const rect = node.getBoundingClientRect();
      return rect.width > 120 && rect.height > 20 && !node.disabled && node.getAttribute("aria-disabled") !== "true";
    }) || null;
  }

  function setComposerValue(composer, value) {
    composer.focus();
    if (composer instanceof HTMLTextAreaElement || composer instanceof HTMLInputElement) {
      const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(composer), "value");
      descriptor?.set?.call(composer, value);
      composer.dispatchEvent(new Event("input", { bubbles: true }));
      composer.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
    composer.textContent = value;
    composer.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
  }

  function composerActionRoot(composer) {
    let current = composer;
    for (let depth = 0; current && depth < 8; depth += 1, current = current.parentElement) {
      const buttons = Array.from(current.querySelectorAll("button"));
      if (buttons.length > 0 && buttons.length <= 8) return current;
    }
    return document;
  }

  function findSendButton(composer = null) {
    const scope = composer ? composerActionRoot(composer) : document;
    const enabledButtons = Array.from(scope.querySelectorAll("button")).filter(
      (button) => !button.disabled && button.getAttribute("aria-disabled") !== "true",
    );
    return enabledButtons.find((button) => {
      const label = visibleText(button.getAttribute("aria-label") || button.getAttribute("title") || button.textContent);
      return /发送|提交|send|submit/i.test(label) || button.type === "submit";
    }) || enabledButtons.at(-1) || null;
  }

  async function waitFor(factory, timeoutMs = 6_000) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const value = factory();
      if (value) return value;
      await new Promise((resolve) => setTimeout(resolve, 150));
    }
    return null;
  }

  async function waitForFreshComposer(previousComposer, previousLocation = "", timeoutMs = 6_000) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const composer = findComposer();
      if (composer && (composer !== previousComposer || (previousLocation && previousLocation !== window.location.href))) {
        return composer;
      }
      await new Promise((resolve) => setTimeout(resolve, 150));
    }
    return null;
  }

  function decodePrompt(result) {
    if (typeof result?.prompt === "string" && result.prompt.trim()) return result.prompt;
    const encoded = String(result?.prompt_b64 || "");
    if (!encoded) return "";
    try {
      const binary = atob(encoded);
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
      return new TextDecoder("utf-8").decode(bytes);
    } catch {
      return "";
    }
  }

  async function copyTextToClipboard(text) {
    if (!text) return false;
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "true");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      textarea.style.top = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      let copied = false;
      try {
        copied = document.execCommand("copy");
      } catch {
        copied = false;
      } finally {
        textarea.remove();
      }
      return copied;
    }
  }

  async function takeoverPrompt(prompt, cwd = "") {
    if (!prompt) throw new Error("移交提示词为空");
    const previousComposer = findComposer();
    const previousLocation = window.location.href;
    const newChat = findNewChatControl(cwd);
    if (!newChat) throw new Error("未找到同目录新对话入口");
    newChat.click();
    const composer = await waitForFreshComposer(previousComposer, previousLocation);
    if (!composer) throw new Error("新对话未打开");
    setComposerValue(composer, prompt);
    const send = await waitFor(() => findSendButton(composer));
    if (!send) throw new Error("未找到发送按钮");
    send.click();
  }

  async function createContextHandoff(row, actionButton) {
    const ref = sessionRefFromRow(row);
    if (!ref.session_id) throw new Error("未找到会话 ID");
    const previousText = actionButton.textContent;
    actionButton.disabled = true;
    actionButton.textContent = "移交中...";
    try {
      const result = await postJson("/handoff-to-same-workspace", ref);
      if (!result.ok && result.status !== "handoff_ready") {
        throw new Error(result.message || "移交失败");
      }
      const prompt = decodePrompt(result);
      if (!prompt) throw new Error("接管提示词为空");
      try {
        await takeoverPrompt(prompt, result.workspace_path || result.cwd || "");
        showToast("已移交到同工作目录的新对话");
      } catch (error) {
        const copied = await copyTextToClipboard(prompt);
        const reason = error instanceof Error ? error.message : "自动打开新对话失败";
        showToast(copied
          ? `移交文件已生成，${reason}，已复制接管提示`
          : `移交文件已生成，${reason}，请手动复制接管提示`);
      }
    } finally {
      actionButton.disabled = false;
      actionButton.textContent = previousText;
    }
  }

  function menuAnchorPosition(button) {
    const rect = button.getBoundingClientRect();
    return {
      left: Math.max(12, Math.min(rect.right - 180, window.innerWidth - 192)),
      top: Math.min(rect.bottom + 6, window.innerHeight - 12),
    };
  }

  function openSessionActionMenu(row, button, event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation?.();
    closeSessionActionMenus();

    const items = actionItems();
    if (!items.length) return;

    const overlay = document.createElement("div");
    overlay.className = actionMenuOverlayClass;
    overlay.addEventListener("click", (clickEvent) => {
      if (clickEvent.target === overlay) closeSessionActionMenus();
    }, true);

    const panel = document.createElement("div");
    panel.className = actionMenuPanelClass;
    const anchor = menuAnchorPosition(button);
    panel.style.left = `${anchor.left}px`;
    panel.style.top = `${anchor.top}px`;

    items.forEach((item) => {
      const actionButton = document.createElement("button");
      actionButton.type = "button";
      actionButton.className = "ai-strategist-session-action-item";
      actionButton.textContent = item.label;
      actionButton.addEventListener("click", async (itemEvent) => {
        itemEvent.preventDefault();
        itemEvent.stopPropagation();
        closeSessionActionMenus();
        try {
          if (item.kind === "move") {
            openMoveOverlay(row);
            return;
          }
          await createContextHandoff(row, actionButton);
        } catch (error) {
          showToast(error instanceof Error ? error.message : "操作失败");
        }
      }, true);
      panel.appendChild(actionButton);
    });

    overlay.appendChild(panel);
    document.body.appendChild(overlay);
  }

  function actionGroupFromRow(row) {
    return row.querySelector(`.${actionGroupClass}`);
  }

  function removeActionGroup(row) {
    actionGroupFromRow(row)?.remove();
  }

  function attachAction(row) {
    row.dataset.aiStrategistThreadRow = "true";
    if (!hasActionsEnabled()) {
      removeActionGroup(row);
      return;
    }

    const signature = JSON.stringify(actionItems().map((item) => item.kind));
    const existing = actionGroupFromRow(row);
    if (existing?.dataset.aiStrategistActionSignature === signature) return;

    removeActionGroup(row);
    const group = document.createElement("div");
    group.className = actionGroupClass;
    group.dataset.aiStrategistActionSignature = signature;

    const button = document.createElement("button");
    button.type = "button";
    button.className = actionButtonClass;
    button.textContent = "⋯";
    ["pointerdown", "mousedown", "mouseup", "touchstart"].forEach((eventName) => {
      button.addEventListener(eventName, (mouseEvent) => {
        mouseEvent.preventDefault();
        mouseEvent.stopPropagation();
        mouseEvent.stopImmediatePropagation?.();
      }, true);
    });
    button.addEventListener("click", (clickEvent) => openSessionActionMenu(row, button, clickEvent), true);

    group.appendChild(button);
    row.appendChild(group);
  }

  function installStyle() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      [data-ai-strategist-thread-row="true"] { position: relative; }
      .${actionGroupClass} {
        position: absolute;
        right: 28px;
        top: 50%;
        transform: translateY(-50%);
        display: flex;
        align-items: center;
        gap: 6px;
        opacity: 0;
        transition: opacity .12s ease;
        z-index: 24;
      }
      [data-ai-strategist-thread-row="true"]:hover .${actionGroupClass} { opacity: 1; }
      .${actionButtonClass} {
        border: 1px solid rgba(16,163,127,.35);
        border-radius: 8px;
        background: rgba(16,163,127,.10);
        color: #0f766e;
        font: 12px system-ui, sans-serif;
        line-height: 16px;
        padding: 2px 8px;
        cursor: pointer;
      }
      .${actionButtonClass}:disabled {
        opacity: .65;
        cursor: wait;
      }
      .${actionMenuOverlayClass}, .${moveOverlayClass} {
        position: fixed;
        inset: 0;
        z-index: 2147483200;
        background: rgba(15,23,42,.18);
      }
      .${actionMenuPanelClass} {
        position: fixed;
        min-width: 180px;
        max-width: min(280px, calc(100vw - 24px));
        border: 1px solid rgba(15,23,42,.14);
        border-radius: 12px;
        background: #ffffff;
        color: #111827;
        box-shadow: 0 18px 60px rgba(15,23,42,.25);
        padding: 6px;
      }
      .ai-strategist-session-action-item {
        display: block;
        width: 100%;
        border: 0;
        border-radius: 8px;
        background: transparent;
        text-align: left;
        padding: 9px 10px;
        cursor: pointer;
        font: 13px system-ui, sans-serif;
        color: #111827;
      }
      .ai-strategist-session-action-item:hover { background: #f3f4f6; }
      .${movePanelClass} {
        position: fixed;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
        width: min(420px, calc(100vw - 32px));
        max-height: min(560px, calc(100vh - 32px));
        overflow: hidden;
        border: 1px solid rgba(15,23,42,.14);
        border-radius: 12px;
        background: #ffffff;
        color: #111827;
        box-shadow: 0 18px 60px rgba(15,23,42,.25);
        font: 13px system-ui, sans-serif;
      }
      .ai-strategist-move-header { padding: 12px 14px; border-bottom: 1px solid #e5e7eb; }
      .ai-strategist-move-title { font-weight: 650; }
      .ai-strategist-move-list { max-height: 440px; overflow-y: auto; padding: 6px; }
      .ai-strategist-move-item {
        display: block;
        width: 100%;
        border: 0;
        border-radius: 8px;
        background: transparent;
        text-align: left;
        padding: 9px 10px;
        cursor: pointer;
      }
      .ai-strategist-move-item:hover { background: #f3f4f6; }
      .ai-strategist-move-item:disabled { opacity: .65; cursor: wait; }
      .ai-strategist-move-item-title { font-weight: 550; }
      .ai-strategist-move-item-path { margin-top: 2px; color: #6b7280; font-size: 12px; white-space: pre-wrap; word-break: break-all; }
      .${toastClass} {
        position: fixed;
        right: 18px;
        bottom: 18px;
        z-index: 2147483300;
        padding: 10px 12px;
        border-radius: 8px;
        background: #111827;
        color: white;
        font: 13px system-ui, sans-serif;
        box-shadow: 0 8px 30px rgba(0,0,0,.25);
        max-width: min(420px, calc(100vw - 24px));
        white-space: pre-wrap;
      }
    `;
    document.head.appendChild(style);
  }

  function scan() {
    installStyle();
    enablePluginEntry();
    sessionRows().forEach((row) => attachAction(row));
    applyProjectMoveProjection();
    unlockMustInstallPluginButtons();
  }

  scan();
  window.__aiStrategistEnhancerObserver?.disconnect?.();
  let scanTimer = null;
  window.__aiStrategistEnhancerObserver = new MutationObserver(() => {
    if (scanTimer) return;
    scanTimer = setTimeout(() => {
      scanTimer = null;
      scan();
    }, 60);
  });
  window.__aiStrategistEnhancerObserver.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
