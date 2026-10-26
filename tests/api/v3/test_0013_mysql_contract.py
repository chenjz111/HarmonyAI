"""Synthetic MySQL metadata; never a claim of real MySQL execution."""
from types import SimpleNamespace
import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable
from backend.app.core import v3_migrations as core


class MetadataConnection:
    dialect = SimpleNamespace(name='mysql')
    def __init__(self, version='8.0.36', collation='utf8mb4_0900_ai_ci', mismatch=False):
        self.version, self.collation, self.mismatch = version, collation, mismatch
        self.queries = []
    def exec_driver_sql(self, sql):
        self.queries.append(sql)
        assert sql == 'SELECT VERSION()'
        return SimpleNamespace(scalar=lambda: self.version)
    def execute(self, statement, params=None):
        self.queries.append(str(statement))
        if params is None:
            return SimpleNamespace(fetchall=lambda: [(t, 'InnoDB') for t in
                ('users','feedback_v3','generation_tasks','music_assets','music_playback_events','user_music_preference_versions')])
        if params['c'] in ('id', 'internal_user_pk', 'playback_event_row_id'):
            row = ('int', None, None)
        else:
            coll = 'utf8mb4_bin' if self.mismatch and params['c'] == 'source_context_id' else self.collation
            row = ('varchar(64)', 'utf8mb4', coll)
        return SimpleNamespace(first=lambda: row)


@pytest.mark.parametrize('version', ['unknown', '8.0.15', '10.11.6-MariaDB'])
def test_unapproved_server_fails_before_render(version):
    from backend.app.core import feedback_mysql_migration as contract
    connection = MetadataConnection(version=version)
    with pytest.raises(core.MigrationSchemaMismatch):
        contract.render_up(connection, core._read_migration('mysql', '0013_v3_feedback_consent', 'up'))
    assert connection.queries == ['SELECT VERSION()']


@pytest.mark.parametrize('collation', ['utf8mb4_bin', 'utf8mb4_0900_ai_ci'])
def test_render_uses_real_parent_metadata_without_placeholders(collation):
    from backend.app.core import feedback_mysql_migration as contract
    sql = contract.render_up(MetadataConnection(collation=collation), core._read_migration('mysql', '0013_v3_feedback_consent', 'up'))
    assert f'source_task_id varchar(64) CHARACTER SET utf8mb4 COLLATE {collation}' in sql
    assert '{{' not in sql
    statements = core._mysql_migration_statements(sql)
    assert sum(s.startswith('CREATE TRIGGER') for s in statements) == 8


def test_mismatching_parent_collation_cannot_render():
    from backend.app.core import feedback_mysql_migration as contract
    with pytest.raises(core.MigrationSchemaMismatch):
        contract.render_up(MetadataConnection(mismatch=True), core._read_migration('mysql', '0013_v3_feedback_consent', 'up'))


def test_production_mysql_orm_has_composite_proof_and_fingerprint_constraints():
    from backend.app.models.v3 import FeedbackV3, MusicPlaybackEvent
    ddl = str(CreateTable(FeedbackV3.__table__).compile(dialect=mysql.dialect()))
    assert 'typeof' not in ddl and 'GLOB' not in ddl
    assert 'REGEXP' in ddl
    assert 'FOREIGN KEY(source_task_id, internal_user_pk, music_asset_id)' in ddl
    assert 'FOREIGN KEY(playback_event_row_id, internal_user_pk, music_asset_id, source_task_id)' in ddl
    assert 'ascii_bin' in ddl
    assert any(i.unique and list(i.columns.keys()) == ['playback_event_row_id', 'internal_user_pk', 'music_asset_id', 'source_context_id'] for i in MusicPlaybackEvent.__table__.indexes)


@pytest.mark.parametrize('disabled', ['int2_0013_consent', 'int2_0013_fingerprint', 'int2_0013_epoch'])
def test_disabled_mysql_check_is_rejected_even_with_correct_definition(disabled):
    from backend.app.core import feedback_mysql_migration as contract
    class CheckConnection:
        def execute(self, statement, params):
            assert 'information_schema.TABLE_CONSTRAINTS' in str(statement)
            return SimpleNamespace(fetchall=lambda: [(name, 'NO' if name == disabled else 'YES')
                for name in ('int2_0013_consent', 'int2_0013_fingerprint', 'int2_0013_epoch')])
    with pytest.raises(core.MigrationSchemaMismatch):
        contract.require_enforced_checks(CheckConnection(), 'feedback_v3',
            {'int2_0013_consent','int2_0013_fingerprint','int2_0013_epoch'})


