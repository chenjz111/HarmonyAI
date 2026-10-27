"""Real SQLite negative schemas must be refused without DDL, ledger or data writes."""
from pathlib import Path
import re

import pytest
from sqlalchemy import event, inspect, text

from backend.app.core import v3_migrations as migrations
from tests.api.v3.test_int2_0012_contract import upgraded, seed

VERSION = '0012_v3_music_library'
ROOT = Path(__file__).parents[3] / 'backend/migrations/v3'
OWNER_FK = 'FOREIGN KEY(owner_internal_user_pk) REFERENCES users(id) ON DELETE CASCADE'
ASSET_FK = 'FOREIGN KEY(music_asset_id) REFERENCES music_assets(music_asset_id) ON DELETE CASCADE'
CONTEXT_FK = 'CONSTRAINT fk_playback_owner_asset_context FOREIGN KEY(source_context_id,internal_user_pk,music_asset_id) REFERENCES generation_tasks(task_id,internal_user_pk,music_asset_id)'
PARENT = 'CREATE UNIQUE INDEX IF NOT EXISTS uq_generation_tasks_owner_asset_context ON generation_tasks(task_id,internal_user_pk,music_asset_id);'

@pytest.fixture(autouse=True)
def historical_0012_registry(monkeypatch):
    """Keep historical 0012 downgrade/recovery assertions; 0013 has its own suite."""
    monkeypatch.setattr(migrations, 'V3_MIGRATION_VERSIONS', migrations.V3_MIGRATION_VERSIONS[:12])


