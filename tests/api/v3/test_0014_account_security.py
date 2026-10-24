"""Formal additive account schema; real MySQL remains NOT RUN."""
import pytest
from sqlalchemy import create_engine,inspect
from backend.app.core import v3_migrations as core
from tests.api.v3.test_v3_migrations import _create_legacy_foundation

VERSION='0014_v3_account_security'
TABLES={'account_credentials','registered_session_state','auth_refresh_proofs','account_login_buckets'}


def test_legacy_upgrade_and_repeat_preserve_historical_checksums(tmp_path,monkeypatch):
    engine=create_engine(f'sqlite:///{tmp_path/"upgrade.sqlite"}')
    _create_legacy_foundation(engine)
    with monkeypatch.context() as patch:
        patch.setattr(core,'V3_MIGRATION_VERSIONS',core.V3_MIGRATION_VERSIONS[:13]);core.apply_v3_migrations(engine)
    with engine.connect() as db:before=db.exec_driver_sql('SELECT version,checksum FROM schema_migrations ORDER BY version').fetchall()
    assert VERSION in core.V3_MIGRATION_VERSIONS
    assert core.apply_v3_migrations(engine)['applied_versions']==[VERSION]
    assert TABLES <= set(inspect(engine).get_table_names())
    assert core.apply_v3_migrations(engine)['applied_versions']==[]
    with engine.connect() as db:assert db.exec_driver_sql('SELECT version,checksum FROM schema_migrations WHERE version != ? ORDER BY version',(VERSION,)).fetchall()==before
    engine.dispose()


def test_fresh_orm_startup_and_partial_schema_refusal(tmp_path,monkeypatch):
    from backend.app.core import database
    from backend.app import models
    engine=create_engine(f'sqlite:///{tmp_path/"fresh.sqlite"}')
    monkeypatch.setattr(database,'engine',engine);database.init_database();database.init_database()
    with engine.connect() as db:assert db.exec_driver_sql('SELECT max(version) FROM schema_migrations').scalar()==VERSION
    with engine.begin() as db:db.exec_driver_sql('DROP TABLE auth_refresh_proofs')
    with pytest.raises(core.MigrationSchemaMismatch):database.init_database()
    engine.dispose()


def test_failed_sqlite_ddl_does_not_leave_partial_tables_or_ledger(tmp_path,monkeypatch):
    engine=create_engine(f'sqlite:///{tmp_path/"failure.sqlite"}');_create_legacy_foundation(engine)
    with monkeypatch.context() as patch:
        patch.setattr(core,'V3_MIGRATION_VERSIONS',core.V3_MIGRATION_VERSIONS[:13]);core.apply_v3_migrations(engine)
    original=core._execute_sqlite_statements
    def fail(cursor,sql):
        if 'CREATE TABLE account_credentials' in sql:
            cursor.execute('CREATE TABLE account_credentials(synthetic INTEGER)');raise RuntimeError('synthetic DDL failure')
        return original(cursor,sql)
    monkeypatch.setattr(core,'_execute_sqlite_statements',fail)
    with pytest.raises(RuntimeError,match='synthetic DDL failure'):core.apply_v3_migrations(engine)
    assert not TABLES.intersection(inspect(engine).get_table_names())
    with engine.connect() as db:assert not db.exec_driver_sql('SELECT 1 FROM schema_migrations WHERE version=?',(VERSION,)).first()
    engine.dispose()


def test_username_lowercase_ascii_is_a_database_constraint(ready_account):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from backend.app.models.v3.account_security import AccountCredential
    from tests.api.v3.test_account_session_r1 import NOW,seed_guest
    seed_guest(ready_account)
    for username in ('Alice','a-b','用户abc'):
        with Session(ready_account) as db,pytest.raises(IntegrityError):
            db.add(AccountCredential(internal_user_pk=7,username=username,password_hash='synthetic',created_at=NOW,updated_at=NOW));db.flush()


@pytest.fixture
def ready_account(ready):return ready
from tests.api.v3.test_feedback_v31_transactions import ready


@pytest.mark.parametrize('engine_name',['MyISAM','MEMORY','unknown'])
def test_mysql_nontransactional_account_engine_is_rejected(engine_name):
    from types import SimpleNamespace
    from backend.app.core.account_security_migration import require_mysql_engines
    class Connection:
        def execute(self,statement):
            assert 'information_schema.TABLES' in str(statement)
            return SimpleNamespace(fetchall=lambda:[(name,engine_name if name=='account_login_buckets' else 'InnoDB') for name in TABLES])
    with pytest.raises(core.MigrationSchemaMismatch):require_mysql_engines(Connection(),TABLES)


@pytest.mark.parametrize('flaw',['length','unique','check','fk'])
def test_sqlite_account_schema_drift_is_not_repaired(ready_account,flaw):
    engine=ready_account
    with engine.begin() as db:
        ddl=db.exec_driver_sql("SELECT sql FROM sqlite_schema WHERE name='account_credentials'").scalar()
        replacement={'length':('VARCHAR(32)','VARCHAR(31)'), 'unique':('UNIQUE (username)','UNIQUE (password_hash)'),
            'check':('length(username) BETWEEN 3 AND 32','1=1'), 'fk':('ON DELETE RESTRICT','ON DELETE CASCADE')}[flaw]
        assert replacement[0] in ddl
        db.exec_driver_sql('DROP TABLE account_credentials');db.exec_driver_sql(ddl.replace(*replacement))
    with pytest.raises(core.MigrationSchemaMismatch):core.preflight_v3_migrations(engine)


def test_mysql_render_is_paired_binary_and_parent_collation_aware(monkeypatch):
    from types import SimpleNamespace
    from backend.app.core import account_security_migration as migration
    monkeypatch.setattr(migration,'validate',lambda engine,applied:False)
    class Connection:
        def execute(self,statement,params=None):
            if params is None:return SimpleNamespace(fetchall=lambda:[('auth_sessions','InnoDB'),('user_identities','InnoDB')])
            return SimpleNamespace(first=lambda:('varchar(64)','utf8mb4','utf8mb4_bin'))
    sql=migration.render(SimpleNamespace(dialect=SimpleNamespace(name='mysql')),core._read_migration('mysql',VERSION,'up'),Connection())
    assert '{{' not in sql and 'CHARACTER SET utf8mb4 COLLATE utf8mb4_bin' in sql
    assert sql.count('ENGINE=InnoDB')==4 and 'ascii_bin' in sql and 'REGEXP' in sql
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects.mysql import dialect
    assert all('ENGINE=InnoDB' in str(CreateTable(model.__table__).compile(dialect=dialect())) for model in migration.MODELS)


def test_account_production_exports_share_single_base():
    from backend.app import models
    from backend.app.core.database import Base
    for name in ('AccountCredential','RegisteredSessionState','RefreshProof','LoginBucket'):
        assert getattr(models,name).__table__.metadata is Base.metadata