class LegacyInspector:
    """Complete old model metadata, with one controlled schema mutation."""
    def __init__(self, flaw=None):
        from backend.app.models.v3 import FeedbackV3, UserMusicPreferenceVersion
        self.tables = {m.__tablename__: m.__table__ for m in (FeedbackV3, UserMusicPreferenceVersion)}
        self.flaw = flaw
    def get_pk_constraint(self, table):
        fields = [c.name for c in self.tables[table].primary_key]
        return {'constrained_columns': [] if self.flaw == 'pk' and table == 'feedback_v3' else fields}
    def get_unique_constraints(self, table):
        fields = ['internal_user_pk','idempotency_key'] if table == 'feedback_v3' else ['profile_id','version']
        return [] if self.flaw == 'unique' and table == 'feedback_v3' else [{'column_names': fields}]
    def get_indexes(self, table):
        return []
    def get_columns(self, table):
        from backend.app.core.feedback_migration import FIELDS
        return [dict(name=c.name, type=mysql.dialect().type_descriptor(c.type), nullable=c.nullable,
                     default='CURRENT_TIMESTAMP(6)' if c.name == 'created_at' else None)
                for c in self.tables[table].c if c.name not in FIELDS]
    def get_check_constraints(self, table):
        return [dict(name=c.name, sqltext='1=1' if self.flaw == 'check' and c.name == 'ck_feedback_v3_change_label' else str(c.sqltext))
                for c in self.tables[table].constraints if hasattr(c,'sqltext') and not c.name.startswith('s7_0013_')]
    def get_foreign_keys(self, table):
        from backend.app.core.feedback_migration import FIELDS
        return [dict(constrained_columns=list(c.column_keys), referred_table=c.referred_table.name,
                     referred_columns=[e.column.name for e in c.elements], options={'ondelete': c.ondelete} if c.ondelete else {})
                for c in self.tables[table].foreign_key_constraints if not FIELDS.intersection(c.column_keys)
                and not (self.flaw == 'fk' and table == 'feedback_v3')]


@pytest.mark.parametrize('flaw', ['unique', 'pk', 'check', 'fk'])
def test_mysql_old_integrity_must_be_verified_before_extension_ddl(flaw):
    from backend.app.core import feedback_mysql_migration as contract
    inspector = LegacyInspector(flaw)
    class CheckConnection:
        def execute(self, statement, params):
            assert str(statement).startswith('SELECT ')
            return SimpleNamespace(fetchall=lambda: [(c['name'],'YES') for c in inspector.get_check_constraints(params['table'])])
    with pytest.raises(core.MigrationSchemaMismatch):
        contract.validate_legacy(CheckConnection(), inspector)


def test_intact_mysql_legacy_schema_is_accepted_without_writes():
    from backend.app.core import feedback_mysql_migration as contract
    inspector = LegacyInspector()
    class CheckConnection:
        def execute(self, statement, params):
            assert str(statement).startswith('SELECT ')
            return SimpleNamespace(fetchall=lambda: [(c['name'],'YES') for c in inspector.get_check_constraints(params['table'])])
    contract.validate_legacy(CheckConnection(), inspector)


@pytest.mark.parametrize('flaw', ['length','precision','epoch','unsigned','collation'])
def test_mysql_receipt_columns_reject_lossy_schema(flaw):
    from backend.app.core.feedback_migration import validate_receipt_columns
    from backend.app.models.v3.feedback import FeedbackClearReceipt
    columns = {c.name:dict(name=c.name,type=c.type.dialect_impl(mysql.dialect()),nullable=False,default=None)
               for c in FeedbackClearReceipt.__table__.c}
    field, replacement = {
      'length':('idempotency_key',mysql.VARCHAR(32)),
      'precision':('cutoff',mysql.DATETIME(fsp=0)),
      'epoch':('resulting_feedback_epoch',mysql.INTEGER()),
      'unsigned':('resulting_feedback_epoch',mysql.BIGINT(unsigned=True)),
      'collation':('request_fingerprint',mysql.VARCHAR(71,charset='ascii',collation='ascii_general_ci')),
    }[flaw]
    columns[field]['type'] = replacement
    with pytest.raises(core.MigrationSchemaMismatch):
        validate_receipt_columns(mysql.dialect(), columns)


def test_mysql_receipt_columns_accept_exact_production_model():
    from backend.app.core.feedback_migration import validate_receipt_columns
    from backend.app.models.v3.feedback import FeedbackClearReceipt
    columns = {c.name:dict(name=c.name,type=c.type.dialect_impl(mysql.dialect()),nullable=False,default=None)
               for c in FeedbackClearReceipt.__table__.c}
    validate_receipt_columns(mysql.dialect(),columns)


def test_mysql_owner_clear_cutoff_preserves_receipt_microseconds():
    from backend.app.models.v3.music_library import OwnerMusicState
    assert 'preference_clear_cutoff DATETIME(6)' in str(CreateTable(OwnerMusicState.__table__).compile(dialect=mysql.dialect()))


def test_mysql_receipt_columns_accept_actual_reflected_signed_integer_types():
    from backend.app.core.feedback_migration import validate_receipt_columns
    from backend.app.models.v3.feedback import FeedbackClearReceipt
    columns={c.name:dict(name=c.name,type=c.type.dialect_impl(mysql.dialect()),nullable=False,default=None) for c in FeedbackClearReceipt.__table__.c}
    columns['internal_user_pk']['type']=mysql.INTEGER(unsigned=False)
    columns['resulting_feedback_epoch']['type']=mysql.BIGINT(unsigned=False)
    validate_receipt_columns(mysql.dialect(),columns)