# These are real SQL mutations, not mocked Inspector results.
CASES = [
    ('owner_fk_missing','owner_music_state',',\n '+OWNER_FK,''),
    ('owner_fk_wrong_table','owner_music_state','REFERENCES users(id)','REFERENCES user_profiles(internal_user_pk)'),
    ('owner_fk_wrong_column','owner_music_state','REFERENCES users(id)','REFERENCES users(openid)'),
    ('owner_fk_no_cascade','owner_music_state',' ON DELETE CASCADE',''),
    ('owner_pk_missing','owner_music_state','NOT NULL PRIMARY KEY','NOT NULL UNIQUE'),
    ('owner_pk_wrong','owner_music_state','NOT NULL PRIMARY KEY','NOT NULL'),
    ('library_check_missing','owner_music_state',' CHECK(library_epoch>=0)',''),
    ('feedback_check_missing','owner_music_state',' CHECK(feedback_evidence_epoch>=0)',''),
    ('library_check_weakened','owner_music_state','CHECK(library_epoch>=0)','CHECK(library_epoch>=0 OR 1=1)'),
    ('feedback_check_weakened','owner_music_state','CHECK(feedback_evidence_epoch>=0)','CHECK(feedback_evidence_epoch>=-1)'),
    ('epoch_default_wrong','owner_music_state','library_epoch BIGINT NOT NULL DEFAULT 0','library_epoch BIGINT NOT NULL DEFAULT 1'),
    ('epoch_nullable','owner_music_state','library_epoch BIGINT NOT NULL','library_epoch BIGINT'),
    ('side_pk_wrong_order','music_library_state','PRIMARY KEY(owner_internal_user_pk,music_asset_id)','PRIMARY KEY(music_asset_id,owner_internal_user_pk)'),
    ('side_pk_weakened','music_library_state','PRIMARY KEY(owner_internal_user_pk,music_asset_id)','PRIMARY KEY(owner_internal_user_pk)'),
    ('side_owner_fk_missing','music_library_state',',\n '+OWNER_FK,''),
    ('side_asset_fk_missing','music_library_state',',\n '+ASSET_FK,''),
    ('side_asset_cascade_missing','music_library_state',ASSET_FK,ASSET_FK.replace(' ON DELETE CASCADE','')),
    ('version_check_missing','music_library_state',' CHECK(metadata_version>=0)',''),
    ('title_check_missing','music_library_state',' CHECK(user_title IS NULL OR (length(user_title)>=1 AND length(user_title)<=120))',''),
    ('title_check_weakened','music_library_state','length(user_title)<=120','length(user_title)<=121'),
    ('title_check_zero_length','music_library_state','length(user_title)>=1','length(user_title)>=0'),
    ('title_nullable_missing','music_library_state','user_title VARCHAR(120) NULL','user_title VARCHAR(120) NOT NULL'),
    ('title_check_bypass','music_library_state','length(user_title)<=120)','length(user_title)<=120) OR 1=1'),
    ('event_unique_missing','music_playback_events',',\n CONSTRAINT uq_music_playback_events_owner_event UNIQUE(internal_user_pk,event_id)',''),
    ('event_unique_weakened','music_playback_events','UNIQUE(internal_user_pk,event_id)','UNIQUE(internal_user_pk,event_id,music_asset_id)'),
    ('event_unique_global','music_playback_events','UNIQUE(internal_user_pk,event_id)','UNIQUE(event_id)'),
    ('event_autoincrement_missing','music_playback_events',' PRIMARY KEY AUTOINCREMENT',' PRIMARY KEY'),
    ('event_pk_wrong','music_playback_events','INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT','BIGINT NOT NULL PRIMARY KEY'),
    ('event_owner_fk_missing','music_playback_events',',\n FOREIGN KEY(internal_user_pk) REFERENCES users(id) ON DELETE CASCADE',''),
    ('event_asset_fk_missing','music_playback_events',',\n '+ASSET_FK,''),
    ('event_owner_cascade_missing','music_playback_events','FOREIGN KEY(internal_user_pk) REFERENCES users(id) ON DELETE CASCADE','FOREIGN KEY(internal_user_pk) REFERENCES users(id)'),
    ('event_context_fk_missing','music_playback_events',',\n '+CONTEXT_FK,''),
    ('event_context_fk_wrong','music_playback_events','REFERENCES generation_tasks(task_id,internal_user_pk,music_asset_id)','REFERENCES generation_tasks(task_id,music_asset_id,internal_user_pk)'),
    ('event_type_check_missing','music_playback_events'," CHECK(event_type IN ('play_started'))",''),
    ('event_type_check_weakened','music_playback_events',"IN ('play_started')","IN ('play_started','seek')"),
    ('event_id_check_missing','music_playback_events',' CHECK(length(event_id)>=1 AND length(event_id)<=64)',''),
    ('event_id_check_weakened','music_playback_events','length(event_id)<=64','length(event_id)<=65'),
    ('context_check_missing','music_playback_events',' CHECK(source_context_id IS NULL OR length(source_context_id)<=64)',''),
    ('context_check_weakened','music_playback_events','length(source_context_id)<=64','length(source_context_id)<=65'),
    ('occurred_nullable','music_playback_events','occurred_at DATETIME NOT NULL','occurred_at DATETIME NULL'),
    ('event_created_nullable','music_playback_events','created_at DATETIME NOT NULL','created_at DATETIME NULL'),
    ('parent_index_missing',None,PARENT,''),
    ('parent_index_nonunique',None,'CREATE UNIQUE INDEX IF NOT EXISTS uq_generation_tasks_owner_asset_context','CREATE INDEX IF NOT EXISTS uq_generation_tasks_owner_asset_context'),
    ('parent_index_wrong_columns',None,PARENT,PARENT.replace('(task_id,internal_user_pk,music_asset_id)','(task_id,music_asset_id,internal_user_pk)')),
    ('parent_index_partial',None,PARENT,PARENT[:-1]+' WHERE internal_user_pk>0;'),
    ('parent_index_wrong_collation',None,PARENT,PARENT.replace('(task_id,','(task_id COLLATE NOCASE,')),
    ('event_unique_wrong_collation','music_playback_events','UNIQUE(internal_user_pk,event_id)','UNIQUE(internal_user_pk,event_id COLLATE NOCASE)'),
    ('unknown_check','owner_music_state','CHECK(library_epoch>=0)','CHECK(library_epoch>=0 AND abs(library_epoch)=library_epoch)'),
]


