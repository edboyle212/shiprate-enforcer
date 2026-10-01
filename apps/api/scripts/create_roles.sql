-- Application DB roles (run once per cluster; safe to re-run).
-- CI/local dev may still use the shiprate superuser until TEST_APP_DATABASE_URL is wired.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'shiprate_migrator') THEN
    CREATE ROLE shiprate_migrator LOGIN PASSWORD 'shiprate' NOSUPERUSER;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'shiprate_app') THEN
    CREATE ROLE shiprate_app LOGIN PASSWORD 'shiprate' NOSUPERUSER NOBYPASSRLS;
  END IF;
END
$$;

DO $$
BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO shiprate_app', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO shiprate_migrator', current_database());
END
$$;

GRANT USAGE ON SCHEMA public TO shiprate_app;
GRANT USAGE ON SCHEMA public TO shiprate_migrator;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO shiprate_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO shiprate_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO shiprate_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO shiprate_app;
