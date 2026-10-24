"""Formal 0013 SQLite validation and rendering. Reuses reviewed R1 checks.

No candidate metadata/ledger is installed and no commit is hidden here.
"""
import re
import sqlite3
from sqlalchemy import inspect
from backend.app.core import v3_migrations as core
from backend.app.models.v3.feedback import FeedbackV3, UserMusicPreferenceVersion

VERSION = '0013_v3_feedback_consent'
FIELDS = {'consent_policy_version','consented_at','deleted_at','source_task_id',
          'playback_event_row_id','evidence_epoch','request_fingerprint','learning_consent'}
TRIGGERS = ('int2_0013_feedback_insert_proof','int2_0013_feedback_immutable',
    'int2_0013_feedback_no_delete','int2_0013_feedback_no_replace',
    'int2_0013_task_proof_immutable','int2_0013_event_proof_immutable',
    'int2_0013_feedback_nonnull_pk','int2_0013_version_nonnull_pk_insert',
    'int2_0013_version_nonnull_pk_update')
TRIGGERS += ('int2_0013_clear_immutable', 'int2_0013_clear_no_delete', 'int2_0013_clear_no_replace')


def statements(sql):
    pending = ''
    for char in sql:
        pending += char
        if char == ';' and sqlite3.complete_statement(pending):
            yield pending.strip()
            pending = ''
    if pending.strip() and any(not line.lstrip().startswith('--') and line.strip()
                               for line in pending.splitlines()):
        raise core.MigrationSchemaMismatch('incomplete 0013 SQL')


def _tokens(sql):
    # Reuse the bounded lexer; preserve string case and literal bytes.
    pattern = r"\s+|--[^\n]*|/\*[\s\S]*?\*/|'(?:''|[^'])*'|[A-Za-z_][A-Za-z_0-9]*|[^\s]"
    return tuple(value if value.startswith("'") else value.lower()
                 for value in re.findall(pattern, sql)
                 if not value.isspace() and not value.startswith(('--', '/*')))


def _expected_triggers(sql):
    result = {}
    for statement in statements(sql):
        match = re.search(r'CREATE TRIGGER (int2_0013_\w+)', statement)
        if match:
            # sqlite_schema excludes a trailing statement delimiter.
            result[match[1]] = statement[match.start():].rstrip(';').strip()
    return result


def validate(engine, *, applied, sql):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    required = {'feedback_v3', 'user_music_preference_versions'}
    if not required.intersection(tables):
        if applied:
            raise core.MigrationSchemaMismatch('0013 tables missing')
        return False
    if not required <= tables:
        raise core.MigrationSchemaMismatch('partial feedback tables')
    columns = {table: {c['name']: c for c in inspector.get_columns(table)} for table in required}
    present = FIELDS.intersection(columns['feedback_v3'])
    version_present = 'evidence_epoch' in columns['user_music_preference_versions']
    if (present or version_present) and (present != FIELDS or not version_present):
        raise core.MigrationSchemaMismatch('partial feedback extension')
    extended = present == FIELDS
    if applied and not extended:
        raise core.MigrationSchemaMismatch('registered feedback columns missing')
    validate_receipts(engine, required=extended or applied)
    if engine.dialect.name != 'sqlite':
        from .feedback_mysql_migration import validate_schema
        validate_schema(engine, extended=extended, applied=applied, sql=sql)
        return extended
    _validate_legacy(engine)
    for model in (FeedbackV3, UserMusicPreferenceVersion):
        actual = set(columns[model.__tablename__])
        expected = set(model.__table__.c.keys())
        if not extended:
            expected -= FIELDS
        if actual != expected:
            raise core.MigrationSchemaMismatch('unknown feedback schema columns')
    with engine.connect() as db:
        if db.exec_driver_sql('PRAGMA foreign_key_check').first() is not None:
            raise core.MigrationSchemaMismatch('legacy foreign key violations')
        objects = db.exec_driver_sql("SELECT type,name,sql FROM sqlite_schema WHERE name LIKE 'int2_0013_%'").fetchall()
        if not extended:
            if objects:
                raise core.MigrationSchemaMismatch('0013 object collision')
            return False
        for table, fields in (('feedback_v3', FIELDS), ('user_music_preference_versions', {'evidence_epoch'})):
            for name in fields:
                column = columns[table][name]
                model = FeedbackV3 if table == 'feedback_v3' else UserMusicPreferenceVersion
                expected_type = str(model.__table__.c[name].type.compile(dialect=engine.dialect)).upper()
                if str(column['type']).upper() != expected_type or column['nullable'] != (name != 'learning_consent'):
                    raise core.MigrationSchemaMismatch('0013 type/nullability mismatch')
                default = column['default']
                invalid_default = str(default).strip("() '") != '0' if name == 'learning_consent' else default is not None
                if invalid_default:
                    raise core.MigrationSchemaMismatch('0013 default mismatch')
        # Accept either exact additive-DDL checks or the production ORM set.
        from sqlalchemy import CheckConstraint
        expected_additive = _extension_checks(sql)
        for model in (FeedbackV3, UserMusicPreferenceVersion):
            checks = {_check_signature(c['sqltext']) for c in inspector.get_check_constraints(model.__tablename__)}
            orm_checks = {_check_signature(str(c.sqltext)) for c in model.__table__.constraints
                          if isinstance(c, CheckConstraint) and str(c.name).startswith('s7_0013_')
                          and c.name != 's7_0013_mysql_fingerprint'}
            if not (expected_additive[model.__tablename__] <= checks or orm_checks <= checks):
                raise core.MigrationSchemaMismatch('0013 CHECK mismatch')
        for field, parent, key in (('source_task_id', 'generation_tasks', 'task_id'),
                                   ('playback_event_row_id', 'music_playback_events', 'playback_event_row_id')):
            # SQLAlchemy loses ON DELETE for SQLite inline ALTER-added FKs.
            # PRAGMA is the engine's authoritative action/column metadata.
            if not any(f[1] == 0 and f[2:5] == (parent, field, key) and f[6] == 'RESTRICT'
                       for f in db.exec_driver_sql('PRAGMA foreign_key_list(feedback_v3)').fetchall()):
                raise core.MigrationSchemaMismatch('0013 proof FK mismatch')
        indexes = inspector.get_indexes('feedback_v3')
        if not any(i['name'] == 'int2_0013_feedback_owner_deleted' and
                   i['column_names'] == ['internal_user_pk', 'deleted_at', 'created_at', 'feedback_id']
                   and not i.get('dialect_options', {}).get('sqlite_where') for i in indexes):
            raise core.MigrationSchemaMismatch('0013 owner index mismatch')
        expected = _expected_triggers(sql)
        actual = {name: text for kind, name, text in objects if kind == 'trigger'}
        if actual or applied:
            if set(actual) != set(expected) or any(_tokens(actual[n]) != _tokens(expected[n]) for n in expected):
                raise core.MigrationSchemaMismatch('0013 trigger mismatch')
        if any(kind not in {'trigger', 'index'} or (kind == 'index' and name != 'int2_0013_feedback_owner_deleted')
               for kind, name, _ in objects):
            raise core.MigrationSchemaMismatch('unknown 0013 object')
    return extended


