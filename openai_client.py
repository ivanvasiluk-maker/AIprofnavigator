import asyncio
import copy
import json
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from config import settings
from prompts import FINAL_REPORT_PROMPT, RESUME_ANALYSIS_PROMPT, STORY_ANALYSIS_PROMPT, SYSTEM_PROMPT
from services.career_assessment import (
    CAREER_ASSESSMENT_SCHEMA,
    CareerAssessment,
    build_deterministic_assessment,
    career_assessment_from_dict,
    validate_career_assessment,
)
from services.runtime_isolation import assert_expected_profiles_not_loaded


CONSTRUCTION_ESTIMATION_DOMAIN = "construction_engineering_cost_estimation"
CONSTRUCTION_ESTIMATION_ROLES = [
    "Assistant Cost Estimator",
    "Junior Quantity Surveyor",
    "Construction Documentation Specialist",
    "Technical Assistant Construction",
    "Construction Project Assistant",
    "Site Office Assistant",
    "Project Coordinator in construction company",
    "Back-office Specialist in construction / engineering company",
]
CONSTRUCTION_FORBIDDEN_FIRST_STEP_TERMS = [
    "плитка",
    "гипсокартон",
    "мебель",
    "покраска",
    "отделка",
    "частные заказы",
    "подработка на объекте руками",
]
CONSTRUCTION_DOMAIN_FIRST_STEP_ACTION = (
    "Сегодня за 15 минут найдите 10 вакансий по запросам:\n"
    "Assistant Cost Estimator, Junior Quantity Surveyor, Technical Assistant Construction,\n"
    "Construction Documentation Specialist, Construction Project Assistant.\n\n"
    "Выпишите повторяющиеся требования:\n"
    "польский язык, программы, строительные нормы, Excel,\n"
    "работа с проектной документацией,\n"
    "опыт в Польше, сертификаты.\n\n"
    "Пока не покупайте курсы — сначала проверяем рынок."
)
CONSTRUCTION_DOMAIN_FIRST_STEP_BUTTONS = [
    "Сделал",
    "Слишком сложно",
    "Сделать проще",
    "Помоги составить таблицу",
    "Хочу примеры запросов",
]

STORY_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        # ── v2 evidence fields ──────────────────────────────────────────────
        "facts_extracted": {"type": "array", "items": {"type": "string"}},
        "functions_detected": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "frequency": {"type": "string"},
                    "autonomy": {"type": "string"},
                    "scale": {"type": "string"},
                    "results": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string"},
                },
                "required": ["name", "evidence", "frequency", "autonomy", "scale", "results", "confidence"],
                "additionalProperties": False,
            },
        },
        "professional_core_hypotheses": {"type": "array", "items": {"type": "string"}},
        "seniority_hypotheses": {"type": "array", "items": {"type": "string"}},
        "explicit_refusals": {"type": "array", "items": {"type": "string"}},
        "legal_access_questions": {"type": "array", "items": {"type": "string"}},
        "contradictions": {"type": "array", "items": {"type": "string"}},
        "critical_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gap_type": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "decision_that_may_change": {"type": "string"},
                    "priority": {"type": "integer"},
                },
                "required": ["gap_type", "why_it_matters", "decision_that_may_change", "priority"],
                "additionalProperties": False,
            },
        },
        "next_question": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "internal_goal": {"type": "string"},
                "expected_information": {"type": "array", "items": {"type": "string"}},
                "skip_if": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["question", "internal_goal", "expected_information", "skip_if"],
            "additionalProperties": False,
        },
        "ready_for_preliminary_result": {"type": "boolean"},
        "readiness_reason": {"type": "string"},
        # ── legacy bridge fields (backward compat) ──────────────────────────
        "story_summary": {"type": "string"},
        "current_identity": {"type": "string"},
        "experience_snapshot": {"type": "array", "items": {"type": "string"}},
        "skills": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "goals": {"type": "array", "items": {"type": "string"}},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "follow_up_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "block": {"type": "string"},
                    "question": {"type": "string"},
                    "type": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "block", "question", "type", "options"],
                "additionalProperties": False,
            },
        },
        "confidence_note": {"type": "string"},
    },
    "required": [
        "facts_extracted",
        "functions_detected",
        "professional_core_hypotheses",
        "seniority_hypotheses",
        "explicit_refusals",
        "constraints",
        "legal_access_questions",
        "contradictions",
        "critical_gaps",
        "next_question",
        "ready_for_preliminary_result",
        "readiness_reason",
        "story_summary",
        "current_identity",
        "experience_snapshot",
        "skills",
        "goals",
        "missing_data",
        "follow_up_questions",
        "confidence_note",
    ],
    "additionalProperties": False,
}

FINAL_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "digital_human": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "previous_identity": {"type": "string"},
                "current_state": {"type": "string"},
                "main_asset": {"type": "string"},
                "main_risk": {"type": "string"},
                "main_barrier": {"type": "string"},
                "main_fear": {"type": "string"},
                "hidden_strengths": {"type": "array", "items": {"type": "string"}},
                "psychological_profile": {
                    "type": "object",
                    "properties": {
                        "dominant_barriers": {"type": "array", "items": {"type": "string"}},
                        "dominant_fears": {"type": "array", "items": {"type": "string"}},
                        "coping_style": {"type": "string"},
                        "support_needed": {"type": "string"},
                    },
                    "required": ["dominant_barriers", "dominant_fears", "coping_style", "support_needed"],
                    "additionalProperties": False,
                },
                "fastest_path_to_income": {"type": "string"},
                "long_term_path": {"type": "string"},
                "skills": {
                    "type": "object",
                    "properties": {
                        "professional": {"type": "array", "items": {"type": "string"}},
                        "transferable": {"type": "array", "items": {"type": "string"}},
                        "hidden": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["professional", "transferable", "hidden"],
                    "additionalProperties": False,
                },
                "barriers": {
                    "type": "object",
                    "properties": {
                        "external": {"type": "array", "items": {"type": "string"}},
                        "internal": {"type": "array", "items": {"type": "string"}},
                        "critical": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["external", "internal", "critical"],
                    "additionalProperties": False,
                },
                "motivation": {
                    "type": "object",
                    "properties": {
                        "money": {"type": "integer"},
                        "stability": {"type": "integer"},
                        "freedom": {"type": "integer"},
                        "meaning": {"type": "integer"},
                        "status": {"type": "integer"},
                        "entrepreneurship": {"type": "integer"},
                    },
                    "required": ["money", "stability", "freedom", "meaning", "status", "entrepreneurship"],
                    "additionalProperties": False,
                },
                "career_readiness": {
                    "type": "object",
                    "properties": {
                        "urgency": {"type": "string"},
                        "learning_capacity": {"type": "string"},
                        "risk_tolerance": {"type": "string"},
                        "language_readiness": {"type": "string"},
                        "mobility": {"type": "string"},
                    },
                    "required": ["urgency", "learning_capacity", "risk_tolerance", "language_readiness", "mobility"],
                    "additionalProperties": False,
                },
                "strategy_mode": {"type": "string"},
            },
            "required": [
                "summary",
                "previous_identity",
                "current_state",
                "main_asset",
                "main_risk",
                "main_barrier",
                "main_fear",
                "hidden_strengths",
                "psychological_profile",
                "fastest_path_to_income",
                "long_term_path",
                "skills",
                "barriers",
                "motivation",
                "career_readiness",
                "strategy_mode",
            ],
            "additionalProperties": False,
        },
        "experience_layers": {"type": "array", "items": {"type": "string"}},
        "what_not_reset": {"type": "array", "items": {"type": "string"}},
        "market_analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "profession": {"type": "string"},
                    "fit_percent": {"type": "integer"},
                    "demand": {"type": "string"},
                    "entry_speed": {"type": "string"},
                    "competition": {"type": "string"},
                    "requirements": {"type": "array", "items": {"type": "string"}},
                    "salary_range": {"type": "string"},
                    "profile_match_reason": {"type": "string"},
                },
                "required": [
                    "profession",
                    "fit_percent",
                    "demand",
                    "entry_speed",
                    "competition",
                    "requirements",
                    "salary_range",
                    "profile_match_reason",
                ],
                "additionalProperties": False,
            },
        },
        "career_translation": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_experience": {"type": "string"},
                    "market_term": {"type": "string"},
                    "suitable_roles": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["source_experience", "market_term", "suitable_roles"],
                "additionalProperties": False,
            },
        },
        "career_bridges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "why_bridge": {"type": "string"},
                    "first_market_test": {"type": "string"},
                },
                "required": ["role", "why_bridge", "first_market_test"],
                "additionalProperties": False,
            },
        },
        "career_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "match_percent": {"type": "integer"},
                    "why_fit": {"type": "string"},
                    "pros": {"type": "array", "items": {"type": "string"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "entry_timeline": {"type": "string"},
                    "income_range": {"type": "string"},
                },
                "required": [
                    "title",
                    "match_percent",
                    "why_fit",
                    "pros",
                    "risks",
                    "entry_timeline",
                    "income_range",
                ],
                "additionalProperties": False,
            },
        },
        "real_solutions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "recommendation_level": {"type": "string"},
                    "success_probability": {"type": "string"},
                    "timeline": {"type": "string"},
                    "why": {"type": "string"},
                    "first_step": {"type": "string"},
                },
                "required": ["title", "recommendation_level", "success_probability", "timeline", "why", "first_step"],
                "additionalProperties": False,
            },
        },
        "career_decision": {
            "type": "object",
            "properties": {
                "recommended_main_path": {"type": "string"},
                "why_this_path": {"type": "string"},
                "why_not_other_paths": {"type": "array", "items": {"type": "string"}},
                "backup_path": {"type": "string"},
                "avoid_for_now": {"type": "string"},
                "decision_summary": {"type": "string"},
            },
            "required": ["recommended_main_path", "why_this_path", "why_not_other_paths", "backup_path", "avoid_for_now", "decision_summary"],
            "additionalProperties": False,
        },
        "route_evidence_blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "route": {"type": "string"},
                    "why_it_fits": {"type": "array", "items": {"type": "string"}},
                    "evidence_from_user": {"type": "array", "items": {"type": "string"}},
                    "missing_competencies": {"type": "array", "items": {"type": "string"}},
                    "entry_level": {"type": "string"},
                    "income_role": {"type": "string", "enum": ["primary", "transition", "quick", "emergency"]},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "what_may_disprove_this_route": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "route",
                    "why_it_fits",
                    "evidence_from_user",
                    "missing_competencies",
                    "entry_level",
                    "income_role",
                    "risks",
                    "what_may_disprove_this_route",
                ],
                "additionalProperties": False,
            },
        },
        "development_map": {
            "type": "object",
            "properties": {
                "current_state": {"type": "string"},
                "goal": {"type": "string"},
                "gap": {"type": "array", "items": {"type": "string"}},
                "route": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stage": {"type": "string"},
                            "objective": {"type": "string"},
                            "actions": {"type": "array", "items": {"type": "string"}},
                            "output": {"type": "string"},
                            "timeline": {"type": "string"},
                        },
                        "required": ["stage", "objective", "actions", "output", "timeline"],
                        "additionalProperties": False,
                    },
                },
                "first_month": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "week": {"type": "integer"},
                            "focus": {"type": "string"},
                            "tasks": {"type": "array", "items": {"type": "string"}},
                            "output": {"type": "string"},
                        },
                        "required": ["week", "focus", "tasks", "output"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["current_state", "goal", "gap", "route", "first_month"],
            "additionalProperties": False,
        },
        "action_plan": {
            "type": "object",
            "properties": {
                "today": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "timebox": {"type": "string"},
                        "result": {"type": "string"},
                    },
                    "required": ["action", "timebox", "result"],
                    "additionalProperties": False,
                },
                "this_week": {"type": "array", "items": {"type": "string"}},
                "this_month": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["today", "this_week", "this_month"],
            "additionalProperties": False,
        },
        "weekly_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "day": {"type": "integer"},
                    "focus": {"type": "string"},
                    "task": {"type": "string"},
                    "time": {"type": "string"},
                    "result": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["day", "focus", "task", "time", "result", "why"],
                "additionalProperties": False,
            },
        },
        "career_barriers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "barrier": {"type": "string"},
                    "severity": {"type": "integer"},
                    "mechanism": {"type": "string"},
                    "recommended_skill": {"type": "string"},
                    "first_exercise": {"type": "string"},
                },
                "required": ["barrier", "severity", "mechanism", "recommended_skill", "first_exercise"],
                "additionalProperties": False,
            },
        },
        "barrier_landscape": {
            "type": "object",
            "properties": {
                "external": {"type": "array", "items": {"type": "string"}},
                "internal": {"type": "array", "items": {"type": "string"}},
                "behavioral_risk": {"type": "string"},
                "first_counter_action": {"type": "string"},
            },
            "required": ["external", "internal", "behavioral_risk", "first_counter_action"],
            "additionalProperties": False,
        },
        "social_integration": {
            "type": "object",
            "properties": {
                "environment": {"type": "array", "items": {"type": "string"}},
                "people": {"type": "array", "items": {"type": "string"}},
                "communities": {"type": "array", "items": {"type": "string"}},
                "opportunities": {"type": "array", "items": {"type": "string"}},
                "contribution": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["environment", "people", "communities", "opportunities", "contribution"],
            "additionalProperties": False,
        },
        "resource_level": {"type": "string"},
        "integration_level": {"type": "string"},
        "energy_sources": {"type": "array", "items": {"type": "string"}},
        "career_priorities": {"type": "array", "items": {"type": "string"}},
        "competency_signals": {"type": "array", "items": {"type": "string"}},
        "decision_layers": {
            "type": "object",
            "properties": {
                "career_profile": {"type": "array", "items": {"type": "string"}},
                "constraints": {"type": "array", "items": {"type": "string"}},
                "psychological_state": {"type": "array", "items": {"type": "string"}},
                "action_capacity": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["career_profile", "constraints", "psychological_state", "action_capacity"],
            "additionalProperties": False,
        },
        "facts_only": {
            "type": "object",
            "properties": {
                "explicit_facts": {"type": "array", "items": {"type": "string"}},
                "resume_facts": {"type": "array", "items": {"type": "string"}},
                "inferences": {"type": "array", "items": {"type": "string"}},
                "unknowns": {"type": "array", "items": {"type": "string"}},
                "contradictions": {"type": "array", "items": {"type": "string"}},
                "career_profile": {"type": "object", "additionalProperties": True},
                "constraints": {"type": "object", "additionalProperties": True},
                "psychological_state": {"type": "object", "additionalProperties": True},
                "action_capacity": {"type": "object", "additionalProperties": True},
                "integration": {"type": "object", "additionalProperties": True},
                "route_preferences": {"type": "object", "additionalProperties": True},
            },
            "required": [
                "explicit_facts",
                "resume_facts",
                "inferences",
                "unknowns",
                "contradictions",
                "career_profile",
                "constraints",
                "psychological_state",
                "action_capacity",
                "integration",
                "route_preferences",
            ],
            "additionalProperties": False,
        },
        "closing_message": {"type": "string"},
    },
    "required": [
        "digital_human",
        "experience_layers",
        "what_not_reset",
        "market_analysis",
        "career_translation",
        "career_bridges",
        "career_recommendations",
        "real_solutions",
        "career_decision",
        "route_evidence_blocks",
        "development_map",
        "action_plan",
        "weekly_plan",
        "career_barriers",
        "barrier_landscape",
        "social_integration",
        "resource_level",
        "integration_level",
        "energy_sources",
        "career_priorities",
        "competency_signals",
        "facts_only",
        "closing_message",
    ],
    "additionalProperties": False,
}

