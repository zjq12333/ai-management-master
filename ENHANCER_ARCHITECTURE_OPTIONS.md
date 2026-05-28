# AI Strategist Enhancer Architecture Options

Updated: 2026-05-25

## Problem Statement

AI Strategist now has two parallel obligations:

1. keep `启动与修复` stable and productizable
2. start delivering enhancer value inspired by Codex++

The architecture choice is not "can injection work". It is "what is the minimum architecture that delivers the first enhancer batch without destabilizing the product".

## Option A: Desktop-owned local-data architecture

### Shape

- AI Strategist UI owns the enhancer entry points
- Tauri commands call product-controlled backend logic
- backend reads and mutates local Codex data directly
- no dependence on Codex renderer DOM structure

### Best-fit features

- workspace reassignment
- archive/unarchive helpers
- preview/report/audit flows

### Advantages

- aligned with existing repo structure
- lower UI fragility
- easier to test
- easier to bundle into a productized runtime
- keeps mutations explicit and auditable

### Disadvantages

- user does not act directly inside the Codex conversation list
- session browsing UX must be built inside AI Strategist
- some "native-feeling" convenience enhancements arrive later

### Verdict

This should be the phase-one architecture.

## Option B: CDP injection architecture

### Shape

- external launcher starts Codex with remote-debugging flags
- helper server runs beside AI Strategist
- injected script augments Codex renderer DOM
- UI actions inside Codex call local helper endpoints

### Best-fit features

- hover delete buttons in existing Codex list
- timeline embedded in Codex UI
- plugin unlock or UI patching
- live status badge inside Codex window

### Advantages

- strongest in-window user experience
- can patch missing controls exactly where the user expects them
- proven reference exists in Codex++

### Disadvantages

- high coupling to Codex UI internals
- more moving parts: debug port, bridge, helper server, selectors
- larger productization burden
- greater maintenance cost after upstream Codex UI changes
- easy to let enhancer concerns swallow mainline reliability work

### Verdict

Do not make this the first enhancer foundation. Keep it as a later targeted capability.

## Option C: Hybrid staged architecture

### Shape

- phase one uses desktop-owned local-data operations
- later, selected actions get optional in-window injection affordances
- local backend remains the source of mutation truth

### Best-fit features

- workspace move: backend-owned, maybe later with contextual entry point
- timeline/status/plugin unlock: injection-only later

### Advantages

- preserves a stable backend contract
- allows future convenience UX without rewriting data logic
- avoids binding product correctness to injected DOM behavior

### Disadvantages

- requires disciplined boundaries now
- needs clear separation between backend actions and UI affordances

### Verdict

This is the long-term architecture. Use Option A immediately, with Option C as the roadmap.

## Technical Recommendation by Feature

| Feature | Recommended architecture | Why |
|---|---|---|
| Workspace reassignment | `Option A` | Directly tied to AI Strategist's ownership model |
| Timeline | `Option B` or later `Option C` | Mostly UI augmentation value |
| Plugin unlock | `Option B` | Depends on Codex UI and behavior patching |
| Provider compatibility indicators | `Option A` | Already adjacent to current status/evidence model |

## Implementation Boundary Recommendation

Even if injection is added later, the mutation authority should stay in AI Strategist backend.

That means:

- injected UI should request actions
- backend should validate, back up, mutate, and report
- injected code should not become the main place where business rules live

This protects:

- testability
- productization
- rollback safety
- future refactor freedom

## Productization Impact

Option A fits current productization work much better than Option B.

Reason:

- runtime resolver work is already active
- mainline is already crossing Rust and Python
- clean-machine delivery is already a known gap
- adding CDP infrastructure before runtime control is finished increases risk on both tracks

## Recommended Route

Adopt this sequence:

1. build enhancer backend contracts and desktop UI
2. ship workspace reassignment
5. only then reassess whether in-window injection adds enough extra value

## Final Choice

For the current phase:

- choose `Option A` as the implementation route
- define `Option C` as the roadmap
- explicitly defer `Option B` as a default foundation

That keeps AI Strategist on its own product line instead of drifting into a fragile Codex++ clone.