def _extension_checks(sql):
    from sqlalchemy import create_engine
    reference = create_engine('sqlite:///:memory:')
    try:
        with reference.begin() as connection:
            for model in (FeedbackV3, UserMusicPreferenceVersion):
                fields = ','.join(name + ' TEXT' for name in model.__table__.c.keys() if name not in FIELDS)
                connection.exec_driver_sql(f'CREATE TABLE {model.__tablename__}({fields})')
            for statement in statements(sql):
                match = re.search(r'ALTER TABLE ', statement)
                if match:
                    connection.exec_driver_sql(statement[match.start():])
        return {model.__tablename__: {_check_signature(c['sqltext']) for c in inspect(reference).get_check_constraints(model.__tablename__)}
                for model in (FeedbackV3, UserMusicPreferenceVersion)}
    finally:
        reference.dispose()


def validate_receipt_columns(dialect, columns):
    from backend.app.models.v3.feedback import FeedbackClearReceipt
    for expected in FeedbackClearReceipt.__table__.c:
        actual = columns[expected.name]
        if actual['nullable'] or actual.get('default') is not None:
            raise core.MigrationSchemaMismatch('clear receipt nullable/default mismatch')
        wanted = expected.type.dialect_impl(dialect)
        reflected = actual['type']
        if dialect.name == 'sqlite':
            matches = str(reflected).upper() == str(wanted.compile(dialect=dialect)).upper()
        else:
            normalize = lambda kind: 'integer' if kind.lower() in {'int','integer'} else kind.lower()
            matches = normalize(reflected.__visit_name__) == normalize(wanted.__visit_name__)
            for attribute in ('length','unsigned','fsp'):
                matches = matches and getattr(reflected,attribute,None) == getattr(wanted,attribute,None)
            if expected.name == 'request_fingerprint':
                matches = matches and getattr(reflected,'charset',None) == 'ascii' and getattr(reflected,'collation',None) == 'ascii_bin'
        if not matches:
            raise core.MigrationSchemaMismatch('clear receipt type/precision/collation mismatch')


