import pytest


class FixedJsonLLM:
    def __init__(self):
        self._responses = [
            {
                "state_summary": {"summary": "Stress is elevated."},
                "context": {"triggers": ["workload"], "physical_signals": []},
                "evidence": [],
                "conflicts": [],
            },
            {"tendency_id": "syd_001", "confidence": 0.9},
        ]

    def complete_json(self, system_prompt, user_prompt):
        del system_prompt, user_prompt
        return self._responses.pop(0)


def questionnaire_answers():
    answers = {
        "q01_mood_weather": "cloudy",
        "q02_tension_worry": 3,
        "q03_overthinking": 2,
        "q04_irritability_anger": 1,
        "q05_low_mood": 4,
        "q06_interest_loss": 0,
        "q07_fear_unease": 2,
        "q08_sleep_disturbance": 3,
        "q09_low_energy": 1,
        "q10_appetite_change": 2,
        "q11_daily_impact": 4,
        "q12_physical_safety": ["none"],
    }
    return {
        "schema_version": "questionnaire_v2.0",
        "time_window_days": 7,
        "answers": [
            {"question_id": question_id, "value": value}
            for question_id, value in answers.items()
        ],
    }


def local_catalog():
    return [
        {
            "music_id": "music-jiao-01",
            "title": "Jiao Calm",
            "stream_url": "local://music/jiao-calm.mp3",
            "duration_seconds": 900,
            "source_type": "matched",
            "tone_id": "jiao",
            "bpm": 68,
            "instruments": ["guzheng", "guqin"],
        }
    ]


@pytest.mark.parametrize("iteration", range(10))
def test_sprint3_v2_workflow_is_stable_across_repeated_runs(iteration):
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    result = run_real_workflow_v2(
        user_id=f"stability-user-{iteration}",
        session_id=f"stability-session-{iteration}",
        questionnaire_answers=questionnaire_answers(),
        assessment_confirmed=True,
        llm=FixedJsonLLM(),
        music_catalog=local_catalog(),
    )

    assert result["assessment"]["analysis_mode"] == "questionnaire_only"
    assert result["music"]["music_id"] == "music-jiao-01"
    assert result["feedback"] == {"status": "not_submitted"}
    assert all(
        result["agent_statuses"][agent] == "success"
        for agent in ("assessment", "diagnosis", "prescription", "music")
    )
