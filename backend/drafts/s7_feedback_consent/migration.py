"""Explicit SQLite review runner. No registration, discovery or MySQL execution."""
import json
import re
from hashlib import sha256
from pathlib import Path
from backend.app.core import v3_migrations as core
from backend.app.models.v3.feedback import FeedbackV3,UserMusicPreferenceVersion

VERSION='0013_v3_feedback_consent'
ROOT=Path(__file__).parent
LEDGER='int2_feedback_0013_review'
FIELDS=('consent_policy_version','consented_at','deleted_at','source_task_id',
        'playback_event_row_id','evidence_epoch','request_fingerprint','learning_consent')
TRIGGERS=('int2_0013_feedback_insert_proof','int2_0013_feedback_immutable',
    'int2_0013_feedback_no_delete','int2_0013_feedback_no_replace',
    'int2_0013_task_proof_immutable','int2_0013_event_proof_immutable',
    'int2_0013_feedback_nonnull_pk','int2_0013_version_nonnull_pk_insert',
    'int2_0013_version_nonnull_pk_update')


class CandidateRejected(RuntimeError):pass


def _checksum():
    return 'sha256:'+sha256(b'\0'.join((ROOT/'sqlite'/f'{VERSION}_{x}.sql').read_bytes() for x in ('up','down'))).hexdigest()


def _signature(cursor):
    objects=cursor.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE tbl_name IN ('feedback_v3','user_music_preference_versions') OR name LIKE 'int2_0013_%' ORDER BY type,name").fetchall()
    return sha256(json.dumps(objects,sort_keys=True).encode()).hexdigest()


def _columns(cursor,table):return {r[1] for r in cursor.execute(f'PRAGMA table_info("{table}")')}


def _sources(engine):
    if engine.dialect.name!='sqlite' or not engine.url.database or engine.url.database==':memory:':
        raise CandidateRejected('explicit file SQLite required; MySQL NOT RUN')
    sources=core.preflight_v3_migrations(engine)
    if len(sources)!=12 or list(sources)[-1]!='0012_v3_music_library':
        raise CandidateRejected('real complete 0011/0012 required; no registration of 0013')
    return sources


def _locked(engine,operation):
    sources=_sources(engine)
    raw=engine.raw_connection()
    try:
        c=raw.cursor()
        if raw.driver_connection.in_transaction:raise CandidateRejected('nested transaction')
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('BEGIN IMMEDIATE')
        files=[r[2] for r in c.execute('PRAGMA database_list') if r[1]=='main']
        if len(files)!=1 or not files[0]:raise CandidateRejected('actual file required')
        rows=c.execute('SELECT version,checksum FROM schema_migrations ORDER BY applied_at,version').fetchall()
        expected=[(v,core._checksum(sql)) for v,sql in sources.items()]
        if rows!=expected:raise CandidateRejected('0012 history prefix or checksum mismatch')
        result=operation(c)
        if c.execute('PRAGMA foreign_key_check').fetchall():raise CandidateRejected('foreign key violation')
        raw.commit()
        return result
    except Exception:
        raw.rollback()
        raise
    finally:raw.close()


def _existing(c):
    if LEDGER not in {r[0] for r in c.execute("SELECT name FROM sqlite_schema WHERE type='table'")}:return False
    row=c.execute(f'SELECT version,checksum,signature FROM {LEDGER}').fetchall()
    if len(row)!=1 or row[0][:2]!=(VERSION,_checksum()) or row[0][2]!=_signature(c):
        raise CandidateRejected('candidate ledger/schema changed; no blind resume')
    return True


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
            raise CandidateRejected('legacy primary key mismatch')
        required=('internal_user_pk','idempotency_key') if table.name=='feedback_v3' else ('profile_id','version')
        if not core._library_sqlite_full_unique(engine,table.name,list(required)):
            raise CandidateRejected('legacy full binary uniqueness missing')
        actual={_check_signature(item['sqltext']) for item in inspector.get_check_constraints(table.name)}
        for check in (c for c in table.constraints if isinstance(c,CheckConstraint)):
            variants={_check_signature(str(check.sqltext))}
            # SQL CHECK UNKNOWN permits NULL; this approved old inline enum is
            # equivalent ONLY because the actual continue_use column is nullable.
            if check.name=='ck_feedback_v3_continue_use':
                variants.add(_check_signature("continue_use IN ('yes','maybe','no')"))
            if not actual.intersection(variants):raise CandidateRejected('legacy CHECK mismatch')
        cols={c['name']:c for c in inspector.get_columns(table.name)}
        for column in table.c:
            actual_type=str(cols[column.name]['type']).upper()
            expected=str(column.type.compile(dialect=engine.dialect)).upper()
            allowed={expected}
            # Frozen SQLite migration used TEXT for strings/JSON and REAL for
            # Float. These are explicit historical alternatives, not arbitrary
            # affinity-based acceptance of unknown types or lengths.
            if expected.startswith('VARCHAR(') or expected in ('JSON','TEXT'):allowed.add('TEXT')
            if expected=='FLOAT':allowed.add('REAL')
            if actual_type not in allowed:raise CandidateRejected('legacy column type mismatch')
            if not column.nullable and not column.primary_key and cols[column.name]['nullable']:
                raise CandidateRejected('legacy nullability mismatch')
            default=cols[column.name]['default']
            normalized='NULL' if default is None else str(default).strip('() ').upper()
            defaults={'NULL'}
            if column.name=='created_at':defaults={'CURRENT_TIMESTAMP'}
            elif table.name=='user_music_preference_versions':
                if column.name=='feedback_count':defaults.add('0')
                if column.name=='minimum_samples_for_application':defaults.add('3')
            if normalized not in defaults:raise CandidateRejected('legacy default mismatch')
            if column.primary_key and cols[column.name]['nullable']:
                if actual_type!='TEXT':raise CandidateRejected('unknown nullable legacy primary key')
                with engine.connect() as db:
                    if db.exec_driver_sql(f'SELECT 1 FROM {table.name} WHERE {column.name} IS NULL LIMIT 1').first():
                        raise CandidateRejected('legacy null primary key data')
        fks={(tuple(f['constrained_columns']),f['referred_table'],tuple(f['referred_columns']),f.get('options',{}).get('ondelete','NO ACTION').upper()) for f in inspector.get_foreign_keys(table.name)}
        for foreign in table.foreign_key_constraints:
            expected=(tuple(c.name for c in foreign.columns),foreign.referred_table.name,
                tuple(e.column.name for e in foreign.elements),(foreign.ondelete or 'NO ACTION').upper())
            if expected not in fks:raise CandidateRejected('legacy FK missing or action mismatch')


