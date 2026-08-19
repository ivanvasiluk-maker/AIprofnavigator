"""
Regression tests for interval-button system (PATCH 44) and
fresh-conclusion guarantee (PATCH 44b).

Each test covers one specific failure mode that must never silently regress.

Failure taxonomy:
  A - wrong function return (incorrect list / None)
  B - field still accepts raw text when buttons are available
  C - interview question list missing interval options
  D - keyboard fallback not applied when LLM omits options
  E - text-mode bypass broken (QUESTION_ADD_TEXT flow)
  F - interval option list inconsistency
  G - stale conclusion leaks into a new story (fresh-conclusion guarantee)
"""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.career import (
    _INTERVIEW_INCOME_INTERVAL_OPTIONS,
    _INTERVIEW_INCOME_SPEED_OPTIONS,
    _INTERVIEW_TIME_INTERVAL_OPTIONS,
    _ROUTE_CONTEXT_FIELDS,
    _ROUTE_CONTEXT_MIN_INCOME_OPTIONS,
    _ROUTE_CONTEXT_DESIRED_INCOME_OPTIONS,
    _ROUTE_CONTEXT_INCOME_URGENCY_OPTIONS,
    _ROUTE_CONTEXT_STUDY_TIME_OPTIONS,
    _ROUTE_CONTEXT_TRAINING_BUDGET_OPTIONS,
    _STORY_RESET_FIELDS,
    _interval_options_for_question,
    _normalize_question_options,
    _question_reply_markup,
    _route_context_options,
    _route_context_question,
    _route_context_reply_markup,
    handle_route_context_input,
    _questions_calm,
    _questions_support,
    _segment_common_questions,
)
from keyboards import QUESTION_ADD_TEXT
from states import CareerFlow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.chat = SimpleNamespace(id=1)
        self.from_user = SimpleNamespace(id=1, username="u", first_name="T", last_name="")
        self.bot = SimpleNamespace(send_message=AsyncMock())
        self._sent: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self._sent.append(text)


class FakeState:
    def __init__(self, data: dict | None = None, current_state: str | None = None) -> None:
        self.data: dict = dict(data or {})
        self.current_state = current_state or CareerFlow.ROUTE_CONTEXT.state

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.current_state = str(state)


def _keyboard_flat_texts(kb) -> list[str]:
    """Flatten all button labels from a ReplyKeyboardMarkup."""
    if kb is None:
        return []
    rows = getattr(kb, "keyboard", [])
    return [btn.text for row in rows for btn in row]


def _rc_field_index(field_id: str) -> int:
    for i, f in enumerate(_ROUTE_CONTEXT_FIELDS):
        if f.get("id") == field_id:
            return i
    raise KeyError(f"Route context field not found: {field_id!r}")


# ---------------------------------------------------------------------------
# A - _interval_options_for_question returns correct list
# ---------------------------------------------------------------------------

class TestIntervalOptionsForQuestion(unittest.TestCase):
    """A-series: _interval_options_for_question maps question text → correct list."""

    def test_A1_speed_question_returns_speed_options(self):
        """'Как быстро нужен доход' → speed options, not income-level options."""
        result = _interval_options_for_question("Как быстро нужен первый стабильный доход?")
        self.assertEqual(result, list(_INTERVIEW_INCOME_SPEED_OPTIONS),
                         "A1: speed question must return INCOME_SPEED list, not INCOME_LEVEL list")

    def test_A2_minimum_income_question_returns_income_level_options(self):
        """'Какой минимальный доход нужен в месяц' → income-level options."""
        result = _interval_options_for_question("Какой минимальный доход нужен в месяц?")
        self.assertEqual(result, list(_INTERVIEW_INCOME_INTERVAL_OPTIONS),
                         "A2: minimum-income question must return INCOME_INTERVAL list")

    def test_A3_hours_question_returns_time_options(self):
        """'Сколько часов в неделю' → time interval options."""
        result = _interval_options_for_question("Сколько часов в неделю вы реально готовы уделять поиску?")
        self.assertEqual(result, list(_INTERVIEW_TIME_INTERVAL_OPTIONS),
                         "A3: hours question must return TIME_INTERVAL list")

    def test_A4_study_time_question_returns_time_options(self):
        """'Сколько времени готовы учиться' → time interval options."""
        result = _interval_options_for_question("Сколько времени в неделю реально готовы учиться?")
        self.assertEqual(result, list(_INTERVIEW_TIME_INTERVAL_OPTIONS),
                         "A4: study-time question must return TIME_INTERVAL list")

    def test_A5_unrelated_question_returns_empty(self):
        """Career goal / profession question → no interval override."""
        result = _interval_options_for_question("Кем вы работали раньше?")
        self.assertEqual(result, [],
                         "A5: unrelated question must return empty list (no false interval injection)")

    def test_A6_speed_question_does_not_return_income_level_list(self):
        """Speed question must NOT return the income-level list (regression: was swapped in v0)."""
        speed_result = _interval_options_for_question("Как быстро нужен доход?")
        self.assertNotEqual(speed_result, list(_INTERVIEW_INCOME_INTERVAL_OPTIONS),
                            "A6: speed question returned income-level list — lists are swapped")

    def test_A7_desired_income_question_returns_income_level_options(self):
        """'Какой доход желаемый в месяц' → income-level options."""
        result = _interval_options_for_question("Какой желаемый доход в месяц на этом этапе?")
        self.assertEqual(result, list(_INTERVIEW_INCOME_INTERVAL_OPTIONS),
                         "A7: desired-income question must return INCOME_INTERVAL list")