def validate_receipts(engine, *, required):
    from backend.app.models.v3.feedback import FeedbackClearReceipt
    from sqlalchemy import CheckConstraint
    inspector = inspect(engine)
    table = FeedbackClearReceipt.__table__
    if table.name not in inspector.get_table_names():
        if required:
            raise core.MigrationSchemaMismatch('clear receipt table missing')
        return
    columns = {c['name']: c for c in inspector.get_columns(table.name)}
    if set(columns) != set(table.c.keys()) or inspector.get_pk_constraint(table.name)['constrained_columns'] != ['operation_id']:
        raise core.MigrationSchemaMismatch('clear receipt schema mismatch')
    validate_receipt_columns(engine.dialect, columns)
    unique = inspector.get_unique_constraints(table.name) + [i for i in inspector.get_indexes(table.name) if i.get('unique')]
    if not any(i['column_names'] == ['internal_user_pk','operation','idempotency_key'] for i in unique):
        raise core.MigrationSchemaMismatch('clear receipt uniqueness missing')
    checks = inspector.get_check_constraints(table.name)
    for expected in table.constraints:
        if isinstance(expected, CheckConstraint) and not any(_check_signature(c['sqltext']) == _check_signature(str(expected.sqltext)) for c in checks):
            raise core.MigrationSchemaMismatch('clear receipt CHECK mismatch')
    with engine.connect() as connection:
        if engine.dialect.name == 'sqlite':
            if not any(row[2:5] == ('users','internal_user_pk','id') and row[6] == 'RESTRICT'
                       for row in connection.exec_driver_sql('PRAGMA foreign_key_list(feedback_clear_receipts)').fetchall()):
                raise core.MigrationSchemaMismatch('clear receipt owner FK mismatch')
        else:
            from .feedback_mysql_migration import require_enforced_checks
            require_enforced_checks(connection, table.name, {c['name'] for c in checks})
            if not any(f['constrained_columns'] == ['internal_user_pk'] and f['referred_table'] == 'users'
                       and f['referred_columns'] == ['id'] and f.get('options',{}).get('ondelete') == 'RESTRICT'
                       for f in inspector.get_foreign_keys(table.name)):
                raise core.MigrationSchemaMismatch('clear receipt owner FK mismatch')


