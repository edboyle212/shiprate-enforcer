# GitHub setup (Shiprate Enforcer)

Source of truth until GitHub exists: `origin/cursor/mvp-finish-787e` on Cursor Origin (`edward-boyle/tmp-73c4e119099081cc`).

## One-time: authenticate GitHub CLI

```bash
gh auth login
```

Or set `GH_TOKEN` with a classic PAT (`repo` scope).

## Create repo and push

From a clone at branch `cursor/mvp-finish-787e`:

```bash
gh repo create shiprate-enforcer --private --description "Multi-tenant parcel rate compliance (Shiprate Enforcer)" --source=. --remote=github --push
```

If the repo already exists:

```bash
git remote add github git@github.com:edward-boyle/shiprate-enforcer.git
git push -u github cursor/mvp-finish-787e:main
```

## Open PR (optional)

```bash
gh pr create --base main --head cursor/mvp-finish-787e --title "Shiprate Enforcer MVP" --draft
```
