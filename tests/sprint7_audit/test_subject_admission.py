"""R1 characterization, not a medical correctness assertion. Synthetic data only."""
import pytest

from backend.app.services.v3.assessment_service import _fact_evidence, _organ_links
from backend.app.services.v3.knowledge_assets import load_organ_mapping
from backend.app.services.v3.organ_dominance_service import build_organ_aggregation_snapshot, canonical_evidence_coverage
from backend.app.services.v3.evidence_admission import admit_projection
from tests.api.conftest import isolated_api_database, db_session_factory  # noqa: F401


def fact(claim, *, subject='self', negated=False, source_type='document', time_window='past_7_days'):
    return {'fact_id': f'fact_{claim}', 'fact_code': claim, 'display_name': claim,
        'category': 'audit', 'value': {'type':'severity','value':'moderate'},
        'time_window': time_window, 'negated':negated, 'subject':subject,
        'confirmation_status':'confirmed','extraction':{'confidence':1.0},
        'source_refs':[{'source_id':'synthetic','source_type':source_type}]}


@pytest.mark.parametrize('subject',['self','other','unknown'])
@pytest.mark.parametrize('source_type',['document','questionnaire'])
@pytest.mark.parametrize('time_window',['past_7_days','source_recorded'])
def test_subject_does_not_change_current_aggregation_population(subject, source_type, time_window):
    mapping=load_organ_mapping()
    evidence=[_fact_evidence('audit',fact(c,subject=subject,source_type=source_type,time_window=time_window),index=i)
              for i,c in enumerate(['anger_tendency','flank_discomfort'])]
    snapshot=build_organ_aggregation_snapshot(evidence,_organ_links(evidence,mapping),mapping)
    assert canonical_evidence_coverage(evidence,mapping)==(2,0.25)
    assert snapshot.raw_support_by_organ['liver']>0
    assert 'subject' not in evidence[0].model_dump()


@pytest.mark.parametrize('subject',['self','other','unknown'])
def test_pragmatic_admission_retains_subject_with_valid_source_span(subject):
    item=fact('anger_tendency',subject=subject,time_window='source_recorded')
    item['source_refs']=[{'source_id':'synthetic','source_type':'document','span_ref':'{"start":0,"end":4}'}]
    admitted,audit=admit_projection([item],sources={'synthetic':{
        'kind':'document','text':'样例记录','time_window':'source_recorded'}},summary='样例记录')
    assert admitted[0]['subject']==subject
    assert admitted[0]['confirmation_status']=='confirmed'
    assert audit[0]['disposition']=='admitted'


@pytest.mark.parametrize('subject',['self','other','unknown'])
def test_diagnosis_public_reason_filter_does_not_recompute_direction(subject, db_session_factory, monkeypatch):
    from backend.app.models.v3.assessment import FactEvidence as Row
    from backend.app.models.v3.understanding import NormalizedFact
    from tests.api.v3.test_phase4_evidence_kernel import _Harness,_candidate,_body
    harness=_Harness(db_session_factory,monkeypatch,payloads=[],organ_support={'spleen':1.8,'liver':1.5})
    with db_session_factory() as db:
        for row in db.query(Row).filter_by(assessment_id=harness.assessment_id):
            db.get(NormalizedFact,row.normalized_fact_row_id).subject=subject
        db.commit()
    harness.use([{'status':'success','candidate_tendencies':[_candidate(knowledge_chunk_ids=['chunk_1'])],
                  'abstained':False,'abstain_reason':None}])
    response=harness.post()
    assert response.status_code==201
    read=harness.run_row(_body(response)['diagnosis_id']).five_tone_read_model_json
    assert read['regulation_mode']=='personalized_five_tone'
    assert read['primary_tone']['tone']=='gong'
    if subject=='self':
        assert '思虑' in read['state_tendency']
    else:
        assert '思虑' not in read['state_tendency']
        assert '食欲' not in read['state_tendency']
