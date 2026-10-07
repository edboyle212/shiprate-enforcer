# Agent workflow (Shiprate Enforcer)

This repo is developed under the **Shiprate Enforcer** Cursor Project. Canonical agent rules live in **Project Context**; this file is the GitHub mirror for contributors and local-only chats.

## Where to work

- **Direction:** Shiprate Enforcer **Project** chat (cloud orchestrator) — not a parallel repo-only “brain” chat.
- **Code:** Mac self-hosted worker at `~/Projects/shiprate-enforcer` by default.
- **Sync:** GitHub `main` is the hub between Mac and cloud (`docs/github-setup.md`, `docs/cursor-connect-github.md`).

## Roles

| Role | Runs where | May change product code? |
|------|------------|---------------------------|
| Orchestrator | Cloud Project | No — plans and delegates |
| Builder | Mac self-hosted | Yes |
| Tester | Mac self-hosted (different model) | Test fixes only |
| Subagent | Scoped | Per task |

**Builder ≠ Tester model** on the same work slice (defaults in Project `preferences.md`: Builder `composer-2.5`, Tester `gemini-3.8-flash-medium`).

## Orchestrator flow

1. Builder implements on Mac (self-hosted worker).
2. Tester verifies (`docs/testing.md`) with a **different** model.
3. On failure: Builder fixes → new Tester turn.
4. Cloud VM workers only when Edward opts in or Mac is unavailable.

## Read before coding

| Topic | Repo doc |
|-------|----------|
| MVP spec, invariants | `docs/shiprate-mvp-spec.md` |
| Partner variables | `docs/partner-variable-sheet.md` |
| ETL file drop | `docs/etl-drop-contract.md` |
| Wizards | `docs/wizard-field-lists.md` |
| Tests | `docs/testing.md` |

Project Context (Cursor) holds extended docs: `project-agent-model.md`, `local-first-project-setup.md`, `github-sync-workflow.md`, orchestrator convention, and **Notes** for status.

## Product invariants

- Rating engine is source of truth (minor units).
- No auto-send disputes; AI assists mapping only.
- RLS / tenant isolation on all tenant data.

Agent-facing rules in-repo: `.cursor/rules/shiprate-project.mdc`.
