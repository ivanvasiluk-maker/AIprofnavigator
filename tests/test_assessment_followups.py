from keyboards import assessment_actions_keyboard
from services.career_assessment import (
    build_income_bridge,
    render_30_day_program,
    render_assessment_html,
    render_personalized_ai_prompt,
    render_interview_product,
    render_linkedin_product,
    render_short_conclusion,
    start_guide_response,
    validated_assessment_result,
)
from tests.test_p0_life_context_routes import build_maria


def result():
    return validated_assessment_result(build_maria())


def test_short_and_full_use_one_assessment_result():
    assessment = build_maria()
    view = validated_assessment_result(assessment)
    short = render_short_conclusion(view)
    full = render_assessment_html(assessment)
    assert view["primary_route"]["title"] in short and view["primary_route"]["title"] in full
    assert all(item in short and item in full for item in view["professional_core"])
    assert "Анализ по маршрутам" not in full
    assert "Прогноз зарплаты или дохода" not in full


def test_short_conclusion_separates_user_routes_from_new_ai_hypotheses():
    assessment = build_maria()
    primary = assessment.routes.by_id(assessment.routes.recommended_route_id)
    alternative = next(route for route in assessment.routes.all_routes() if route.route_id != primary.route_id)
    assessment.user_choice.preferred_directions = [primary.title]

    view = validated_assessment_result(assessment)
    short = render_short_conclusion(view)

    assert primary.title in [item["title"] for item in view["user_proposed_routes"]]
    assert alternative.title in [item["title"] for item in view["ai_discovered_routes"]]
    assert f"Ваши варианты: {primary.title}" in short
    assert "Новые гипотезы ИИ:" in short and alternative.title in short
    assert "Известно:" in short
    assert "Выведено из фактов:" in short
    assert "Подтверждено рынком:" in short
    assert "Нужно проверить:" in short


def test_start_guide_asks_one_question_instead_of_rendering_report():
    text = start_guide_response(result())
    assert text.count(".") <= 2
    assert "Выберем одну причину" in text
    assert "Профессиональное ядро" not in text


def test_route_priority_reuses_existing_routes():
    view = result()
    before = {view["primary_route"]["title"], *(item["title"] for item in view["alternative_routes"])}
    answer = start_guide_response(view, "choose", "experience")
    assert any(title in answer for title in before)
    assert set(before) == {view["primary_route"]["title"], *(item["title"] for item in view["alternative_routes"])}


def test_vacancy_search_returns_queries_and_analysis_criteria():
    text = start_guide_response(result(), "vacancies")
    assert "Поисковые запросы" in text
    assert "ежедневные задачи" in text and "обязательный опыт" in text


def test_experience_branch_ends_with_one_evidence_question():
    text = start_guide_response(result(), "experience")
    assert text.endswith("процесс?")
    assert "готовый карьерный кейс" in text


def test_low_energy_action_matches_time_box():
    view = result()
    assert "один запрос" in start_guide_response(view, "energy", "5")
    assert "одну вакансию" in start_guide_response(view, "energy", "15")
    assert "три вакансии" in start_guide_response(view, "energy", "30")


def test_income_bridge_requires_confirmed_urgency():
    view = result()
    assert view["income_bridge"] is None
    assert build_income_bridge(view, "3_6") is None
    assert build_income_bridge(view, "month")["demand_signal"]


def test_followup_keyboard_uses_callbacks_not_assessment_generation():
    assessment = build_maria()
    callbacks = [button.callback_data for row in assessment_actions_keyboard(assessment).inline_keyboard for button in row]
    assert any(item.endswith(":full") for item in callbacks)
    assert any(item.endswith(":career") for item in callbacks)
    assert any(item.endswith(":group") for item in callbacks)
    assert any(item.endswith(":program30") for item in callbacks)
    assert any(item.endswith(":prompt") for item in callbacks)
    assert any(item.endswith(":reconsider") for item in callbacks)
    assert any(item.endswith(":linkedin") for item in callbacks)
    assert any(item.endswith(":interview") for item in callbacks)
    assert not any(item.endswith(":guide") for item in callbacks)
    assert all("generate" not in item and "rebuild" not in item for item in callbacks)


def test_post_report_products_reuse_selected_route():
    view = result()
    title = view["primary_route"]["title"]
    assert title in render_30_day_program(view)
    assert title in render_personalized_ai_prompt(view)
    assert title in render_linkedin_product(view)
    assert title in render_interview_product(view)