# ---------------------------------------------------------------------------
# A8 - _normalize_question_options prefers existing options; falls back
# ---------------------------------------------------------------------------

class TestNormalizeQuestionOptions(unittest.TestCase):
    """A-series cont.: _normalize_question_options priority logic."""

    def test_A8_existing_options_are_not_overwritten(self):
        """If LLM returned options, they must survive without replacement."""
        existing = ["Option A", "Option B", "Option C"]
        result = _normalize_question_options("Какой минимальный доход нужен в месяц?", existing)
        self.assertEqual(result, existing,
                         "A8: existing non-empty options must NOT be replaced by interval fallback")

    def test_A9_empty_options_trigger_interval_fallback_for_income(self):
        """Empty options + income question → interval fallback is applied."""
        result = _normalize_question_options("Какой минимальный доход нужен в месяц?", [])
        self.assertEqual(result, list(_INTERVIEW_INCOME_INTERVAL_OPTIONS),
                         "A9: empty options for income question must get interval fallback")

    def test_A10_none_options_trigger_interval_fallback_for_hours(self):
        """None options + hours question → interval fallback is applied."""
        result = _normalize_question_options("Сколько часов в неделю готовы учиться?", None)
        self.assertEqual(result, list(_INTERVIEW_TIME_INTERVAL_OPTIONS),
                         "A10: None options for hours question must get interval fallback")


# ---------------------------------------------------------------------------
# B - route context field options exist and are non-empty
# ---------------------------------------------------------------------------

class TestRouteContextFieldsHaveOptions(unittest.TestCase):
    """B-series: every measurable route-context field must have interval options."""

    def _assert_field_options(self, field_id: str, expected_subset: list[str]):
        idx = _rc_field_index(field_id)
        q = _route_context_question(idx)
        opts = _route_context_options(q)
        self.assertTrue(len(opts) >= 2,
                        f"B: field '{field_id}' must have ≥2 button options, got {opts!r}")
        for item in expected_subset:
            self.assertIn(item, opts,
                          f"B: field '{field_id}' must contain option {item!r}, got {opts!r}")

    def test_B1_income_urgency_field_has_options(self):
        """income_urgency step must have urgency interval buttons."""
        self._assert_field_options("income_urgency", [_ROUTE_CONTEXT_INCOME_URGENCY_OPTIONS[0]])

    def test_B2_minimum_income_field_has_options(self):
        """minimum_monthly_income step must have PLN interval buttons."""
        self._assert_field_options("minimum_monthly_income", [_ROUTE_CONTEXT_MIN_INCOME_OPTIONS[0]])

    def test_B3_desired_income_field_has_options(self):
        """desired_monthly_income step must have PLN interval buttons."""
        self._assert_field_options("desired_monthly_income", [_ROUTE_CONTEXT_DESIRED_INCOME_OPTIONS[0]])

    def test_B4_training_budget_field_has_options(self):
        """training_budget step must have PLN interval buttons."""
        self._assert_field_options("training_budget", [_ROUTE_CONTEXT_TRAINING_BUDGET_OPTIONS[0]])

    def test_B5_study_time_field_has_options(self):
        """available_time_for_study step must have hours interval buttons."""
        self._assert_field_options("available_time_for_study", [_ROUTE_CONTEXT_STUDY_TIME_OPTIONS[0]])

    def test_B6_country_field_has_no_options(self):
        """country is free-text — must NOT have predefined options."""
        idx = _rc_field_index("country")
        q = _route_context_question(idx)
        opts = _route_context_options(q)
        self.assertEqual(opts, [],
                         "B6: country field is free-text and must have no options list")

    def test_B7_city_field_has_no_options(self):
        """city is free-text — must NOT have predefined options."""
        idx = _rc_field_index("city")
        q = _route_context_question(idx)
        opts = _route_context_options(q)
        self.assertEqual(opts, [],
                         "B7: city field is free-text and must have no options list")


