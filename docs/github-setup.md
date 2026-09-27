# GitHub setup (Shiprate Enforcer)

Source of truth until GitHub exists: `origin/cursor/mvp-finish-787e` on Cursor Origin (`edward-boyle/tmp-73c4e119099081cc`).

## One-time: authenticate GitHub CLI

```bash
gh auth login
```

Or set `GH_TOKEN` with a classic PAT (`repo` scope).

## Create repo and push

From a clone at branch `main`:

```bash
gh auth login   # once, on your Mac
git remote add github https://github.com/edboyle212/shiprate-enforcer.git
git push -u github main
```

**Cloud Project agents:** add `GH_TOKEN` (fine-grained PAT, Contents read/write) to the Project environment, then the coordinator can `git push github main` from the cloud workspace.

**Transfer without Origin clone:** a `shiprate-main.bundle` of `main` may be in Project Context; on your Mac:

```bash
gh repo clone edboyle212/shiprate-enforcer ~/Projects/shiprate-enforcer
cd ~/Projects/shiprate-enforcer
git pull /path/to/shiprate-main.bundle main
git push origin main
```

## Open PR (optional)

```bash
gh pr create --base main --head cursor/mvp-finish-787e --title "Shiprate Enforcer MVP" --draft
```