RESUME_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "professions": {"type": "array", "items": {"type": "string"}},
        "periods": {"type": "array", "items": {"type": "string"}},
        "tasks": {"type": "array", "items": {"type": "string"}},
        "education": {"type": "array", "items": {"type": "string"}},
        "languages": {"type": "array", "items": {"type": "string"}},
        "certificates": {"type": "array", "items": {"type": "string"}},
        "achievements": {"type": "array", "items": {"type": "string"}},
        "skills": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "inconsistencies": {"type": "array", "items": {"type": "string"}},
        "clarifying_questions": {"type": "array", "items": {"type": "string"}},
        "career_level": {"type": "string"},
        "what_is_good": {"type": "array", "items": {"type": "string"}},
        "what_is_missing": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "professions",
        "periods",
        "tasks",
        "education",
        "languages",
        "certificates",
        "achievements",
        "skills",
        "gaps",
        "inconsistencies",
        "clarifying_questions",
        "career_level",
        "what_is_good",
        "what_is_missing",
    ],
    "additionalProperties": False,
}

STORY_ANALYSIS_FALLBACK = {
    # ── v2 evidence fields ──────────────────────────────────────────────────
    "facts_extracted": ["Есть профессиональный опыт до переезда", "Текущая ситуация требует нового карьерного ориентира"],
    "functions_detected": [],
    "professional_core_hypotheses": ["Профессиональное ядро требует уточнения через конкретные функции"],
    "seniority_hypotheses": [],
    "explicit_refusals": [],
    "legal_access_questions": ["Какое право на работу и признание квалификации есть сейчас?"],
    "contradictions": [],
    "critical_gaps": [
        {"gap_type": "minimum_income", "why_it_matters": "Влияет на допустимые маршруты", "decision_that_may_change": "Быстрый vs долгосрочный маршрут", "priority": 95},
        {"gap_type": "income_deadline", "why_it_matters": "Определяет темп и срочность", "decision_that_may_change": "Темп перехода", "priority": 92},
        {"gap_type": "legal_access", "why_it_matters": "Ограничивает допустимые роли", "decision_that_may_change": "Набор профессий в маршруте", "priority": 88},
    ],
    "next_question": {
        "question": "Какой минимальный доход в месяц вам нужен, чтобы стабилизировать ситуацию?",
        "internal_goal": "Зафиксировать финансовое ограничение для выбора маршрута",
        "expected_information": ["Конкретная сумма или диапазон"],
        "skip_if": ["Пользователь уже назвал сумму"],
    },
    "ready_for_preliminary_result": False,
    "readiness_reason": "Недостаточно данных о профессиональных функциях и финансовых ограничениях.",
    # ── legacy bridge fields ────────────────────────────────────────────────
    "story_summary": "Пока видно общий карьерный переход после переезда и запрос на новую опору.",
    "current_identity": "Мигрант в переходе с профессиональным опытом и потребностью в новом карьерном маршруте.",
    "experience_snapshot": ["Есть профессиональный опыт до переезда", "Сейчас нужен новый карьерный ориентир"],
    "skills": ["коммуникация", "адаптивность", "ответственность"],
    "constraints": ["нужно уточнить язык", "нужно уточнить документы", "нужно уточнить срочность дохода"],
    "goals": ["понять подходящие карьерные направления", "получить реалистичный план перехода"],
    "missing_data": ["minimum_income", "income_deadline", "legal_access"],
    "follow_up_questions": [
        {
            "id": 1,
            "block": "financial_pressure",
            "question": "Какой минимальный доход вам нужен в месяц?",
            "type": "short_text",
            "options": [],
        },
        {
            "id": 2,
            "block": "financial_pressure",
            "question": "Как быстро вам нужен стабильный доход?",
            "type": "single_choice",
            "options": ["в течение 2-4 недель", "в течение 1-3 месяцев", "могу учиться 3-6 месяцев", "могу менять траекторию год"],
        },
        {
            "id": 3,
            "block": "interests_motivation",
            "question": "Сколько часов в неделю вы готовы выделять на обучение или поиск работы?",
            "type": "short_text",
            "options": [],
        },
        {
            "id": 4,
            "block": "professional_experience",
            "question": "Какой формат работы вам ближе?",
            "type": "single_choice",
            "options": [
                "Больше с документами",
                "Больше с людьми",
                "50/50",
                "Лучше без активных продаж",
            ],
        },
        {
            "id": 5,
            "block": "interests_motivation",
            "question": "Что вы точно не хотите делать в новой работе?",
            "type": "short_text",
            "options": [],
        },
        {
            "id": 6,
            "block": "language_local_context",
            "question": "Какие языки вы знаете и на каком уровне?",
            "type": "short_text",
            "options": [],
        },
        {
            "id": 7,
            "block": "social_integration",
            "question": "Есть ли у вас поддержка сейчас?",
            "type": "single_choice",
            "options": ["Есть семья/партнер", "Есть друзья", "Есть профконтакты", "Почти нет поддержки"],
        },
        {
            "id": 8,
            "block": "barriers_psychological",
            "question": "Какие направления вы уже рассматриваете или точно не хотите?",
            "type": "short_text",
            "options": [],
        },
    ],
    "confidence_note": "Часть профиля собрана из общей истории, несколько ключевых параметров нужно уточнить.",
}

STORY_ANALYSIS_FALLBACK_BE = {
    # ── v2 evidence fields ──────────────────────────────────────────────────
    "facts_extracted": ["Ёсць прафесійны досвед да пераезду", "Зараз патрэбны новы кар'ерны арыенцір"],
    "functions_detected": [],
    "professional_core_hypotheses": ["Прафесійнае ядро патрабуе ўдакладнення праз канкрэтныя функцыі"],
    "seniority_hypotheses": [],
    "explicit_refusals": [],
    "legal_access_questions": ["Якое права на працу і прызнанне кваліфікацыі ёсць зараз?"],
    "contradictions": [],
    "critical_gaps": [
        {"gap_type": "minimum_income", "why_it_matters": "Уплывае на дапушчальныя маршруты", "decision_that_may_change": "Хуткі vs доўгатэрміновы маршрут", "priority": 95},
        {"gap_type": "income_deadline", "why_it_matters": "Вызначае тэмп і тэрміновасць", "decision_that_may_change": "Тэмп пераходу", "priority": 92},
    ],
    "next_question": {
        "question": "Які мінімальны даход у месяц вам патрэбны, каб стабілізаваць сітуацыю?",
        "internal_goal": "Зафіксаваць фінансавае абмежаванне для выбару маршруту",
        "expected_information": ["Канкрэтная сума або дыяпазон"],
        "skip_if": ["Карыстальнік ужо назваў суму"],
    },
    "ready_for_preliminary_result": False,
    "readiness_reason": "Недастаткова дадзеных аб прафесійных функцыях і фінансавых абмежаваннях.",
    # ── legacy bridge fields ────────────────────────────────────────────────
    "story_summary": "Пакуль бачны агульны кар'ерны пераход пасля пераезду і запыт на новую апору.",
    "current_identity": "Мігрант у пераходзе з прафесійным досведам і патрэбай у новым кар'ерным маршруце.",
    "experience_snapshot": ["Ёсць прафесійны досвед да пераезду", "Зараз патрэбны новы кар'ерны арыенцір"],
    "skills": ["камунікацыя", "адаптыўнасць", "адказнасць"],
    "constraints": ["трэба ўдакладніць мову", "трэба ўдакладніць дакументы", "трэба ўдакладніць тэрміновасць даходу"],
    "goals": ["зразумець прыдатныя кар'ерныя напрамкі", "атрымаць рэалістычны план пераходу"],
    "missing_data": ["minimum_income", "income_deadline", "legal_access"],
    "follow_up_questions": copy.deepcopy(STORY_ANALYSIS_FALLBACK["follow_up_questions"]),
    "confidence_note": "Частка профілю сабраная з агульнай гісторыі, некалькі ключавых параметраў трэба ўдакладніць.",
}

RESUME_ANALYSIS_FALLBACK = {
    "professions": ["Sales Manager", "Account Manager"],
    "periods": ["2018-2024"],
    "tasks": ["ведение клиентов", "переговоры", "работа с CRM"],
    "education": ["Данных недостаточно"],
    "languages": ["русский", "польский: данных недостаточно", "английский: данных недостаточно"],
    "certificates": ["Данных недостаточно"],
    "achievements": ["Выполнение KPI", "Рост клиентского удержания"],
    "skills": ["коммуникация", "переговоры", "организация процессов"],
    "gaps": ["не хватает цифр по достижениям", "нет адаптации под локальный рынок"],
    "inconsistencies": ["Данных недостаточно для проверки несостыковок"],
    "clarifying_questions": ["Какие были точные периоды работы по каждой роли?"],
    "career_level": "middle",
    "what_is_good": [
        "Есть релевантный профессиональный опыт",
        "Понятный вектор компетенций",
    ],
    "what_is_missing": [
        "цифры и метрики достижений",
        "английская версия CV",
        "ссылка на LinkedIn",
        "ключевые навыки под целевые вакансии",
    ],
}

REPORT_PIPELINE_VERSION = "career-report-clean-v2"