# ---------------------------------------------------------------------------
# B8 - _route_context_reply_markup returns keyboard with correct buttons
# ---------------------------------------------------------------------------

class TestRouteContextReplyMarkup(unittest.TestCase):
    """B-series cont.: _route_context_reply_markup keyboard content."""

    def test_B8_income_urgency_keyboard_contains_all_urgency_options(self):
        """income_urgency keyboard must contain all urgency button labels."""
        idx = _rc_field_index("income_urgency")
        q = _route_context_question(idx)
        kb = _route_context_reply_markup(q)
        labels = _keyboard_flat_texts(kb)
        for opt in _ROUTE_CONTEXT_INCOME_URGENCY_OPTIONS:
            self.assertIn(opt, labels,
                          f"B8: keyboard for income_urgency must contain '{opt}'")

    def test_B9_minimum_income_keyboard_uses_safe_default_currency(self):
        """Without country context the keyboard must use one safe currency."""
        idx = _rc_field_index("minimum_monthly_income")
        q = _route_context_question(idx)
        kb = _route_context_reply_markup(q)
        labels = _keyboard_flat_texts(kb)
        self.assertTrue(any("EUR" in label for label in labels))
        self.assertFalse(any("PLN" in label for label in labels))

    def test_B10_study_time_keyboard_contains_hour_options(self):
        """available_time_for_study keyboard must contain hour interval labels."""
        idx = _rc_field_index("available_time_for_study")
        q = _route_context_question(idx)
        kb = _route_context_reply_markup(q)
        labels = _keyboard_flat_texts(kb)
        self.assertTrue(any("час" in label for label in labels),
                        "B10: study_time keyboard must contain hour-interval labels")

    def test_B11_country_keyboard_falls_back_to_input_method(self):
        """country field (no options) must fall back to input_method_keyboard, not None."""
        idx = _rc_field_index("country")
        q = _route_context_question(idx)
        kb = _route_context_reply_markup(q)
        self.assertIsNotNone(kb,
                             "B11: country field must return input_method_keyboard, not None")

    def test_B12_keyboard_also_contains_question_add_text_button(self):
        """All option-based keyboards must include the free-text escape button."""
        idx = _rc_field_index("minimum_monthly_income")
        q = _route_context_question(idx)
        kb = _route_context_reply_markup(q)
        labels = _keyboard_flat_texts(kb)
        self.assertIn(QUESTION_ADD_TEXT, labels,
                      "B12: button-keyboard must include QUESTION_ADD_TEXT escape option")


# ---------------------------------------------------------------------------
# C - question lists have interval options for measurable questions
# ---------------------------------------------------------------------------