def replace_table(sql, table, old, new):
    if table is None:
        assert old in sql
        return sql.replace(old,new,1)
    pattern = rf'CREATE TABLE IF NOT EXISTS {table} \([\s\S]*?\n\);'
    match = re.search(pattern,sql)
    assert match and old in match[0]
    return sql[:match.start()] + match[0].replace(old,new,1) + sql[match.end():]


def run_sql(engine, sql):
    with engine.begin() as connection:
        for statement in sql.split(';'):
            if statement.strip():
                connection.exec_driver_sql(statement)


def old_0011(engine, monkeypatch):
    with monkeypatch.context() as context:
        context.setattr(migrations,'V3_MIGRATION_VERSIONS',migrations.V3_MIGRATION_VERSIONS[:11])
        migrations.apply_v3_migrations(engine)
    with engine.begin() as connection:
        seed(connection)


def snapshot(engine):
    with engine.connect() as connection:
        schema = connection.exec_driver_sql('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').all()
        rows = {name: connection.exec_driver_sql(f'SELECT * FROM "{name}" ORDER BY 1').all()
                for name in inspect(connection).get_table_names()}
        return schema, rows


def refuse_without_writes(engine):
    before = snapshot(engine)
    writes = []
    def capture(connection,cursor,statement,parameters,context,many):
        if re.match(r'\s*(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|REPLACE)\b',statement,re.I):
            writes.append(statement.split()[0])
    event.listen(engine,'before_cursor_execute',capture)
    try:
        with pytest.raises(migrations.MigrationSchemaMismatch):
            migrations.apply_v3_migrations(engine)
    finally:
        event.remove(engine,'before_cursor_execute',capture)
    assert writes == []
    assert snapshot(engine) == before


@pytest.mark.parametrize('case',CASES,ids=[case[0] for case in CASES])
def test_malformed_existing_schema_refused_before_ddl(upgraded, monkeypatch, case):
    old_0011(upgraded,monkeypatch)
    name,table,old,new = case
    sql = replace_table((ROOT/'sqlite'/f'{VERSION}_up.sql').read_text(),table,old,new)
    run_sql(upgraded,sql)
    # Preserve extension data where the malformed owner FK itself permits it.
    if table != 'owner_music_state' or name == 'owner_fk_missing':
        with upgraded.begin() as connection:
            connection.execute(text('INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(7)'))
    refuse_without_writes(upgraded)
    with upgraded.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM schema_migrations WHERE version=:v'),{'v':VERSION}).scalar_one() == 0


@pytest.mark.parametrize('table',['owner_music_state','music_library_state','music_playback_events'])
def test_recorded_0012_missing_table_is_corruption(upgraded,table):
    migrations.apply_v3_migrations(upgraded)
    with upgraded.begin() as connection:
        connection.exec_driver_sql(f'DROP TABLE {table}')
    refuse_without_writes(upgraded)


@pytest.mark.parametrize('column',['library_epoch','feedback_evidence_epoch'])
def test_fractional_epoch_weakened_check_refused(upgraded,monkeypatch,column):
    old_0011(upgraded,monkeypatch)
    sql = (ROOT/'sqlite'/f'{VERSION}_up.sql').read_text()
    sql = sql.replace(f'{column}>=0',f'{column}>-1')
    run_sql(upgraded,sql)
    with upgraded.begin() as connection:
        connection.execute(text(f'INSERT INTO owner_music_state(owner_internal_user_pk,{column}) VALUES(7,-0.5)'))
        assert connection.execute(text(f'SELECT {column} FROM owner_music_state')).scalar_one() == -0.5
    refuse_without_writes(upgraded)


