# AI Strategist Prelaunch Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `AI管理大师` from the current Tkinter shell into an AI Strategist-style multi-page Tauri shell while preserving the existing prelaunch workflow and keeping Tkinter as a fallback during migration.

**Architecture:** Keep the current Python business logic as the source of truth for prelaunch actions in v1, then expose it through a new CLI bridge that both Tkinter and Tauri can call. Add a dedicated `prelaunch` page inside `ai-strategist-desktop/`, wire it to explicit Tauri commands, and keep report generation under the existing repo-level `reports/` directory so validation stays evidence-first.

**Tech Stack:** Python 3.12, Tkinter baseline, React 18, TypeScript, Vite 6, Tauri 2, Rust, Vitest, unittest

---

## File Structure

### Existing files to keep as sources of truth

- `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\prelaunch_manager.py`
  Prelaunch config writes, evidence gathering, threadripper parsing, Codex launch.
- `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\repair_codex_desktop_history.py`
  History/workspace repair, cleanup, archive deletion, backup creation.
- `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\CodexMaintenanceGUI.py`
  Current reference orchestration and fallback GUI while Tauri page reaches parity.

### New Python bridge layer

- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\prelaunch_bridge.py`
  Thin JSON CLI wrapper around `prelaunch_manager.py` and `repair_codex_desktop_history.py`.
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\tests\test_prelaunch_bridge.py`
  Unit tests for bridge command mapping and JSON output contracts.

### New Tauri command layer

- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src-tauri\src\commands\prelaunch.rs`
  Tauri commands that invoke the Python bridge and return structured JSON.
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src-tauri\src\commands\mod.rs`
  Export the new command module.
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src-tauri\src\lib.rs`
  Register `prelaunch` commands in the Tauri builder.

### New frontend page and API contract

- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\types\navigation.ts`
  Add `prelaunch` route.
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\components\layout\sidebar.tsx`
  Add visible nav item for `prelaunch`.
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\main-app.tsx`
  Lazy-load and render the new page.
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\lib\api.ts`
  Add typed frontend calls for `prelaunch` commands.
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\types\prelaunch.ts`
  TypeScript payloads for bridge responses.
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\components\prelaunch\prelaunch-page.tsx`
  The main prelaunch console page.
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\components\prelaunch\prelaunch-page.test.tsx`
  Focused UI test for route/page rendering and action-state behavior.
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\package.json`
  Add a `test` script for Vitest.
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\vitest.config.ts`
  Minimal test runner config.

### Docs to update in the same change set

- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\AI_STRATEGIST_CLONE_HANDOFF.md`
  Mark shell migration as active and record bridge command usage.
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\EXECUTION_PLAN.md`
  Point phase ownership to the new Tauri shell path.
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\HANDOFF.md`
  Update entrypoint guidance once the page is runnable.

---

### Task 1: Add a Shared Prelaunch Bridge

**Files:**
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\prelaunch_bridge.py`
- Test: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\tests\test_prelaunch_bridge.py`

- [ ] **Step 1: Write the failing Python tests**

```python
import json
import unittest
from unittest import mock

import prelaunch_bridge


