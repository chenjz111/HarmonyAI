"""Formal0013 MySQL metadata rendering; bounded real-server evidence in docs/sprint7/REAL_MYSQL_ACCEPTANCE_20261027.md."""
import re
from pathlib import Path
from .v3_migrations import MigrationSchemaMismatch


def read_parent_contract(connection):
    """Reads actual INFORMATION_SCHEMA, not caller-claimed matching strings.

    Unit tests use synthetic connections; the opt-in harness uses a new real DB.
    """
    if connection.dialect.name!='mysql':raise MigrationSchemaMismatch('MySQL metadata connection required')
    version=connection.exec_driver_sql('SELECT VERSION()').scalar()
    match=re.match(r'^(\d+)\.(\d+)\.(\d+)',str(version))
    if not match or 'mariadb' in str(version).lower() or tuple(map(int,match.groups()))<(8,0,16):
        raise MigrationSchemaMismatch('unapproved CHECK/version capability')
    def col(table,name):
        from sqlalchemy import text
        row=connection.execute(text('SELECT COLUMN_TYPE,CHARACTER_SET_NAME,COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t AND COLUMN_NAME=:c'),{'t':table,'c':name}).first()
        if row is None:raise MigrationSchemaMismatch('unknown parent column metadata')
        return tuple(row)
    task=col('generation_tasks','task_id')
    if not re.fullmatch(r'varchar\(64\)',task[0],re.I) or not all(isinstance(x,str) and re.fullmatch('[a-zA-Z0-9_]+',x) for x in task[1:]):
        raise MigrationSchemaMismatch('unknown task key type/charset/collation')
    if col('music_playback_events','source_context_id')!=task:raise MigrationSchemaMismatch('task/event collation mismatch')
    asset=col('generation_tasks','music_asset_id')
    if not re.fullmatch(r'varchar\(64\)',asset[0],re.I) or not all(isinstance(x,str) and re.fullmatch('[a-zA-Z0-9_]+',x) for x in asset[1:]):
        raise MigrationSchemaMismatch('unsupported asset key type/charset/collation')
    if col('feedback_v3','music_asset_id')!=asset or col('music_playback_events','music_asset_id')!=asset or col('music_assets','music_asset_id')!=asset:
        raise MigrationSchemaMismatch('existing asset key mismatch; no implicit ALTER')
    owner=col('users','id')
    if not re.fullmatch(r'int(?:\(\d+\))?',owner[0],re.I) or owner[1:]!=(None,None):raise MigrationSchemaMismatch('unknown internal owner PK type')
    for table in ('feedback_v3','generation_tasks','music_playback_events'):
        if col(table,'internal_user_pk')!=owner:raise MigrationSchemaMismatch('owner FK type mismatch')
    event=col('music_playback_events','playback_event_row_id')
    if not re.fullmatch(r'int(?:\(\d+\))?',event[0],re.I) or event[1:]!=(None,None):
        raise MigrationSchemaMismatch('unknown signed event row PK')
    from sqlalchemy import text
    engines=connection.execute(text("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('users','feedback_v3','generation_tasks','music_assets','music_playback_events','user_music_preference_versions')")).fetchall()
    if len(engines)!=6 or any(engine.lower()!='innodb' for _,engine in engines):raise MigrationSchemaMismatch('InnoDB parents required')
    return dict(task=task,asset=asset,event=event,owner=owner)


def render_up(connection, sql):
    types=read_parent_contract(connection)
    task,event=types['task'],types['event']
    return sql.replace('{{TASK_ID_TYPE}}',f'{task[0]} CHARACTER SET {task[1]} COLLATE {task[2]}').replace('{{EVENT_ROW_TYPE}}',event[0])


def _check_expressions(sql):
    result = {}
    for match in re.finditer(r'ADD CONSTRAINT (\w+) CHECK\(', sql):
        start, depth, quoted, index = match.end(), 1, False, match.end()
        while index < len(sql) and depth:
            char = sql[index]
            if char == "'":
                if quoted and index + 1 < len(sql) and sql[index + 1] == "'":
                    index += 2
                    continue
                quoted = not quoted
            elif not quoted:
                depth += (char == '(') - (char == ')')
            index += 1
        if depth or quoted:
            raise MigrationSchemaMismatch('invalid MySQL 0013 CHECK source')
        result[match[1]] = sql[start:index - 1]
    return result


