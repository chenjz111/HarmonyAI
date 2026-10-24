"""Review-only ORM difference, never added to production Base or exports."""
from sqlalchemy import MetaData,Column,String,Integer,BigInteger,DateTime,ForeignKey,ForeignKeyConstraint,CheckConstraint,Index
from sqlalchemy.orm import registry
from sqlalchemy.dialects import mysql
from backend.app.core.database import Base
from backend.app.models.v3 import feedback,music,music_library


class ReviewMetadata(MetaData):
    def create_all(self,*args,**kwargs):
        raise RuntimeError('explicit trigger-complete candidate installer required')
    def drop_all(self,*args,**kwargs):
        raise RuntimeError('verified extension-empty downgrade executor required')


metadata=ReviewMetadata()
for table in Base.metadata.tables.values():table.to_metadata(metadata)
table=metadata.tables['feedback_v3']
for column in (
    Column('consent_policy_version',String(64)),
    Column('consented_at',DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6),'mysql')),
    Column('deleted_at',DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6),'mysql')),
    Column('source_task_id',String(64),ForeignKey('generation_tasks.task_id',ondelete='RESTRICT')),
    Column('playback_event_row_id',Integer,ForeignKey('music_playback_events.playback_event_row_id',ondelete='RESTRICT')),
    Column('evidence_epoch',BigInteger),Column('request_fingerprint',String(71)),
    Column('learning_consent',Integer,nullable=False,server_default='0')):
    table.append_column(column)
table.append_constraint(CheckConstraint("learning_consent IN (0,1) AND ((learning_consent=0 AND consent_policy_version IS NULL AND consented_at IS NULL) OR (learning_consent=1 AND consent_policy_version IS NOT NULL AND length(consent_policy_version) BETWEEN 1 AND 64 AND consented_at IS NOT NULL AND evidence_epoch IS NOT NULL AND source_task_id IS NOT NULL AND playback_event_row_id IS NOT NULL AND request_fingerprint IS NOT NULL))",name='ck_feedback_candidate_consent'))
table.append_constraint(CheckConstraint('evidence_epoch IS NULL OR evidence_epoch>=0',name='ck_feedback_candidate_epoch'))
table.append_constraint(CheckConstraint("typeof(learning_consent)='integer'",name='ck_feedback_candidate_bool_type').ddl_if(dialect='sqlite'))
table.append_constraint(CheckConstraint("evidence_epoch IS NULL OR typeof(evidence_epoch)='integer'",name='ck_feedback_candidate_epoch_type').ddl_if(dialect='sqlite'))
table.append_constraint(CheckConstraint("request_fingerprint IS NULL OR (length(request_fingerprint)=71 AND substr(request_fingerprint,1,7)='sha256:' AND substr(request_fingerprint,8) NOT GLOB '*[^0-9a-f]*')",name='ck_feedback_candidate_fingerprint').ddl_if(dialect='sqlite'))
table.append_constraint(CheckConstraint("request_fingerprint IS NULL OR (CHAR_LENGTH(request_fingerprint)=71 AND LEFT(request_fingerprint,7)='sha256:' AND SUBSTRING(request_fingerprint,8) REGEXP '^[0-9a-f]+$')",name='ck_feedback_candidate_mysql_fingerprint').ddl_if(dialect='mysql'))
table.append_constraint(ForeignKeyConstraint(['source_task_id','internal_user_pk','music_asset_id'],
    ['generation_tasks.task_id','generation_tasks.internal_user_pk','generation_tasks.music_asset_id'],name='int2_0013_task_fk',ondelete='RESTRICT').ddl_if(dialect='mysql'))
table.append_constraint(ForeignKeyConstraint(['playback_event_row_id','internal_user_pk','music_asset_id','source_task_id'],
    ['music_playback_events.playback_event_row_id','music_playback_events.internal_user_pk','music_playback_events.music_asset_id','music_playback_events.source_context_id'],name='int2_0013_event_fk',ondelete='RESTRICT').ddl_if(dialect='mysql'))
table.append_constraint(CheckConstraint('playback_event_row_id IS NULL OR source_task_id IS NOT NULL',name='int2_0013_event_context'))
Index('int2_0013_feedback_owner_deleted',table.c.internal_user_pk,table.c.deleted_at,table.c.created_at,table.c.feedback_id)
events=metadata.tables['music_playback_events']
Index('int2_0013_playback_proof_key',events.c.playback_event_row_id,events.c.internal_user_pk,events.c.music_asset_id,events.c.source_context_id,unique=True).ddl_if(dialect='mysql')
version=metadata.tables['user_music_preference_versions']
version.append_column(Column('evidence_epoch',BigInteger,nullable=True))
version.append_constraint(CheckConstraint('evidence_epoch IS NULL OR evidence_epoch>=0',name='ck_version_candidate_epoch'))
version.append_constraint(CheckConstraint("evidence_epoch IS NULL OR typeof(evidence_epoch)='integer'",name='ck_version_candidate_epoch_type').ddl_if(dialect='sqlite'))
mapper=registry(metadata=metadata)


@mapper.mapped
class FeedbackCandidate:
    __table__=table


@mapper.mapped
class PreferenceVersionCandidate:
    __table__=version


def mysql_metadata(connection):
    """Compile only after the SAME actual parent inspection used by SQL render.

    Returned metadata is guarded against create_all/drop_all. It never mutates
    the generic SQLite candidate or the production ORM's metadata/types.
    """
    from .mysql_contract import read_parent_contract
    types=read_parent_contract(connection)
    result=ReviewMetadata()
    for existing in metadata.tables.values():existing.to_metadata(result)
    # SQLAlchemy to_metadata does not preserve conditional-DDL filters. Remove
    # the explicit SQLite-only checks and single FK alternatives on this COPY.
    sqlite_checks={'ck_feedback_candidate_bool_type','ck_feedback_candidate_epoch_type',
        'ck_feedback_candidate_fingerprint','ck_version_candidate_epoch_type'}
    for copied in result.tables.values():
        for constraint in list(copied.constraints):
            single_fk=(copied.name=='feedback_v3' and isinstance(constraint,ForeignKeyConstraint)
                and tuple(constraint.column_keys) in (('source_task_id',),('playback_event_row_id',)))
            if constraint.name in sqlite_checks or single_fk:copied.constraints.remove(constraint)
    def string_type(contract):
        return mysql.VARCHAR(64,charset=contract[1],collation=contract[2])
    for table_name,column_name in (('generation_tasks','task_id'),('music_playback_events','source_context_id'),('feedback_v3','source_task_id')):
        result.tables[table_name].c[column_name].type=string_type(types['task'])
    for table_name in ('music_assets','generation_tasks','music_playback_events','feedback_v3'):
        result.tables[table_name].c.music_asset_id.type=string_type(types['asset'])
    result.tables['feedback_v3'].c.request_fingerprint.type=mysql.VARCHAR(71,charset='ascii',collation='ascii_bin')
    return result

# SQLite proof/immutability is trigger-enforced, not magically represented by
# create_all. MySQL template additionally uses composite FK, requiring actual
# parent collation/type reflection before rendering. No production ORM mutation.
