"""Formal0014: additive reviewed structures, no automatic repair or evidence deletion."""
import re
from sqlalchemy import inspect,CheckConstraint,UniqueConstraint,text
from backend.app.models.v3.account_security import AccountCredential,RegisteredSessionState,RefreshProof,LoginBucket
from .v3_migrations import MigrationSchemaMismatch,_library_sql_tokens

MODELS=(AccountCredential,RegisteredSessionState,RefreshProof,LoginBucket)
VERSION='0014_v3_account_security'


def signature(value):
    return tuple(t for t in _library_sql_tokens(re.sub(r'\bchar_length\b','length',value,flags=re.I)) if t not in ('(',')'))


def require_mysql_engines(connection,names):
    rows=connection.execute(text('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')).fetchall()
    engines=dict(rows)
    if any(engines.get(name)!='InnoDB' for name in names):raise MigrationSchemaMismatch('0014 requires verified InnoDB tables')


def validate(engine,*,applied):
    inspector=inspect(engine);tables=set(inspector.get_table_names());required={m.__tablename__ for m in MODELS}
    present=required.intersection(tables)
    if not present:
        if applied:raise MigrationSchemaMismatch('0014 account tables missing')
        return False
    if present != required:raise MigrationSchemaMismatch('partial0014 account schema; operator recovery required')
    dialect=engine.dialect
    if dialect.name=='mysql':
        with engine.connect() as db:require_mysql_engines(db,required|{'auth_sessions','user_identities'})
    for model in MODELS:
        table=model.__table__;columns={c['name']:c for c in inspector.get_columns(table.name)}
        if set(columns) != set(table.c.keys()):raise MigrationSchemaMismatch('0014 unknown/missing columns')
        if inspector.get_pk_constraint(table.name)['constrained_columns'] != [c.name for c in table.primary_key]:raise MigrationSchemaMismatch('0014 primary key mismatch')
        for expected in table.c:
            actual=columns[expected.name];wanted=expected.type.dialect_impl(dialect);reflected=actual['type']
            norm=lambda name:'integer' if name.lower() in {'int','integer'} else 'varchar' if name.lower() in {'string','varchar'} else name.lower()
            if (norm(reflected.__visit_name__) != norm(wanted.__visit_name__) or actual['nullable'] != expected.nullable
                or actual.get('default') is not None or getattr(reflected,'length',None) != getattr(wanted,'length',None)):
                raise MigrationSchemaMismatch(f'0014 column contract mismatch: {table.name}.{expected.name}')
            if dialect.name=='mysql':
                if getattr(reflected,'unsigned',False) or getattr(reflected,'fsp',None) != getattr(wanted,'fsp',None):raise MigrationSchemaMismatch('0014 MySQL precision/signedness mismatch')
                if getattr(wanted,'charset',None)=='ascii' and (getattr(reflected,'charset',None),getattr(reflected,'collation',None)) != ('ascii','ascii_bin'):
                    raise MigrationSchemaMismatch('0014 MySQL binary credential/username collation mismatch')
        uniques={tuple(c['column_names']) for c in inspector.get_unique_constraints(table.name)}
        uniques.update(tuple(i['column_names']) for i in inspector.get_indexes(table.name) if i['unique'])
        if uniques != {tuple(c.name for c in constraint.columns) for constraint in table.constraints if isinstance(constraint,UniqueConstraint)}:
            raise MigrationSchemaMismatch('0014 unique key mismatch')
        foreign=inspector.get_foreign_keys(table.name)
        for constraint in table.foreign_key_constraints:
            if not any(f['constrained_columns']==list(constraint.column_keys) and f['referred_table']==constraint.referred_table.name
                and f['referred_columns']==[e.column.name for e in constraint.elements] and f.get('options',{}).get('ondelete')=='RESTRICT' for f in foreign):
                raise MigrationSchemaMismatch('0014 foreign key mismatch')
        checks=inspector.get_check_constraints(table.name)
        expected_checks=[c for c in table.constraints if isinstance(c,CheckConstraint) and
            (c._ddl_if is None or c._ddl_if.dialect==dialect.name)]
        if {signature(c['sqltext']) for c in checks} != {signature(str(c.sqltext)) for c in expected_checks}:
            raise MigrationSchemaMismatch('0014 CHECK mismatch')
        indexes=inspector.get_indexes(table.name)
        for index in table.indexes:
            if not any(i['column_names']==list(index.columns.keys()) and bool(i['unique'])==index.unique for i in indexes):raise MigrationSchemaMismatch('0014 index mismatch')
        if dialect.name=='mysql':
            from .feedback_mysql_migration import require_enforced_checks
            with engine.connect() as db:require_enforced_checks(db,table.name,{c['name'] for c in checks})
    return True


def render(engine,sql,connection=None):
    if validate(engine,applied=False):return ''
    if engine.dialect.name=='mysql':
        require_mysql_engines(connection,{'auth_sessions','user_identities'})
        row=connection.execute(text('SELECT COLUMN_TYPE,CHARACTER_SET_NAME,COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t AND COLUMN_NAME=:c'),{'t':'auth_sessions','c':'auth_session_id'}).first()
        if row is None or row[0].lower()!='varchar(64)' or any(not isinstance(v,str) or re.fullmatch('[A-Za-z0-9_]+',v) is None for v in row[1:]):
            raise MigrationSchemaMismatch('0014 unverifiable parent session key')
        sql=sql.replace('{{AUTH_SID_TYPE}}',f'{row[0]} CHARACTER SET {row[1]} COLLATE {row[2]}')
    return sql
