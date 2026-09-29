# GitHub sync hub (Local Mac ↔ Cloud)

**Source of truth:** [`edboyle212/shiprate-enforcer`](https://github.com/edboyle212/shiprate-enforcer), branch **`main`**.

| Surface | What to use |
|---------|-------------|
| **Mac** | Clone or `~/Projects/shiprate-enforcer`; `git pull` / `git push` **`origin`** (GitHub). |
| **Cloud agents** | Remote **`github`** → same repo; after Mac pushes, `git fetch github && git merge github/main`. Always `git push origin` (Cursor Project mirror). |
| **Cursor Project UI** | Optional: connect the Project to GitHub so new agents clone from GitHub instead of only the mirror. |

You do **not** need github.com for day-to-day work — Terminal and agents are enough.

## One-time: Cursor Project → GitHub (desktop)

Cloud agents **cannot** click **Connect repository** in the UI.

1. Open **Cursor** → **Projects** → **Shiprate Enforcer**.
2. **Project settings** → **Repository** / **GitHub** → **`edboyle212/shiprate-enforcer`**, branch **`main`**.
3. **Cursor Settings → GitHub** — sign in if needed.

## One-time: GitHub App access

1. https://github.com/settings/installations → **Cursor** → allow **`shiprate-enforcer`**.
2. https://cursor.com/dashboard/integrations → **Connect GitHub**.

## Cloud push to GitHub

Set **`GH_TOKEN`** (fine-grained PAT, Contents read/write) on the Project environment if agents should `git push github main`. Without it, Mac pushes and cloud pulls.

See also: Project Context **`docs/github-sync-workflow.md`** (Edward workflow).