def install_sqlite(engine):
    def install(c):
        if _existing(c):return 'already_installed'
        if _columns(c,'feedback_v3')!=set(FeedbackV3.__table__.c.keys()) or _columns(c,'user_music_preference_versions')!=set(UserMusicPreferenceVersion.__table__.c.keys()):
            raise CandidateRejected('partial/unknown feedback schema')
        _validate_legacy(engine)
        # An object with an owned name must not be overwritten/adopted.
        if c.execute("SELECT name FROM sqlite_schema WHERE name LIKE 'int2_0013_%'").fetchall():
            raise CandidateRejected('candidate object collision')
        core._execute_sqlite_statements(c,(ROOT/'sqlite'/f'{VERSION}_up.sql').read_text())
        c.execute(f'CREATE TABLE {LEDGER}(version TEXT PRIMARY KEY,checksum TEXT NOT NULL,signature TEXT NOT NULL)')
        c.execute(f'INSERT INTO {LEDGER} VALUES(?,?,?)',(VERSION,_checksum(),_signature(c)))
        return 'installed'
    return _locked(engine,install)


def remove_sqlite(engine):
    def remove(c):
        if not _existing(c):raise CandidateRejected('not installed')
        nonnull=' OR '.join(f'{field} IS NOT NULL' for field in FIELDS if field!='learning_consent')
        if c.execute(f'SELECT 1 FROM feedback_v3 WHERE learning_consent!=0 OR {nonnull} LIMIT 1').fetchone() or c.execute('SELECT 1 FROM user_music_preference_versions WHERE evidence_epoch IS NOT NULL LIMIT 1').fetchone():
            raise CandidateRejected('extension data/tombstone cannot be discarded')
        # Conservative gate: any unknown View/Trigger is uncertain, even unrelated.
        # This is intentionally NOT claimed to parse arbitrary SQL dependencies.
        unknown=c.execute("SELECT name FROM sqlite_schema WHERE type IN ('view','trigger')").fetchall()
        if any(name not in TRIGGERS for (name,) in unknown):raise CandidateRejected('unknown external SQL object')
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_schema WHERE type='table'")]
        for table in tables:
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',table):raise CandidateRejected('unknown table identifier')
            for fk in c.execute(f'PRAGMA foreign_key_list("{table}")'):
                if ((fk[2]=='feedback_v3' and fk[4] in FIELDS) or
                    (fk[2]=='user_music_preference_versions' and fk[4]=='evidence_epoch')):
                    raise CandidateRejected('external FK depends on extension')
        for trigger in TRIGGERS:c.execute(f'DROP TRIGGER {trigger}')
        c.execute('DROP INDEX int2_0013_feedback_owner_deleted')
        # Drop the joint CHECK-bearing field before columns it references.
        for field in ('learning_consent',)+FIELDS[:-1]:c.execute(f'ALTER TABLE feedback_v3 DROP COLUMN {field}')
        c.execute('ALTER TABLE user_music_preference_versions DROP COLUMN evidence_epoch')
        c.execute(f'DROP TABLE {LEDGER}')
        return 'removed'
    return _locked(engine,remove)
