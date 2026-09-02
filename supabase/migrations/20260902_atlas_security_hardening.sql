-- ATLAS Supabase security hardening
-- Applied to production on 2026-09-02 and persisted here for reproducibility.
-- ATLAS is server-side only: anon/authenticated must not access internal tables,
-- views, or RPC helpers. service_role remains available to trusted backend code.

-- 1) Protect every ATLAS table and remove direct client grants.
do $$
declare
  r record;
begin
  for r in
    select n.nspname as schema_name, c.relname as object_name
    from pg_catalog.pg_class c
    join pg_catalog.pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind in ('r','p')
      and c.relname like 'atlas\_%' escape '\'
  loop
    execute format('alter table %I.%I enable row level security', r.schema_name, r.object_name);
    execute format('revoke all privileges on table %I.%I from anon, authenticated', r.schema_name, r.object_name);
  end loop;
end
$$;

-- 2) Make ATLAS views run with caller privileges and keep them off the public API.
do $$
declare
  r record;
begin
  for r in
    select n.nspname as schema_name, c.relname as object_name
    from pg_catalog.pg_class c
    join pg_catalog.pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind = 'v'
      and c.relname like 'atlas\_%' escape '\'
  loop
    execute format('alter view %I.%I set (security_invoker = true)', r.schema_name, r.object_name);
    execute format('revoke all privileges on table %I.%I from anon, authenticated', r.schema_name, r.object_name);
  end loop;
end
$$;

-- 3) Harden all ATLAS functions/RPC helpers.
do $$
declare
  r record;
  fn_signature text;
begin
  for r in
    select n.nspname as schema_name,
           p.proname as function_name,
           pg_catalog.pg_get_function_identity_arguments(p.oid) as identity_args
    from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname like 'atlas\_%' escape '\'
  loop
    fn_signature := format('%I.%I(%s)', r.schema_name, r.function_name, r.identity_args);
    execute format('alter function %s set search_path = pg_catalog, public', fn_signature);
    execute format('revoke execute on function %s from public, anon, authenticated', fn_signature);
  end loop;
end
$$;

-- 4) Safe defaults: future objects are private unless explicitly exposed.
alter default privileges for role postgres in schema public
  revoke select, insert, update, delete on tables from anon, authenticated;

alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated;

alter default privileges for role postgres in schema public
  revoke usage, select on sequences from anon, authenticated;

-- Expected postconditions:
--   ATLAS public tables without RLS                 = 0
--   ATLAS public views without security_invoker     = 0
--   ATLAS functions executable by anon/authenticated = 0
--
-- Intentionally no RLS policies are added for ATLAS internal tables. With RLS
-- enabled and no client policy, anon/authenticated are denied while trusted
-- server-side service-role workflows remain available.