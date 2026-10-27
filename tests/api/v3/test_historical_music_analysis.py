"""Old music reads its own persisted public explanation; never today's input."""
import uuid
from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from backend.app.main import app
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.models.v3.prescription import PrescriptionV3
from backend.app.services.v3.legacy_mode_compat import payload_checksum
from tests.api.v3.test_diagnosis_v3 import _guest_headers,_setup_flow_session,_seed_confirmed_assessment
from tests.api.v3.test_diagnosis_read_model_endpoint import _read_model
from tests.api.v3.test_s7_music_library_api import _asset,_task

client=TestClient(app)

def seed(factory):
    headers=_guest_headers();suffix=uuid.uuid4().hex
    with factory() as db:
        _,owner,session=_setup_flow_session(db,headers)
        assessment=_seed_confirmed_assessment(db,user_pk=owner,session_row=session,
            organ_profile_json={'status':'insufficient','weights':None,'score_semantics':'relative_evidence_distribution'})
        payload=_read_model().model_dump(mode='json');diagnosis='diag-'+suffix;music='music-'+suffix;task='task-'+suffix
        row=DiagnosisRun(diagnosis_id=diagnosis,internal_user_pk=owner,session_row_id=session.id,
            assessment_id=assessment,assessment_revision=1,status='success',abstained=0,
            degradation_json={'active':False,'reason_codes':[]},presentation_json={'title':'Stored'},
            five_tone_read_model_json=payload,five_tone_read_model_checksum=payload_checksum(payload),
            five_tone_read_model_schema_version=payload['schema_version'])
        db.add(row)
        db.add(PrescriptionV3(prescription_id='rx-'+task,internal_user_pk=owner,session_row_id=session.id,
            diagnosis_id=diagnosis,status='success',generation_spec_json={'stored':'unchanged'},
            personalization_json={},presentation_json={}))
        db.add(_asset(music,owner=owner,created_at=datetime.now(timezone.utc)))
        generation=_task(task,owner=owner,music_id=music,completed_at=datetime.now(timezone.utc));generation.session_row_id=session.id
        db.add(generation);db.commit()
        return headers,music,task,diagnosis,session.id,payload

def test_old_analysis_survives_current_input_change_and_performs_no_writes(db_session_factory):
    headers,music,task,diagnosis,session_id,payload=seed(db_session_factory)
    from backend.app.models.session import Session
    with db_session_factory() as db:
        db.get(Session,session_id).input_revision+=1;db.commit()
        before=db.get(DiagnosisRun,diagnosis).five_tone_read_model_checksum
        engine=db.get_bind()
    def readonly(_conn,_cursor,statement,*_args):
        assert statement.lstrip().split()[0].upper() not in {'INSERT','UPDATE','DELETE','CREATE','ALTER','DROP'}
    event.listen(engine,'before_cursor_execute',readonly)
    try:response=client.get(f'/api/v3/music/assets/{music}/analysis',params={'context_id':task},headers=headers)
    finally:event.remove(engine,'before_cursor_execute',readonly)
    assert response.status_code==200,response.text
    assert response.json()['data']==payload
    assert response.headers['cache-control']=='no-store'
    with db_session_factory() as db:
        row=db.get(DiagnosisRun,diagnosis);assert row.five_tone_read_model_json==payload;assert row.five_tone_read_model_checksum==before

@pytest.mark.parametrize('corruption',['missing','checksum'])
def test_unverifiable_old_snapshot_is_not_regenerated(db_session_factory,corruption):
    headers,music,task,diagnosis,_,_=seed(db_session_factory)
    with db_session_factory() as db:
        row=db.get(DiagnosisRun,diagnosis)
        if corruption=='missing':row.five_tone_read_model_json=None
        else:row.five_tone_read_model_checksum='sha256:invalid'
        db.commit()
    response=client.get(f'/api/v3/music/assets/{music}/analysis',params={'context_id':task},headers=headers)
    assert response.status_code==409

def test_history_requires_explicit_owned_context(db_session_factory):
    headers,music,task,_,_,_=seed(db_session_factory)
    assert client.get(f'/api/v3/music/assets/{music}/analysis',headers=headers).status_code==422
    assert client.get(f'/api/v3/music/assets/{music}/analysis',params={'context_id':'foreign-task'},headers=headers).status_code==404

def test_foreign_owner_and_absent_asset_do_not_disclose_analysis(db_session_factory):
    _,music,task,_,_,_=seed(db_session_factory);stranger=_guest_headers()
    for music_id in [music,'absent']:
        response=client.get(f'/api/v3/music/assets/{music_id}/analysis',params={'context_id':task},headers=stranger)
        assert response.status_code==404
