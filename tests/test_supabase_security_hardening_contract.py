from pathlib import Path


def test_supabase_security_hardening_contract():
    sql = Path('supabase/migrations/20260902_atlas_security_hardening.sql').read_text(encoding='utf-8').lower()

    assert 'enable row level security' in sql
    assert 'security_invoker = true' in sql
    assert 'search_path = pg_catalog, public' in sql
    assert 'revoke execute on function' in sql
    assert 'from public, anon, authenticated' in sql
    assert 'alter default privileges for role postgres' in sql
    # Trusted backend access must not be accidentally removed by this migration.
    assert 'from service_role' not in sql