def render_sqlite(engine, sql):
    extended = validate(engine, applied=False, sql=sql)
    if not extended:
        return sql
    triggers = _expected_triggers(sql)
    with engine.connect() as db:
        installed = {r[0] for r in db.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='trigger'")}
    return '\n'.join(statement for statement in statements(sql)
                     if any(f'CREATE TRIGGER {name}' in statement and name not in installed for name in triggers))


def rollback(engine):
    if engine.dialect.name != 'sqlite':
        raise core.MigrationSchemaMismatch('MySQL downgrade requires operator recovery')
    core.preflight_v3_migrations(engine)
    raw = engine.raw_connection()
    try:
        c = raw.cursor()
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1').fetchone() != (VERSION,):
            raise core.MigrationOrderError('0013 must be the latest migration')
        nonnull = ' OR '.join(f'{field} IS NOT NULL' for field in FIELDS - {'learning_consent'})
        if c.execute(f'SELECT 1 FROM feedback_v3 WHERE learning_consent!=0 OR {nonnull} LIMIT 1').fetchone() or c.execute('SELECT 1 FROM user_music_preference_versions WHERE evidence_epoch IS NOT NULL LIMIT 1').fetchone():
            raise core.MigrationSchemaMismatch('cannot discard feedback evidence')
        if c.execute('SELECT 1 FROM feedback_clear_receipts LIMIT 1').fetchone():
            raise core.MigrationSchemaMismatch('cannot discard clear receipts')
        if any(name not in TRIGGERS for (name,) in c.execute("SELECT name FROM sqlite_schema WHERE type IN ('trigger','view')")):
            raise core.MigrationSchemaMismatch('unknown external SQL dependency')
        for (table,) in c.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall():
            if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', table):
                raise core.MigrationSchemaMismatch('unknown table identifier')
            for fk in c.execute(f'PRAGMA foreign_key_list("{table}")'):
                if fk[2] in {'feedback_v3', 'user_music_preference_versions'} and fk[4] in FIELDS:
                    raise core.MigrationSchemaMismatch('external FK dependency')
        # Probe schema-only copies first, just as the existing 0011 executor
        # does. ORM table CHECKs cannot survive DROP COLUMN; never rebuild them.
        from contextlib import closing
        with closing(sqlite3.connect(':memory:')) as probe:
            try:
                for table in ('feedback_v3', 'user_music_preference_versions'):
                    ddl = c.execute("SELECT sql FROM sqlite_schema WHERE type='table' AND name=?", (table,)).fetchone()[0]
                    probe.execute(ddl)
                for field in ['learning_consent', *sorted(FIELDS - {'learning_consent'})]:
                    probe.execute(f'ALTER TABLE feedback_v3 DROP COLUMN {field}')
                probe.execute('ALTER TABLE user_music_preference_versions DROP COLUMN evidence_epoch')
            except sqlite3.Error as error:
                raise core.MigrationSchemaMismatch('0013 downgrade requires approved schema recovery') from error
        for name in TRIGGERS:
            c.execute(f'DROP TRIGGER {name}')
        c.execute('DROP TABLE feedback_clear_receipts')
        c.execute('DROP INDEX int2_0013_feedback_owner_deleted')
        for field in ['learning_consent', *sorted(FIELDS - {'learning_consent'})]:
            c.execute(f'ALTER TABLE feedback_v3 DROP COLUMN {field}')
        c.execute('ALTER TABLE user_music_preference_versions DROP COLUMN evidence_epoch')
        c.execute('DELETE FROM schema_migrations WHERE version=?', (VERSION,))
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()

def _check_signature(sql):
    try:return core._library_check_signature(sql)
    except ValueError:
        # 0012's bounded parser intentionally does not implement IS NOT NULL.
        # For old profile's paired-null CHECK accept ONLY the exact approved
        # token sequence (format/case/comments normalized), not guessed semantics.
        return ('exact_tokens',tuple(core._library_sql_tokens(sql)))


def _validate_legacy(engine):
    from sqlalchemy import inspect,CheckConstraint
    inspector=inspect(engine)
    for model in (FeedbackV3,UserMusicPreferenceVersion):
        table=model.__table__
        if inspector.get_pk_constraint(table.name)['constrained_columns']!=[c.name for c in table.primary_key]:
            raise core.MigrationSchemaMismatch('legacy primary key mismatch')
        required=('internal_user_pk','idempotency_key') if table.name=='feedback_v3' else ('profile_id','version')
        if not core._library_sqlite_full_unique(engine,table.name,list(required)):
            raise core.MigrationSchemaMismatch('legacy full binary uniqueness missing')
        actual={_check_signature(item['sqltext']) for item in inspector.get_check_constraints(table.name)}
        for check in (c for c in table.constraints if isinstance(c,CheckConstraint) and not str(c.name).startswith('s7_0013_')):
            variants={_check_signature(str(check.sqltext))}
            # SQL CHECK UNKNOWN permits NULL; this approved old inline enum is
            # equivalent ONLY because the actual continue_use column is nullable.
            if check.name=='ck_feedback_v3_continue_use':
                variants.add(_check_signature("continue_use IN ('yes','maybe','no')"))
            if not actual.intersection(variants):raise core.MigrationSchemaMismatch('legacy CHECK mismatch')
        cols={c['name']:c for c in inspector.get_columns(table.name)}
        for column in table.c:
            if column.name in FIELDS:continue
            actual_type=str(cols[column.name]['type']).upper()
            expected=str(column.type.compile(dialect=engine.dialect)).upper()
            allowed={expected}
            # Frozen SQLite migration used TEXT for strings/JSON and REAL for
            # Float. These are explicit historical alternatives, not arbitrary
            # affinity-based acceptance of unknown types or lengths.
            if expected.startswith('VARCHAR(') or expected in ('JSON','TEXT'):allowed.add('TEXT')
            if expected=='FLOAT':allowed.add('REAL')
            if actual_type not in allowed:raise core.MigrationSchemaMismatch('legacy column type mismatch')
            if not column.nullable and not column.primary_key and cols[column.name]['nullable']:
                raise core.MigrationSchemaMismatch('legacy nullability mismatch')
            default=cols[column.name]['default']
            normalized='NULL' if default is None else str(default).strip('() ').upper()
            defaults={'NULL'}
            if column.name=='created_at':defaults={'CURRENT_TIMESTAMP'}
            elif table.name=='user_music_preference_versions':
                if column.name=='feedback_count':defaults.add('0')
                if column.name=='minimum_samples_for_application':defaults.add('3')
            if normalized not in defaults:raise core.MigrationSchemaMismatch('legacy default mismatch')
            if column.primary_key and cols[column.name]['nullable']:
                if actual_type!='TEXT':raise core.MigrationSchemaMismatch('unknown nullable legacy primary key')
                with engine.connect() as db:
                    if db.exec_driver_sql(f'SELECT 1 FROM {table.name} WHERE {column.name} IS NULL LIMIT 1').first():
                        raise core.MigrationSchemaMismatch('legacy null primary key data')
        fks={(tuple(f['constrained_columns']),f['referred_table'],tuple(f['referred_columns']),f.get('options',{}).get('ondelete','NO ACTION').upper()) for f in inspector.get_foreign_keys(table.name)}
        for foreign in table.foreign_key_constraints:
            if set(foreign.column_keys).intersection(FIELDS):continue
            expected=(tuple(c.name for c in foreign.columns),foreign.referred_table.name,
                tuple(e.column.name for e in foreign.elements),(foreign.ondelete or 'NO ACTION').upper())
            if expected not in fks:raise core.MigrationSchemaMismatch('legacy FK missing or action mismatch')


