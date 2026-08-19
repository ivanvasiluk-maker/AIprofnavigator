from services.canonical_profile import build_canonical_profile


def test_all_languages_are_extracted_from_dialogue_and_structured_context():
    profile = build_canonical_profile(
        {
            "story_text": (
                "Украинский — родной, русский — свободный, "
                "испанский B1 и английский A2."
            ),
            "languages": ["каталанский A2"],
        },
        assessment_id="all-languages",
    )

    rendered = " ".join(
        str(fact.normalized_value).casefold()
        for fact in profile.facts_of_type("language")
    )
    for expected in ("ukrainian", "russian", "spanish", "english", "каталан"):
        assert expected in rendered