@pytest.mark.parametrize('version,mariadb,allowed',[
    (None,False,False),((8,0,15),False,False),((8,0,16),False,True),
    ((8,4,0),False,True),((10,11,0),True,False),
])
def test_mysql_first_0012_requires_supported_check_version(monkeypatch,version,mariadb,allowed):
    """Only metadata transport is synthetic; no MySQL connection or DDL."""
    from types import SimpleNamespace
    class Metadata:
        def get_table_names(self):
            return []
    class Engine:
        dialect=SimpleNamespace(name='mysql',server_version_info=version,is_mariadb=mariadb)
        def connect(self):
            raise AssertionError('first-table preflight must not execute DDL')
    monkeypatch.setattr(migrations,'inspect',lambda _:Metadata())
    if allowed:
        migrations._validate_library_existing_schema(Engine())
    else:
        with pytest.raises(migrations.MigrationSchemaMismatch,match='MySQL'):
            migrations._validate_library_existing_schema(Engine())


TIME_DEFAULT_COLUMNS = [
    ('owner_music_state','created_at'),('owner_music_state','updated_at'),
    ('music_library_state','created_at'),('music_library_state','updated_at'),
    ('music_playback_events','created_at'),
]


@pytest.mark.parametrize('table,column',TIME_DEFAULT_COLUMNS)
@pytest.mark.parametrize('default',[''," DEFAULT '2000-01-01 00:00:00'"])
def test_missing_or_fixed_time_default_refused_without_writes(upgraded,monkeypatch,table,column,default):
    old_0011(upgraded,monkeypatch)
    sql=replace_table((ROOT/'sqlite'/f'{VERSION}_up.sql').read_text(),table,
                      f'{column} DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP',
                      f'{column} DATETIME NOT NULL{default}')
    run_sql(upgraded,sql)
    # Explicit timestamps keep the synthetic pre-existing row valid even when
    # defaults are missing; refusal must preserve that data, not just empty DDL.
    run_sql(upgraded,"INSERT INTO owner_music_state(owner_internal_user_pk,created_at,updated_at) VALUES(7,'2001-01-01','2001-01-01');")
    refuse_without_writes(upgraded)
    with upgraded.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM schema_migrations WHERE version=:v'),{'v':VERSION}).scalar_one()==0


@pytest.mark.parametrize('default',["CURRENT_TIMESTAMP","'2000-01-01 00:00:00'"])
def test_nonnull_cutoff_default_refused_without_writes(upgraded,monkeypatch,default):
    old_0011(upgraded,monkeypatch)
    sql=replace_table((ROOT/'sqlite'/f'{VERSION}_up.sql').read_text(),'owner_music_state',
                      'preference_clear_cutoff DATETIME NULL',f'preference_clear_cutoff DATETIME NULL DEFAULT {default}')
    run_sql(upgraded,sql)
    run_sql(upgraded,'INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(7);')
    refuse_without_writes(upgraded)
    with upgraded.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM schema_migrations WHERE version=:v'),{'v':VERSION}).scalar_one()==0


@pytest.mark.parametrize('default',['(current_timestamp)',"(datetime('now'))"])
def test_equivalent_sqlite_time_and_null_cutoff_defaults_accepted(upgraded,monkeypatch,default):
    old_0011(upgraded,monkeypatch)
    sql=(ROOT/'sqlite'/f'{VERSION}_up.sql').read_text().replace('DEFAULT CURRENT_TIMESTAMP',f'DEFAULT {default}')
    sql=sql.replace('preference_clear_cutoff DATETIME NULL','preference_clear_cutoff DATETIME NULL DEFAULT (NULL)')
    run_sql(upgraded,sql)
    assert migrations.apply_v3_migrations(upgraded)['applied_versions']==[VERSION]
    with upgraded.begin() as connection:
        connection.execute(text('INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(7)'))
        row=connection.execute(text('SELECT created_at,updated_at,preference_clear_cutoff FROM owner_music_state')).one()
        assert row[0] is not None and row[1] is not None and row[2] is None


