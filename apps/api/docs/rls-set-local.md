# PostgreSQL RLS and `SET LOCAL`

Shiprate Enforcer isolates tenant data with **PostgreSQL row-level security (RLS)** on every table that carries an `organization_id`, plus a narrow read policy on `organizations`.

## Session variable

Each request handler calls:

```python
await session.execute(
    text("SELECT set_config('app.organization_id', :org_id, true)"),
    {"org_id": str(organization_id)},
)
```

`set_config(name, value, true)` is transaction-scoped, same as `SET LOCAL`. PostgreSQL does not accept bound parameters in `SET`, so the helper is required. Connection pooling cannot leak tenant context across requests.

RLS policies compare `organization_id::text` to `current_setting('app.organization_id', true)` via helper `app_current_organization_id()`. Migration `005_force_rls` forces those policies on the table owner. `organizations` stays unforced so bootstrap inserts still work. An empty setting remains a bypass for migrations.

## Dev tenancy header

For local development, send:

```http
X-Organization-Id: <uuid>
```

`TenancyMiddleware` stores this in a context var; route dependencies call `set_rls_organization` before queries.

## Clerk (stub)

When `CLERK_SECRET_KEY` is set, production auth will validate JWTs and map the Clerk organization to our `organizations.id`. Until then, the same `X-Organization-Id` header (or `X-Clerk-Org-Id` alongside Bearer token) is accepted for integration tests.

## Bootstrap without tenant context

Migrations and org creation endpoints run with an empty `app.organization_id`, which policies treat as bypass (`IS NULL`) so Alembic and admin scripts can seed data. Application routes that read tenant data **must** set the variable first.