def _check_signature(expression):
    from .feedback_migration import _check_signature as signature
    from .v3_migrations import _library_sql_tokens
    # MySQL8 rewrites this REGEXP predicate into REGEXP_LIKE/SUBSTR. The
    # general bounded parser does not implement those functions. Recognize
    # only these two COMPLETE, immutable expressions; never discard boolean
    # parentheses or infer equivalence from a substring.
    source = "request_fingerprint IS NULL OR (CHAR_LENGTH(request_fingerprint)=71 AND LEFT(request_fingerprint,7)='sha256:' AND SUBSTRING(request_fingerprint,8) REGEXP '^[0-9a-f]+$')"
    reflected = "((request_fingerprint is null) or ((char_length(request_fingerprint) = 71) and (left(request_fingerprint,7) = _ascii'sha256:') and regexp_like(substr(request_fingerprint,8),_ascii'^[0-9a-f]+$')))"
    tokens = tuple(_library_sql_tokens(expression))
    if tokens in (tuple(_library_sql_tokens(source)), tuple(_library_sql_tokens(reflected))):
        return ('mysql_fingerprint_v1',)
    # MySQL reflects CHAR_LENGTH as char_length, and may quote identifiers.
    return signature(re.sub(r'\bchar_length\b', 'length', expression, flags=re.I))


def require_enforced_checks(connection, table, names):
    from sqlalchemy import text
    rows = connection.execute(text("SELECT CONSTRAINT_NAME,ENFORCED FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=:table AND CONSTRAINT_TYPE='CHECK'"), {'table':table}).fetchall()
    enforced = {name: value for name, value in rows}
    if any(enforced.get(name) != 'YES' for name in names):
        raise MigrationSchemaMismatch('MySQL CHECK is missing or not enforced')


def validate_legacy(connection, inspector):
    from sqlalchemy import CheckConstraint
    from .feedback_migration import FIELDS, FeedbackV3, UserMusicPreferenceVersion
    for model in (FeedbackV3, UserMusicPreferenceVersion):
        table = model.__table__
        if inspector.get_pk_constraint(table.name)['constrained_columns'] != [c.name for c in table.primary_key]:
            raise MigrationSchemaMismatch('MySQL legacy primary key mismatch')
        required = ['internal_user_pk','idempotency_key'] if table.name == 'feedback_v3' else ['profile_id','version']
        unique = inspector.get_unique_constraints(table.name) + [i for i in inspector.get_indexes(table.name) if i.get('unique')]
        if not any(i['column_names'] == required and not i.get('dialect_options',{}).get('mysql_length') for i in unique):
            raise MigrationSchemaMismatch('MySQL legacy full uniqueness missing')
        checks = inspector.get_check_constraints(table.name)
        for check in table.constraints:
            if isinstance(check, CheckConstraint) and not str(check.name).startswith('s7_0013_'):
                matching = {c['name'] for c in checks if _check_signature(c['sqltext']) == _check_signature(str(check.sqltext))}
                if not matching:
                    raise MigrationSchemaMismatch('MySQL legacy CHECK mismatch')
                require_enforced_checks(connection, table.name, matching)
        columns = {c['name']: c for c in inspector.get_columns(table.name)}
        for expected in table.c:
            if expected.name in FIELDS:
                continue
            actual = columns.get(expected.name)
            if actual is None or actual['nullable'] != expected.nullable:
                raise MigrationSchemaMismatch('MySQL legacy column nullability mismatch')
            from .v3_migrations import _canonical_sql_type_name
            kind = _canonical_sql_type_name(actual['type'].__visit_name__)
            wanted = _canonical_sql_type_name(expected.type.__visit_name__)
            if kind in {'int','integer'}:
                kind = 'integer'
            if wanted in {'int','integer'}:
                wanted = 'integer'
            if wanted == 'float' and kind in {'decimal','numeric'}:
                if (actual['type'].precision, actual['type'].scale) != (6,5):
                    raise MigrationSchemaMismatch('MySQL legacy decimal mismatch')
            elif kind != wanted:
                raise MigrationSchemaMismatch('MySQL legacy column type mismatch')
            if getattr(actual['type'], 'unsigned', False) or getattr(actual['type'], 'length', None) != getattr(expected.type, 'length', None):
                raise MigrationSchemaMismatch('MySQL legacy column length/signedness mismatch')
            default = actual.get('default')
            if expected.name == 'created_at':
                from .v3_migrations import _is_current_timestamp_default
                if not _is_current_timestamp_default(default,'mysql'):
                    raise MigrationSchemaMismatch('MySQL legacy timestamp default mismatch')
            elif default is not None and str(default).upper() != 'NULL':
                raise MigrationSchemaMismatch('MySQL legacy column default mismatch')
        fks = inspector.get_foreign_keys(table.name)
        for foreign in table.foreign_key_constraints:
            if FIELDS.intersection(foreign.column_keys):
                continue
            if not any(f['constrained_columns'] == list(foreign.column_keys) and
                       f['referred_table'] == foreign.referred_table.name and
                       f['referred_columns'] == [e.column.name for e in foreign.elements] and
                       (f.get('options',{}).get('ondelete') or 'NO ACTION') == (foreign.ondelete or 'NO ACTION') for f in fks):
                raise MigrationSchemaMismatch('MySQL legacy FK mismatch')


