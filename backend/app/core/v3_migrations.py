"""Versioned Sprint 5 V3 migrations with immutable checksums."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re

from sqlalchemy import event, inspect, Integer, String, DateTime
from sqlalchemy.engine import Engine


V3_FOUNDATION_VERSION = "0001_v3_foundation"
V3_MIGRATION_VERSIONS = [
    "0001_v3_foundation",
    "0002_v3_business",
    "0003_v3_owner_flow",
    "0004_v3_multidoc",
    "0005_v3_relevance",
    "0006_v3_doc_fk",
    "0007_v3_prescription_mode",
    "0008_v3_prescription_user_goal_snapshot",
    "0009_v3_five_tone_read_model",
    "0010_v3_generation_prompt_audit",
    "0011_v3_auth_foundation",
    "0012_v3_music_library",
]

_REQUIRED_TABLES = {
    "owner_music_state", "music_library_state", "music_playback_events",
    "auth_sessions",
    # 0001 foundation
    "user_identities",
    "user_profiles",
    "idempotency_records",
    # 0002 business (information understanding)
    "understanding_runs",
    "understanding_sources",
    "understanding_revisions",
    "normalized_facts",
    "fact_source_refs",
    "questionnaire_submissions_v3",
    # 0002 business (assessment)
    "assessment_v3",
    "assessment_revisions_v3",
    "fact_evidence",
    "organ_evidence",
    # 0002 business (diagnosis / rag)
    "diagnosis_runs",
    "diagnosis_candidates",
    "diagnosis_candidate_evidence",
    "knowledge_manifests",
    "knowledge_chunks_v3",
    "rag_retrieval_runs",
    "rag_retrieval_hits",
    "ai_provider_runs",
    # 0002 business (prescription / music)
    "prescription_v3",
    "generation_tasks",
    "music_assets",
    # 0002 business (feedback / preference / favorite)
    "feedback_v3",
    "user_music_preferences",
    "user_music_preference_versions",
    "user_preference_items",
    "preference_events",
    "favorites",
    # 0003 owner flow amendment (session activity audit)
    "session_input_revisions",
    # 0004 multi-document (document set)
    "document_sets",
    "document_set_items",
    # 0005 document relevance
    "document_relevances",
}


class MigrationChecksumMismatch(RuntimeError):
    """Raised when an already-applied migration file was changed."""


class MigrationOrderError(RuntimeError):
    """History is not a legal immutable prefix; reject before DDL."""


class MigrationSchemaMismatch(RuntimeError):
    """Existing partial/create_all schema is incompatible; do not guess repair."""


def preflight_v3_migrations(engine: Engine, *, migrations_root=None):
    """Read-only validation; called before initialization create_all as well."""
    versions = list(V3_MIGRATION_VERSIONS)
    numbers = [int(v[:4]) if re.fullmatch(r'\d{4}_[a-z0-9_]+', v) else -1 for v in versions]
    if not versions or numbers != list(range(1, len(versions)+1)) or len(set(versions)) != len(versions):
        raise MigrationOrderError('registered migration order is invalid')
    dialect = engine.dialect.name
    if dialect not in {'sqlite','mysql'}:
        raise RuntimeError(f'unsupported V3 migration dialect: {dialect}')
    inspector = inspect(engine)
    rows = []
    if 'schema_migrations' in inspector.get_table_names():
        with engine.connect() as connection:
            rows = connection.exec_driver_sql('SELECT version,checksum FROM schema_migrations ORDER BY applied_at,version').fetchall()
    applied = [row[0] for row in rows]
    if applied != versions[:len(applied)] or len(set(applied)) != len(applied):
        raise MigrationOrderError('applied migration order is not a complete registered prefix')
    # Read every source before applying anything, not one migration at a time.
    sources = {version: _read_migration(dialect,version,'up',migrations_root) for version in versions}
    for version,checksum in rows:
        if checksum != _checksum(sources[version]):
            raise MigrationChecksumMismatch(f'applied migration {version} checksum changed')
    _validate_auth_existing_schema(engine)
    _validate_library_existing_schema(engine, library_applied='0012_v3_music_library' in applied)
    return sources


def _library_sql_tokens(sql):
    """Tokenize the bounded CHECK vocabulary; never evaluate SQL or ignore gaps."""
    if not isinstance(sql, str) or len(sql) > 65536:
        raise ValueError('unverifiable SQL')
    pattern = r"\s+|--[^\n]*|/\*[\s\S]*?\*/|'(?:''|[^'])*'|`(?:``|[^`])*`|\"(?:\"\"|[^\"])*\"|\[[^\]]+\]|>=|<=|<>|!=|==|[=><(),.+-]|\d+|[A-Za-z_][A-Za-z_0-9]*"
    tokens, offset = [], 0
    for match in re.finditer(pattern, sql):
        if match.start() != offset:
            raise ValueError('unsupported SQL token')
        value = match[0]
        offset = match.end()
        if value.isspace() or value.startswith(('--','/*')):
            continue
        if value.startswith(('`','"','[')):
            value = value[1:-1].replace('``','`').replace('""','"').lower()
        elif not value.startswith("'"):
            value = value.lower()
        tokens.append(value)
    if offset != len(sql):
        raise ValueError('unsupported SQL suffix')
    return tokens


def _library_check_signature(sql):
    """Small structural parser, not a substring test or a general SQL solver.

    Accept parentheses, quoting, commutative AND/OR, reversed comparisons,
    integer boundary equivalents, BETWEEN and singleton IN. Unknown expressions
    fail closed; an extra OR branch cannot masquerade as a required CHECK.
    """
    tokens = _library_sql_tokens(sql)
    position = 0

    def take(expected=None):
        nonlocal position
        if position >= len(tokens) or (expected is not None and tokens[position] != expected):
            raise ValueError('unexpected CHECK token')
        value = tokens[position]
        position += 1
        return value

    def peek():
        return tokens[position] if position < len(tokens) else None

    def boolean(kind, children):
        flat = []
        for child in children:
            flat.extend(child[1] if child[0] == kind else [child])
        return flat[0] if len(flat) == 1 else (kind, tuple(sorted(flat, key=repr)))

    def operand():
        value = take()
        if value in ('+','-'):
            number = take()
            if not number.isdigit():
                raise ValueError('noninteger boundary')
            return ('literal', int(number) * (-1 if value == '-' else 1))
        if value.isdigit():
            return ('literal', int(value))
        if value in ('_utf8mb4','_utf8mb3','_utf8','_ascii','_latin1'):
            value = take()
            if not value.startswith("'"):
                raise ValueError('invalid character introducer')
        if value.startswith("'"):
            return ('literal', value[1:-1].replace("''", "'"))
        if not re.fullmatch('[a-z_][a-z_0-9]*', value):
            raise ValueError('unsupported CHECK operand')
        if peek() == '(':
            if value not in ('length','char_length','character_length'):
                raise ValueError('unsupported CHECK function')
            take('(')
            argument = operand()
            take(')')
            if argument[0] != 'column':
                raise ValueError('unsupported function argument')
            return ('char_length' if value == 'character_length' else value, argument)
        return ('column', value)

    def comparison(left, op, right):
        if left[0] == 'literal' and right[0] != 'literal':
            left, right = right, left
            op = {'>=':'<=','<=':'>=','>':'<','<':'>','=':'=','==':'=','!=':'!=','<>':'!='}[op]
        if op in ('==','<>'):
            op = {'==':'=','<>':'!='}[op]
        # SQLite INTEGER affinity does not exclude REAL values. Only length
        # functions are guaranteed integral, so do not fold column boundaries.
        if left[0] in ('length','char_length') and right[0] == 'literal' and isinstance(right[1],int) and op in ('>','<'):
            op, right = ('>=',('literal',right[1]+1)) if op == '>' else ('<=',('literal',right[1]-1))
        return ('compare', op, left, right)

    def predicate():
        if peek() == '(':
            take('(')
            value = disjunction()
            take(')')
            return value
        left = operand()
        op = take()
        if op == 'is':
            take('null')
            return ('is_null', left)
        if op == 'between':
            low = operand()
            take('and')
            high = operand()
            return boolean('and',[comparison(left,'>=',low),comparison(left,'<=',high)])
        if op == 'in':
            take('(')
            values = [operand()]
            while peek() == ',':
                take(',')
                values.append(operand())
            take(')')
            if len(values) == 1:
                return comparison(left,'=',values[0])
            return ('in',left,tuple(sorted(values,key=repr)))
        if op not in ('>=','<=','>','<','=','==','!=','<>'):
            raise ValueError('unsupported CHECK comparison')
        return comparison(left,op,operand())

    def conjunction():
        values = [predicate()]
        while peek() == 'and':
            take('and')
            values.append(predicate())
        return boolean('and',values)

    def disjunction():
        values = [conjunction()]
        while peek() == 'or':
            take('or')
            values.append(conjunction())
        return boolean('or',values)

    signature = disjunction()
    if position != len(tokens):
        raise ValueError('unparsed CHECK expression')
    return signature


def _library_full_unique(item, columns):
    options = item.get('dialect_options') or {}
    for key,value in options.items():
        if key.endswith(('_where','_length','_prefix')) and value is not None and value is not False:
            if not isinstance(value,dict) or value:
                return False
    return (item.get('unique', True) in (True,1)
            and item.get('column_names') == columns
            and not item.get('expressions'))


def _library_sqlite_full_unique(engine, table, columns, *, index_name=None):
    """Inspector omits SQLite expression/collation details; verify real keys."""
    from sqlalchemy import text
    with engine.connect() as connection:
        indexes = connection.execute(text('SELECT name,"unique",partial FROM pragma_index_list(:table)'),{'table':table}).all()
        for name,unique,partial in indexes:
            if not unique or partial or (index_name is not None and name != index_name):
                continue
            rows = connection.execute(text('SELECT cid,name,coll,"key" FROM pragma_index_xinfo(:name) ORDER BY seqno'),{'name':name}).all()
            keys = [row for row in rows if row[3]]
            if ([row[1] for row in keys] == columns
                    and all(row[0] >= 0 and str(row[2]).upper() == 'BINARY' for row in keys)):
                return True
    return False


def _validate_library_existing_schema(engine, *, library_applied=False):
    """Read-only complete 0012 contract check; unknown metadata is not approval."""
    from sqlalchemy import BigInteger, text
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    contracts = {
        'owner_music_state': {
            'owner_internal_user_pk':(Integer,None,False), 'library_epoch':(BigInteger,None,False),
            'feedback_evidence_epoch':(BigInteger,None,False), 'preference_clear_cutoff':(DateTime,None,True),
            'created_at':(DateTime,None,False), 'updated_at':(DateTime,None,False),
        },
        'music_library_state': {
            'owner_internal_user_pk':(Integer,None,False), 'music_asset_id':(String,64,False),
            'user_title':(String,120,True), 'metadata_version':(BigInteger,None,False),
            'created_at':(DateTime,None,False), 'updated_at':(DateTime,None,False),
        },
        'music_playback_events': {
            'playback_event_row_id':(Integer,None,False), 'internal_user_pk':(Integer,None,False),
            'event_id':(String,64,False), 'music_asset_id':(String,64,False),
            'event_type':(String,24,False), 'source_context_id':(String,64,True),
            'occurred_at':(DateTime,None,False), 'created_at':(DateTime,None,False),
        },
    }
    existing = tables.intersection(contracts)
    if library_applied and existing != set(contracts):
        raise MigrationSchemaMismatch('recorded 0012 is missing required tables')
    pks = {'owner_music_state':['owner_internal_user_pk'],
           'music_library_state':['owner_internal_user_pk','music_asset_id'],
           'music_playback_events':['playback_event_row_id']}
    checks = {
        'owner_music_state':['library_epoch>=0','feedback_evidence_epoch>=0'],
        'music_library_state':['metadata_version>=0','user_title IS NULL OR (length(user_title)>=1 AND length(user_title)<=120)'],
        'music_playback_events':["event_type IN ('play_started')",'length(event_id)>=1 AND length(event_id)<=64',
                                 'source_context_id IS NULL OR length(source_context_id)<=64'],
    }
    expected_fks = {
        'owner_music_state': [(['owner_internal_user_pk'],'users',['id'],'CASCADE')],
        'music_library_state': [(['owner_internal_user_pk'],'users',['id'],'CASCADE'),
                                (['music_asset_id'],'music_assets',['music_asset_id'],'CASCADE')],
        'music_playback_events': [(['internal_user_pk'],'users',['id'],'CASCADE'),
                                  (['music_asset_id'],'music_assets',['music_asset_id'],'CASCADE'),
                                  (['source_context_id','internal_user_pk','music_asset_id'],'generation_tasks',
                                   ['task_id','internal_user_pk','music_asset_id'],'NO ACTION')],
    }
    dialect = engine.dialect.name
    if existing and dialect == 'sqlite':
        with engine.connect() as connection:
            if connection.exec_driver_sql('PRAGMA ignore_check_constraints').scalar() != 0:
                raise MigrationSchemaMismatch('SQLite CHECK enforcement is unverifiable or disabled')
    if existing and dialect == 'mysql':
        version = engine.dialect.server_version_info
        if not version or version < (8,0,16) or getattr(engine.dialect,'is_mariadb',False):
            raise MigrationSchemaMismatch('0012 requires verified MySQL >=8.0.16 CHECK enforcement')

    def terms(signature):
        return set(signature[1]) if signature[0] == 'and' else {signature}

    def normalized_check(sql, table):
        signature = _library_check_signature(sql)
        # The frozen ORM uses LENGTH for ASCII opaque event/context identifiers;
        # the paired MySQL DDL uses CHAR_LENGTH. Both bound those identifiers.
        def normalize(node):
            if not isinstance(node,tuple):
                return node
            if (dialect == 'mysql' and table == 'music_playback_events' and node[0] == 'length'
                    and node[1] in (('column','event_id'),('column','source_context_id'))):
                return ('char_length',node[1])
            return tuple(normalize(value) for value in node)
        return normalize(signature)

    for table in sorted(existing):
        columns = {column['name']:column for column in inspector.get_columns(table)}
        if set(columns) != set(contracts[table]):
            raise MigrationSchemaMismatch(f'incompatible library columns: {table}')
        for name,(kind,length,nullable) in contracts[table].items():
            column = columns[name]
            if (not isinstance(column['type'],kind) or column['nullable'] != nullable
                    or (kind is Integer and isinstance(column['type'],BigInteger))
                    or getattr(column['type'],'unsigned',False)
                    or (length is not None and getattr(column['type'],'length',None) != length)):
                raise MigrationSchemaMismatch(f'incompatible library column: {table}.{name}')
            if name in ('library_epoch','feedback_evidence_epoch','metadata_version'):
                try:
                    default = _library_sql_tokens(str(column.get('default')))
                except ValueError as error:
                    raise MigrationSchemaMismatch(f'unverifiable library default: {table}.{name}') from error
                if [token for token in default if token not in ('(',')')] not in (['0'],["'0'"]):
                    raise MigrationSchemaMismatch(f'incompatible library default: {table}.{name}')
        if inspector.get_pk_constraint(table).get('constrained_columns') != pks[table]:
            raise MigrationSchemaMismatch(f'incompatible library primary key: {table}')
        fks = inspector.get_foreign_keys(table)
        for local,target,remote,ondelete in expected_fks[table]:
            if target not in tables:
                raise MigrationSchemaMismatch(f'missing library foreign-key parent: {target}')
            def matches(fk):
                options = fk.get('options') or {}
                return (fk.get('constrained_columns') == local and fk.get('referred_table') == target
                        and fk.get('referred_columns') == remote
                        and fk.get('referred_schema') in (None,engine.dialect.default_schema_name)
                        and options.get('ondelete','NO ACTION').upper() == ondelete
                        and options.get('onupdate','NO ACTION').upper() == 'NO ACTION'
                        and not options.get('deferrable') and options.get('initially','IMMEDIATE').upper() == 'IMMEDIATE')
            if not any(matches(fk) for fk in fks):
                raise MigrationSchemaMismatch(f'incompatible library foreign key: {table}.{local[0]}')
        if len(fks) != len(expected_fks[table]):
            raise MigrationSchemaMismatch(f'unexpected library foreign key: {table}')
        reflected_checks = inspector.get_check_constraints(table)
        try:
            expected = set()
            actual = set()
            for sql in checks[table]:
                if dialect == 'mysql':
                    sql = sql.replace('length(', 'char_length(')
                expected.update(terms(normalized_check(sql,table)))
            for check in reflected_checks:
                actual.update(terms(normalized_check(check['sqltext'],table)))
            if actual != expected:
                raise ValueError('CHECK differs from approved contract')
        except (ValueError,KeyError,TypeError,RecursionError) as error:
            raise MigrationSchemaMismatch(f'unverifiable library CHECK: {table}') from error
        if dialect == 'mysql':
            try:
                with engine.connect() as connection:
                    rows = connection.execute(text("SELECT CONSTRAINT_NAME, ENFORCED FROM information_schema.TABLE_CONSTRAINTS "
                                                   "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND CONSTRAINT_TYPE='CHECK'"),
                                              {'table':table}).all()
                enforced = dict(rows)
                if any(not check.get('name') or enforced.get(check['name']) != 'YES' for check in reflected_checks):
                    raise ValueError('CHECK enforcement not confirmed')
            except Exception as error:
                raise MigrationSchemaMismatch(f'MySQL CHECK enforcement unverifiable: {table}') from error
        if table == 'music_playback_events':
            indexes = inspector.get_indexes(table)
            uniques = inspector.get_unique_constraints(table) + indexes
            if not any(_library_full_unique(item,['internal_user_pk','event_id']) for item in uniques):
                raise MigrationSchemaMismatch('missing playback owner/event uniqueness')
            # MySQL UNIQUE-constraint reflection can omit prefix lengths. The
            # physical index metadata must independently prove full uniqueness.
            if dialect == 'mysql' and not any(_library_full_unique(item,['internal_user_pk','event_id']) for item in indexes):
                raise MigrationSchemaMismatch('MySQL playback uniqueness is partial or unverifiable')
            if dialect == 'sqlite' and not _library_sqlite_full_unique(engine,table,['internal_user_pk','event_id']):
                raise MigrationSchemaMismatch('playback uniqueness has incompatible expression/collation')
            if dialect == 'sqlite':
                with engine.connect() as connection:
                    ddl = connection.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"),{'table':table}).scalar_one()
                tokens = _library_sql_tokens(ddl)
                # Verify the actual inline rowid/autoincrement declaration, not a
                # constraint name or a comment containing AUTOINCREMENT.
                start = tokens.index('(') + 1
                declarations, current, depth = [], [], 0
                for token in tokens[start:]:
                    if token == ')' and depth == 0:
                        declarations.append(current)
                        break
                    if token == ',' and depth == 0:
                        declarations.append(current)
                        current = []
                        continue
                    current.append(token)
                    depth += (token == '(') - (token == ')')
                wanted = ['playback_event_row_id','integer','not','null','primary','key','autoincrement']
                if wanted not in declarations:
                    raise MigrationSchemaMismatch('playback SQLite autoincrement PK is incompatible')
            elif not columns['playback_event_row_id'].get('autoincrement'):
                raise MigrationSchemaMismatch('playback MySQL autoincrement is unverifiable')
    if 'generation_tasks' in tables:
        parent_columns = ['task_id','internal_user_pk','music_asset_id']
        parent_name = 'uq_generation_tasks_owner_asset_context'
        if dialect == 'sqlite':
            with engine.connect() as connection:
                physical_names = set(connection.execute(text('SELECT name FROM pragma_index_list(:table)'),{'table':'generation_tasks'}).scalars())
        else:
            try:
                with engine.connect() as connection:
                    physical_names = set(connection.execute(text('SELECT DISTINCT INDEX_NAME FROM information_schema.STATISTICS '
                                                                  'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table'),
                                                            {'table':'generation_tasks'}).scalars())
            except Exception as error:
                raise MigrationSchemaMismatch('task context index metadata unverifiable') from error
        indexes = inspector.get_indexes('generation_tasks')
        named = [item for item in indexes if item.get('name') == parent_name]
        if parent_name in physical_names and not named:
            raise MigrationSchemaMismatch('task context index omitted by Inspector; fail closed')
        if any(not _library_full_unique(item,parent_columns) for item in named):
            raise MigrationSchemaMismatch('conflicting task context parent index')
        if dialect == 'sqlite' and named and not _library_sqlite_full_unique(engine,'generation_tasks',parent_columns,index_name=parent_name):
            raise MigrationSchemaMismatch('task context parent index expression/collation differs')
        if ('music_playback_events' in existing or library_applied) and not any(_library_full_unique(item,parent_columns) for item in indexes):
            raise MigrationSchemaMismatch('missing task context parent unique index')
        if dialect == 'sqlite' and ('music_playback_events' in existing or library_applied) and not _library_sqlite_full_unique(engine,'generation_tasks',parent_columns):
            raise MigrationSchemaMismatch('no compatible full task context parent uniqueness')


def rollback_music_library(engine):
    """SQLite-only explicit candidate downgrade, refusing nonempty extension data."""
    if engine.dialect.name!='sqlite':
        raise RuntimeError('MySQL downgrade requires separately verified recovery')
    preflight_v3_migrations(engine)
    with engine.connect() as connection:
        latest=connection.exec_driver_sql('SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1').scalar()
    if latest!='0012_v3_music_library':
        raise MigrationOrderError('0012 must be the latest applied migration')
    raw=engine.raw_connection()
    try:
        cursor=raw.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        _execute_sqlite_statements(cursor,_read_migration('sqlite','0012_v3_music_library','down'))
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def _validate_auth_existing_schema(engine):
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    normalize = lambda value: re.sub(r'[\s`"()]','',str(value)).lower()
    if 'user_identities' in tables:
        columns = {c['name']:c for c in inspector.get_columns('user_identities')}
        if 'auth_epoch' in columns:
            epoch = columns['auth_epoch']
            checks = [normalize(c['sqltext']) for c in inspector.get_check_constraints('user_identities')]
            if (not isinstance(epoch['type'],Integer) or epoch['nullable'] or normalize(epoch.get('default')) not in {'0',"'0'"}
                    or not any('auth_epoch>=0' in c for c in checks)):
                raise MigrationSchemaMismatch('incompatible existing auth_epoch')
    if 'auth_sessions' not in tables:
        return
    columns = {c['name']:c for c in inspector.get_columns('auth_sessions')}
    expected = {'auth_session_id':(String,64,False), 'internal_user_pk':(Integer,None,False),
                'refresh_credential_hash':(String,255,False),'family_id':(String,64,False),
                'created_at':(DateTime,None,False),'expires_at':(DateTime,None,False),'revoked_at':(DateTime,None,True)}
    for name,(kind,length,nullable) in expected.items():
        c = columns.get(name)
        if c is None or not isinstance(c['type'],kind) or c['nullable'] != nullable or (length and c['type'].length != length):
            raise MigrationSchemaMismatch(f'incompatible auth_sessions column {name}')
    if ('current_timestamp' not in normalize(columns['created_at'].get('default'))
            or columns['expires_at'].get('default') is not None):
        raise MigrationSchemaMismatch('incompatible auth session time defaults')
    if inspector.get_pk_constraint('auth_sessions')['constrained_columns'] != ['auth_session_id']:
        raise MigrationSchemaMismatch('incompatible auth_sessions primary key')
    uniques = inspector.get_unique_constraints('auth_sessions') + [i for i in inspector.get_indexes('auth_sessions') if i.get('unique')]
    if not any(u['column_names']==['refresh_credential_hash'] for u in uniques):
        raise MigrationSchemaMismatch('missing auth session hash uniqueness')
    fks = inspector.get_foreign_keys('auth_sessions')
    if not any(f['constrained_columns']==['internal_user_pk'] and f['referred_table']=='users' and f['referred_columns']==['id'] and f.get('options',{}).get('ondelete','').upper()=='CASCADE' for f in fks):
        raise MigrationSchemaMismatch('missing auth session owner FK')
    checks = [normalize(c['sqltext']) for c in inspector.get_check_constraints('auth_sessions')]
    if not any('expires_at>created_at' in c for c in checks) or not any('revoked_atisnullorrevoked_at>=created_at' in c for c in checks):
        raise MigrationSchemaMismatch('missing auth session lifecycle checks')
    if not any('lengthrefresh_credential_hash>0' in c for c in checks):
        raise MigrationSchemaMismatch('missing nonempty auth digest check')
    if engine.dialect.name == 'mysql' and getattr(columns['refresh_credential_hash']['type'],'collation',None) != 'utf8mb4_bin':
        raise MigrationSchemaMismatch('auth digest requires case-sensitive collation')


def _render_auth_foundation(engine, sql):
    _validate_auth_existing_schema(engine)
    columns = {c['name'] for c in inspect(engine).get_columns('user_identities')}
    if 'auth_epoch' in columns:
        sql = '\n'.join(line for line in sql.splitlines() if not line.startswith('ALTER TABLE user_identities ADD COLUMN auth_epoch'))
    return sql


def _execute_sqlite_statements(cursor, sql):
    import sqlite3
    pending = ''
    for line in sql.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            cursor.execute(pending)
            pending = ''
    if any(line.strip() and not line.strip().startswith('--') for line in pending.splitlines()):
        raise RuntimeError('incomplete migration SQL')


def _render_mysql_model_columns(engine, version, sql):
    """create_all compatibility for existing nullable 0009/0010 model columns.

    Source SQL/checksums remain immutable; only omit already-present ADDs.
    This does not claim full MySQL fresh-init execution has been verified.
    """
    tables = {'0009_v3_five_tone_read_model':'diagnosis_runs',
              '0010_v3_generation_prompt_audit':'generation_tasks'}
    table = tables.get(version)
    if table is None or table not in inspect(engine).get_table_names():
        return sql
    columns = {c['name'] for c in inspect(engine).get_columns(table)}
    additions = re.findall(r'ADD COLUMN\s+(\w+)\s+([^,;]+)',sql)
    missing = [(name,definition) for name,definition in additions if name not in columns]
    if not missing:
        return '-- model-created nullable columns already present\n'
    return f'ALTER TABLE {table} ' + ', '.join(f'ADD COLUMN {name} {definition.strip()}' for name,definition in missing) + ';\n'


def rollback_auth_foundation(engine: Engine):
    """Explicit SQLite-only safe downgrade. Never called by initialization."""
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('MySQL downgrade requires separately verified operator recovery')
    preflight_v3_migrations(engine)
    with engine.connect() as connection:
        latest = connection.exec_driver_sql('SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1').scalar()
    if latest != '0011_v3_auth_foundation':
        raise MigrationOrderError('0011 must be the last applied version to downgrade')
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        _preflight_sqlite_auth_epoch_drop(cursor)
        _execute_sqlite_statements(cursor,_read_migration('sqlite','0011_v3_auth_foundation','down'))
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def _preflight_sqlite_auth_epoch_drop(cursor):
    """Probe table CHECK compatibility on a schema-only in-memory copy.

    SQLite cannot drop an auth_epoch referenced by an ORM table-level CHECK.
    Do not rebuild the real identity table or first drop auth_sessions and hope
    rollback is sufficient. This conservative probe never copies user rows and
    is performed under the original connection's write transaction/lock.
    """
    import sqlite3
    from contextlib import closing
    row = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_identities'").fetchone()
    if row is None or not row[0]:
        raise MigrationSchemaMismatch('SQLite auth downgrade has no identity table definition')
    with closing(sqlite3.connect(':memory:')) as probe:
        try:
            probe.execute(row[0])
            probe.execute('ALTER TABLE user_identities DROP COLUMN auth_epoch')
        except sqlite3.Error as error:
            raise MigrationSchemaMismatch(
                'SQLite auth downgrade unsupported for this identity table definition; '
                'fresh-create table CHECK requires separately approved rebuild or snapshot recovery'
            ) from error


def _default_migrations_root() -> Path:
    return Path(__file__).resolve().parents[2] / "migrations" / "v3"


def _read_migration(
    dialect: str,
    version: str,
    direction: str,
    migrations_root: Path | None = None,
) -> str:
    root = migrations_root or _default_migrations_root()
    path = root / dialect / f"{version}_{direction}.sql"
    return path.read_text(encoding="utf-8")


def _checksum(sql: str) -> str:
    return f"sha256:{sha256(sql.encode('utf-8')).hexdigest()}"


def _remove_marked_block(sql: str, marker: str) -> str:
    begin = f"-- {marker}_BEGIN"
    end = f"-- {marker}_END"
    if sql.count(begin) != 1 or sql.count(end) != 1:
        raise RuntimeError(f"invalid migration marker: {marker}")
    before, remainder = sql.split(begin, 1)
    _, after = remainder.split(end, 1)
    return before + after


def _session_contract(engine: Engine) -> tuple[bool, bool]:
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return False, False
    has_flow_version = "flow_version" in {
        column["name"] for column in inspector.get_columns("sessions")
    }
    has_user_fk = any(
        foreign_key.get("referred_table") == "users"
        and foreign_key.get("constrained_columns") == ["user_id"]
        for foreign_key in inspector.get_foreign_keys("sessions")
    )
    return has_flow_version, has_user_fk


def _has_session_owner_created_index(engine: Engine) -> bool:
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return False
    return any(
        index.get("column_names") == ["user_id", "created_at"]
        for index in inspector.get_indexes("sessions")
    )


def _has_owner_flow_session_columns(engine: Engine) -> bool:
    """True when sessions already carries the v3-owner-flow-1 columns (e.g. a
    fresh create_all schema), so 0003 must not re-ADD them."""
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return False
    return "flow_contract_version" in {
        column["name"] for column in inspector.get_columns("sessions")
    }


def _render_sqlite_five_tone_migration(engine: Engine, sql: str) -> str:
    """Skip already-present 0009 columns in model-created local schemas.

    ``init_database`` creates the current SQLAlchemy model schema before it
    applies versioned migrations. A fresh local database can therefore already
    contain some or all of the nullable 0009 columns. The source SQL checksum
    remains unchanged; only execution omits duplicate ADD COLUMN statements.
    Legacy databases still execute every missing ADD COLUMN normally.
    """
    if "diagnosis_runs" not in inspect(engine).get_table_names():
        return sql

    present = {
        column["name"]
        for column in inspect(engine).get_columns("diagnosis_runs")
    }
    rendered_lines: list[str] = []
    add_column = re.compile(
        r"^ALTER TABLE diagnosis_runs ADD COLUMN (?P<name>[A-Za-z0-9_]+)"
    )
    for line in sql.splitlines():
        match = add_column.match(line.strip())
        if match and match.group("name") in present:
            continue
        rendered_lines.append(line)
    return "\n".join(rendered_lines)


def _render_sqlite_generation_prompt_audit_migration(engine: Engine, sql: str) -> str:
    """Skip the 0010 ADD COLUMN when a model-created schema already has it.

    ``init_database`` creates the current SQLAlchemy model schema before it
    applies versioned migrations, so a fresh local database may already carry the
    nullable ``generation_tasks.prompt_audit_json`` column. The source SQL
    checksum is unchanged; only execution omits the duplicate ADD COLUMN.
    """

    if "generation_tasks" not in inspect(engine).get_table_names():
        return sql

    present = {
        column["name"]
        for column in inspect(engine).get_columns("generation_tasks")
    }
    if "prompt_audit_json" not in present:
        return sql
    rendered_lines = [
        line
        for line in sql.splitlines()
        if not line.strip().startswith(
            "ALTER TABLE generation_tasks ADD COLUMN prompt_audit_json"
        )
    ]
    return "\n".join(rendered_lines)


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    if getattr(engine, "_harmonyai_v3_fk_listener", False):
        return

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    setattr(engine, "_harmonyai_v3_fk_listener", True)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def _apply_sqlite_migration(
    engine: Engine,
    version: str,
    sql: str,
    checksum: str,
    *,
    session_upgrade: bool,
    session_owner_flow: bool = False,
) -> bool:
    _enable_sqlite_foreign_keys(engine)
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(64) PRIMARY KEY, "
            "checksum VARCHAR(96) NOT NULL, "
            "applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        row = cursor.execute(
            "SELECT checksum FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if row is not None:
            if row[0] != checksum:
                raise MigrationChecksumMismatch(
                    f"applied migration {version} checksum changed"
                )
            cursor.execute("PRAGMA foreign_keys=ON")
            raw.commit()
            return False

        rendered = sql
        if session_upgrade:
            has_flow_version, has_user_fk = _session_contract(engine)
            rendered = rendered.replace(
                "{{FLOW_VERSION_SELECT}}",
                "flow_version" if has_flow_version else "NULL",
            )
            if has_flow_version and has_user_fk:
                rendered = _remove_marked_block(rendered, "V3_SESSION_UPGRADE")
        if session_owner_flow and _has_owner_flow_session_columns(engine):
            rendered = _remove_marked_block(rendered, "V3_OWNER_FLOW_SESSION")
        if version == "0009_v3_five_tone_read_model":
            rendered = _render_sqlite_five_tone_migration(engine, rendered)
        if version == "0010_v3_generation_prompt_audit":
            rendered = _render_sqlite_generation_prompt_audit_migration(
                engine, rendered
            )
        if version in {'0011_v3_auth_foundation','0012_v3_music_library'}:
            if version == '0011_v3_auth_foundation':
                rendered = _render_auth_foundation(engine,rendered)
            # Unlike historical scripts, 0011 DDL and ledger are one transaction.
            cursor.execute('BEGIN IMMEDIATE')
            _execute_sqlite_statements(cursor,rendered)
        else:
            raw.executescript(rendered)
        cursor.execute(
            "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
            (version, checksum),
        )
        cursor.execute("PRAGMA foreign_keys=ON")
        raw.commit()
        return True
    except Exception:
        raw.rollback()
        try:
            raw.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        raise
    finally:
        raw.close()


def _apply_mysql_migration(
    engine: Engine,
    version: str,
    sql: str,
    checksum: str,
    *,
    session_upgrade: bool,
    session_owner_flow: bool = False,
) -> bool:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(64) PRIMARY KEY, "
            "checksum VARCHAR(96) NOT NULL, "
            "applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6))"
        )
        row = connection.exec_driver_sql(
            "SELECT checksum FROM schema_migrations WHERE version = %s",
            (version,),
        ).first()
        if row is not None:
            if row[0] != checksum:
                raise MigrationChecksumMismatch(
                    f"applied migration {version} checksum changed"
                )
            return False

        rendered = sql
        if session_upgrade:
            has_flow_version, has_user_fk = _session_contract(engine)
            if has_flow_version:
                rendered = _remove_marked_block(rendered, "V3_SESSION_FLOW")
            if has_user_fk:
                rendered = _remove_marked_block(rendered, "V3_SESSION_FK")
            if _has_session_owner_created_index(engine):
                rendered = _remove_marked_block(rendered, "V3_SESSION_OWNER_INDEX")
        if session_owner_flow and _has_owner_flow_session_columns(engine):
            rendered = _remove_marked_block(rendered, "V3_OWNER_FLOW_SESSION")
        if version == '0011_v3_auth_foundation':
            rendered = _render_auth_foundation(engine,rendered)
        if version == '0012_v3_music_library':
            indexes = inspect(engine).get_indexes('generation_tasks')
            if any(i['name']=='uq_generation_tasks_owner_asset_context' for i in indexes):
                rendered = '\n'.join(line for line in rendered.splitlines() if not line.startswith('CREATE UNIQUE INDEX uq_generation_tasks_owner_asset_context'))
        rendered = _render_mysql_model_columns(engine,version,rendered)
        statements = [item.strip() for item in rendered.split(";") if item.strip()]
        for statement in statements:
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql(
            "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
            (version, checksum),
        )
        return True


def apply_v3_migrations(
    engine: Engine,
    *,
    migrations_root: Path | None = None,
) -> dict[str, object]:
    """Apply all pending V3 migrations in order and reject changed applied SQL."""

    dialect = engine.dialect.name
    if dialect not in {"sqlite", "mysql"}:
        raise RuntimeError(f"unsupported V3 migration dialect: {dialect}")
    sources = preflight_v3_migrations(engine,migrations_root=migrations_root)
    applied: list[str] = []
    last_checksum = ""
    for version in V3_MIGRATION_VERSIONS:
        sql = sources[version]
        checksum = _checksum(sql)
        last_checksum = checksum
        session_upgrade = version == V3_FOUNDATION_VERSION
        session_owner_flow = version == "0003_v3_owner_flow"
        if dialect == "sqlite":
            applied_version = _apply_sqlite_migration(
                engine,
                version,
                sql,
                checksum,
                session_upgrade=session_upgrade,
                session_owner_flow=session_owner_flow,
            )
        else:
            applied_version = _apply_mysql_migration(
                engine,
                version,
                sql,
                checksum,
                session_upgrade=session_upgrade,
                session_owner_flow=session_owner_flow,
            )
        if applied_version:
            applied.append(version)
    return {
        "applied_versions": applied,
        "current_version": V3_MIGRATION_VERSIONS[-1],
        "checksum": last_checksum,
    }


def v3_migration_status(engine: Engine) -> dict[str, object]:
    """Return structural status without exposing connection details."""

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing_tables = sorted(_REQUIRED_TABLES - tables)
    has_flow_version, has_user_fk = _session_contract(engine)
    foreign_keys_enabled = True
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            foreign_keys_enabled = bool(
                connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
            )
    return {
        "applied": (
            not missing_tables
            and has_flow_version
            and has_user_fk
            and foreign_keys_enabled
        ),
        "missing_tables": missing_tables,
        "sessions_flow_version": has_flow_version,
        "sessions_user_fk": has_user_fk,
        "foreign_keys_enabled": foreign_keys_enabled,
    }


def mysql_migration_sql(
    migrations_root: Path | None = None,
) -> tuple[str, str]:
    """Expose the concatenated MySQL SQL for credential-free structural validation."""

    up = "\n".join(
        _read_migration("mysql", version, "up", migrations_root)
        for version in V3_MIGRATION_VERSIONS
    )
    down = "\n".join(
        _read_migration("mysql", version, "down", migrations_root)
        for version in reversed(V3_MIGRATION_VERSIONS)
    )
    return up, down