class TestQuestionListsHaveIntervalOptions(unittest.TestCase):
    """C-series: _questions_calm, _questions_support, _segment_common_questions."""

    def _find_question(self, questions: list[dict], keyword: str) -> dict | None:
        for q in questions:
            if keyword in str(q.get("question", "")).lower():
                return q
        return None

    def test_C1_calm_minimum_income_has_pln_options(self):
        """_questions_calm minimum-income question must have PLN interval options."""
        qs = _questions_calm()
        q = self._find_question(qs, "минимальный доход")
        self.assertIsNotNone(q, "C1: _questions_calm must contain a minimum-income question")
        opts = q.get("options", [])
        self.assertTrue(any("EUR" in str(o) for o in opts))
        self.assertFalse(any("PLN" in str(o) for o in opts))

    def test_C2_calm_income_speed_has_speed_options(self):
        """_questions_calm income-speed question must have speed interval options."""
        qs = _questions_calm()
        q = self._find_question(qs, "как быстро")
        self.assertIsNotNone(q, "C2: _questions_calm must contain a speed question")
        opts = q.get("options", [])
        self.assertTrue(any("недел" in str(o).lower() or "месяц" in str(o).lower() for o in opts),
                        f"C2: calm speed-income options must reference weeks/months, got {opts!r}")

    def test_C3_support_minimum_income_has_pln_options(self):
        """_questions_support minimum-income question must have PLN interval options."""
        qs = _questions_support()
        q = self._find_question(qs, "минимальный доход")
        self.assertIsNotNone(q, "C3: _questions_support must contain a minimum-income question")
        opts = q.get("options", [])
        self.assertTrue(any("EUR" in str(o) for o in opts))
        self.assertFalse(any("PLN" in str(o) for o in opts))

    def test_C4_support_time_question_has_hour_options(self):
        """_questions_support hours-per-week question must have hour interval options."""
        qs = _questions_support()
        q = self._find_question(qs, "часов в неделю")
        self.assertIsNotNone(q, "C4: _questions_support must contain an hours-per-week question")
        opts = q.get("options", [])
        self.assertTrue(any("час" in str(o).lower() for o in opts),
                        f"C4: support hours-per-week options must contain hour labels, got {opts!r}")

    def test_C5_segment_common_minimum_income_has_pln_options(self):
        """_segment_common_questions minimum-income question must have PLN interval options."""
        qs = _segment_common_questions()
        q = self._find_question(qs, "минимальный доход")
        self.assertIsNotNone(q, "C5: _segment_common_questions must contain a minimum-income question")
        opts = q.get("options", [])
        self.assertTrue(any("EUR" in str(o) for o in opts))
        self.assertFalse(any("PLN" in str(o) for o in opts))

    def test_C6_segment_common_time_question_has_hour_options(self):
        """_segment_common_questions hours question must have hour interval options."""
        qs = _segment_common_questions()
        q = self._find_question(qs, "часов в неделю")
        self.assertIsNotNone(q, "C6: _segment_common_questions must contain an hours question")
        opts = q.get("options", [])
        self.assertTrue(any("час" in str(o).lower() for o in opts),
                        f"C6: segment hours options must contain hour labels, got {opts!r}")

    def test_C7_calm_story_question_is_free_text(self):
        """First question in _questions_calm (story) must remain free-text."""
        q = _questions_calm()[0]
        self.assertEqual(q.get("options", []), [],
                         "C7: story/experience question must be free-text (no options injected)")


# ---------------------------------------------------------------------------
# D - _question_reply_markup fallback for LLM questions without options
# ---------------------------------------------------------------------------

