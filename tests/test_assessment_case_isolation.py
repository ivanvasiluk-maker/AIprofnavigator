from handlers.career import _STORY_RESET_FIELDS, _build_profile_snapshot
from services.assessment_integrity import build_fact_ledger, contamination_errors
from services.canonical_profile import build_canonical_profile
from services.career_assessment import build_deterministic_assessment, validate_career_assessment


DENTAL_CASE = {
    "assessment_id": "dental-current-case",
    "story_text": (
        "Я зубной техник в Валенсии. Изготавливаю коронки и протезы, работаю с керамикой. "
        "Диагностирую причины дефектов, общаюсь со стоматологами, объясняю технические проблемы "
        "и выполняю базовые операции CAD/CAM. Хочу меньше ручной работы. "
        "Интересуют Technical Support и CAD/CAM dental technician. "
        "Испанский B1, Spanish, английский A2, English."
    ),
    "story_analysis": {
        "current_role": "Зубной техник",
        "confirmed_functions": [
            "диагностика причин дефектов",
            "техническое взаимодействие со стоматологами",
            "объяснение технических проблем",
            "базовые операции CAD/CAM",
            "изготовление коронок",
        ],
        "target_roles": ["Technical Support dental equipment", "CAD/CAM dental technician"],
        "target_change": ["меньше ручной работы"],
    },
}


def test_new_story_reset_removes_every_assessment_scoped_object():
    assert {
        "assessment_id", "source_messages", "uploaded_documents", "canonical_profile",
        "profile_snapshot", "career_assessment", "resume_analysis", "route_comparison",
    } <= set(_STORY_RESET_FIELDS)
    assert _STORY_RESET_FIELDS["assessment_id"] == ""
    assert _STORY_RESET_FIELDS["source_messages"] == []


def test_fact_ledger_rejects_messages_from_another_assessment():
    messages = [
        {"assessment_id": "current", "message_id": "1", "text": "SaaS support", "created_at": "now"},
        {"assessment_id": "previous", "message_id": "2", "text": "коронки и керамика", "created_at": "then"},
    ]
    ledger = build_fact_ledger("current", "user", messages)
    assert [fact["source_quote"] for fact in ledger] == ["SaaS support"]
    assert all(fact["assessment_id"] == "current" for fact in ledger)


def test_languages_are_deduplicated_with_provenance():
    profile = build_canonical_profile(DENTAL_CASE, assessment_id=DENTAL_CASE["assessment_id"])
    assert profile.normalized_profile.languages == {"Spanish": "B1", "English": "A2"}
    details = profile.normalized_profile.language_details
    assert {(item["language"], item["level"]) for item in details} == {("Spanish", "B1"), ("English", "A2")}
    assert all(item["source"] and item["confidence"] > 0 for item in details)


def test_dental_case_cannot_inherit_industrial_quality_route():
    snapshot = _build_profile_snapshot(DENTAL_CASE)
    assessment = build_deterministic_assessment(
        snapshot,
        DENTAL_CASE["story_analysis"],
        {},
        assessment_id=DENTAL_CASE["assessment_id"],
        session_id="dental-session",
        profile_version="1",
    )
    routes = assessment.routes.all_routes()
    assert routes
    assert not any("Supplier Quality" in route.title or "Industrial" in route.title for route in routes)
    assert all(len(route.evidence_ids) >= 2 for route in routes)
    assert all(route.transferable_functions and route.typical_tasks and route.new_functions for route in routes)
    assert all("изготовление коронок" not in " ".join(route.typical_tasks).casefold() for route in routes if "support" in route.title.casefold())


def test_final_contamination_check_blocks_foreign_domain_jump():
    snapshot = _build_profile_snapshot(DENTAL_CASE)
    report = {
        "assessment_id": DENTAL_CASE["assessment_id"],
        "evidence": [
            {"evidence_id": "e1", "fact": "изготовление коронок"},
            {"evidence_id": "e2", "fact": "работа с керамикой"},
        ],
        "routes": {
            "primary_routes": [{
                "route_id": "foreign-route",
                "title": "Industrial Supplier Quality Engineer",
                "evidence_ids": ["e1", "e2"],
            }],
        },
    }
    errors = contamination_errors(report, snapshot, DENTAL_CASE["assessment_id"])
    assert "UNSUPPORTED_CROSS_DOMAIN_ROUTE:foreign-route" in errors


def test_evidence_with_foreign_assessment_id_fails_final_validation():
    snapshot = _build_profile_snapshot(DENTAL_CASE)
    assessment = build_deterministic_assessment(
        snapshot, DENTAL_CASE["story_analysis"], {},
        assessment_id=DENTAL_CASE["assessment_id"], session_id="dental-session", profile_version="1",
    )
    assessment.evidence[0].assessment_id = "previous-case"
    validation = validate_career_assessment(assessment)
    assert any(issue.code == "FOREIGN_ASSESSMENT_EVIDENCE" for issue in validation.errors)
