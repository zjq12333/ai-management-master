# AI Strategist Enhancer Feature Matrix

Updated: 2026-05-25

## Purpose

This matrix does not restart product analysis from zero. It maps Codex++ capabilities onto the already-confirmed AI Strategist direction:

- `启动与修复` remains the mainline
- enhancer work starts as a controlled second track
- workspace/session attribution remains the source of truth
- provider is diagnostic or launch-channel metadata, not the ownership rule

## Decision Rules

Classification used in this document:

- `Now`: fits the current AI Strategist product boundary and can be planned immediately
- `Later`: useful, but should wait until mainline and productization are more stable
- `Do not import`: conflicts with current product logic or creates avoidable fragility

Implementation labels:

- `Desktop-owned`: can be implemented inside AI Strategist UI + Tauri/Rust/Python backend
- `Injection-needed`: only worth doing if the user must interact inside the Codex window itself
- `Hybrid`: start desktop-owned, optionally add injection later for convenience

## Matrix

| Codex++ capability | User value | Fit for AI Strategist | Why | Recommended implementation |
|---|---|---:|---|---|
| Markdown export from rollout | Medium | `Later` | Not part of the current enhancer scope; can return later as a low-risk read-only feature | `Desktop-owned` if revisited |
| Session delete | Medium | `Later` | Not part of the current enhancer scope; keep it out of the first implementation batch | `Desktop-owned` if revisited |
| Delete undo | Medium | `Later` | Only meaningful if delete ever returns; not part of the current plan | `Desktop-owned` if revisited |
| Session move / workspace reassignment | High | `Now` | Strongly aligned with AI Strategist's workspace/session ownership model | `Desktop-owned` |
| Archived-session handling | Medium | `Now` | Already adjacent to repair flow; same safety model | `Desktop-owned` |
| Preview before mutation | High | `Now` | Needed for trust and safe productization | `Desktop-owned` |
| Batch operations on selected sessions | Medium | `Later` | Useful after single-session flows are stable | `Desktop-owned` |
| Timeline panel in Codex UI | Medium | `Later` | Experience enhancement, not mainline-critical | `Injection-needed` |
| Hover delete button inside Codex list | Medium | `Later` | Nice convenience, but not required if AI Strategist provides session actions | `Injection-needed` |
| Backend/helper status indicator | Medium | `Later` | Useful if injection stack exists, not required for initial value | `Hybrid` |
| Plugin entry unlock | Medium | `Later` | Valuable for some users, but outside current launch/repair core | `Injection-needed` |
| Force install unavailable plugins | Low to Medium | `Later` | Higher maintenance and UI-coupling cost | `Injection-needed` |
| Provider sync | Low | `Do not import` as a mainline feature | Conflicts with current ownership model if elevated beyond diagnostics | Only keep compatible metadata inspection if needed |
| Full CDP launcher stack as the default architecture | Low | `Do not import` now | Adds fragility before the productized runtime foundation is done | Consider only after proven feature need |
| Watcher auto-takeover | Low | `Later` | Operational convenience, not phase-one enhancer value | `Desktop-owned` |
| Release updater / external launcher extras | Low | `Later` | Productization-adjacent, not core enhancer MVP | `Desktop-owned` |

## Recommended Phase-1 Enhancer Set

The first enhancer batch should be:

1. Session workspace reassignment

This feature has the best mix of:

- direct user value
- strong fit with existing local data logic
- low dependence on Codex UI internals
- clear safety boundaries

## Why These Three Win

### Workspace reassignment

- Most consistent with the product's core truth: conversations belong to workspace/session, not provider buckets
- Helps fix historical misplacement without restoring provider-centric logic
- Reuses the same metadata layers already manipulated by repair

## Functional Requirements by Priority

### 1. Workspace reassignment

Minimum requirement:

- preview current workspace and target workspace
- update `threads.cwd`
- update rollout `session_meta.cwd`
- write a report of what changed

Recommended additions:

- optional refresh of related global-state hints
- choose existing workspace from known list
- bulk move later

## Safety Boundary

Enhancer functions must not weaken the mainline safety model.

Required rules:

1. Block mutation while Codex Desktop or codex CLI is running.
2. Always create backups before workspace reassignment.
3. Keep mutation scope explicit:
   - workspace reassignment only touches the selected session's ownership metadata
4. Always emit a report bundle for destructive or metadata-changing actions.
5. Never reintroduce provider-based ownership as an automatic repair rule.

## Recommendation Summary

AI Strategist should absorb Codex++ selectively.

It should not become "Codex++ rewritten inside Tauri". The right first move is:

- keep launch/repair as the mainline
- add a tightly scoped desktop-owned local data operation
- postpone UI injection until there is a feature that truly cannot deliver value without it