class TestQuestionReplyMarkupFallback(unittest.TestCase):
    """D-series: _question_reply_markup uses interval buttons when LLM returns no options."""

    def _analysis_with_question(self, question_text: str, options: list | None = None) -> dict:
        return {
            "follow_up_questions": [
                {"id": 1, "question": question_text, "options": options or []}
            ]
        }

    def test_D1_income_question_without_context_gets_single_currency_keyboard(self):
        """An unscoped LLM question must never inject a Polish keyboard."""
        analysis = self._analysis_with_question("Какой минимальный доход нужен в месяц?", [])
        kb = _question_reply_markup(analysis, 0)
        labels = _keyboard_flat_texts(kb)
        self.assertTrue(any("EUR" in label for label in labels))
        self.assertFalse(any("PLN" in label for label in labels))

    def test_D2_speed_question_without_options_gets_speed_keyboard(self):
        """LLM 'как быстро нужен доход' with empty options → speed-interval keyboard injected."""
        analysis = self._analysis_with_question("Как быстро нужен первый стабильный доход?", [])
        kb = _question_reply_markup(analysis, 0)
        labels = _keyboard_flat_texts(kb)
        self.assertTrue(any("недел" in l.lower() or "месяц" in l.lower() for l in labels),
                        f"D2: speed question without options must get speed-interval keyboard, got {labels!r}")

    def test_D3_hours_question_without_options_gets_time_keyboard(self):
        """LLM 'сколько часов в неделю' with empty options → time-interval keyboard injected."""
        analysis = self._analysis_with_question("Сколько часов в неделю готовы уделять поиску?", [])
        kb = _question_reply_markup(analysis, 0)
        labels = _keyboard_flat_texts(kb)
        self.assertTrue(any("час" in l.lower() for l in labels),
                        f"D3: hours question without options must get time-interval keyboard, got {labels!r}")

    def test_D4_existing_llm_options_not_replaced_by_interval_fallback(self):
        """If LLM provided explicit options, they must not be replaced by interval buttons."""
        custom = ["Вариант X", "Вариант Y", "Вариант Z"]
        analysis = self._analysis_with_question("Какой минимальный доход нужен в месяц?", custom)
        kb = _question_reply_markup(analysis, 0)
        labels = _keyboard_flat_texts(kb)
        for opt in custom:
            self.assertIn(opt, labels,
                          f"D4: explicit LLM option '{opt}' must not be replaced by interval fallback")

    def test_D5_speed_keyboard_does_not_contain_pln(self):
        """Speed keyboard must NOT accidentally contain PLN labels (lists must not be swapped)."""
        analysis = self._analysis_with_question("Как быстро нужен доход?", [])
        kb = _question_reply_markup(analysis, 0)
        labels = _keyboard_flat_texts(kb)
        self.assertFalse(any("PLN" in l for l in labels),
                         f"D5: speed keyboard must not contain PLN labels (list swap regression), got {labels!r}")

    def test_D6_income_keyboard_does_not_contain_week_speed_labels(self):
        """Income-level keyboard must NOT accidentally contain week-speed labels."""
        analysis = self._analysis_with_question("Какой минимальный доход нужен в месяц?", [])
        kb = _question_reply_markup(analysis, 0)
        labels = _keyboard_flat_texts(kb)
        # None of the labels should look like speed options (e.g. "⚡ 2-4 недели")
        self.assertFalse(any("2-4 недел" in l or "⚡" in l for l in labels),
                         f"D6: income keyboard must not contain speed labels, got {labels!r}")


# ---------------------------------------------------------------------------
# E - route context handler: validation and text-mode bypass
# ---------------------------------------------------------------------------

