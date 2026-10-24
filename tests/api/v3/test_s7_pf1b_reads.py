"""Owner and tombstone predicates shared by candidate list/count/detail."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.api.v3.test_int2_feedback_0013_candidate import database, candidate
from tests.api.v3.test_int2_pf1b_contract import principal
from backend.app.services.v3.feedback_v31_candidate_service import FeedbackNotFound
from backend.app.services.v3.feedback_v31_candidate_queries import get_owned_feedback, read_owned_feedback_page


def test_read_page_total_filter_and_stable_order_without_state_write(database):
    candidate().install_sqlite(database)
    with database.begin() as conn:
        for record in ("fb_a", "fb_b"):
            conn.execute(text("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status,created_at) VALUES(:id,7,1,'music_shared','no_change','[]','[]',:id,'skipped','2099-01-01 00:00:00')"), {"id": record})
        conn.exec_driver_sql("UPDATE feedback_v3 SET deleted_at='2026-10-22' WHERE feedback_id='old-feedback'")
    with Session(database, autoflush=False) as db:
        rows, total = read_owned_feedback_page(db, principal=principal(), limit=1)
        assert [r.feedback_id for r in rows] == ["fb_b"] and total == 2
        rows, total = read_owned_feedback_page(db, principal=principal(), music_id="missing")
        assert rows == [] and total == 0
        rows, total = read_owned_feedback_page(db, principal=principal(1))
        assert rows == [] and total == 0
        assert get_owned_feedback(db, principal=principal(), feedback_id="fb_a").feedback_id == "fb_a"
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM owner_music_state").scalar() == 0


@pytest.mark.parametrize("owner,record", [(1, "old-feedback"), (7, "missing"), (7, "old-feedback")])
def test_detail_hides_other_missing_and_deleted(database, owner, record):
    candidate().install_sqlite(database)
    with database.begin() as conn:
        conn.exec_driver_sql("UPDATE feedback_v3 SET deleted_at='2026-10-22' WHERE feedback_id='old-feedback'")
    with Session(database, autoflush=False) as db:
        with pytest.raises(FeedbackNotFound):
            get_owned_feedback(db, principal=principal(owner), feedback_id=record)


@pytest.mark.parametrize("limit", [0, 101, True])
def test_page_limit_rejects_invalid_values(database, limit):
    candidate().install_sqlite(database)
    with Session(database) as db:
        with pytest.raises(ValueError):
            read_owned_feedback_page(db, principal=principal(), limit=limit)