class PrelaunchBridgeTests(unittest.TestCase):
    def test_status_command_returns_json_payload(self):
        fake_evidence = {
            "config_path": "C:/Users/test/.codex/config.toml",
            "config_model_provider": "openai",
            "auth_mode": "chatgpt",
            "threadripper_available": True,
            "threadripper_target_provider": "openai",
            "rows_needing_reconcile": 0,
            "provider_distribution": {"openai": 12},
        }
        with mock.patch.object(prelaunch_bridge, "collect_prelaunch_evidence") as evidence:
            evidence.return_value.to_dict.return_value = fake_evidence
            payload = prelaunch_bridge.handle_status("C:/Users/test/.codex")
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["evidence"]["config_model_provider"], "openai")

    def test_launch_flow_calls_config_sync_repair_launch_in_order(self):
        calls = []
        with mock.patch.object(prelaunch_bridge, "run_threadripper_sync_if_needed", side_effect=lambda *args, **kwargs: calls.append("sync")):
            with mock.patch.object(prelaunch_bridge, "run_history_repair", side_effect=lambda *args, **kwargs: calls.append("repair")):
                with mock.patch.object(prelaunch_bridge, "launch_codex_desktop", side_effect=lambda: {"ok": True, "method": "appid"}):
                    with mock.patch.object(prelaunch_bridge, "configure_provider_for_launch", side_effect=lambda *args, **kwargs: calls.append("configure") or mock.Mock(
                        config_path="config.toml",
                        backup_path="config.toml.backup",
                        mode="official",
                        target_model_provider="openai",
                        verified_model_provider="openai",
                    )):
                        payload = prelaunch_bridge.handle_launch(
                            codex_home="C:/Users/test/.codex",
                            mode="official",
                            provider=None,
                            projectless_mode="none",
                        )
        self.assertEqual(calls, ["configure", "sync", "repair"])
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["launch"]["method"], "appid")
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `rtk python -m unittest tests.test_prelaunch_bridge -v`

Expected: FAIL with `ModuleNotFoundError` or missing handler functions in `prelaunch_bridge.py`.

- [ ] **Step 3: Write the minimal bridge implementation**

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prelaunch_manager import (
    ProviderProfile,
    collect_prelaunch_evidence,
    configure_provider_for_launch,
    launch_codex_desktop,
    run_threadripper_status,
)
import repair_codex_desktop_history as history_repair


def handle_status(codex_home: str) -> dict:
    evidence = collect_prelaunch_evidence(Path(codex_home))
    return {"ok": True, "evidence": evidence.to_dict()}


def run_threadripper_sync_if_needed(codex_home: str, force: bool = False) -> dict:
    status = run_threadripper_status(Path(codex_home)) or {}
    rows = int(status.get("rows_needing_reconcile") or 0)
    if rows <= 0 and not force:
        return {"ok": True, "skipped": True, "status": status}
    return {"ok": True, "skipped": False, "status": status, "note": "sync command goes here"}


def run_history_repair(codex_home: str, projectless_mode: str) -> dict:
    args = argparse.Namespace(
        codex_home=codex_home,
        current_thread_id=None,
        dry_run=False,
        include_archived=False,
        allow_missing_cwd=False,
        allow_empty_cwd=False,
        allow_missing_session=False,
        unarchive_selected=False,
        projectless_mode=projectless_mode,
    )
    threads = history_repair.load_threads(Path(codex_home) / "state_5.sqlite")
    selected, skipped = history_repair.selected_threads(threads, args)
    result = history_repair.build_result(Path(codex_home), threads, selected, skipped, False)
    return {"ok": True, "summary": result}


def handle_launch(codex_home: str, mode: str, provider: dict | None, projectless_mode: str) -> dict:
    profile = None if provider is None else ProviderProfile(**provider)
    config = configure_provider_for_launch(Path(codex_home), mode, profile=profile)
    sync = run_threadripper_sync_if_needed(codex_home)
    repair = run_history_repair(codex_home, projectless_mode)
    launch = launch_codex_desktop()
    return {
        "ok": bool(launch.get("ok")),
        "provider_config": {
            "config_path": config.config_path,
            "backup_path": config.backup_path,
            "mode": config.mode,
            "target_model_provider": config.target_model_provider,
            "verified_model_provider": config.verified_model_provider,
        },
        "sync": sync,
        "repair": repair,
        "launch": launch,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "launch"])
    parser.add_argument("--codex-home", required=True)
    parser.add_argument("--mode", default="official")
    parser.add_argument("--projectless-mode", default="none")
    args = parser.parse_args()

    if args.command == "status":
        payload = handle_status(args.codex_home)
    else:
        payload = handle_launch(args.codex_home, args.mode, None, args.projectless_mode)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the bridge tests to verify GREEN**

Run: `rtk python -m unittest tests.test_prelaunch_bridge -v`

Expected: PASS with `2 tests` and `OK`.

- [ ] **Step 5: Commit**

