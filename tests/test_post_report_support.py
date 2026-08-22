from keyboards import consent_keyboard, post_report_support_keyboard, prompt_actions_keyboard, support_detail_keyboard
from services.career_assessment import (
    human_escalation_reasons,
    optimized_followup_context,
    personal_ai_prompt,
    support_recommendation,
    support_recommendation_text,
    validated_assessment_result,
)
from tests.test_p0_life_context_routes import build_maria


def view():
    return validated_assessment_result(build_maria())


def test_post_report_options_include_four_support_formats():
    keyboard = post_report_support_keyboard("maria-pl")
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert any("карьерным экспертом" in label for label in labels)
    assert any("психологом" in label for label in labels)
    assert any("промт" in label for label in labels)
    assert any("человек + нейронка" in label for label in labels)


def test_market_uncertainty_routes_to_career_expert():
    result = view()
    result["main_uncertainty"] = "Нужно проверить требования польского рынка и уровень входа"
    assert support_recommendation(result)["format"] == "career_expert"


def test_psychology_requires_confirmed_barrier():
    result = view()
    result["confirmed_barriers"] = []
    assert support_recommendation(result)["format"] != "psychologist"
    result["confirmed_barriers"] = ["страх ошибки мешает отправлять отклики"]
    assert support_recommendation(result)["format"] == "psychologist"


def test_personal_prompt_is_scoped_to_current_assessment():
    prompt = personal_ai_prompt(view())
    assert "командой из 20 человек" in prompt
    assert "Process Improvement Specialist" in prompt
    assert "assessment-profile-10" not in prompt
    assert "Не придумывай факты" in prompt
    assert "AI-карьерный помощник, а не живой специалист" in prompt


def test_consent_defaults_to_no_transfer():
    callbacks = [button.callback_data for row in consent_keyboard("maria-pl", "career_expert").inline_keyboard for button in row]
    assert callbacks[-1].endswith(":none")
    sharing = {"career_expert": False, "psychologist": False, "hybrid_support": False, "scope": "none", "consented_at": None}
    assert not any(sharing[key] for key in ("career_expert", "psychologist", "hybrid_support"))


def test_followup_context_excludes_transcript_and_is_bounded():
    context = optimized_followup_context(view(), ["one", "two", "three", "four"])
    assert set(context) == {"professional_core", "selected_route", "main_gap", "constraints", "current_experiment", "recent_messages"}
    assert context["recent_messages"] == ["two", "three", "four"]
    assert "telegram_transcript" not in context


def test_support_submenus_and_chatgpt_action_are_available():
    career = [button.text for row in support_detail_keyboard("maria-pl", "career").inline_keyboard for button in row]
    hybrid = [button.text for row in support_detail_keyboard("maria-pl", "hybrid").inline_keyboard for button in row]
    prompt_buttons = [button for row in prompt_actions_keyboard("maria-pl").inline_keyboard for button in row]
    assert career == ["Записаться", "Что будет на встрече", "Вернуться назад"]
    assert "Сравнить форматы" in hybrid
    assert any(button.text == "Отправить в ChatGPT" and button.url for button in prompt_buttons)


def test_recommendation_is_neutral_or_grounded_and_human_escalation_is_explicit():
    result = view()
    text = support_recommendation_text(result)
    assert "потому что" in text or "недостаточно" in text
    assert human_escalation_reasons(user_requests_human=True) == ["user_requested_human"]
    assert "two_unhelpful_ai_answers" in human_escalation_reasons(ai_failures=2)
    result["desired_changes"] = ["Нужна последовательная серия действий с обратной связью"]
    assert support_recommendation(result)["format"] == "hybrid"