def test_valid_readonly_preflight_and_equivalent_checks(upgraded,monkeypatch):
    old_0011(upgraded,monkeypatch)
    sql = (ROOT/'sqlite'/f'{VERSION}_up.sql').read_text()
    sql = sql.replace('library_epoch>=0','(0 <= "library_epoch")')
    sql = sql.replace('feedback_evidence_epoch>=0','(0 <= "feedback_evidence_epoch")')
    sql = sql.replace('length(user_title)>=1 AND length(user_title)<=120','length(user_title) BETWEEN 1 AND 120')
    sql = sql.replace("event_type IN ('play_started')","event_type = 'play_started'")
    run_sql(upgraded,sql)
    before = snapshot(upgraded)
    migrations.preflight_v3_migrations(upgraded)
    assert snapshot(upgraded) == before
    assert migrations.apply_v3_migrations(upgraded)['applied_versions']==[VERSION]
    assert migrations.apply_v3_migrations(upgraded)['applied_versions']==[]


def test_unique_index_form_is_valid_not_constraint_name(upgraded,monkeypatch):
    old_0011(upgraded,monkeypatch)
    sql = replace_table((ROOT/'sqlite'/f'{VERSION}_up.sql').read_text(),'music_playback_events',
                        ',\n CONSTRAINT uq_music_playback_events_owner_event UNIQUE(internal_user_pk,event_id)','')
    sql += '\nCREATE UNIQUE INDEX synthetic_event_unique ON music_playback_events(internal_user_pk,event_id);'
    run_sql(upgraded,sql)
    assert migrations.apply_v3_migrations(upgraded)['applied_versions']==[VERSION]


@pytest.mark.parametrize('replacement',[
    'CREATE INDEX uq_generation_tasks_owner_asset_context ON generation_tasks(task_id);',
    'CREATE UNIQUE INDEX uq_generation_tasks_owner_asset_context ON generation_tasks(lower(task_id),internal_user_pk,music_asset_id);',
])
def test_bad_named_parent_index_refused_before_any_library_table(upgraded,monkeypatch,replacement):
    old_0011(upgraded,monkeypatch)
    run_sql(upgraded,replacement)
    # No playback table exists yet; IF NOT EXISTS must not mask this name collision.
    refuse_without_writes(upgraded)


def test_recorded_0012_constraint_damage_still_checked(upgraded):
    migrations.apply_v3_migrations(upgraded)
    run_sql(upgraded,'DROP TABLE owner_music_state;')
    sql=(ROOT/'sqlite'/f'{VERSION}_up.sql').read_text()
    sql=replace_table(sql,'owner_music_state',',\n '+OWNER_FK,'')
    run_sql(upgraded,re.search(r'CREATE TABLE IF NOT EXISTS owner_music_state \([\s\S]*?\n\);',sql)[0])
    refuse_without_writes(upgraded)


def test_playback_parent_table_missing_is_corruption(upgraded):
    migrations.apply_v3_migrations(upgraded)
    run_sql(upgraded,'DROP TABLE generation_tasks;')
    refuse_without_writes(upgraded)


def test_disabled_sqlite_checks_not_treated_as_valid(upgraded):
    migrations.apply_v3_migrations(upgraded)
    # PRAGMA is connection-local: model the unsafe configuration on every
    # checkout, not whichever pooled connection happened to be used for setup.
    def unsafe_checkout(connection,record,proxy):
        connection.execute('PRAGMA ignore_check_constraints=ON')
    event.listen(upgraded,'checkout',unsafe_checkout)
    try:
        refuse_without_writes(upgraded)
    finally:
        event.remove(upgraded,'checkout',unsafe_checkout)