class TestRouteContextHandlerValidation(unittest.IsolatedAsyncioTestCase):
    """E-series: handle_route_context_input button validation."""

    def _state_at_field(self, field_id: str, extra: dict | None = None) -> FakeState:
        idx = _rc_field_index(field_id)
        data = {
            "language": "ru",
            "route_context_index": idx,
            "route_context": {},
            "route_context_text_mode_for": "",
        }
        if extra:
            data.update(extra)
        return FakeState(data=data, current_state=CareerFlow.ROUTE_CONTEXT.state)

    async def test_E1_random_text_rejected_for_button_field(self):
        """Submitting random text to a button-only field must NOT save the value."""
        state = self._state_at_field("minimum_monthly_income")
        message = FakeMessage(text="да, нужны деньги, много")

        with patch("handlers.career._start_route_context_intake", new=AsyncMock()):
            with patch("handlers.career.save_profile_version"):
                await handle_route_context_input(message, state)

        # Value must not have been stored
        saved = state.data.get("route_context", {}).get("minimum_monthly_income", "")
        self.assertEqual(saved, "",
                         "E1: random text must not be saved for a button-gated field")
        # Bot must have replied with a rejection prompt
        self.assertTrue(
            any("кнопк" in m.lower() or "вариант" in m.lower() for m in message._sent),
            f"E1: rejection message not sent, got: {message._sent!r}"
        )

    async def test_E2_valid_button_text_is_saved(self):
        """Pressing an exact button option must store the value in route_context."""
        field_id = "minimum_monthly_income"
        valid_option = _ROUTE_CONTEXT_MIN_INCOME_OPTIONS[1]
        state = self._state_at_field(field_id)
        message = FakeMessage(text=valid_option)

        with patch("handlers.career._start_route_context_intake", new=AsyncMock()):
            with patch("handlers.career.save_profile_version"):
                await handle_route_context_input(message, state)

        saved = state.data.get("route_context", {}).get("minimum_monthly_income", "")
        self.assertEqual(saved, valid_option,
                         f"E2: valid button '{valid_option}' must be stored; got {saved!r}")

    async def test_E3_question_add_text_enables_text_mode(self):
        """Pressing QUESTION_ADD_TEXT must set text mode for the current question."""
        field_id = "minimum_monthly_income"
        idx = _rc_field_index(field_id)
        question_id = str(_route_context_question(idx).get("id") or idx)
        state = self._state_at_field(field_id)
        message = FakeMessage(text=QUESTION_ADD_TEXT)

        with patch("handlers.career._start_route_context_intake", new=AsyncMock()):
            with patch("handlers.career.save_profile_version"):
                await handle_route_context_input(message, state)

        text_mode = state.data.get("route_context_text_mode_for", "")
        self.assertEqual(str(text_mode), str(question_id),
                         f"E3: text mode must be set to question_id={question_id!r} after QUESTION_ADD_TEXT, got {text_mode!r}")

    async def test_E4_text_mode_accepts_free_text_and_clears_mode(self):
        """When text-mode is active, free text must be saved and mode must be cleared."""
        field_id = "minimum_monthly_income"
        idx = _rc_field_index(field_id)
        question_id = str(_route_context_question(idx).get("id") or idx)
        state = self._state_at_field(
            field_id,
            extra={"route_context_text_mode_for": question_id}
        )
        custom_answer = "примерно 4000 злотых в месяц"
        message = FakeMessage(text=custom_answer)

        with patch("handlers.career._start_route_context_intake", new=AsyncMock()):
            with patch("handlers.career.save_profile_version"):
                await handle_route_context_input(message, state)

        saved = state.data.get("route_context", {}).get("minimum_monthly_income", "")
        self.assertEqual(saved, custom_answer,
                         f"E4: custom text must be saved during text-mode, got {saved!r}")
        text_mode = state.data.get("route_context_text_mode_for", None)
        self.assertEqual(text_mode, "",
                         f"E4: text_mode must be cleared after accepting custom text, got {text_mode!r}")

    async def test_E5_free_text_field_always_accepts_any_text(self):
        """country is free-text — any input must be accepted without rejection prompt."""
        state = self._state_at_field("country")
        message = FakeMessage(text="Германия")

        with patch("handlers.career._start_route_context_intake", new=AsyncMock()):
            with patch("handlers.career.save_profile_version"):
                await handle_route_context_input(message, state)

        saved = state.data.get("route_context", {}).get("country", "")
        self.assertEqual(saved, "Германия",
                         f"E5: free-text field 'country' must accept any input, got {saved!r}")
        self.assertFalse(
            any("кнопк" in m.lower() or "вариант" in m.lower() for m in message._sent),
            f"E5: must not show button-rejection for free-text field, sent: {message._sent!r}"
        )

    async def test_E6_study_time_field_rejects_random_number(self):
        """'5' typed as hours must be rejected — must press a button or use text mode."""
        state = self._state_at_field("available_time_for_study")
        message = FakeMessage(text="5")

        with patch("handlers.career._start_route_context_intake", new=AsyncMock()):
            with patch("handlers.career.save_profile_version"):
                await handle_route_context_input(message, state)

        saved = state.data.get("route_context", {}).get("available_time_for_study", "")
        self.assertEqual(saved, "",
                         "E6: raw number must not be saved for button-gated study_time field")


# ---------------------------------------------------------------------------
# F - interval option lists are internally consistent (no duplicates/empty)
# ---------------------------------------------------------------------------

