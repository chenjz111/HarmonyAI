"""Explicit SQLite-only draft harness, NOT a production migration runner.

No URL/configuration/global engine is used. Caller supplies an isolated SQLite
connection. Uses a separate draft ledger; 0011 is never skipped in production.
"""
from hashlib import sha256
from pathlib import Path
import sqlite3

ROOT = Path(__file__).parent
VERSIONS = ('0012_library', '0013_consent')


class DraftMigrationError(RuntimeError):
    pass


def validate_migration_history(registered, applied):
    """Future integration contract: applied history must be an exact prefix.

    MUST be called before any new production DDL when registration is approved.
    Deliberately not wired into the current production runner in this draft PR.
    """
    if (len(set(registered)) != len(registered) or registered != sorted(registered)
            or list(applied) != list(registered[:len(applied)])):
        raise DraftMigrationError('migration order is not an immutable applied prefix')


def _script(connection, sql):
    pending = ''
    for line in sql.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            connection.execute(pending)
            pending = ''
    if pending.strip() and not all(line.strip().startswith('--') for line in pending.splitlines() if line.strip()):
        raise DraftMigrationError('incomplete SQL statement')


def _start(connection):
    if not isinstance(connection, sqlite3.Connection) or connection.in_transaction:
        raise DraftMigrationError('requires an isolated idle sqlite3 connection')
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('BEGIN IMMEDIATE')


def _validate_checksums(rows, root):
    for version, checksum in rows:
        sql = (root / 'sqlite' / f'{version}_up.sql').read_text(encoding='utf-8')
        if checksum != 'sha256:' + sha256(sql.encode()).hexdigest():
            raise DraftMigrationError('draft checksum changed')


def apply_draft(connection, version, *, root=ROOT):
    if version not in VERSIONS:
        raise DraftMigrationError('unknown draft version')
    sql = (root / 'sqlite' / f'{version}_up.sql').read_text(encoding='utf-8')
    checksum = 'sha256:' + sha256(sql.encode()).hexdigest()
    _start(connection)
    try:
        connection.execute('CREATE TABLE IF NOT EXISTS int2_draft_migrations(version TEXT PRIMARY KEY, checksum TEXT NOT NULL)')
        rows = connection.execute('SELECT version,checksum FROM int2_draft_migrations ORDER BY version').fetchall()
        validate_migration_history(list(VERSIONS), [row[0] for row in rows])
        _validate_checksums(rows, root)
        previous = dict(rows).get(version)
        if previous is not None:
            if previous != checksum:
                raise DraftMigrationError('draft checksum changed')
            connection.commit()
            return False
        if version != VERSIONS[len(rows)]:
            raise DraftMigrationError('draft order violation')
        _script(connection, sql)
        if connection.execute('PRAGMA foreign_key_check').fetchone():
            raise DraftMigrationError('draft foreign key violation')
        connection.execute('INSERT INTO int2_draft_migrations VALUES(?,?)', (version, checksum))
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise


def rollback_draft(connection, version):
    if version not in VERSIONS:
        raise DraftMigrationError('unknown draft version')
    _start(connection)
    try:
        rows = connection.execute('SELECT version,checksum FROM int2_draft_migrations ORDER BY version').fetchall()
        validate_migration_history(list(VERSIONS), [row[0] for row in rows])
        _validate_checksums(rows, ROOT)
        if not rows or rows[-1][0] != version:
            raise DraftMigrationError('rollback must use reverse order')
        if version == '0013_consent':
            dirty = connection.execute('SELECT count(*) FROM feedback_v3 WHERE learning_consent!=0 OR consent_policy_version IS NOT NULL OR consented_at IS NOT NULL OR deleted_at IS NOT NULL OR source_task_id IS NOT NULL OR evidence_epoch IS NOT NULL OR request_fingerprint IS NOT NULL').fetchone()[0]
            dirty += connection.execute('SELECT count(*) FROM user_music_preference_versions WHERE evidence_epoch IS NOT NULL').fetchone()[0]
        else:
            dirty = sum(connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                        for table in ('owner_music_state','music_library_state','music_playback_events'))
        if dirty:
            raise DraftMigrationError('nonempty extension data: downgrade refused')
        _script(connection, (ROOT / 'sqlite' / f'{version}_down.sql').read_text(encoding='utf-8'))
        connection.execute('DELETE FROM int2_draft_migrations WHERE version=?', (version,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