@pytest.mark.parametrize('enforced',['NO',None])
def test_mysql_unverified_check_enforcement_is_blocked_without_network(upgraded,monkeypatch,enforced):
    """Mock only unavailable MySQL metadata transport; real validator runs.

    This is not execution of MySQL DDL or proof of real MySQL compatibility.
    """
    from types import SimpleNamespace
    from contextlib import contextmanager
    migrations.apply_v3_migrations(upgraded)
    actual_inspector=inspect(upgraded)
    class Metadata:
        def __getattr__(self,name):
            return getattr(actual_inspector,name)
        def get_table_names(self):
            return ['owner_music_state','users']
    class Rows:
        def all(self):
            return [(c['name'],enforced) for c in actual_inspector.get_check_constraints('owner_music_state')]
    class ReadOnlyConnection:
        def execute(self,statement,parameters):
            if enforced is None:
                raise RuntimeError('synthetic metadata unavailable')
            return Rows()
    class MySQLEngine:
        dialect=SimpleNamespace(name='mysql',server_version_info=(8,0,16),is_mariadb=False,default_schema_name='synthetic')
        @contextmanager
        def connect(self):
            yield ReadOnlyConnection()
    engine=MySQLEngine()
    monkeypatch.setattr(migrations,'inspect',lambda inspected: Metadata())
    with pytest.raises(migrations.MigrationSchemaMismatch,match='enforcement unverifiable'):
        migrations._validate_library_existing_schema(engine)


@pytest.mark.parametrize('prefix',[True,False])
@pytest.mark.parametrize('time_default',['CURRENT_TIMESTAMP(6)','(now())','LOCALTiMeSTAMP(0)'])
def test_mysql_prefix_unique_not_mistaken_for_full_unique(upgraded,monkeypatch,prefix,time_default):
    """Credential-free metadata boundary test, not real MySQL execution."""
    from types import SimpleNamespace
    from contextlib import contextmanager
    migrations.apply_v3_migrations(upgraded)
    source=inspect(upgraded)
    class Metadata:
        def __getattr__(self,name):
            return getattr(source,name)
        def get_columns(self,table):
            return [dict(c,autoincrement=True) if c['name']=='playback_event_row_id'
                    else dict(c,default=time_default) if c['name'] in ('created_at','updated_at') else dict(c)
                    for c in source.get_columns(table)]
        def get_check_constraints(self,table):
            return [dict(c,name=f'synthetic_{table}_{i}',
                         sqltext=c['sqltext'].replace('length(user_title)','char_length(user_title)'))
                    for i,c in enumerate(source.get_check_constraints(table))]
        def get_indexes(self,table):
            indexes=source.get_indexes(table)
            if table=='music_playback_events':
                indexes += [{'name':'synthetic_event_index','unique':True,
                             'column_names':['internal_user_pk','event_id'],
                             'dialect_options':{'mysql_length':{'event_id':8}} if prefix else {}}]
            return indexes
    metadata=Metadata()
    class Rows:
        def __init__(self,values):
            self.values=values
        def all(self):
            return self.values
        def scalars(self):
            return [row[0] for row in self.values]
    class Connection:
        def execute(self,statement,parameters):
            sql=str(statement)
            if 'TABLE_CONSTRAINTS' in sql:
                return Rows([(c['name'],'YES') for c in metadata.get_check_constraints(parameters['table'])])
            if 'STATISTICS' in sql:
                return Rows([(i['name'],) for i in source.get_indexes('generation_tasks')])
            raise AssertionError('unexpected metadata SQL')
    class Engine:
        dialect=SimpleNamespace(name='mysql',server_version_info=(8,0,16),is_mariadb=False,default_schema_name=None)
        @contextmanager
        def connect(self):
            yield Connection()
    monkeypatch.setattr(migrations,'inspect',lambda _:metadata)
    if prefix:
        with pytest.raises(migrations.MigrationSchemaMismatch,match='uniqueness'):
            migrations._validate_library_existing_schema(Engine())
    else:
        migrations._validate_library_existing_schema(Engine())
