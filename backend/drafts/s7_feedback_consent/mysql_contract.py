"""Read-only MySQL preflight/render contract; no execute/install API."""
import re
from pathlib import Path
from .migration import CandidateRejected


def read_parent_contract(connection):
    """Reads actual INFORMATION_SCHEMA, not caller-claimed matching strings.

    Unit tests use synthetic read-only connections. Real MySQL NOT RUN.
    """
    if connection.dialect.name!='mysql':raise CandidateRejected('MySQL metadata connection required')
    version=connection.exec_driver_sql('SELECT VERSION()').scalar()
    match=re.match(r'^(\d+)\.(\d+)\.(\d+)',str(version))
    if not match or 'mariadb' in str(version).lower() or tuple(map(int,match.groups()))<(8,0,16):
        raise CandidateRejected('unapproved CHECK/version capability')
    def col(table,name):
        from sqlalchemy import text
        row=connection.execute(text('SELECT COLUMN_TYPE,CHARACTER_SET_NAME,COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t AND COLUMN_NAME=:c'),{'t':table,'c':name}).first()
        if row is None:raise CandidateRejected('unknown parent column metadata')
        return tuple(row)
    task=col('generation_tasks','task_id')
    if not re.fullmatch(r'varchar\(64\)',task[0],re.I) or not all(isinstance(x,str) and re.fullmatch('[a-zA-Z0-9_]+',x) for x in task[1:]):
        raise CandidateRejected('unknown task key type/charset/collation')
    if col('music_playback_events','source_context_id')!=task:raise CandidateRejected('task/event collation mismatch')
    asset=col('generation_tasks','music_asset_id')
    if not re.fullmatch(r'varchar\(64\)',asset[0],re.I) or not all(isinstance(x,str) and re.fullmatch('[a-zA-Z0-9_]+',x) for x in asset[1:]):
        raise CandidateRejected('unsupported asset key type/charset/collation')
    if col('feedback_v3','music_asset_id')!=asset or col('music_playback_events','music_asset_id')!=asset or col('music_assets','music_asset_id')!=asset:
        raise CandidateRejected('existing asset key mismatch; no implicit ALTER')
    owner=col('users','id')
    if not re.fullmatch(r'int(?:\(\d+\))?',owner[0],re.I) or owner[1:]!=(None,None):raise CandidateRejected('unknown internal owner PK type')
    for table in ('feedback_v3','generation_tasks','music_playback_events'):
        if col(table,'internal_user_pk')!=owner:raise CandidateRejected('owner FK type mismatch')
    event=col('music_playback_events','playback_event_row_id')
    if not re.fullmatch(r'int(?:\(\d+\))?',event[0],re.I) or event[1:]!=(None,None):
        raise CandidateRejected('unknown signed event row PK')
    from sqlalchemy import text
    engines=connection.execute(text("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('users','feedback_v3','generation_tasks','music_assets','music_playback_events','user_music_preference_versions')")).fetchall()
    if len(engines)!=6 or any(engine.lower()!='innodb' for _,engine in engines):raise CandidateRejected('InnoDB parents required')
    return dict(task=task,asset=asset,event=event,owner=owner)


def render_up(connection):
    types=read_parent_contract(connection)
    task,event=types['task'],types['event']
    sql=(Path(__file__).parent/'mysql/0013_v3_feedback_consent_up.sql').read_text()
    return sql.replace('{{TASK_ID_TYPE}}',f'{task[0]} CHARACTER SET {task[1]} COLLATE {task[2]}').replace('{{EVENT_ROW_TYPE}}',event[0])