def validate_schema(engine, *, extended, applied, sql):
    """Refuse partial DDL; never infer a successful install from column names."""
    from sqlalchemy import inspect, text
    from .feedback_migration import _tokens, FIELDS, FeedbackV3, UserMusicPreferenceVersion
    inspector = inspect(engine)
    with engine.connect() as connection:
        parent = read_parent_contract(connection)
        validate_legacy(connection, inspector)
        cutoff = next((c for c in inspector.get_columns('owner_music_state') if c['name'] == 'preference_clear_cutoff'), None)
        if cutoff is None or cutoff['type'].__visit_name__.lower() != 'datetime' or not cutoff['nullable'] or getattr(cutoff['type'],'fsp',None) not in ({6} if applied else {None,0,6}):
            raise MigrationSchemaMismatch('MySQL owner cutoff precision/profile mismatch')
        rows = connection.execute(text("SELECT TRIGGER_NAME,ACTION_TIMING,EVENT_MANIPULATION,EVENT_OBJECT_TABLE,ACTION_STATEMENT FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND TRIGGER_NAME LIKE 'int2_0013_%'")).fetchall()
        if not extended:
            if rows:
                raise MigrationSchemaMismatch('partial MySQL 0013 triggers')
            return
        for model in (FeedbackV3, UserMusicPreferenceVersion):
            columns = {c['name']: c for c in inspector.get_columns(model.__tablename__)}
            if set(columns) != set(model.__table__.c.keys()):
                raise MigrationSchemaMismatch('unknown MySQL feedback columns')
            for name in FIELDS.intersection(columns):
                c = columns[name]
                actual = str(c['type'].__visit_name__).lower()
                expected = ('integer' if name in {'learning_consent','playback_event_row_id'} else
                            'bigint' if name == 'evidence_epoch' else
                            'datetime' if name in {'consented_at','deleted_at'} else 'varchar')
                if actual in {'int', 'integer'}:
                    actual = 'integer'
                if actual != expected or getattr(c['type'], 'unsigned', False):
                    raise MigrationSchemaMismatch('MySQL extension type mismatch')
                if getattr(c['type'], 'length', None) != getattr(model.__table__.c[name].type, 'length', None):
                    raise MigrationSchemaMismatch('MySQL extension length mismatch')
                if expected == 'datetime' and getattr(c['type'], 'fsp', None) != 6:
                    raise MigrationSchemaMismatch('MySQL timestamp precision mismatch')
                if c['nullable'] != (name != 'learning_consent'):
                    raise MigrationSchemaMismatch('MySQL extension nullability mismatch')
                default = c.get('default')
                if name == 'learning_consent':
                    if str(default).strip("() '") != '0':
                        raise MigrationSchemaMismatch('MySQL consent default mismatch')
                elif default is not None and str(default).upper() != 'NULL':
                    raise MigrationSchemaMismatch('MySQL extension default mismatch')
        def reflected(table, column):
            return connection.execute(text('SELECT COLUMN_TYPE,CHARACTER_SET_NAME,COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t AND COLUMN_NAME=:c'), {'t':table,'c':column}).first()
        if tuple(reflected('feedback_v3','source_task_id') or ()) != parent['task']:
            raise MigrationSchemaMismatch('MySQL feedback task collation mismatch')
        fingerprint = reflected('feedback_v3','request_fingerprint')
        if fingerprint is None or tuple(fingerprint) != ('varchar(71)','ascii','ascii_bin'):
            raise MigrationSchemaMismatch('MySQL fingerprint binary type mismatch')
        fks = inspector.get_foreign_keys('feedback_v3')
        for fields, table, parents in (
            (['source_task_id','internal_user_pk','music_asset_id'], 'generation_tasks', ['task_id','internal_user_pk','music_asset_id']),
            (['playback_event_row_id','internal_user_pk','music_asset_id','source_task_id'], 'music_playback_events', ['playback_event_row_id','internal_user_pk','music_asset_id','source_context_id'])):
            if not any(f['constrained_columns'] == fields and f['referred_table'] == table and
                       f['referred_columns'] == parents and f.get('options',{}).get('ondelete') == 'RESTRICT' for f in fks):
                raise MigrationSchemaMismatch('MySQL composite proof FK mismatch')
        for table, fields, unique in (
            ('music_playback_events', ['playback_event_row_id','internal_user_pk','music_asset_id','source_context_id'], True),
            ('feedback_v3', ['internal_user_pk','deleted_at','created_at','feedback_id'], False)):
            if not any(i['column_names'] == fields and bool(i['unique']) == unique for i in inspector.get_indexes(table)):
                raise MigrationSchemaMismatch('MySQL feedback index mismatch')
        # Validate installed CHECKs against known production or additive names.
        required = {'feedback_v3': [({'int2_0013_consent','s7_0013_consent'}),
            {'int2_0013_epoch','s7_0013_epoch'}, {'int2_0013_fingerprint','s7_0013_mysql_fingerprint'},
            {'int2_0013_event_context','s7_0013_event_context'}],
            'user_music_preference_versions': [{'int2_0013_version_epoch','s7_0013_version_epoch'}]}
        for table, groups in required.items():
            checks = {c['name']: c['sqltext'] for c in inspector.get_check_constraints(table)}
            model = FeedbackV3 if table == 'feedback_v3' else UserMusicPreferenceVersion
            expected_checks = _check_expressions(sql)
            expected_checks.update({c.name: str(c.sqltext) for c in model.__table__.constraints if hasattr(c, 'sqltext')})
            for group in groups:
                if not group.intersection(checks):
                    raise MigrationSchemaMismatch('MySQL feedback CHECK missing')
                if not any(_check_signature(checks[name]) == _check_signature(expected_checks[name]) for name in group.intersection(checks)):
                    raise MigrationSchemaMismatch('MySQL feedback CHECK definition mismatch')
                require_enforced_checks(connection, table, group.intersection(checks))
        expected_triggers = {}
        from .v3_migrations import _mysql_migration_statements
        for statement in _mysql_migration_statements(sql):
            match = re.fullmatch(r'CREATE TRIGGER (\w+) (BEFORE|AFTER) (INSERT|UPDATE|DELETE) ON (\w+) FOR EACH ROW\s+(.*)', statement, re.S)
            if match:
                expected_triggers[match[1]] = (match[2], match[3], match[4], _tokens(match[5]))
        actual_triggers = {name: (timing, event, table, _tokens(body)) for name,timing,event,table,body in rows}
        if (rows or applied) and actual_triggers != expected_triggers:
            raise MigrationSchemaMismatch('MySQL 0013 trigger mismatch; operator recovery required')


def render_for_engine(engine, connection, sql):
    from sqlalchemy import inspect
    rendered = render_up(connection, sql)
    if 'learning_consent' in {c['name'] for c in inspect(engine).get_columns('feedback_v3')}:
        validate_schema(engine, extended=True, applied=False, sql=sql)
        from .v3_migrations import _mysql_migration_statements
        return ';\n'.join(s for s in _mysql_migration_statements(rendered) if s.startswith('CREATE TRIGGER') or s.startswith('ALTER TABLE owner_music_state')) + ';'
    return rendered