# Safe empty fallback — contains NO user-specific content, NO admin roles, NO migration profile.
# Used only when the LLM call fails completely. All substantive content comes from LLM output.
FINAL_REPORT_FALLBACK: dict[str, Any] = {
    "_pipeline_status": "insufficient_data",
    "_pipeline_version": REPORT_PIPELINE_VERSION,
    "digital_human": {
        "summary": "-",
        "previous_identity": "-",
        "current_state": "-",
        "main_asset": "-",
        "main_risk": "-",
        "main_barrier": "-",
        "main_fear": "-",
        "hidden_strengths": [],
        "psychological_profile": {
            "dominant_barriers": [],
            "dominant_fears": [],
            "coping_style": "-",
            "support_needed": "-",
        },
        "fastest_path_to_income": "-",
        "long_term_path": "-",
        "skills": {"professional": [], "transferable": [], "hidden": []},
        "barriers": {"external": [], "internal": [], "critical": []},
        "motivation": {"money": 0, "stability": 0, "freedom": 0, "meaning": 0, "status": 0, "entrepreneurship": 0},
        "career_readiness": {
            "urgency": "не определена",
            "learning_capacity": "не определена",
            "risk_tolerance": "не определена",
            "language_readiness": "не определена",
            "mobility": "не определена",
        },
        "strategy_mode": "Growth",  # Never default to Survival without explicit evidence
    },
    "experience_layers": [],
    "what_not_reset": [],
    "market_analysis": [],
    "career_translation": [],
    "career_bridges": [],
    "career_recommendations": [],
    "real_solutions": [],
    "career_decision": {
        "recommended_main_path": "-",
        "why_this_path": "-",
        "why_not_other_paths": [],
        "backup_path": "-",
        "avoid_for_now": "-",
        "decision_summary": "-",
    },
    "route_evidence_blocks": [],
    "development_map": {"current_state": "-", "goal": "-", "gap": [], "route": [], "first_month": []},
    "action_plan": {
        "today": {"action": "-", "timebox": "-", "result": "-"},
        "this_week": [],
        "this_month": [],
    },
    "weekly_plan": [],
    "career_barriers": [],
    "barrier_landscape": {"external": [], "internal": [], "behavioral_risk": "-", "first_counter_action": "-"},
    "social_integration": {"environment": [], "people": [], "communities": [], "opportunities": [], "contribution": []},
    "resource_level": "medium",
    "integration_level": "medium",
    "energy_sources": [],
    "career_priorities": [],
    "competency_signals": [],
    "decision_layers": {"career_profile": [], "constraints": [], "psychological_state": [], "action_capacity": []},
    "facts_only": {
        "explicit_facts": [],
        "resume_facts": [],
        "inferences": [],
        "unknowns": [],
        "contradictions": [],
        "career_profile": {"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []},
        "constraints": {"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []},
        "psychological_state": {"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []},
        "action_capacity": {"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []},
        "integration": {"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []},
        "route_preferences": {"from_story": [], "from_answers": [], "from_resume": [], "inferred": [], "unknown": []},
    },
    "closing_message": "-",
}

MANDATORY_QUESTIONS_RU = [
    {
        "block": "financial_pressure",
        "question": "Какой минимальный доход нужен в месяц?",
        "type": "short_text",
        "options": [],
    },
    {
        "block": "financial_pressure",
        "question": "Как быстро нужен доход?",
        "type": "single_choice",
        "options": ["⚡ 2–4 недели", "📆 1–3 месяца", "📚 3–6 месяцев", "🧭 Могу менять траекторию год"],
    },
    {
        "block": "interests_motivation",
        "question": "Сколько часов в неделю есть на поиск работы или обучение?",
        "type": "short_text",
        "options": [],
    },
    {
        "block": "professional_experience",
        "question": "Какой формат работы вам ближе?",
        "type": "single_choice",
        "options": [
            "📄 Больше с документами",
            "👥 Больше с людьми",
            "⚖️ 50/50",
            "🚫 Лучше без активных продаж",
            "✅ Могу общаться, если есть понятные правила",
        ],
    },
    {
        "block": "interests_motivation",
        "question": "Чего вы точно не хотите делать?",
        "type": "short_text",
        "options": [],
    },
    {
        "block": "language_local_context",
        "question": "Какие языки вы знаете и примерно на каком уровне?",
        "type": "short_text",
        "options": [],
    },
    {
        "block": "social_integration",
        "question": "Есть ли у вас поддержка сейчас?",
        "type": "single_choice",
        "options": [
            "👨‍👩‍👧 Есть семья/партнёр",
            "👥 Есть друзья",
            "💼 Есть профессиональные контакты",
            "🌫 Почти нет поддержки",
            "🧭 Нужна помощь с адаптацией",
        ],
    },
    {
        "block": "professional_experience",
        "question": "Какие направления вы уже рассматриваете или точно не хотите?",
        "type": "short_text",
        "options": [],
    },
]

FINAL_REPORT_FALLBACK_BE = copy.deepcopy(FINAL_REPORT_FALLBACK)

EXECUTION_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "result_summary": {"type": "string"},
        "confirmed_facts": {"type": "array", "items": {"type": "string"}},
        "hypothesis_update": {"type": "string"},
        "route_changed": {"type": "boolean"},
        "next_step": {"type": "string"},
        "next_step_result": {"type": "string"},
        "human_escalation_recommended": {"type": "boolean"},
        "human_escalation_reason": {"type": "string"},
        "response": {"type": "string"},
    },
    "required": ["result_summary", "confirmed_facts", "hypothesis_update", "route_changed", "next_step", "next_step_result", "human_escalation_recommended", "human_escalation_reason", "response"],
    "additionalProperties": False,
}

EXECUTION_RESULT_FALLBACK = {
    "result_summary": "Результат шага сохранён, но автоматический разбор сейчас недоступен.",
    "confirmed_facts": [],
    "hypothesis_update": "Маршрут пока не меняется.",
    "route_changed": False,
    "next_step": "Отметьте 3 требования, которые повторяются чаще всего.",
    "next_step_result": "Список из 3 повторяющихся требований.",
    "human_escalation_recommended": False,
    "human_escalation_reason": "",
    "response": "Я сохранил результат. Маршрут пока не меняем: следующим шагом выделите три наиболее частых требования.",
}


class CareerOpenAIClient:
    def __init__(self, api_key: str, model: str, transcribe_model: str) -> None:
        self.model = model
        self.transcribe_model = transcribe_model
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1) if api_key else None

    def _ensure_client(self) -> OpenAI:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return self.client

    def _chat(self, user_prompt: str, schema: dict[str, Any], language: str = "ru") -> str:
        language = "be" if (language or "ru") == "be" else "ru"
        client = self._ensure_client()
        response = client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "career_gps_response",
                    "strict": True,
                    "schema": schema,
                },
            },
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT.format(
                        language=language,
                        lang_instruction=self._lang_instruction(language),
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        if isinstance(content, str):
            return content
        return ""

    async def _run_json(
        self,
        prompt: str,
        fallback: dict[str, Any],
        schema: dict[str, Any],
        language: str = "ru",
    ) -> dict[str, Any]:
        try:
            raw_text = await asyncio.wait_for(
                asyncio.to_thread(self._chat, prompt, schema, language),
                timeout=55.0,
            )
            return json.loads(raw_text)
        except asyncio.TimeoutError:
            print("[openai] request timed out; using fallback response", flush=True)
            return copy.deepcopy(fallback)
        except Exception:
            return copy.deepcopy(fallback)

    def _lang_instruction(self, language: str) -> str:
        if (language or "ru") == "be":
            return (
                "language=be. "
                "Адказвай выключна па-беларуску ва ўсіх тэкставых палях JSON. "
                "Не выкарыстоўвай рускія словы і фразы (акрамя імёнаў філосафаў)."
            )
        return (
            "language=ru. "
            "Отвечай строго по-русски во всех текстовых полях JSON. "
            "Не используй белорусские фразы (кроме имён философов)."
        )

    def _normalize_question_count(self, questions: Any, language: str) -> list[dict[str, Any]]:
        fallback = STORY_ANALYSIS_FALLBACK["follow_up_questions"]
        mandatory = MANDATORY_QUESTIONS_RU

        cleaned: list[dict[str, Any]] = []
        if isinstance(questions, list):
            for item in questions:
                if not isinstance(item, dict):
                    continue
                question_text = " ".join(str(item.get("question", "")).split())
                # Some model responses append dangling 'Варианты:' into question text.
                # Strip that suffix so the UI doesn't show an empty options section.
                question_text = re.sub(r"\s*(Варианты|варианты)\s*:\s*$", "", question_text).strip()
                if not question_text:
                    continue
                q_type = str(item.get("type", "short_text")).strip() or "short_text"
                if q_type not in {"short_text", "single_choice", "multi_choice"}:
                    q_type = "short_text"
                entry = {
                    "id": int(item.get("id", len(cleaned) + 1)),
                    "block": str(item.get("block", "professional_experience")).strip() or "professional_experience",
                    "question": question_text,
                    "type": q_type,
                    "options": [
                        option
                        for option in [str(opt).strip() for opt in (item.get("options", []) if isinstance(item.get("options", []), list) else [])]
                        if option
                        and "ответьте" not in option.lower()
                        and "можно" not in option.lower()
                        and "сообщением" not in option.lower()
                    ],
                }
                if all(existing["question"] != entry["question"] for existing in cleaned):
                    cleaned.append(entry)

        if not cleaned:
            cleaned = [dict(item) for item in fallback]

        for required in mandatory:
            if all(existing.get("question") != required["question"] for existing in cleaned):
                cleaned.append(dict(required))

        if len(cleaned) < 8:
            for item in fallback:
                if all(existing.get("question") != item["question"] for existing in cleaned):
                    cleaned.append(dict(item))
                if len(cleaned) >= 8:
                    break

        if len(cleaned) < 12:
            extra = [
                {
                    "id": len(cleaned) + 1,
                    "block": "social_integration",
                    "question": "Есть ли у вас круг поддержки в новой стране?",
                    "type": "single_choice",
                    "options": ["да, есть", "частично", "почти нет", "совсем нет"],
                },
                {
                    "id": len(cleaned) + 2,
                    "block": "interests_motivation",
                    "question": "Что сейчас важнее всего?",
                    "type": "single_choice",
                    "options": [
                        "Быстро найти работу",
                        "Вернуть прежний доход",
                        "Сменить сферу",
                        "Найти смысл",
                        "Встроиться в новую страну",
                        "Открыть своё дело",
                    ],
                },
                {
                    "id": len(cleaned) + 3,
                    "block": "professional_experience",
                    "question": "Готовы ли вы начать с позиции ниже прежней?",
                    "type": "single_choice",
                    "options": ["Да", "Да, но временно", "Не уверен", "Нет"],
                },
                {
                    "id": len(cleaned) + 4,
                    "block": "professional_experience",
                    "question": "Что вам ближе по типу задач?",
                    "type": "single_choice",
                    "options": ["люди", "процессы", "бизнес", "технологии", "обучение", "помощь другим", "творчество", "управление"],
                },
            ]
            for item in extra:
                if all(existing.get("question") != item["question"] for existing in cleaned):
                    cleaned.append(item)
                if len(cleaned) >= 12:
                    break

        trimmed = cleaned[:12]
        for idx, item in enumerate(trimmed, start=1):
            item["id"] = idx
        return trimmed

    async def analyze_story(self, user_text: str, language: str = "ru") -> dict[str, Any]:
        language = "be" if language == "be" else "ru"
        prompt = STORY_ANALYSIS_PROMPT.format(
            user_text=user_text,
            language=language,
        )
        fallback = STORY_ANALYSIS_FALLBACK_BE if language == "be" else STORY_ANALYSIS_FALLBACK
        data = await self._run_json(prompt, fallback, STORY_ANALYSIS_SCHEMA, language)
        data["follow_up_questions"] = self._normalize_question_count(data.get("follow_up_questions"), language)
        return data

    async def analyze_resume(self, resume_text: str, language: str = "ru") -> dict[str, Any]:
        language = "be" if language == "be" else "ru"
        prompt = RESUME_ANALYSIS_PROMPT.format(
            resume_text=resume_text,
            language=language,
        )
        return await self._run_json(prompt, RESUME_ANALYSIS_FALLBACK, RESUME_ANALYSIS_SCHEMA, language)

    async def analyze_execution_result(
        self,
        *,
        selected_route: str,
        constraints: list[str],
        current_step: dict[str, Any],
        user_result: str,
        previous_results: list[dict[str, Any]],
        language: str = "ru",
    ) -> dict[str, Any]:
        """Review a completed step without restarting career diagnosis."""
        prompt = f"""
Ты сопровождаешь выполнение уже выбранного карьерного маршрута.
Маршрут: {selected_route}
Ограничения: {json.dumps(constraints, ensure_ascii=False)}
Текущий шаг: {json.dumps(current_step, ensure_ascii=False)}
Предыдущие результаты: {json.dumps(previous_results[-5:], ensure_ascii=False)}
Результат пользователя: {user_result}

Разбери только присланный результат. Не начинай диагностику заново и не скрывай
полезный вывод за консультацией. Отдели новые подтверждённые факты от гипотез.
Маршрут можно изменить только при новом факте, который ему противоречит; иначе
route_changed=false. Дай один следующий измеримый шаг. Рекомендуй человека мягко
только при высоком финансовом риске, противоречивых данных, нескольких близких
стратегиях, длительном отсутствии результата, интервью или переговорах.
Верни короткий самостоятельный ответ и JSON по заданной схеме.
""".strip()
        return await self._run_json(prompt, EXECUTION_RESULT_FALLBACK, EXECUTION_RESULT_SCHEMA, language)

    async def build_career_assessment(
        self,
        profile_snapshot: dict[str, Any],
        *,
        assessment_id: str,
        session_id: str,
        profile_version: str,
        story_analysis: dict[str, Any] | None = None,
        resume_analysis: dict[str, Any] | None = None,
        language: str = "ru",
    ) -> CareerAssessment:
        """Build the one canonical assessment consumed by every output renderer."""
        language = "be" if language == "be" else "ru"
        assert_expected_profiles_not_loaded(settings.environment, profile_snapshot)
        fixed_identity = {
            "assessment_id": assessment_id,
            "session_id": session_id,
            "profile_version": profile_version,
        }
        # The generator receives one evidence source. Derived country/currency values
        # are transport guards only and may not compete with canonical facts.
        model_profile = {
            "canonical_profile": copy.deepcopy(profile_snapshot.get("canonical_profile") or {}),
            "transport_guards": {
                "country_code": profile_snapshot.get("country_code"),
                "currency": profile_snapshot.get("currency"),
            },
            "market_research": {
                "date": profile_snapshot.get("market_data_date"),
                "sources": copy.deepcopy(profile_snapshot.get("market_data_sources") or []),
                "confidence": profile_snapshot.get("market_data_confidence") or "low",
            },
        }
        prompt = """Собери единый CareerAssessment только по canonical_profile из входного ProfileSnapshot.

Это единственный аналитический вызов. Он должен определить профессиональное ядро, вторичные функции,
текущий и переходный seniority, доказательства, выбор пользователя, ограничения, маршруты, вопросы,
обязательные выводы и 3-5 разных первых шагов.

Правила:
- используй только canonical_profile.facts текущего assessment; запрещено повторно извлекать факты отдельно из story_analysis/resume_analysis;
- сначала создай 8-12 разных карьерных моделей (экспертная, координация, обучение, смежная роль, производитель, B2B, консалтинг, самостоятельная и гибридная модели), затем выбери основной и 2-4 альтернативных маршрута;
- новая профессия с переобучением допустима только при явном желании пользователя;
- route.title обязан быть реальным рыночным названием роли: условия труда, количество выездов, симптомы, ограничения, нежелательные задачи и отдельные действия запрещены;
- основной маршрут не должен сохранять главные нежелательные задачи; текущая работа допустима только как временная финансовая опора с явным объяснением;
- формируй самостоятельное заключение из фактов пользователя, не пытайся воспроизводить готовый образец;
- сначала выдели функции, переносимые навыки и отраслевой опыт, затем создай широкий список ролей и отфильтруй его по рынку; не выбирай из фиксированного списка и не копируй профессии из примеров;
- context.residence_country и context.target_countries не смешивай; preferred_currency определяй по целевому рынку (Литва=EUR, Польша=PLN);
- если страна известна, анализируй именно её рынок; каждое рыночное утверждение указывает страну, дату, источник и уверенность;
- если актуального источника нет, не придумывай цифры: назови отсутствующие данные и конкретный способ проверки;
- прогноз дохода не смешивает gross/net, месяц/год, зарплату/выручку и разные рынки;
- market_analysis заполни отдельно для каждого выбранного route_id: спрос, реальные названия, работодатели/клиенты, задачи, требования, язык, допуски, договоры, формат, конкуренция, развитие и влияние ИИ; без источника формулируй только план проверки;
- income_forecasts заполни для каждого route_id тремя сценариями; числовой amount допустим только со страной, валютой, периодом, gross/net, датой и источником; иначе amount=null и дай конкретный verification_plan;
- scenarios содержат ровно safe, main и ambitious и различаются моделью занятости, риском, горизонтом и действиями; каждое поле сценария должно быть содержательным;
- personal_insights содержит минимум три вывода, каждый связывает минимум два evidence_id и даёт отдельное practical_consequence;
- psychology_factors добавляй только по явным психологическим/социальным фактам; миграцию, язык, деньги, лицензии и физические ограничения не психологизируй;
- для каждого маршрута выбери отдельный entry_path и сделай уникальными why_it_fits, missing, risks, market_test и disconfirming_conditions;
- для каждого маршрута отдельно заполни transferable_functions, new_functions и typical_tasks; typical_tasks описывает целевую роль, а не копирует текущие задачи;
- evidence_ids каждого маршрута должны ссылаться минимум на два факта только текущего assessment_id и смыслово объяснять именно этот переход;
- assessment_id каждого evidence дословно равен fixed_identity.assessment_id;
- cross-domain маршрут допустим только при явном мосте из минимум двух transferable_functions; иначе не включай его;
- каждый существенный route claim помести в evidence_claims с непустыми evidence_fact_ids; claim без фактов запрещён;
- психологические и социальные условия выводи только из явно сообщённых фактов, без диагнозов;
- основной маршрут обязан ссылаться минимум на два evidence_id;
- primary_routes обязательны;
- transition_routes добавляй только для доказанного карьерного моста;
- quick_income_routes добавляй только при приоритете быстрого дохода;
- emergency_routes добавляй только при подтверждённой срочности;
- не создавай пустые маршруты и название «Возможный маршрут»;
- не предлагай административную работу, документооборот, психологию, бизнес или обнуление опыта без прямых доказательств и выбора пользователя;
- не добавляй SWOT или неподтверждённый миграционный вывод;
- прямой отказ пользователя от функции или профессии имеет приоритет над похожестью прошлого опыта;
- переносимый профессиональный капитал не обязывает продолжать прежнюю профессию;
- оценивай текущий seniority и уровень входа в новую функцию отдельно; не переноси и не обнуляй уровень автоматически;
- перерыв, миграция, новый стек, язык или отсутствие локального допуска сами по себе не уничтожают профессиональный уровень;
- для регулируемой деятельности разделяй квалификацию и законное право практиковать;
- титулы owner, lead и manager проверяй по функциям, масштабу и ответственности, а не по названию;
- недовольство условиями, people management, on-call или выгорание не считай автоматическим отказом от профессии;
- практическую квалифицированную профессию не направляй в офис как универсальный карьерный рост;
- при разрозненном опыте допустимо честно указать отсутствие устойчивого экспертного ядра;
- не присваивай регулируемую профессию, клиническую компетентность или инженерный статус без подтверждения;
- вопросы должны включать только неизвестные, способные изменить решение;
- first_steps должны иметь 3-5 разных type, быть конкретными и не требовать увольнения;
- learning допустим только для конкретного доказанного пробела;
- country_code и валюты дословно перенеси из ProfileSnapshot;
- значения assessment_id, session_id и profile_version дословно перенеси из fixed_identity;
- selected_first_step_id верни null.

ВХОД:
""" + json.dumps(
            {
                "fixed_identity": fixed_identity,
                "profile_snapshot": model_profile,
            },
            ensure_ascii=False,
        )
        payload = await self._run_json(prompt, {}, CAREER_ASSESSMENT_SCHEMA, language)
        assessment = career_assessment_from_dict(payload)
        validation = validate_career_assessment(
            assessment,
            snapshot_country_code=str(profile_snapshot.get("country_code") or "") or None,
            snapshot_currency=str(profile_snapshot.get("currency") or "") or None,
        )
        identity_matches = (
            assessment.assessment_id == assessment_id
            and assessment.session_id == session_id
            and assessment.profile_version == profile_version
        )
        diagnostics: dict[str, Any] = {
            "assessment_id": assessment_id,
            "profile_version": profile_version,
            "raw_model_output": copy.deepcopy(payload),
            "parsed_before_repair": assessment.to_dict(),
            "validation_before_repair": validation.to_dict(),
            "generation_stopped_at": validation.errors[0].field_path if validation.errors else None,
            "repair_started": False,
            "repair_attempts": [],
        }
        if validation.valid and identity_matches:
            assessment.metadata.update(diagnostics)
            assessment.metadata["recovered_by"] = "initial_generation"
            return assessment

        if not identity_matches:
            diagnostics["identity_error"] = {
                "expected": fixed_identity,
                "actual": {
                    "assessment_id": assessment.assessment_id,
                    "session_id": assessment.session_id,
                    "profile_version": assessment.profile_version,
                },
            }
        diagnostics["repair_started"] = True
        current_assessment = assessment
        current_validation = validation
        for attempt in range(1, 2):
            repair_prompt = """Исправь CareerAssessment по точным ошибкам валидации.

Правила repair:
- используй только canonical_profile.facts из ProfileSnapshot;
- не добавляй новые факты и не меняй подтверждённые факты;
- исправь только поля, перечисленные в validation_errors;
- сохрани assessment_id, session_id и profile_version из fixed_identity дословно;
- professional_core содержит только краткие названия ролей или функций;
- каждый route.title называет конкретную роль;
- market_research step обязан ссылаться на related_route_id и дословно использовать title этого route;
- верни полный CareerAssessment, selected_first_step_id=null.

ДАННЫЕ:
""" + json.dumps(
                {
                    "fixed_identity": fixed_identity,
                    "original_assessment": payload,
                    "assessment_to_repair": current_assessment.to_dict(),
                    "validation_errors": [issue.to_dict() for issue in current_validation.errors],
                    "profile_snapshot": model_profile,
                },
                ensure_ascii=False,
            )
            repaired_payload = await self._run_json(repair_prompt, {}, CAREER_ASSESSMENT_SCHEMA, language)
            repaired = career_assessment_from_dict(repaired_payload)
            repaired_validation = validate_career_assessment(
                repaired,
                snapshot_country_code=str(profile_snapshot.get("country_code") or "") or None,
                snapshot_currency=str(profile_snapshot.get("currency") or "") or None,
            )
            repaired_identity_matches = (
                repaired.assessment_id == assessment_id
                and repaired.session_id == session_id
                and repaired.profile_version == profile_version
            )
            diagnostics["repair_attempts"].append(
                {
                    "attempt": attempt,
                    "raw_output": copy.deepcopy(repaired_payload),
                    "parsed_assessment": repaired.to_dict(),
                    "validation": repaired_validation.to_dict(),
                    "identity_matches": repaired_identity_matches,
                }
            )
            if repaired_validation.valid and repaired_identity_matches:
                repaired.metadata.update(diagnostics)
                repaired.metadata["recovered_by"] = "repair"
                repaired.metadata["successful_repair_attempt"] = attempt
                return repaired
            current_assessment = repaired
            current_validation = repaired_validation

        fallback = build_deterministic_assessment(
            profile_snapshot,
            story_analysis or {},
            resume_analysis or {},
            assessment_id=assessment_id,
            session_id=session_id,
            profile_version=profile_version,
        )
        # Invalid model bodies may themselves contain facts from another
        # assessment. Never persist them inside fallback diagnostics.
        fallback.metadata.update({
            "assessment_id": assessment_id,
            "profile_version": profile_version,
            "repair_attempt_count": len(diagnostics.get("repair_attempts") or []),
        })
        fallback.metadata.update(
            {
                "recovered_by": "deterministic_fallback",
                "fallback_reason": "One repair attempt did not produce a valid CareerAssessment",
                "fallback_validation": validate_career_assessment(
                    fallback,
                    snapshot_country_code=str(profile_snapshot.get("country_code") or "") or None,
                    snapshot_currency=str(profile_snapshot.get("currency") or "") or None,
                ).to_dict(),
            }
        )
        return fallback

    async def build_report(
        self,
        story: str,
        story_analysis: dict[str, Any],
        answers: str,
        decision_layers: dict[str, Any] | None = None,
        resume_analysis: dict[str, Any] | None = None,
        selected_barriers: list[str] | None = None,
        selected_fears: list[str] | None = None,
        selected_psych_markers: list[str] | None = None,
        selected_energy_sources: list[str] | None = None,
        selected_career_priorities: list[str] | None = None,
        user_segment: str = "",
        user_segment_label: str = "",
        language: str = "ru",
    ) -> dict[str, Any]:
        language = "be" if language == "be" else "ru"
        facts_only = self._build_facts_only(story, story_analysis, answers, decision_layers, resume_analysis)
        prompt = FINAL_REPORT_PROMPT.format(
            story=story,
            analysis_json=json.dumps(story_analysis or {}, ensure_ascii=False),
            resume_analysis_json=json.dumps(resume_analysis or {}, ensure_ascii=False),
            decision_layers_json=json.dumps(self._normalize_decision_layers(decision_layers), ensure_ascii=False),
            selected_barriers=json.dumps(selected_barriers or [], ensure_ascii=False),
            selected_fears=json.dumps(selected_fears or [], ensure_ascii=False),
            selected_psych_markers=json.dumps(selected_psych_markers or [], ensure_ascii=False),
            selected_energy_sources=json.dumps(selected_energy_sources or [], ensure_ascii=False),
            selected_career_priorities=json.dumps(selected_career_priorities or [], ensure_ascii=False),
            user_segment=str(user_segment or "").strip(),
            user_segment_label=str(user_segment_label or "").strip(),
            facts_only_json=json.dumps(facts_only, ensure_ascii=False),
            answers=answers,
            language=language,
        )
        fallback = FINAL_REPORT_FALLBACK_BE if language == "be" else FINAL_REPORT_FALLBACK
        report = await self._run_json(prompt, fallback, FINAL_REPORT_SCHEMA, language)
        return self._align_report_with_story(
            report,
            story_analysis,
            answers,
            story,
            facts_only,
            decision_layers,
            user_segment=user_segment,
            user_segment_label=user_segment_label,
        )

    def _align_report_with_story(
        self,
        report: dict[str, Any],
        story_analysis: dict[str, Any],
        answers_text: str = "",
        story_text: str = "",
        facts_only: dict[str, Any] | None = None,
        decision_layers: dict[str, Any] | None = None,
        user_segment: str = "",
        user_segment_label: str = "",
    ) -> dict[str, Any]:
        if not isinstance(report, dict):
            return copy.deepcopy(FINAL_REPORT_FALLBACK)

        normalized_facts = self._normalize_facts_only(
            report.get("facts_only"),
            base=(
                self._build_facts_only(story_text, story_analysis, answers_text, decision_layers, None)
                if facts_only is None
                else facts_only
            ),
        )
        report["facts_only"] = normalized_facts

        digital_human = report.get("digital_human")
        if isinstance(digital_human, dict):
            current_identity = str(story_analysis.get("current_identity", "")).strip()
            if current_identity:
                digital_human["current_state"] = current_identity

            snapshot = story_analysis.get("experience_snapshot", [])
            if isinstance(snapshot, list) and snapshot:
                first = str(snapshot[0]).strip()
                if first and not str(digital_human.get("previous_identity", "")).strip():
                    digital_human["previous_identity"] = first

        preferred_titles = self._preferred_polish_roles(story_analysis, user_segment)
        if preferred_titles:
            self._normalize_admin_backoffice_roles(report, preferred_titles)

        profile_domain = self._detect_profile_domain(story_analysis, answers_text, story_text)
        if profile_domain:
            report["profile_domain"] = profile_domain

        self._deduplicate_directions(report)
        self._enrich_layers_and_non_reset(report, story_analysis, answers_text)
        self._inject_signal_roles(report, story_analysis, answers_text)
        self._ensure_strategy_mode(report)
        self._ensure_social_integration(report)
        self._ensure_resource_level(report, answers_text)
        self._ensure_integration_level(report, answers_text)
        self._ensure_competency_signals(report, story_analysis, answers_text)
        self._normalize_market_geography(report, story_text, story_analysis, answers_text)
        self._ensure_career_first_today_action(report)
        self._ensure_barrier_driven_today_action(report, answers_text)
        self._enforce_segment_routes(report, user_segment, user_segment_label)
        normalized_layers = self._normalize_decision_layers(decision_layers)
        self._enforce_route_change_guardrails(report, story_analysis, answers_text, normalized_layers)
        self._enforce_domain_specific_routes(report, profile_domain)
        self._sanitize_unconfirmed_claims(report, normalized_facts)

        return report

    def _normalize_decision_layers(self, payload: Any) -> dict[str, list[str]]:
        source = payload if isinstance(payload, dict) else {}
        normalized: dict[str, list[str]] = {}
        for key in ("career_profile", "constraints", "psychological_state", "action_capacity"):
            values = source.get(key, []) if isinstance(source.get(key), list) else []
            bucket: list[str] = []
            for item in values:
                text = str(item or "").strip()
                if text and text not in bucket:
                    bucket.append(text)
            normalized[key] = bucket
        return normalized

    def _contains_emotional_overload(self, layers: dict[str, list[str]], answers_text: str) -> bool:
        blob = " ".join([*(layers.get("psychological_state", []) or []), str(answers_text or "")]).lower().replace("ё", "е")
        markers = [
            "не знаю, с чего начать",
            "не знаю с чего начать",
            "слишком сложно",
            "тревог",
            "устал",
            "сомне",
            "страх отказ",
            "перегруз",
            "хаос",
            "signal: overwhelm",
        ]
        return any(marker in blob for marker in markers)

    def _has_route_change_driver(self, layers: dict[str, list[str]], answers_text: str) -> bool:
        blob = " ".join([
            *(layers.get("career_profile", []) or []),
            *(layers.get("constraints", []) or []),
            str(answers_text or ""),
        ]).lower().replace("ё", "е")
        drivers = [
            "опыт",
            "язык",
            "документ",
            "право работать",
            "доход",
            "доступное время",
            "финансов",
            "рынок",
            "риск",
            "реальная цель",
            "сменить профес",
            "поменял",
            "изменил",
        ]
        return any(marker in blob for marker in drivers)

    def _enforce_route_change_guardrails(
        self,
        report: dict[str, Any],
        story_analysis: dict[str, Any],
        answers_text: str,
        decision_layers: dict[str, list[str]],
    ) -> None:
        report["decision_layers"] = decision_layers
        profile_domain = self._detect_profile_domain(story_analysis, answers_text)
        facts_only_payload = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
        contradictions = facts_only_payload.get("contradictions", []) if isinstance(facts_only_payload, dict) else []
        has_contradictions = isinstance(contradictions, list) and any(str(item).strip() for item in contradictions)
        overload = self._contains_emotional_overload(decision_layers, answers_text)
        has_driver = self._has_route_change_driver(decision_layers, answers_text)

        if overload:
            action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
            today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}
            # Derive example from the user's own skills/experience, never use generic construction examples
            example_roles: str
            if profile_domain == CONSTRUCTION_ESTIMATION_DOMAIN:
                example_roles = "сметы, проверка проектной документации, расчёт объёмов работ"
            else:
                user_skills = [str(s).strip() for s in story_analysis.get("skills", []) if str(s).strip()]
                user_exp = [str(e).strip() for e in story_analysis.get("experience_snapshot", []) if str(e).strip()]
                candidates = (user_skills + user_exp)[:3]
                example_roles = ", ".join(candidates) if candidates else "конкретные задачи из вашего опыта"
            today["action"] = (
                "Напишите в заметках три вида работ, которые вы реально умеете делать лучше всего "
                f"(например: {example_roles})."
            )
            today["timebox"] = "10 минут"
            today["result"] = "Есть список из 3 конкретных типов работ без смены текущего маршрута."
            action_plan["today"] = today
            report["action_plan"] = action_plan

            # Overwhelm affects STEP SIZE only — never mode or route
            digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
            if digital_human:
                # Do NOT set Survival: emotional state does not justify Survival mode
                pass

            decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
            if decision:
                summary = str(decision.get("decision_summary", "")).strip()
                lock_note = "Эмоциональное состояние влияет на темп и размер шага, но не меняет профессиональный маршрут."
                if lock_note not in summary:
                    decision["decision_summary"] = f"{lock_note} {summary}".strip()

            full_blob = " ".join(
                [
                    str(story_analysis.get("current_identity", "")),
                    " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
                    " ".join(decision_layers.get("career_profile", [])),
                ]
            ).lower().replace("ё", "е")
            has_private_orders_anchor = any(token in full_blob for token in ["частн", "плитк", "гипсокарт", "мебел", "ремонт"])
            if has_private_orders_anchor and decision:
                current_main = str(decision.get("recommended_main_path", "")).lower()
                if "частн" not in current_main and "самозан" not in current_main:
                    decision["recommended_main_path"] = "Частные заказы в текущем профиле / Смежные роли по вашему опыту"
                    backup = str(decision.get("backup_path", "")).strip()
                    if not backup:
                        decision["backup_path"] = "Локальный найм по текущему профилю как стабилизирующий трек"

            if overload and (not has_driver or has_contradictions):
                # No admin role injection here — done in _align_report_with_story with segment guard
                pass

    def _build_facts_only(
        self,
        story_text: str,
        story_analysis: dict[str, Any],
        answers_text: str,
        decision_layers: dict[str, Any] | None = None,
        resume_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        explicit_facts: list[str] = []
        resume_facts: list[str] = []

        def _append_unique(target: list[str], value: str) -> None:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in target:
                target.append(cleaned)

        def _make_layer() -> dict[str, list[str]]:
            return {
                "from_story": [],
                "from_answers": [],
                "from_resume": [],
                "inferred": [],
                "unknown": [],
            }

        source_layers: dict[str, dict[str, list[str]]] = {
            "career_profile": _make_layer(),
            "constraints": _make_layer(),
            "psychological_state": _make_layer(),
            "action_capacity": _make_layer(),
            "integration": _make_layer(),
            "route_preferences": _make_layer(),
        }

        def _append_layer(layer: str, bucket: str, value: str) -> None:
            cleaned = str(value or "").strip()
            if not cleaned:
                return
            target = source_layers.get(layer, {}).get(bucket)
            if isinstance(target, list) and cleaned not in target:
                target.append(cleaned)

        for value in [story_analysis.get("current_identity"), story_analysis.get("story_summary")]:
            _append_unique(explicit_facts, value)
            _append_layer("career_profile", "from_story", str(value or ""))

        for key in ("experience_snapshot", "skills", "constraints", "goals"):
            items = story_analysis.get(key)
            if isinstance(items, list):
                for item in items:
                    _append_unique(explicit_facts, item)
                    if key in {"experience_snapshot", "skills"}:
                        _append_layer("career_profile", "from_story", str(item))
                    elif key == "constraints":
                        _append_layer("constraints", "from_story", str(item))
                    elif key == "goals":
                        _append_layer("route_preferences", "from_story", str(item))

        for raw_line in str(answers_text or "").splitlines():
            line = raw_line.strip().strip("-•")
            if len(line) >= 3:
                _append_unique(explicit_facts, f"Ответ пользователя: {line}")
                lowered = line.lower()
                if any(token in lowered for token in ["срок", "документ", "деньг", "доход", "огранич"]):
                    _append_layer("constraints", "from_answers", line)
                if any(token in lowered for token in ["устал", "трев", "ресурс", "выгор", "сил"]):
                    _append_layer("psychological_state", "from_answers", line)
                if any(token in lowered for token in ["время", "час", "действ", "делать", "каждый день"]):
                    _append_layer("action_capacity", "from_answers", line)
                if any(token in lowered for token in ["язык", "рынок", "польша", "контакт", "сообще", "интеграц"]):
                    _append_layer("integration", "from_answers", line)
                if any(token in lowered for token in ["хочу", "предпоч", "направлен", "роль", "маршрут"]):
                    _append_layer("route_preferences", "from_answers", line)

        if isinstance(resume_analysis, dict):
            for key in ("professions", "achievements", "skills", "what_is_good"):
                items = resume_analysis.get(key)
                if isinstance(items, list):
                    for item in items:
                        text = str(item or "").strip()
                        if text:
                            _append_unique(resume_facts, text)
                            _append_layer("career_profile", "from_resume", text)
            for key in ("gaps", "what_is_missing"):
                items = resume_analysis.get(key)
                if isinstance(items, list):
                    for item in items:
                        text = str(item or "").strip()
                        if text:
                            _append_unique(resume_facts, text)
                            _append_layer("constraints", "from_resume", text)

        if isinstance(decision_layers, dict):
            mapping = {
                "career_profile": "career_profile",
                "constraints": "constraints",
                "psychological_state": "psychological_state",
                "action_capacity": "action_capacity",
            }
            for src, dst in mapping.items():
                values = decision_layers.get(src)
                if isinstance(values, list):
                    for value in values:
                        _append_layer(dst, "from_answers", str(value))

        blob = " ".join([str(story_text or ""), str(answers_text or ""), " ".join(explicit_facts)]).lower()

        inferences: list[str] = []
        if any(token in blob for token in ["клиент", "общ", "коммуника", "договар", "переговор"]):
            inference = "Похоже, у вас есть опыт коммуникации и взаимодействия с людьми в рабочих задачах."
            inferences.append(inference)
            _append_layer("career_profile", "inferred", inference)
        if any(token in blob for token in ["задач", "срок", "организ", "координа"]):
            inference = "Похоже, у вас есть опыт самостоятельного ведения небольших задач."
            inferences.append(inference)
            _append_layer("action_capacity", "inferred", inference)
        if any(token in blob for token in ["клиент", "договор", "переговор", "заказ"]):
            inference = "Вероятно, вам может подойти маршрут с частными заказами, потому что вы уже договаривались с клиентами."
            inferences.append(inference)
            _append_layer("route_preferences", "inferred", inference)

        allowed_inference_prefixes = ("Похоже", "Вероятно", "Можно предположить")
        inferences = [item for item in inferences if item.startswith(allowed_inference_prefixes)]

        unknowns: list[str] = []
        if not any(token in blob for token in ["рынок", "ваканс", "рынка труда"]):
            unknown = "Пока недостаточно данных, чтобы это оценить. Можно уточнить это в следующих шагах."
            unknowns.append(unknown)
            _append_layer("integration", "unknown", unknown)
        if not any(token in blob for token in ["контакт", "сообще", "нетворк", "знаком"]):
            unknown = "Пока недостаточно данных, чтобы это оценить. Можно уточнить это в следующих шагах."
            unknowns.append(unknown)
            _append_layer("integration", "unknown", unknown)
        if not any(token in blob for token in ["учиться", "обуч", "переуч", "курс"]):
            unknown = "Пока недостаточно данных, чтобы это оценить. Можно уточнить это в следующих шагах."
            unknowns.append(unknown)
            _append_layer("action_capacity", "unknown", unknown)

        for layer_name, payload in source_layers.items():
            # Keep at least one unknown marker in each layer if no direct evidence exists.
            if not payload["from_story"] and not payload["from_answers"] and not payload["from_resume"]:
                _append_layer(
                    layer_name,
                    "unknown",
                    "Пока недостаточно данных, чтобы это оценить. Можно уточнить это в следующих шагах.",
                )

        contradictions: list[str] = []
        if ("2-4 недели" in blob or "2–4 недели" in blob) and ("3-6 месяцев" in blob or "3–6 месяцев" in blob or "траекторию год" in blob):
            contradictions.append(
                "Есть противоречие в сроках: одновременно указан срочный доход и длинный горизонт смены траектории."
            )

        return self._normalize_facts_only(
            {
                "explicit_facts": explicit_facts,
                "resume_facts": resume_facts,
                "inferences": inferences,
                "unknowns": unknowns,
                "contradictions": contradictions,
                "career_profile": source_layers["career_profile"],
                "constraints": source_layers["constraints"],
                "psychological_state": source_layers["psychological_state"],
                "action_capacity": source_layers["action_capacity"],
                "integration": source_layers["integration"],
                "route_preferences": source_layers["route_preferences"],
            }
        )

    def _normalize_facts_only(self, payload: Any, base: dict[str, Any] | None = None) -> dict[str, Any]:
        source = payload if isinstance(payload, dict) else {}
        seed = base if isinstance(base, dict) else {}
        normalized: dict[str, Any] = {}

        for key in ("explicit_facts", "resume_facts", "inferences", "unknowns", "contradictions"):
            merged: list[str] = []
            for candidate in [
                *(source.get(key, []) if isinstance(source.get(key), list) else []),
                *(seed.get(key, []) if isinstance(seed.get(key), list) else []),
            ]:
                text = str(candidate or "").strip()
                if text and text not in merged:
                    merged.append(text)
            normalized[key] = merged

        default_unknown = "Пока недостаточно данных, чтобы это оценить. Можно уточнить это в следующих шагах."
        allowed_inference_prefixes = ("Похоже", "Вероятно", "Можно предположить")
        normalized["inferences"] = [
            item for item in normalized["inferences"] if str(item).startswith(allowed_inference_prefixes)
        ]

        def _normalize_layer(layer_key: str) -> dict[str, list[str]]:
            layer_source = source.get(layer_key) if isinstance(source.get(layer_key), dict) else {}
            layer_seed = seed.get(layer_key) if isinstance(seed.get(layer_key), dict) else {}
            layer: dict[str, list[str]] = {}
            for bucket in ("from_story", "from_answers", "from_resume", "inferred", "unknown"):
                merged: list[str] = []
                for candidate in [
                    *(layer_source.get(bucket, []) if isinstance(layer_source.get(bucket), list) else []),
                    *(layer_seed.get(bucket, []) if isinstance(layer_seed.get(bucket), list) else []),
                ]:
                    text = str(candidate or "").strip()
                    if text and text not in merged:
                        merged.append(text)
                layer[bucket] = merged
            if not layer["unknown"] and not layer["from_story"] and not layer["from_answers"] and not layer["from_resume"]:
                layer["unknown"] = [default_unknown]
            return layer

        for layer_key in (
            "career_profile",
            "constraints",
            "psychological_state",
            "action_capacity",
            "integration",
            "route_preferences",
        ):
            normalized[layer_key] = _normalize_layer(layer_key)

        if not normalized["unknowns"]:
            normalized["unknowns"] = [default_unknown]

        return normalized

    def _ensure_resource_level(self, report: dict[str, Any], answers_text: str = "") -> None:
        digital_human = report.get("digital_human")
        if not isinstance(digital_human, dict):
            return
        current = str(report.get("resource_level", "")).strip().lower()
        if current in {"high", "medium", "low"}:
            return

        answers_low = str(answers_text or "").lower()
        # Derive from explicit resource/psycho-emotional answers
        if any(token in answers_low for token in [
            "уровень внутреннего ресурса", "внутреннего ресурса", "чувствуете", "чувствую"
        ]):
            low_signals = ["тяжело держать темп", "слишком много неопределённост", "выгора", "нет сил", "слишком много неопределен"]
            medium_signals = ["бывают просадки", "иногда тяжело", "двигаюсь, но", "просадки и сомнения"]
            high_signals = ["есть силы и устойчивост", "уверенно, есть план", "чувствую себя уверенн"]
            if any(token in answers_low for token in low_signals):
                report["resource_level"] = "low"
                return
            if any(token in answers_low for token in high_signals):
                report["resource_level"] = "high"
                return
            if any(token in answers_low for token in medium_signals):
                report["resource_level"] = "medium"
                return

        readiness = digital_human.get("career_readiness") if isinstance(digital_human.get("career_readiness"), dict) else {}
        urgency = str((readiness or {}).get("urgency", "")).lower()
        support_needed = str((readiness or {}).get("support_needed", "")).lower()

        if any(token in support_needed for token in ["high", "выс", "силь", "тяж"]):
            report["resource_level"] = "low"
            return
        if any(token in urgency for token in ["high", "выс", "urgent", "сроч"]):
            report["resource_level"] = "low"
            return
        if any(token in support_needed for token in ["medium", "сред", "умер"]):
            report["resource_level"] = "medium"
            return
        report["resource_level"] = "high"

    def _ensure_integration_level(self, report: dict[str, Any], answers_text: str = "") -> None:
        current = str(report.get("integration_level", "")).strip().lower()
        if current in {"high", "medium", "low"}:
            return

        answers_low = str(answers_text or "").lower()
        if "интеграция" in answers_low or "меньше 6 месяцев" in answers_low or "6–12 месяцев" in answers_low or "1–2 года" in answers_low or "больше 2 лет" in answers_low:
            integration_score = 0
            for token in [
                "местный язык", "профессиональные контакты", "местные знакомые", "сообщества", "рынок труда", "больше 12 месяцев",
                "больше 2 лет", "1–2 года", "понимаю, как устроен",
            ]:
                if token in answers_low:
                    integration_score += 1
            # Time-in-country boost
            if "больше 2 лет" in answers_low:
                integration_score += 2
            elif "1–2 года" in answers_low or "6–12 месяцев" in answers_low:
                integration_score += 1
            elif "меньше 6 месяцев" in answers_low:
                integration_score = max(0, integration_score - 1)
            if integration_score >= 4:
                report["integration_level"] = "high"
                return
            if integration_score >= 2:
                report["integration_level"] = "medium"
                return
            if integration_score >= 1:
                report["integration_level"] = "low"
                return

        integration = report.get("social_integration") if isinstance(report.get("social_integration"), dict) else {}
        score = 0
        for key in ("environment", "people", "communities", "opportunities", "contribution"):
            value = integration.get(key)
            if isinstance(value, list) and any(str(item).strip() for item in value):
                score += 1

        if score >= 4:
            report["integration_level"] = "high"
        elif score >= 2:
            report["integration_level"] = "medium"
        else:
            report["integration_level"] = "low"

    def _ensure_competency_signals(self, report: dict[str, Any], story_analysis: dict[str, Any], answers_text: str) -> None:
        blob = " ".join(
            [
                str(story_analysis.get("current_identity", "")),
                str(story_analysis.get("story_summary", "")),
                " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
                " ".join(str(item) for item in story_analysis.get("skills", []) if isinstance(item, str)),
                str(answers_text or ""),
            ]
        ).lower()

        patterns = [
            ("Лидерство", ["руковод", "lead", "team lead", "head of", "директор", "управлял команд"]),
            ("Управление", ["управлен", "manager", "менеджер", "координа", "координиров", "организов"]),
            ("Обучение", ["обучал", "настав", "ментор", "тренир", "передавал опыт"]),
            ("Переговоры", ["переговор", "догов", "согласов", "коммуникац", "взаимодейств"]),
            ("Коммуникация", ["коммуникац", "клиент", "общен", "контакт", "связ"]),
            ("Организация процессов", ["организа", "процесс", "workflow", "операц", "дедлайн", "срок"]),
            ("Аналитика", ["аналит", "excel", "таблиц", "данн", "отчет", "report"]),
            ("Решение проблем", ["решил", "решала", "problem", "сложн", "кризис", "исправ"]),
            ("Стратегическое мышление", ["стратег", "план", "roadmap", "развит", "долгосроч"]),
        ]

        existing = [str(item).strip() for item in report.get("competency_signals", []) if str(item).strip()] if isinstance(report.get("competency_signals"), list) else []
        extracted = [label for label, markers in patterns if any(marker in blob for marker in markers)]
        if not extracted and isinstance(existing, list) and existing:
            report["competency_signals"] = list(dict.fromkeys(existing))[:6]
            return
        merged = list(dict.fromkeys([*existing, *extracted]))
        report["competency_signals"] = merged[:6]

    def _detect_target_country(self, story_text: str, story_analysis: dict[str, Any], answers_text: str) -> str:
        blob = " ".join(
            [
                str(story_text or ""),
                str(story_analysis.get("current_identity", "")),
                " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
                str(answers_text or ""),
            ]
        ).lower().replace("ё", "е")

        lithuania_tokens = ["литв", "литва", "вильню", "каунас", "klaipeda", "lithuania", "lithuanian"]
        poland_tokens = ["польш", "польша", "варшав", "краков", "warsaw", "krakow", "poland", "polish"]

        if any(token in blob for token in lithuania_tokens):
            return "lt"
        if any(token in blob for token in poland_tokens):
            return "pl"
        return "unknown"

    def _replace_recursive_text(self, value: Any, replacements: dict[str, str]) -> Any:
        if isinstance(value, str):
            text = value
            for old, new in replacements.items():
                text = text.replace(old, new)
            return text
        if isinstance(value, list):
            return [self._replace_recursive_text(item, replacements) for item in value]
        if isinstance(value, dict):
            return {key: self._replace_recursive_text(val, replacements) for key, val in value.items()}
        return value

    def _normalize_market_geography(self, report: dict[str, Any], story_text: str, story_analysis: dict[str, Any], answers_text: str) -> None:
        country = self._detect_target_country(story_text, story_analysis, answers_text)
        if country != "lt":
            return

        replacements = {
            "PLN brutto": "EUR brutto",
            "PLN netto": "EUR netto",
            "PLN": "EUR",
            "Польши": "Литвы",
            "Польше": "Литве",
            "Польша": "Литва",
            "польский": "литовский",
            "польского": "литовского",
            "польском": "литовском",
            "Poland": "Lithuania",
            "polish": "lithuanian",
            "Polish": "Lithuanian",
        }
        normalized = self._replace_recursive_text(report, replacements)
        if isinstance(normalized, dict):
            report.clear()
            report.update(normalized)

    def _deduplicate_directions(self, report: dict[str, Any]) -> None:
        market = report.get("market_analysis")
        if isinstance(market, list):
            merged: dict[str, dict[str, Any]] = {}
            for item in market:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("profession", "")).strip().lower()
                if not key:
                    continue
                if key not in merged:
                    merged[key] = item
                    continue
                current = merged[key]
                if int(item.get("fit_percent", 0)) > int(current.get("fit_percent", 0)):
                    current.update(item)
                req = set(current.get("requirements", []) or []) | set(item.get("requirements", []) or [])
                current["requirements"] = [str(r) for r in req if str(r).strip()]
                current["profile_match_reason"] = "; ".join(
                    part for part in [str(current.get("profile_match_reason", "")).strip(), str(item.get("profile_match_reason", "")).strip()] if part
                )
            report["market_analysis"] = list(merged.values())

        recs = report.get("career_recommendations")
        if isinstance(recs, list):
            merged_rec: dict[str, dict[str, Any]] = {}
            for item in recs:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("title", "")).strip().lower()
                if not key:
                    continue
                if key not in merged_rec:
                    merged_rec[key] = item
                    continue
                current = merged_rec[key]
                if int(item.get("match_percent", 0)) > int(current.get("match_percent", 0)):
                    current.update(item)
                current["pros"] = list({*map(str, current.get("pros", []) or []), *map(str, item.get("pros", []) or [])})
                current["risks"] = list({*map(str, current.get("risks", []) or []), *map(str, item.get("risks", []) or [])})
                current["why_fit"] = "; ".join(
                    part for part in [str(current.get("why_fit", "")).strip(), str(item.get("why_fit", "")).strip()] if part
                )
            report["career_recommendations"] = list(merged_rec.values())

    def _enrich_layers_and_non_reset(self, report: dict[str, Any], story_analysis: dict[str, Any], answers_text: str) -> None:
        layers = report.get("experience_layers") if isinstance(report.get("experience_layers"), list) else []
        if not layers:
            layers = []
        blob = " ".join(
            [
                str(story_analysis.get("current_identity", "")),
                " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
                str(answers_text or ""),
            ]
        ).lower()
        has_admin = any(word in blob for word in ["докумен", "админ", "срок", "координа", "поручен"])
        sales_markers = ["продаж", "crm", "sap", "erp", "kpi", "лид", "воронк"]
        has_sales = sum(1 for word in sales_markers if word in blob) >= 2
        if has_admin:
            layers.append("Похоже, у вас есть административный слой опыта: документы, сроки и координация задач.")
        if has_sales:
            layers.append("Похоже, у вас есть коммерческий слой опыта: продажи, клиентская база и CRM-процессы.")
        if not layers:
            layers = ["Пока не хватает данных, чтобы выделить устойчивые слои опыта. Это можно уточнить позже."]
        report["experience_layers"] = list(dict.fromkeys(layers))[:3]

        not_reset = report.get("what_not_reset") if isinstance(report.get("what_not_reset"), list) else []
        base: list[str] = []
        if has_admin:
            base.extend([
                "Похоже, у вас есть опыт работы с документами и формальными процедурами.",
                "Похоже, у вас есть навык контроля сроков и поручений.",
                "Похоже, у вас есть опыт координации задач.",
            ])
        if any(word in blob for word in ["клиент", "коммуника", "общен", "переговор"]):
            base.append("Похоже, у вас есть опыт работы с клиентской коммуникацией.")
        if has_sales:
            base.extend([
                "Похоже, у вас есть опыт продаж и ведения клиентской базы.",
                "Похоже, у вас есть опыт работы с CRM/SAP/ERP как рабочим инструментом.",
            ])
        merged_not_reset = list(dict.fromkeys([*(str(item).strip() for item in not_reset if str(item).strip()), *base]))
        if not merged_not_reset:
            merged_not_reset = ["Пока не хватает данных, чтобы выделить переносимые навыки, которые точно не обнулились. Это можно уточнить позже."]
        report["what_not_reset"] = merged_not_reset[:8]

    def _sanitize_unconfirmed_claims(self, report: dict[str, Any], facts_only: dict[str, Any]) -> None:
        allowed_blob = " ".join(
            facts_only.get("explicit_facts", [])
            + facts_only.get("inferences", [])
        ).lower()

        checks = [
            (re.compile(r"документ|формальн|процедур", re.IGNORECASE), ["документ", "формаль", "процедур", "документооборот"]),
            (re.compile(r"срок|поручен|процесс|управля", re.IGNORECASE), ["срок", "поруч", "процесс", "координа"]),
            (re.compile(r"рынок", re.IGNORECASE), ["рынок", "ваканс", "рынка труда"]),
            (re.compile(r"контакт|интеграц|сообществ", re.IGNORECASE), ["контакт", "интеграц", "сообще", "знаком"]),
            (re.compile(r"переуч|обучени", re.IGNORECASE), ["переуч", "учиться", "обуч", "курс"]),
        ]

        def has_evidence(markers: list[str]) -> bool:
            return any(marker in allowed_blob for marker in markers)

        def scrub_list(items: list[str], unknown_fallback: str) -> list[str]:
            cleaned: list[str] = []
            for item in items:
                text = str(item or "").strip()
                if not text:
                    continue
                blocked = False
                for pattern, markers in checks:
                    if pattern.search(text) and not has_evidence(markers):
                        blocked = True
                        break
                if not blocked:
                    cleaned.append(text)
            return cleaned or [unknown_fallback]

        what_not_reset = report.get("what_not_reset")
        if isinstance(what_not_reset, list):
            report["what_not_reset"] = scrub_list(
                [str(item) for item in what_not_reset],
                "Пока не хватает данных, чтобы выделить переносимые навыки, которые точно не обнулились. Это можно уточнить позже.",
            )[:8]

        experience_layers = report.get("experience_layers")
        if isinstance(experience_layers, list):
            report["experience_layers"] = scrub_list(
                [str(item) for item in experience_layers],
                "Пока не хватает данных, чтобы выделить устойчивые слои опыта. Это можно уточнить позже.",
            )[:3]

        competency_signals = report.get("competency_signals")
        if isinstance(competency_signals, list):
            report["competency_signals"] = scrub_list(
                [str(item) for item in competency_signals],
                "Пока не хватает данных, чтобы выделить подтвержденные STAR-компетенции. Это можно уточнить позже.",
            )[:6]

    def _ensure_career_first_today_action(self, report: dict[str, Any]) -> None:
        action_plan = report.get("action_plan")
        if not isinstance(action_plan, dict):
            return
        today = action_plan.get("today")
        if not isinstance(today, dict):
            return
        action = str(today.get("action", "")).lower()
        if not action:
            return
        language_only = any(token in action for token in ["язык", "курс", "польск"])
        if language_only:
            today["action"] = "Собрать 10 ключевых слов из вакансий и отправить 3 первых отклика по выбранному маршруту."
            today["timebox"] = "15 минут"
            today["result"] = "Первые рыночные данные и список требований для доработки CV."

    def _today_action_profile_hint(self, report: dict[str, Any]) -> str:
        decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
        recommended = str(decision.get("recommended_main_path") or "").strip()
        if recommended:
            return recommended

        solutions = report.get("real_solutions") if isinstance(report.get("real_solutions"), list) else []
        for row in solutions:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if title:
                return title

        return "вашему текущему профилю"

    def _ensure_barrier_driven_today_action(self, report: dict[str, Any], answers_text: str = "") -> None:
        action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
        today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}
        if not today:
            today = {"action": "", "timebox": "", "result": ""}

        digital_human = report.get("digital_human") if isinstance(report.get("digital_human"), dict) else {}
        main_barrier = str(digital_human.get("main_barrier", "")).lower().replace("ё", "е")
        main_fear = str(digital_human.get("main_fear", "")).lower().replace("ё", "е")
        answers_low = str(answers_text or "").lower().replace("ё", "е")
        barrier_blob = " ".join([main_barrier, main_fear, answers_low])

        matrix: list[tuple[list[str], dict[str, str]]] = [
            (
                ["страх отказ", "боюсь отказ", "отказ"],
                {
                    "action": (
                        "Шаг на сегодня, 10 минут: напишите одному знакомому:\n"
                        f"«Привет. Ищу работу по направлению: {self._today_action_profile_hint(report)}. "
                        "Если услышишь о подходящей вакансии или задаче — буду благодарен за контакт».\n"
                        "[Скопировать текст] [Сделал] [Слишком страшно] [Сделать проще]"
                    ),
                    "timebox": "10 минут",
                    "result": "Отправлено 1 безопасное сообщение, которое запускает контакт без риска большого отказа.",
                },
            ),
            (
                ["хаос", "слишком много", "раскидан", "не могу выбрать"],
                {
                    "action": "Выберите один маршрут на ближайшие 7 дней и зафиксируйте правило: не переключаться до конца недели.",
                    "timebox": "10 минут",
                    "result": "Один маршрут зафиксирован на 7 дней без метаний.",
                },
            ),
            (
                ["нет резюме", "резюме нет", "cv нет", "без резюме"],
                {
                    "action": "Заполните 4 строки о прошлом опыте: что делали, какой результат, с какими задачами работали, что умеете лучше всего.",
                    "timebox": "10 минут",
                    "result": "Готов черновик из 4 строк для основы резюме.",
                },
            ),
            (
                ["нет языка", "язык мешает", "плохой язык", "не знаю язык"],
                {
                    "action": "Выучите 10 профессиональных слов по своей сфере и составьте 2 короткие рабочие фразы для общения с заказчиком/работодателем.",
                    "timebox": "10 минут",
                    "result": "Есть 10 слов и 2 рабочие фразы для практики.",
                },
            ),
            (
                ["нет контактов", "нет знакомых", "нет сети", "нетворк"],
                {
                    "action": "Напишите одному знакомому про ваш текущий профиль или вступите в один местный профессиональный чат по вашей сфере.",
                    "timebox": "10 минут",
                    "result": "Сделан 1 новый контактный шаг в локальной среде.",
                },
            ),
            (
                ["нет сил", "устал", "выгор", "не тяну"],
                {
                    "action": "Выберите действие на 5 минут: открыть 1 вакансию, выписать 3 требования и остановиться на этом.",
                    "timebox": "5 минут",
                    "result": "Сделан минимальный шаг без перегрузки.",
                },
            ),
            (
                ["не знаю, с чего начать", "не знаю с чего начать", "сложно начать"],
                {
                    "action": (
                        "Выберите один из 3 мини-шагов:\n"
                        "1) выписать 3 вида работ, которые умеете лучше всего;\n"
                        "2) открыть 3 вакансии и выписать повторяющиеся требования;\n"
                        "3) написать 1 знакомому о том, какую работу ищете."
                    ),
                    "timebox": "10 минут",
                    "result": "Выбран и выполнен 1 мини-шаг вместо попытки решить всю карьеру сразу.",
                },
            ),
        ]

        for markers, template in matrix:
            if any(marker in barrier_blob for marker in markers):
                today["action"] = template["action"]
                today["timebox"] = template["timebox"]
                today["result"] = template["result"]
                action_plan["today"] = today
                report["action_plan"] = action_plan
                return

    def _segment_route_pack(self, user_segment: str, user_segment_label: str) -> tuple[str, str, str, str]:
        segment = str(user_segment or "").strip().lower()
        label = str(user_segment_label or "").strip() or "Сегмент не уточнен"

        packs: dict[str, tuple[str, str, str]] = {
            "worker_production": (
                "Быстрый доход: профильная роль по текущей квалификации (смена/участок)",
                "Основной маршрут: рост до мастера смены / старшего участка",
                "Долгосрочная стратегия: руководитель участка / производственный координатор",
            ),
            "service_care": (
                "Быстрый доход: сервис/уход в роли с коротким входом",
                "Основной маршрут: старший специалист сервиса/ухода",
                "Долгосрочная стратегия: координатор ухода / управляющий сервисным блоком",
            ),
            "logistics_transport": (
                "Быстрый доход: водитель/склад/доставка по текущим допускам",
                "Основной маршрут: диспетчер / логист / старший смены склада",
                "Долгосрочная стратегия: координатор перевозок / менеджер транспортного отдела",
            ),
            "office_staff": (
                "Быстрый доход: Administrative Assistant / Back-office Specialist",
                "Основной маршрут: Office Administrator / Operations Coordinator",
                "Долгосрочная стратегия: руководитель офисных процессов / operations lead",
            ),
            "specialist_expert": (
                "Быстрый доход: смежная экспертная роль с коротким входом",
                "Основной маршрут: профильная экспертная позиция по ядру компетенций",
                "Долгосрочная стратегия: senior/expert-track и масштаб ответственности",
            ),
            "leader": (
                "Быстрый доход: роль team lead/координатора в близкой функции",
                "Основной маршрут: руководитель направления/подразделения",
                "Долгосрочная стратегия: head/director-track",
            ),
            "entrepreneur": (
                "Быстрый доход: гибридный трек найм + монетизация экспертных услуг",
                "Основной маршрут: устойчивый микро-бизнес/консалтинг в новой стране",
                "Долгосрочная стратегия: масштабирование бизнеса и партнерская модель",
            ),
        }
        quick, main, long_term = packs.get(
            segment,
            packs["specialist_expert"],
        )
        return quick, main, long_term, label

    def _enforce_segment_routes(self, report: dict[str, Any], user_segment: str, user_segment_label: str) -> None:
        quick_route, main_route, long_route, label = self._segment_route_pack(user_segment, user_segment_label)

        solutions = report.get("real_solutions") if isinstance(report.get("real_solutions"), list) else []
        if len(solutions) < 3:
            solutions = []
        normalized_solutions: list[dict[str, Any]] = []
        defaults = [
            {
                "title": quick_route,
                "recommendation_level": "быстрый доход",
                "success_probability": "средняя",
                "timeline": "2-8 недель",
                "why": "Маршрут опирается на текущие подтвержденные навыки и снижает риск долгого простоя.",
                "first_step": "Собрать 10 релевантных вакансий/заказов и отправить 3 прицельных отклика.",
            },
            {
                "title": main_route,
                "recommendation_level": "основной маршрут развития",
                "success_probability": "средняя",
                "timeline": "2-6 месяцев",
                "why": "Маршрут закрепляет сегментный профиль и дает устойчивую траекторию роста.",
                "first_step": "Определить 3 критичных требования рынка и закрыть их в течение 14 дней.",
            },
            {
                "title": long_route,
                "recommendation_level": "долгосрочная стратегия",
                "success_probability": "средняя",
                "timeline": "6-18 месяцев",
                "why": "Маршрут масштабирует доход и ответственность после стабилизации.",
                "first_step": "Сформировать план развития компетенций и сети контактов на 90 дней.",
            },
        ]

        for idx in range(3):
            if idx < len(solutions) and isinstance(solutions[idx], dict):
                row = dict(solutions[idx])
                row["title"] = defaults[idx]["title"]
                row["recommendation_level"] = defaults[idx]["recommendation_level"]
                if not str(row.get("why") or "").strip():
                    row["why"] = defaults[idx]["why"]
                if not str(row.get("first_step") or "").strip():
                    row["first_step"] = defaults[idx]["first_step"]
                if not str(row.get("timeline") or "").strip():
                    row["timeline"] = defaults[idx]["timeline"]
                if not str(row.get("success_probability") or "").strip():
                    row["success_probability"] = defaults[idx]["success_probability"]
                normalized_solutions.append(row)
            else:
                normalized_solutions.append(dict(defaults[idx]))

        report["real_solutions"] = normalized_solutions

        decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
        decision["recommended_main_path"] = str(decision.get("recommended_main_path") or main_route)
        if not str(decision.get("why_this_path") or "").strip():
            decision["why_this_path"] = "Решение закреплено по вашему сегменту, текущим ограничениям и приоритету устойчивого дохода."
        summary = str(decision.get("decision_summary") or "").strip()
        segment_note = f"Сегмент: {label}."
        if segment_note not in summary:
            decision["decision_summary"] = f"{segment_note} {summary}".strip()
        report["career_decision"] = decision

    def _ensure_strategy_mode(self, report: dict[str, Any]) -> None:
        digital_human = report.get("digital_human")
        if not isinstance(digital_human, dict):
            return
        mode = str(digital_human.get("strategy_mode", "")).strip()
        if mode in {"Survival", "Transition", "Growth"}:
            # Survival requires explicit evidence - demote if evidence missing
            if mode == "Survival":
                facts_only = report.get("facts_only") if isinstance(report.get("facts_only"), dict) else {}
                explicit_facts = " ".join(str(f) for f in (facts_only.get("explicit_facts") or [])).lower()
                survival_signals = [
                    "без дохода", "no income", "долг", "debt",
                    "срочно нужна", "urgent", "потери жилья", "housing risk",
                    "финансовый дедлайн", "financial deadline",
                ]
                if not any(s in explicit_facts for s in survival_signals):
                    digital_human["strategy_mode"] = "Transition"
            return
        readiness = digital_human.get("career_readiness") if isinstance(digital_human.get("career_readiness"), dict) else {}
        urgency = str((readiness or {}).get("urgency", "")).lower()
        if "сред" in urgency or "moder" in urgency or "medium" in urgency:
            digital_human["strategy_mode"] = "Transition"
        else:
            digital_human["strategy_mode"] = "Growth"

    def _ensure_social_integration(self, report: dict[str, Any]) -> None:
        integration = report.get("social_integration")
        if not isinstance(integration, dict):
            integration = {}
        for key in ("environment", "people", "communities", "opportunities", "contribution"):
            current = integration.get(key)
            if not isinstance(current, list):
                integration[key] = []
        report["social_integration"] = integration

    def _detect_profile_domain(
        self,
        story_analysis: dict[str, Any],
        answers_text: str = "",
        story_text: str = "",
    ) -> str:
        chunks = [
            str(story_analysis.get("current_identity", "")),
            str(story_analysis.get("story_summary", "")),
            " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
            " ".join(str(item) for item in story_analysis.get("skills", []) if isinstance(item, str)),
            str(answers_text or ""),
            str(story_text or ""),
        ]
        blob = " ".join(chunks).lower().replace("ё", "е")

        core_signals = [
            "инженер-сметчик",
            "инженер сметчик",
            "сметчик",
            "смет",
            "quantity surveyor",
            "cost estimator",
        ]
        support_signals = [
            "строитель",
            "construction",
            "проектная документац",
            "документац",
            "материал",
            "обьем работ",
            "объем работ",
            "подрядчик",
            "проектировщик",
            "строительные нормы",
            "помощник инженера",
            "координатор строительных проектов",
            "site office",
            "construction project assistant",
        ]

        core_hits = {token for token in core_signals if token in blob}
        support_hits = {token for token in support_signals if token in blob}

        if core_hits and (support_hits or len(core_hits) >= 2):
            return CONSTRUCTION_ESTIMATION_DOMAIN
        return ""

    def _is_forbidden_construction_main_path(self, value: str) -> bool:
        text = str(value or "").strip().lower().replace("ё", "е")
        if not text:
            return True

        allowed_markers = [
            "assistant cost estimator",
            "junior quantity surveyor",
            "construction documentation specialist",
            "technical assistant construction",
            "construction project assistant",
            "site office assistant",
            "project coordinator in construction company",
            "back-office specialist in construction / engineering company",
            "administrative assistant in construction / engineering company",
        ]
        if any(marker in text for marker in allowed_markers):
            return False

        forbidden_markers = [
            "generic back-office specialist",
            "sales operations assistant",
            "master of shift",
            "warehouse team lead",
            "courier",
            "private repair jobs",
            "tile",
            "drywall",
            "furniture work",
            "частные заказы",
            "плитк",
            "гипсокарт",
            "покраск",
            "ремонт",
            "курьер",
            "кладов",
            "склад",
        ]
        if any(marker in text for marker in forbidden_markers):
            return True

        if "administrative assistant" in text and "construction" not in text and "engineering" not in text:
            return True
        if "back-office specialist" in text and "construction" not in text and "engineering" not in text:
            return True

        return False

    def _contains_forbidden_construction_first_step_terms(self, value: str) -> bool:
        text = str(value or "").lower().replace("ё", "е")
        return any(term in text for term in CONSTRUCTION_FORBIDDEN_FIRST_STEP_TERMS)

    def _enforce_domain_specific_routes(self, report: dict[str, Any], profile_domain: str) -> None:
        if profile_domain != CONSTRUCTION_ESTIMATION_DOMAIN:
            return

        decision = report.get("career_decision") if isinstance(report.get("career_decision"), dict) else {}
        main_path = str(decision.get("recommended_main_path", "")).strip()
        if self._is_forbidden_construction_main_path(main_path):
            decision["recommended_main_path"] = "Assistant Cost Estimator / Junior Quantity Surveyor"

        backup_path = str(decision.get("backup_path", "")).strip()
        if self._is_forbidden_construction_main_path(backup_path):
            decision["backup_path"] = "Construction Documentation Specialist / Technical Assistant Construction"

        avoid_for_now = str(decision.get("avoid_for_now", "")).strip()
        avoid_note = "Избегать generic office ролей и несвязанных с construction подработок как основного пути."
        if avoid_note not in avoid_for_now:
            decision["avoid_for_now"] = f"{avoid_note} {avoid_for_now}".strip()

        why_this_path = str(decision.get("why_this_path", "")).strip()
        domain_note = "Профиль зафиксирован в домене construction engineering / cost estimation."
        if domain_note not in why_this_path:
            decision["why_this_path"] = f"{domain_note} {why_this_path}".strip()

        report["career_decision"] = decision

        market_analysis = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
        for idx, item in enumerate(market_analysis):
            if not isinstance(item, dict):
                continue
            profession = str(item.get("profession", "")).strip()
            if self._is_forbidden_construction_main_path(profession):
                replacement = CONSTRUCTION_ESTIMATION_ROLES[min(idx, len(CONSTRUCTION_ESTIMATION_ROLES) - 1)]
                item["profession"] = replacement
        report["market_analysis"] = market_analysis

        recommendations = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
        for idx, item in enumerate(recommendations):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if self._is_forbidden_construction_main_path(title):
                item["title"] = CONSTRUCTION_ESTIMATION_ROLES[min(idx, len(CONSTRUCTION_ESTIMATION_ROLES) - 1)]
        report["career_recommendations"] = recommendations

        bridges = report.get("career_bridges") if isinstance(report.get("career_bridges"), list) else []
        for item in bridges:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip().lower()
            if role == "administrative assistant":
                item["role"] = "Administrative Assistant in construction / engineering company"
            elif role == "back-office specialist":
                item["role"] = "Back-office Specialist in construction / engineering company"
        report["career_bridges"] = bridges

        solutions = report.get("real_solutions") if isinstance(report.get("real_solutions"), list) else []
        if solutions:
            first = solutions[0] if isinstance(solutions[0], dict) else {}
            first_title = str(first.get("title", "")).strip()
            if self._is_forbidden_construction_main_path(first_title):
                first["title"] = "Решение №1: Assistant Cost Estimator / Junior Quantity Surveyor"
            first["first_step"] = CONSTRUCTION_DOMAIN_FIRST_STEP_ACTION
            first["timeline"] = str(first.get("timeline") or "1-3 недели")
            solutions[0] = first
        report["real_solutions"] = solutions

        action_plan = report.get("action_plan") if isinstance(report.get("action_plan"), dict) else {}
        today = action_plan.get("today") if isinstance(action_plan.get("today"), dict) else {}
        current_today_action = str(today.get("action", "")).strip()

        # Domain lock: always keep the first step market-check oriented for estimator track.
        if not current_today_action or self._contains_forbidden_construction_first_step_terms(current_today_action):
            today["action"] = CONSTRUCTION_DOMAIN_FIRST_STEP_ACTION
        else:
            today["action"] = CONSTRUCTION_DOMAIN_FIRST_STEP_ACTION

        today["timebox"] = "15 минут"
        today["result"] = (
            "Есть список из 10 вакансий и перечень повторяющихся требований рынка "
            "для маршрута инженера-сметчика."
        )
        action_plan["today"] = today
        report["action_plan"] = action_plan
        report["first_step_buttons"] = list(CONSTRUCTION_DOMAIN_FIRST_STEP_BUTTONS)

    def _preferred_polish_roles(self, story_analysis: dict[str, Any], user_segment: str = "") -> list[str]:
        # Guard: senior/leader/specialist/entrepreneur segments never get admin default roles
        _no_admin_segments = {"leader", "specialist_expert", "entrepreneur"}
        if str(user_segment or "").strip().lower() in _no_admin_segments:
            return []

        chunks = [
            str(story_analysis.get("current_identity", "")),
            " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
            " ".join(str(item) for item in story_analysis.get("skills", []) if isinstance(item, str)),
        ]
        haystack = " ".join(chunks).lower()

        profile_domain = self._detect_profile_domain(story_analysis)
        if profile_domain == CONSTRUCTION_ESTIMATION_DOMAIN:
            return CONSTRUCTION_ESTIMATION_ROLES[:4]

        # Raised threshold to 3 to prevent accidental triggers from generic words
        project_ops_keywords = ["ngo", "participant", "program coordinator", "координатор программ"]
        if sum(1 for keyword in project_ops_keywords if keyword in haystack) >= 2:
            return [
                "Operations Coordinator",
                "Project Coordinator",
                "Program Assistant",
                "Back-office Specialist",
            ]

        sales_ops_keywords = ["продаж", "sales", "crm", "sap", "erp", "аккаунт", "лид", "воронк"]
        if sum(1 for keyword in sales_ops_keywords if keyword in haystack) >= 3:
            return [
                "Sales Operations Assistant",
                "CRM Specialist",
                "Sales Support Specialist",
                "Administrative Assistant",
            ]

        # Only trigger admin roles if EXPLICIT admin/backoffice/documentation keywords present
        admin_keywords = [
            "документооборот",
            "back-office",
            "секретар",
            "document control",
            "делопроизводств",
            "formal procedure",
            "канцелярия",
        ]
        if sum(1 for keyword in admin_keywords if keyword in haystack) >= 2:
            return [
                "Administrative Assistant",
                "Back-office Specialist",
                "Document Controller",
                "Operations Coordinator",
            ]

        return []

    def _normalize_admin_backoffice_roles(self, report: dict[str, Any], preferred_titles: list[str]) -> None:
        generic_titles = {
            "customer support specialist",
            "customer success",
            "customer success entry",
            "sales support",
            "b2b sales",
            "junior recruiter / sourcer",
            "офис-менеджер",
            "office manager",
        }

        market_analysis = report.get("market_analysis")
        if isinstance(market_analysis, list):
            for idx, item in enumerate(market_analysis[: len(preferred_titles)]):
                if not isinstance(item, dict):
                    continue
                profession = str(item.get("profession", "")).strip()
                if not profession or profession.lower() in generic_titles or profession not in preferred_titles:
                    item["profession"] = preferred_titles[idx]

        recommendations = report.get("career_recommendations")
        if isinstance(recommendations, list):
            for idx, item in enumerate(recommendations[: len(preferred_titles)]):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).strip()
                if not title or title.lower() in generic_titles or title not in preferred_titles:
                    item["title"] = preferred_titles[idx]

        translation = report.get("career_translation")
        if isinstance(translation, list) and translation:
            first = translation[0]
            if isinstance(first, dict) and str(first.get("market_term", "")).strip().lower() in {"", "office manager", "офис-менеджер"}:
                first["market_term"] = preferred_titles[0]

        decision = report.get("career_decision")
        if isinstance(decision, dict):
            main_path = str(decision.get("recommended_main_path", "")).strip().lower()
            if (
                not main_path
                or main_path in generic_titles
                or any(token in main_path for token in ["sales", "customer support", "customer success"])
            ):
                decision["recommended_main_path"] = f"{preferred_titles[0]} / {preferred_titles[1]}"

            backup_path = str(decision.get("backup_path", "")).strip().lower()
            if (
                not backup_path
                or backup_path in generic_titles
                or any(token in backup_path for token in ["sales", "customer support", "customer success"])
            ):
                decision["backup_path"] = f"{preferred_titles[2]} / {preferred_titles[3]}"

        solutions = report.get("real_solutions")
        if isinstance(solutions, list):
            normalized: list[dict[str, Any]] = []
            for item in solutions:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).lower()
                if any(token in title for token in ["продаж", "sales", "customer success"]):
                    continue
                normalized.append(item)
            # No admin hardcoded fallback — keep original solutions or leave empty
            if normalized:
                report["real_solutions"] = normalized[:3]

    def _inject_signal_roles(self, report: dict[str, Any], story_analysis: dict[str, Any], answers_text: str) -> None:
        blob = " ".join(
            [
                str(story_analysis.get("current_identity", "")),
                " ".join(str(item) for item in story_analysis.get("experience_snapshot", []) if isinstance(item, str)),
                str(answers_text or ""),
            ]
        ).lower()
        sales_tokens = ["продаж", "crm", "sap", "erp", "kpi", "воронк", "лид"]
        wants_sales_ops = sum(1 for token in sales_tokens if token in blob) >= 2
        if not wants_sales_ops:
            return

        market = report.get("market_analysis") if isinstance(report.get("market_analysis"), list) else []
        existing_prof = {str(item.get("profession", "")).strip().lower() for item in market if isinstance(item, dict)}
        for role, fit in [
            ("Sales Operations Assistant", 82),
            ("CRM Specialist", 78),
            ("Sales Support Specialist", 76),
        ]:
            if role.lower() in existing_prof:
                continue
            market.append(
                {
                    "profession": role,
                    "fit_percent": fit,
                    "demand": "средний",
                    "entry_speed": "средняя",
                    "competition": "средняя",
                    "requirements": ["Excel", "CRM/SAP", "коммуникация"],
                    "salary_range": "6000-9500 PLN brutto",
                    "profile_match_reason": "Маршрут использует опыт клиентских процессов, данных и операционной дисциплины.",
                }
            )
        report["market_analysis"] = market

        recs = report.get("career_recommendations") if isinstance(report.get("career_recommendations"), list) else []
        existing_titles = {str(item.get("title", "")).strip().lower() for item in recs if isinstance(item, dict)}
        if "sales operations assistant" not in existing_titles:
            recs.append(
                {
                    "title": "Sales Operations Assistant",
                    "match_percent": 80,
                    "why_fit": "Использует коммерческий и процессный слой опыта без радикальной смены трека.",
                    "pros": ["опора на текущие навыки", "близость к доходным функциям", "рост в operations"],
                    "risks": ["нужен прикладной польский", "нужна точная упаковка кейсов"],
                    "entry_timeline": "2-4 месяца",
                    "income_range": "6000-9500 PLN brutto",
                }
            )
        report["career_recommendations"] = recs

    def _transcribe(self, file_path: str) -> str:
        client = self._ensure_client()
        with Path(file_path).open("rb") as audio_file:
            result = client.audio.transcriptions.create(model=self.transcribe_model, file=audio_file)
        text = getattr(result, "text", "")
        return (text or "").strip()

    async def transcribe_voice(self, file_path: str) -> str:
        try:
            return await asyncio.to_thread(self._transcribe, file_path)
        except Exception:
            return ""


ai_client = CareerOpenAIClient(
    api_key=settings.openai_api_key,
    model=settings.openai_model,
    transcribe_model=settings.openai_transcribe_model,
)
