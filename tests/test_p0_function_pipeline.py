from services.report_snapshot import build_report_snapshot, merge_functions, normalize_functions


def test_aliases_normalize_without_mixing_skills():
    rows = normalize_functions({
        "tasks": ["Контроль качества"],
        "functions": ["Обучение сотрудников"],
        "responsibilities": ["Подготовка к аудитам"],
        "skills": ["Excel"],
    }, "resume")
    assert {row["label"] for row in rows} == {
        "Контроль качества", "Обучение сотрудников", "Подготовка к аудитам",
    }
    assert all(row["category"] == "function" and row["sources"] == ["resume"] for row in rows)


def test_empty_input_preserves_existing_and_duplicate_merges_evidence():
    story = normalize_functions({"functions": [{
        "id": "quality_control", "label": "Контроль качества",
        "evidence": ["следил за качеством сборки"],
    }]}, "story")
    resume = normalize_functions({"responsibilities": [{
        "id": "quality_control", "label": "Контроль качества",
        "evidence": ["контроль готовой продукции"], "frequency": "regular", "confidence": "high",
    }]}, "resume")
    assert merge_functions(story, [])[0]["sources"] == ["story"]
    merged = merge_functions(story, resume)
    assert len(merged) == 1
    assert merged[0]["sources"] == ["story", "resume"]
    assert len(merged[0]["evidence"]) == 2


def test_sergey_alias_pipeline_reaches_snapshot():
    functions = [
        "Контроль качества производственных процессов", "Анализ причин брака и неисправностей",
        "Улучшение производственных процессов", "Разработка технических и рабочих инструкций",
        "Обучение и адаптация сотрудников", "Подготовка производства к аудитам",
        "Координация работы производственной команды",
    ]
    data = {
        "assessment_id": "sergey-alias-regression", "story_text": "Меня зовут Сергей. Живу в Брно, Чехия.",
        "story_analysis": {"tasks": functions[:5]},
        "resume_analysis": {"responsibilities": functions[1:]},
        "resume_parse_status": "completed",
    }
    snapshot = build_report_snapshot(data)
    assert len(snapshot.facts["confirmed_functions"]) == 7
    assert len(snapshot.facts["professional_functions"]) == 7
    assert snapshot.resume["loaded"] is True
