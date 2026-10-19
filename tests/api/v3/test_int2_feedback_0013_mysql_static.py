"""Synthetic metadata rendering only. NEVER a real MySQL execution claim."""
from types import SimpleNamespace
import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mysql
from backend.drafts.s7_feedback_consent.migration import CandidateRejected
from backend.drafts.s7_feedback_consent import mysql_contract,models


class MetadataConnection:
    dialect=SimpleNamespace(name='mysql')
    def __init__(self,version='8.0.36',collation='utf8mb4_0900_ai_ci',mismatch=False):
        self.version=version;self.collation=collation;self.mismatch=mismatch;self.queries=[]
    def exec_driver_sql(self,sql):
        self.queries.append(sql)
        assert sql=='SELECT VERSION()'
        return SimpleNamespace(scalar=lambda:self.version)
    def execute(self,statement,params=None):
        self.queries.append(str(statement))
        if params is None:
            return SimpleNamespace(fetchall=lambda:[(t,'InnoDB') for t in ('users','feedback_v3','generation_tasks','music_assets','music_playback_events','user_music_preference_versions')])
        if params['c'] in ('id','internal_user_pk','playback_event_row_id'):row=('int',None,None)
        else:
            coll='utf8mb4_bin' if self.mismatch and params['c']=='source_context_id' else self.collation
            row=('varchar(64)','utf8mb4',coll)
        return SimpleNamespace(first=lambda:row)


@pytest.mark.parametrize('version',['unknown','8.0.15','10.11.6-MariaDB'])
def test_mysql_unapproved_server_rejected_before_render(version):
    connection=MetadataConnection(version=version)
    with pytest.raises(CandidateRejected):mysql_contract.render_up(connection)
    assert len(connection.queries)==1


@pytest.mark.parametrize('collation',['utf8mb4_bin','utf8mb4_0900_ai_ci'])
def test_mysql_render_and_orm_share_actual_reflected_parent_collation(collation):
    sql=mysql_contract.render_up(MetadataConnection(collation=collation))
    assert f'source_task_id varchar(64) CHARACTER SET utf8mb4 COLLATE {collation}' in sql
    assert '{{' not in sql
    metadata=models.mysql_metadata(MetadataConnection(collation=collation))
    ddl=str(CreateTable(metadata.tables['feedback_v3']).compile(dialect=mysql.dialect()))
    assert f'COLLATE {collation}' in ddl
    assert 'typeof' not in ddl and 'GLOB' not in ddl
    assert 'REGEXP' in ddl


def test_mysql_mismatch_does_not_guess_or_change_existing_column():
    with pytest.raises(CandidateRejected):mysql_contract.render_up(MetadataConnection(mismatch=True))


@pytest.mark.parametrize('asset_type',['varchar(128)','char(64)'])
def test_matching_but_unsupported_asset_type_cannot_render_divergent_orm(asset_type):
    class Unsupported(MetadataConnection):
        def execute(self,statement,params=None):
            result=super().execute(statement,params)
            if params and params['c']=='music_asset_id':
                return SimpleNamespace(first=lambda:(asset_type,'utf8mb4',self.collation))
            return result
    for render in (mysql_contract.render_up,models.mysql_metadata):
        with pytest.raises(CandidateRejected):render(Unsupported())


def test_r1_mysql_render_contract_uses_binary_null_safe_input_comparisons():
    # Static rendered artifact validation ONLY; not real MySQL Trigger evidence.
    sql=mysql_contract.render_up(MetadataConnection(collation='utf8mb4_0900_ai_ci'))
    trigger=sql.split('CREATE TRIGGER int2_0013_feedback_immutable',1)[1].split('END;',1)[0]
    for field in ('change_label','pre_state_snapshot_json','post_state_json','experience_json',
        'continue_use','liked_features_json','adjustment_preferences_json','comment_ciphertext',
        'playback_json','feedback_id','idempotency_key','music_asset_id','consent_policy_version','source_task_id'):
        assert f'NOT(CAST(NEW.{field} AS BINARY) <=> CAST(OLD.{field} AS BINARY))' in trigger
    assert 'OLD.request_fingerprint IS NOT NULL' in trigger
    assert 'NOT(NEW.created_at <=> OLD.created_at)' in trigger
    assert 'NEW.preference_update_status' not in trigger