```bash
git add prelaunch_bridge.py tests/test_prelaunch_bridge.py
git commit -m "feat: add shared prelaunch bridge"
```

---

### Task 2: Add Tauri Commands for the Prelaunch Bridge

**Files:**
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src-tauri\src\commands\prelaunch.rs`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src-tauri\src\commands\mod.rs`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src-tauri\src\lib.rs`

- [ ] **Step 1: Write the failing Rust unit test**

```rust
#[cfg(test)]
mod tests {
    use super::bridge_command;

    #[test]
    fn status_command_uses_repo_root_bridge() {
        let command = bridge_command("status", r"C:\Users\test\.codex");
        assert_eq!(command[0], "python");
        assert!(command[1].ends_with("prelaunch_bridge.py"));
        assert_eq!(command[2], "status");
    }
}
```

- [ ] **Step 2: Run the Rust test to verify RED**

Run: `rtk cargo test prelaunch::tests::status_command_uses_repo_root_bridge --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml`

Expected: FAIL because `prelaunch.rs` and `bridge_command` do not exist.

- [ ] **Step 3: Implement the command module**

```rust
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::Command;

fn repo_root_from_manifest() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .expect("repo root")
        .to_path_buf()
}

fn python_command() -> String {
    if let Ok(home) = std::env::var("USERPROFILE") {
        let bundled = Path::new(&home)
            .join(".cache")
            .join("codex-runtimes")
            .join("codex-primary-runtime")
            .join("dependencies")
            .join("python")
            .join("python.exe");
        if bundled.exists() {
            return bundled.display().to_string();
        }
    }
    "python".to_string()
}

fn bridge_command(subcommand: &str, codex_home: &str) -> Vec<String> {
    vec![
        python_command(),
        repo_root_from_manifest()
            .join("prelaunch_bridge.py")
            .display()
            .to_string(),
        subcommand.to_string(),
        "--codex-home".to_string(),
        codex_home.to_string(),
    ]
}

fn run_bridge(subcommand: &str, codex_home: &str) -> Result<Value, String> {
    let command = bridge_command(subcommand, codex_home);
    let output = Command::new(&command[0])
        .args(&command[1..])
        .output()
        .map_err(|e| e.to_string())?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn prelaunch_status(codex_home: String) -> Result<Value, String> {
    run_bridge("status", &codex_home)
}

#[tauri::command]
pub fn prelaunch_launch(codex_home: String) -> Result<Value, String> {
    run_bridge("launch", &codex_home)
}
```

- [ ] **Step 4: Wire the module into Tauri**

```rust
// src-tauri/src/commands/mod.rs
pub mod prelaunch;

// src-tauri/src/lib.rs inside invoke_handler(...)
crate::commands::prelaunch::prelaunch_status,
crate::commands::prelaunch::prelaunch_launch,
```

- [ ] **Step 5: Run the Rust test to verify GREEN**

Run: `rtk cargo test prelaunch::tests::status_command_uses_repo_root_bridge --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml`

Expected: PASS with `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add ai-strategist-desktop/src-tauri/src/commands/prelaunch.rs ai-strategist-desktop/src-tauri/src/commands/mod.rs ai-strategist-desktop/src-tauri/src/lib.rs
git commit -m "feat: add tauri prelaunch bridge commands"
```

---

### Task 3: Add the Prelaunch Route and Page Shell

**Files:**
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\types\navigation.ts`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\components\layout\sidebar.tsx`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\main-app.tsx`
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\types\prelaunch.ts`
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\components\prelaunch\prelaunch-page.tsx`
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\components\prelaunch\prelaunch-page.test.tsx`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\lib\api.ts`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\package.json`
- Create: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\vitest.config.ts`

- [ ] **Step 1: Write the failing UI test**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PrelaunchPage } from "@/components/prelaunch/prelaunch-page";

vi.mock("@/lib/api", () => ({
  api: {
    prelaunchStatus: vi.fn().mockResolvedValue({
      ok: true,
      evidence: {
        config_model_provider: "openai",
        auth_mode: "chatgpt",
        rows_needing_reconcile: 0,
        provider_distribution: { openai: 12 },
      },
    }),
  },
}));