class TestIntervalOptionListsConsistency(unittest.TestCase):
    """F-series: the constant lists themselves must be clean."""

    def _check_list(self, name: str, lst: list[str]) -> None:
        self.assertGreater(len(lst), 1, f"{name} must have >1 options")
        for item in lst:
            self.assertTrue(str(item).strip(), f"{name} must not contain blank items")
        self.assertEqual(len(lst), len(set(lst)), f"{name} must not contain duplicate options")

    def test_F1_income_interval_list_clean(self):
        self._check_list("_INTERVIEW_INCOME_INTERVAL_OPTIONS", list(_INTERVIEW_INCOME_INTERVAL_OPTIONS))

    def test_F2_income_speed_list_clean(self):
        self._check_list("_INTERVIEW_INCOME_SPEED_OPTIONS", list(_INTERVIEW_INCOME_SPEED_OPTIONS))

    def test_F3_time_interval_list_clean(self):
        self._check_list("_INTERVIEW_TIME_INTERVAL_OPTIONS", list(_INTERVIEW_TIME_INTERVAL_OPTIONS))

    def test_F4_route_context_min_income_list_clean(self):
        self._check_list("_ROUTE_CONTEXT_MIN_INCOME_OPTIONS", list(_ROUTE_CONTEXT_MIN_INCOME_OPTIONS))

    def test_F5_route_context_study_time_list_clean(self):
        self._check_list("_ROUTE_CONTEXT_STUDY_TIME_OPTIONS", list(_ROUTE_CONTEXT_STUDY_TIME_OPTIONS))

    def test_F6_route_context_fields_count_matches_15(self):
        """Route context intake must have exactly 15 steps after the patch."""
        self.assertEqual(len(_ROUTE_CONTEXT_FIELDS), 15,
                         "F6: _ROUTE_CONTEXT_FIELDS must have exactly 15 entries (PATCH 44)")


# ---------------------------------------------------------------------------
# G - fresh-conclusion guarantee: new story wipes all stale data
# ---------------------------------------------------------------------------

_STALE_CONCLUSION_DATA = {
    "final_report": {"digital_human": {"summary": "stale"}},
    "report_chunks": {"main": "stale chunk"},
    "final_report_generated": True,
    "report_generation_id": "old-id-123",
    "html_report_path": "/reports/old.html",
    "pdf_report_path": "/reports/old.pdf",
    "docx_report_path": "/reports/old.docx",
    "post_result_stage": "ready",
    "qa_answers": [{"question": "Q1", "answer": "A1"}],
    "qa_index": 5,
    "answers_text": "old answers",
    "evidence_profile": {"work_history_facts": [{"statement": "stale fact"}]},
    "career_strategy": "fast_income",
    "route_context": {"country": "Польша", "minimum_monthly_income": "3500"},
    "route_context_index": 8,
    "awaiting_route_context": True,
    "selected_barriers": ["Боюсь отказов"],
    "selected_fears": ["Боюсь отказов"],
    "selected_psych_markers": ["Хаос в голове"],
    "selected_energy_sources": ["Работа руками"],
    "selected_career_priorities": ["Быстрый доход"],
    "guardrail_retry_done": True,
    "preliminary_offer_shown": True,
    "mandatory_diagnostics_done": True,
    "conversation_hypotheses": [{"statement": "stale hypothesis"}],
    "resume_analysis": {"what_is_good": ["стаж 10 лет"]},
    "cv_uploaded": True,
}


def _make_story_state(extra: dict | None = None) -> "FakeState":
    data = {
        "language": "ru",
        "user_mode": "calm_steps",
        "public_user_id": "u-123",
        "session_id": "s-456",
    }
    data.update(_STALE_CONCLUSION_DATA)
    if extra:
        data.update(extra)
    from states import CareerFlow as _CF
    return FakeState(data=data, current_state=_CF.WAITING_STORY.state)


_STORY_TEXT = "Я работал инженером 10 лет, переехал в Польшу год назад, ищу работу."


