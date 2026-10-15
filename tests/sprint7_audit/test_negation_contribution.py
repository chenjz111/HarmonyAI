"""R2: observe the existing fact/link sign boundary without modifying rules."""
import pytest
from backend.app.services.v3.assessment_service import _fact_evidence,_organ_links,_build_conflicts
from backend.app.services.v3.knowledge_assets import load_organ_mapping
from backend.app.services.v3.organ_dominance_service import build_organ_aggregation_snapshot
from tests.sprint7_audit.test_subject_admission import fact


@pytest.mark.parametrize('negated',[False,True])
@pytest.mark.parametrize('source_type',['document','questionnaire'])
@pytest.mark.parametrize('time_window',['past_7_days','source_recorded'])
@pytest.mark.parametrize('multi',[False,True])
def test_fact_negation_does_not_invert_approved_mapping_link(negated,source_type,time_window,multi):
    mapping=load_organ_mapping()
    claims=['anger_tendency','flank_discomfort','agitation_tendency','palpitation_at_rest']
    if multi:
        claims.append('sleep_disturbance')
    evidence=[_fact_evidence('audit',fact(c,negated=negated,source_type=source_type,time_window=time_window),index=i)
              for i,c in enumerate(claims)]
    links=_organ_links(evidence,mapping)
    assert all(e.direction==('contradicting' if negated else 'supporting') for e in evidence)
    assert all(link.direction=='supporting' for link in links)
    snapshot=build_organ_aggregation_snapshot(evidence,links,mapping)
    assert snapshot.raw_support_by_organ['liver']>0
    assert snapshot.raw_support_by_organ['heart']>0


@pytest.mark.parametrize('fact_negative',[False,True])
@pytest.mark.parametrize('link_negative',[False,True])
def test_aggregation_sign_follows_link_not_fact(fact_negative,link_negative):
    mapping=load_organ_mapping()
    evidence=[_fact_evidence('audit',fact(c,negated=fact_negative),index=i)
              for i,c in enumerate(['anger_tendency','flank_discomfort'])]
    links=[l.model_copy(update={'direction':'contradicting' if link_negative else 'supporting'})
           for l in _organ_links(evidence,mapping)]
    score=build_organ_aggregation_snapshot(evidence,links,mapping).raw_support_by_organ['liver']
    assert (score<0) if link_negative else (score>0)


@pytest.mark.parametrize('same_time',[False,True])
def test_questionnaire_document_opposition_requires_comparable_time(same_time):
    mapping=load_organ_mapping()
    left=_fact_evidence('audit',fact('anger_tendency',source_type='questionnaire',fact_id='fact_anger_q'),index=0)
    right=_fact_evidence('audit',fact('anger_tendency',negated=True,
        time_window='past_7_days' if same_time else 'source_recorded',fact_id='fact_anger_d'),index=1)
    conflicts=_build_conflicts([left,right],mapping)
    assert any(c.conflict_kind=='direct_contradiction' for c in conflicts)==same_time
