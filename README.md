# Shiprate Enforcer

Multi-tenant parcel rate-compliance platform (MVP in progress).

## Run tests

See [docs/testing.md](docs/testing.md).

Quick start (API contract tests; most skip until app code lands):

```bash
cd apps/api && pip install pytest pytest-asyncio httpx && PYTHONPATH=. pytest tests -v
```