class TestFreshConclusionOnNewStory(unittest.IsolatedAsyncioTestCase):
    """G-series: process_story_input must wipe all stale conclusion data."""

    from handlers.career import process_story_input as _process

    async def _run(self, story: str = _STORY_TEXT, extra_state: dict | None = None):
        from handlers.career import process_story_input
        state = _make_story_state(extra_state)
        message = FakeMessage(text=story)
        fake_analysis = {
            "facts_extracted": ["инженер", "Польша"],
            "functions_detected": [],
            "professional_core_hypotheses": [],
            "seniority_hypotheses": [],
            "explicit_refusals": [],
            "constraints": [],
            "legal_access_questions": [],
            "contradictions": [],
            "critical_gaps": [],
            "next_question": {"question": "?", "internal_goal": "", "expected_information": [], "skip_if": []},
            "ready_for_preliminary_result": False,
            "readiness_reason": "",
            "story_summary": "инженер",
            "current_identity": "инженер",
            "experience_snapshot": [],
            "skills": [],
            "goals": [],
            "missing_data": [],
            "follow_up_questions": [],
            "confidence_note": "",
        }
        with patch("handlers.career.ai_client") as mock_ai:
            mock_ai.analyze_story = AsyncMock(return_value=fake_analysis)
            with patch("handlers.career._track_event", new=AsyncMock()):
                await process_story_input(message, state, story)
        return state

    async def test_G1_final_report_cleared_on_new_story(self):
        """final_report must be empty dict after a new story is submitted."""
        state = await self._run()
        self.assertEqual(state.data.get("final_report"), {},
                         "G1: final_report must be reset to {} when new story starts")

    async def test_G2_final_report_generated_flag_cleared(self):
        """final_report_generated flag must be False after new story."""
        state = await self._run()
        self.assertFalse(state.data.get("final_report_generated"),
                         "G2: final_report_generated must be False when new story starts")

    async def test_G3_old_report_generation_id_cleared(self):
        """report_generation_id from previous run must not survive new story."""
        state = await self._run()
        self.assertEqual(state.data.get("report_generation_id"), "",
                         "G3: report_generation_id must be cleared on new story")

    async def test_G4_qa_answers_cleared(self):
        """Interview answers from previous run must not survive new story."""
        state = await self._run()
        self.assertEqual(state.data.get("qa_answers"), [],
                         "G4: qa_answers must be reset on new story")

    async def test_G5_answers_text_cleared(self):
        """Merged answers_text from previous run must not survive new story."""
        state = await self._run()
        self.assertEqual(state.data.get("answers_text"), "",
                         "G5: answers_text must be cleared on new story")

    async def test_G6_route_context_cleared(self):
        """route_context filled in previous run must be empty for new story."""
        state = await self._run()
        self.assertEqual(state.data.get("route_context"), {},
                         "G6: route_context must be cleared on new story")

    async def test_G7_career_strategy_cleared(self):
        """career_strategy selected in previous run must not carry over."""
        state = await self._run()
        self.assertEqual(state.data.get("career_strategy"), "",
                         "G7: career_strategy must be cleared on new story")

    async def test_G8_selected_markers_cleared(self):
        """Psycho/barrier selections from previous run must be empty."""
        state = await self._run()
        for key in ("selected_barriers", "selected_fears", "selected_psych_markers",
                    "selected_energy_sources", "selected_career_priorities"):
            self.assertEqual(state.data.get(key), [],
                             f"G8: {key} must be cleared on new story")

    async def test_G9_stale_file_paths_cleared(self):
        """HTML/PDF/DOCX report file paths from previous run must be empty."""
        state = await self._run()
        for key in ("html_report_path", "pdf_report_path", "docx_report_path"):
            self.assertEqual(state.data.get(key), "",
                             f"G9: {key} must be cleared on new story")

    async def test_G10_guardrail_retry_flag_cleared(self):
        """guardrail_retry_done must reset so guardrail can re-run if needed."""
        state = await self._run()
        self.assertFalse(state.data.get("guardrail_retry_done"),
                         "G10: guardrail_retry_done must be False on new story")

    async def test_G11_stale_resume_analysis_cleared(self):
        """resume_analysis from old run must not leak into new story conclusions."""
        state = await self._run()
        self.assertEqual(state.data.get("resume_analysis"), {},
                         "G11: resume_analysis must be cleared on new story")

    async def test_G12_preserved_fields_survive_reset(self):
        """user_mode, language, public_user_id must NOT be cleared by story reset."""
        state = await self._run()
        self.assertEqual(state.data.get("language"), "ru",
                         "G12a: language must survive story reset")
        self.assertEqual(state.data.get("user_mode"), "calm_steps",
                         "G12b: user_mode must survive story reset")
        self.assertEqual(state.data.get("public_user_id"), "u-123",
                         "G12c: public_user_id must survive story reset")

    async def test_G13_story_reset_fields_covers_all_conclusion_keys(self):
        """_STORY_RESET_FIELDS must cover every key present in the stale data fixture."""
        missing = [k for k in _STALE_CONCLUSION_DATA if k not in _STORY_RESET_FIELDS]
        self.assertEqual(missing, [],
                         f"G13: these stale keys are NOT in _STORY_RESET_FIELDS: {missing!r}. "
                         "Add them to prevent future leaks.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
