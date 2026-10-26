"""Regression for the actual MySQL8 fresh-create syntax failure."""
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mysql,sqlite


def test_rank_check_uses_dialect_identifier_quoting_without_changing_bound():
    from backend.app.models.v3.diagnosis import DiagnosisCandidate
    statement=str(CreateTable(DiagnosisCandidate.__table__).compile(dialect=mysql.dialect()))
    assert 'CHECK (`rank` >= 1)' in statement
    assert 'CHECK (relative_support >= 0 AND relative_support <= 1)' in statement
    assert 'rank >= 1' in str(CreateTable(DiagnosisCandidate.__table__).compile(dialect=sqlite.dialect()))


def test_real_mysql_now_default_is_equivalent_but_expressions_and_literals_are_not():
    from backend.app.core.v3_migrations import _is_current_timestamp_default
    for value in ['(now())','CURRENT_TIMESTAMP','CURRENT_TIMESTAMP(6)']:
        assert _is_current_timestamp_default(value,'mysql')
    for value in [None,"'now'",'now()+INTERVAL 1 DAY','custom_current_timestamp()','CURRENT_TIMESTAMP - 1']:
        assert not _is_current_timestamp_default(value,'mysql')
    assert not _is_current_timestamp_default('(now())','sqlite')


def test_mysql_reflected_charset_introducers_preserve_literal_contract():
    from backend.app.core.feedback_mysql_migration import _check_signature
    assert _check_signature("(`change_label` in (_utf8mb4'much_better',_utf8mb4'worse'))") == _check_signature("change_label IN ('much_better','worse')")
    assert _check_signature("change_label IN (_utf8mb4'WORSE')") != _check_signature("change_label IN ('worse')")


def test_mysql_reflected_not_null_check_accepts_parentheses_but_not_changed_logic():
    from backend.app.core.feedback_mysql_migration import _check_signature
    expected="a IS NULL OR (a IS NOT NULL AND b IS NOT NULL)"
    assert _check_signature('((`a` is null) or ((`a` is not null) and (`b` is not null)))') == _check_signature(expected)
    assert _check_signature('a IS NULL OR (a IS NOT NULL OR b IS NOT NULL)') != _check_signature(expected)


def test_mysql_fingerprint_server_rewrite_remains_exactly_bounded():
    from backend.app.core.feedback_mysql_migration import _check_signature
    source="request_fingerprint IS NULL OR (CHAR_LENGTH(request_fingerprint)=71 AND LEFT(request_fingerprint,7)='sha256:' AND SUBSTRING(request_fingerprint,8) REGEXP '^[0-9a-f]+$')"
    reflected="((`request_fingerprint` is null) or ((char_length(`request_fingerprint`) = 71) and (left(`request_fingerprint`,7) = _ascii'sha256:') and regexp_like(substr(`request_fingerprint`,8),_ascii'^[0-9a-f]+$')))"
    assert _check_signature(reflected)==_check_signature(source)
    for old,new in [(' = 71',' = 70'),(' and regexp_like',' or regexp_like'),('^[0-9a-f]+$','[0-9a-f]+'),("_ascii'sha256:'","_ascii'SHA256:'")]:
        assert _check_signature(reflected.replace(old,new))!=_check_signature(source)


def test_account_mysql_regex_rewrite_and_boolean_grouping_are_verified():
    from backend.app.core.account_security_migration import signature
    source="username = lower(username) AND username REGEXP '^[a-z0-9_]{3,32}$'"
    reflected="((`username` = lower(`username`)) and regexp_like(`username`,_utf8mb4'^[a-z0-9_]{3,32}$'))"
    assert signature(source)==signature(reflected)
    assert signature(reflected.replace(' and ', ' or '))!=signature(source)
    assert signature('a IS NULL OR (b=1 AND c=2)')!=signature('(a IS NULL OR b=1) AND c=2')


def test_fresh_model_cycle_fk_is_omitted_only_when_exactly_verified(monkeypatch):
    import pytest
    from backend.app.core import v3_migrations as core
    class Inspector:
        def get_table_names(self):return ['music_assets']
        def get_foreign_keys(self,table):return [dict(name='fk_music_assets_generation_task',constrained_columns=['generation_task_id'],referred_table='generation_tasks',referred_columns=['task_id'],options={})]
    inspector=Inspector();monkeypatch.setattr(core,'inspect',lambda engine:inspector)
    source=core._read_migration('mysql','0002_v3_business','up')
    assert 'ADD CONSTRAINT fk_music_assets_generation_task' not in core._render_mysql_model_columns(None,'0002_v3_business',source)
    inspector.get_foreign_keys=lambda table:[dict(name='fk_music_assets_generation_task',constrained_columns=['wrong'],referred_table='generation_tasks',referred_columns=['task_id'],options={})]
    with pytest.raises(core.MigrationSchemaMismatch):core._render_mysql_model_columns(None,'0002_v3_business',source)


def test_existing_owner_flow_column_rejects_unsigned_or_injected_defaults(monkeypatch):
    import pytest
    from sqlalchemy.dialects.mysql import INTEGER
    from backend.app.core import v3_migrations as core
    column={'name':'user_goal_revision','type':INTEGER(),'nullable':True,'default':None}
    class Inspector:
        def get_table_names(self):return ['prescription_v3']
        def get_columns(self,table):return [column]
    monkeypatch.setattr(core,'inspect',lambda engine:Inspector())
    sql='ALTER TABLE prescription_v3 ADD COLUMN user_goal_revision INTEGER NULL;'
    assert 'ADD COLUMN' not in core._render_mysql_model_columns(None,'0007_v3_prescription_mode',sql)
    for flaw in ({'default':'1'},{'type':INTEGER(unsigned=True)}):
        old=column.copy();column.update(flaw)
        with pytest.raises(core.MigrationSchemaMismatch):core._render_mysql_model_columns(None,'0007_v3_prescription_mode',sql)
        column.clear();column.update(old)