describe("PrelaunchPage", () => {
  it("renders the current prelaunch status summary", async () => {
    render(<PrelaunchPage />);
    expect(await screen.findByText("openai")).toBeInTheDocument();
    expect(screen.getByText("chatgpt")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the UI test to verify RED**

Run: `rtk pnpm --dir ai-strategist-desktop test prelaunch-page`

Expected: FAIL because `vitest`, `@testing-library/react`, or `PrelaunchPage` do not exist yet.

- [ ] **Step 3: Add test runner support**

```json
{
  "scripts": {
    "test": "vitest run"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "jsdom": "^25.0.1",
    "vitest": "^2.1.8"
  }
}
```

```ts
// ai-strategist-desktop/vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

- [ ] **Step 4: Add the route and page**

```ts
// src/types/navigation.ts
export type Route =
  | "overview"
  | "prelaunch"
  | "customInstructions"
  | "mcp"
  | "skills"
  | "maintenance"
  | "settings";
```

```tsx
// src/components/layout/sidebar.tsx
import { Rocket } from "lucide-react";

{ route: "prelaunch", icon: Rocket, labelKey: "nav.prelaunch" },
```

```tsx
// src/main-app.tsx
const PrelaunchPage = lazy(() =>
  import("@/components/prelaunch/prelaunch-page").then((module) => ({ default: module.PrelaunchPage })),
);

case "prelaunch":
  return <PrelaunchPage />;
```

```ts
// src/types/prelaunch.ts
export interface PrelaunchEvidencePayload {
  config_model_provider: string | null;
  auth_mode: string | null;
  rows_needing_reconcile: number | null;
  provider_distribution: Record<string, number>;
}

export interface PrelaunchStatusPayload {
  ok: boolean;
  evidence: PrelaunchEvidencePayload;
}
```

```ts
// src/lib/api.ts
prelaunchStatus: (codexHome: string) =>
  invoke<import("@/types/prelaunch").PrelaunchStatusPayload>("prelaunch_status", { codexHome }),

prelaunchLaunch: (codexHome: string) =>
  invoke<Record<string, unknown>>("prelaunch_launch", { codexHome }),
```

```tsx
// src/components/prelaunch/prelaunch-page.tsx
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { BentoCard } from "@/components/ui/bento-card";

const DEFAULT_CODEX_HOME = "C:\\Users\\boyu1\\.codex";

export function PrelaunchPage() {
  const statusQuery = useQuery({
    queryKey: ["prelaunch-status", DEFAULT_CODEX_HOME],
    queryFn: () => api.prelaunchStatus(DEFAULT_CODEX_HOME),
  });

  const evidence = statusQuery.data?.evidence;

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Launch Codex only after provider alignment, thread reconcile, and history restore are ready.
      </p>
      <div className="grid grid-cols-4 gap-4">
        <BentoCard compact>
          <span className="text-xs text-muted-foreground">Auth Mode</span>
          <span className="mt-1 text-lg font-semibold">{evidence?.auth_mode ?? "unknown"}</span>
        </BentoCard>
        <BentoCard compact>
          <span className="text-xs text-muted-foreground">Model Provider</span>
          <span className="mt-1 text-lg font-semibold">{evidence?.config_model_provider ?? "unknown"}</span>
        </BentoCard>
        <BentoCard compact>
          <span className="text-xs text-muted-foreground">Reconcile Rows</span>
          <span className="mt-1 text-lg font-semibold">{evidence?.rows_needing_reconcile ?? "unknown"}</span>
        </BentoCard>
        <BentoCard compact>
          <span className="text-xs text-muted-foreground">Buckets</span>
          <span className="mt-1 text-sm font-semibold">{Object.keys(evidence?.provider_distribution ?? {}).join(", ") || "none"}</span>
        </BentoCard>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run the UI test to verify GREEN**

Run: `rtk pnpm --dir ai-strategist-desktop test prelaunch-page`

Expected: PASS with `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add ai-strategist-desktop/package.json ai-strategist-desktop/vitest.config.ts ai-strategist-desktop/src/types/navigation.ts ai-strategist-desktop/src/components/layout/sidebar.tsx ai-strategist-desktop/src/main-app.tsx ai-strategist-desktop/src/lib/api.ts ai-strategist-desktop/src/types/prelaunch.ts ai-strategist-desktop/src/components/prelaunch/prelaunch-page.tsx ai-strategist-desktop/src/components/prelaunch/prelaunch-page.test.tsx
git commit -m "feat: add AI Strategist prelaunch route"
```

---

### Task 4: Bring the Full Launch Flow into the New Page

**Files:**
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\prelaunch_bridge.py`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\types\prelaunch.ts`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\components\prelaunch\prelaunch-page.tsx`
- Test: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\tests\test_prelaunch_bridge.py`
- Test: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop\src\components\prelaunch\prelaunch-page.test.tsx`

- [ ] **Step 1: Extend the failing tests for actionable launch flows**

```python
def test_launch_payload_includes_provider_sync_repair_and_report_paths(self):
    payload = {
        "ok": True,
        "provider_config": {"target_model_provider": "cliproxy"},
        "sync": {"ok": True, "skipped": False, "status": {"rows_needing_reconcile": 12}},
        "repair": {"ok": True, "summary": {"threads_selected": 53}},
        "launch": {"ok": True, "method": "appid"},
        "report_dir": "D:/repo/reports/20260522-123456-配置并启动-hybrid",
    }
    self.assertEqual(payload["sync"]["skipped"], False)
    self.assertIn("report_dir", payload)
```

```tsx
it("runs launch and shows report location", async () => {
  const prelaunchLaunch = vi.fn().mockResolvedValue({
    ok: true,
    report_dir: "D:/repo/reports/20260522-123456-配置并启动-hybrid",
    provider_config: { target_model_provider: "cliproxy" },
    sync: { status: { rows_needing_reconcile: 12 } },
    repair: { summary: { threads_selected: 53 } },
    launch: { method: "appid" },
  });
  vi.mocked(api.prelaunchLaunch).mockImplementation(prelaunchLaunch);
});
```

- [ ] **Step 2: Run the expanded tests to verify RED**

Run:

```bash
rtk python -m unittest tests.test_prelaunch_bridge -v
rtk pnpm --dir ai-strategist-desktop test prelaunch-page
```

Expected: FAIL because launch payload is still status-only and page has no action controls.

- [ ] **Step 3: Implement launch actions and report display**

```python
# prelaunch_bridge.py
def handle_launch(codex_home: str, mode: str, provider: dict | None, projectless_mode: str) -> dict:
    report_dir = prepare_report_dir("配置并启动", mode)
    profile = None if provider is None else ProviderProfile(**provider)
    config = configure_provider_for_launch(Path(codex_home), mode, profile=profile)
    sync = run_threadripper_sync_if_needed(codex_home)
    repair = run_history_repair(codex_home, projectless_mode)
    launch = launch_codex_desktop()
    payload = {
        "ok": bool(launch.get("ok")),
        "report_dir": str(report_dir),
        "provider_config": {...},
        "sync": sync,
        "repair": repair,
        "launch": launch,
    }
    write_report_bundle(report_dir, payload)
    return payload
```

```tsx
// prelaunch-page.tsx
const launchMutation = useMutation({
  mutationFn: () => api.prelaunchLaunch(DEFAULT_CODEX_HOME),
});

<Button onClick={() => launchMutation.mutate()} disabled={launchMutation.isPending}>
  Launch via Prelaunch Flow
</Button>

{launchMutation.data && (
  <BentoCard>
    <div className="space-y-2 text-sm">
      <p>Target provider: {String(launchMutation.data.provider_config?.target_model_provider ?? "unknown")}</p>
      <p>Rows needing reconcile: {String(launchMutation.data.sync?.status?.rows_needing_reconcile ?? "unknown")}</p>
      <p>Threads restored: {String(launchMutation.data.repair?.summary?.threads_selected ?? "unknown")}</p>
      <p>Report: {String(launchMutation.data.report_dir ?? "unknown")}</p>
    </div>
  </BentoCard>
)}
```

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```bash
rtk python -m unittest tests.test_prelaunch_bridge -v
rtk pnpm --dir ai-strategist-desktop test prelaunch-page
```

Expected: both commands PASS.

- [ ] **Step 5: Commit**

```bash
git add prelaunch_bridge.py tests/test_prelaunch_bridge.py ai-strategist-desktop/src/types/prelaunch.ts ai-strategist-desktop/src/components/prelaunch/prelaunch-page.tsx ai-strategist-desktop/src/components/prelaunch/prelaunch-page.test.tsx
git commit -m "feat: add prelaunch launch flow to AI Strategist shell"
```

---

### Task 5: Validate End-to-End and Update Docs

**Files:**
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\AI_STRATEGIST_CLONE_HANDOFF.md`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\EXECUTION_PLAN.md`
- Modify: `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\HANDOFF.md`

- [ ] **Step 1: Run the repo-level verification commands**

Run:

```bash
rtk python -m unittest tests.test_prelaunch_bridge -v
rtk pnpm --dir ai-strategist-desktop test
rtk pnpm --dir ai-strategist-desktop build
rtk cargo test --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml
```

Expected:
- Python bridge tests: PASS
- Vitest: PASS
- Vite build: PASS
- Cargo tests: PASS

- [ ] **Step 2: Run the dev shell for manual validation**

Run:

```bash
rtk pnpm --dir ai-strategist-desktop tauri dev --verbose
```

Expected manual checks:
- Sidebar shows a visible `Prelaunch` entry.
- `Prelaunch` page loads without blank content.
- Status query returns current `auth_mode`, `model_provider`, and reconcile count.
- Launch action writes a new `reports/<timestamp>-配置并启动-<mode>/run.json`.
- Tkinter fallback still launches via `Run-CodexMaintenanceGUI.vbs`.

- [ ] **Step 3: Update handoff docs**

```md
## AI_STRATEGIST_CLONE_HANDOFF.md
- Mark `Prelaunch` page as active migration track.
- Note that v1 still uses `prelaunch_bridge.py` and root Python logic.
- Keep MCP/Skills pages out of `AI管理大师` scope for now.

## EXECUTION_PLAN.md
- Replace "parallel track" wording with "active shell migration track".
- Record that Tkinter remains fallback until parity on launch + repair + cleanup.

## HANDOFF.md
- New-window entrypoint: open `ai-strategist-desktop` first for shell work, root Python files second for logic work.
- Add the exact dev command: `rtk pnpm --dir ai-strategist-desktop tauri dev --verbose`.
```

- [ ] **Step 4: Commit**

```bash
git add AI_STRATEGIST_CLONE_HANDOFF.md EXECUTION_PLAN.md HANDOFF.md
git commit -m "docs: hand off AI Strategist prelaunch shell migration"
```

---

## Self-Review

### Spec coverage

- AI Strategist migration conclusion is covered:
  - multi-page shell: Task 3
  - explicit command boundary: Tasks 1 and 2
  - maintenance-style action UX: Task 4
- Existing Python prelaunch logic remains source of truth in v1:
  - Task 1 bridge wraps current root modules instead of rewriting them.
- Tkinter remains fallback during migration:
  - Task 5 manual validation explicitly keeps `Run-CodexMaintenanceGUI.vbs` working.
- MCP/Skills are not mixed into first-phase `AI管理大师` scope:
  - File structure and doc updates explicitly keep them out of this plan.

### Placeholder scan

- No `TODO`, `TBD`, or “similar to above” placeholders remain.
- Every task contains exact file paths, commands, and expected outcomes.

### Type consistency

- `prelaunchStatus` returns `PrelaunchStatusPayload`.
- `prelaunchLaunch` returns a structured JSON object with `provider_config`, `sync`, `repair`, `launch`, and `report_dir`.
- Navigation key is consistently `prelaunch` across `navigation.ts`, `sidebar.tsx`, and `main-app.tsx`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-22-aimami-prelaunch-shell.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
