# Connect Cursor Project to GitHub

The cloud agent **cannot** click **Connect repository** in the Cursor UI — that binding is only in the desktop app.

## Do this once (≈30 seconds)

1. Open **Cursor** → **Projects** → **Shiprate Enforcer** (this chat).
2. Open **Project settings** (gear next to the project name, or **⋯** menu).
3. Find **Repository** / **GitHub** / **Connect repository**.
4. Choose **`edboyle212/shiprate-enforcer`**, branch **`main`**, confirm.

If you don’t see it: **Cursor Settings → GitHub** and ensure GitHub is signed in, then retry step 3.

## Already done outside Cursor

- GitHub: https://github.com/edboyle212/shiprate-enforcer (`main` @ `766151e`)
- Mac clone: `~/Projects/shiprate-enforcer`
- Cloud workspace remote **`github`** → same repo (push needs `GH_TOKEN` on cloud agents)

After connecting in step 4, new cloud agents for this Project should use GitHub as the repo source of truth.
