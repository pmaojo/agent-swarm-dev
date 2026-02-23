from pathlib import Path


def test_editable_field_hydration_respects_user_editing_guard() -> None:
    """Editable field hydration should be blocked while user edits are in progress."""
    main_gd: Path = Path("visualizer/scripts/Main.gd")
    script_text: str = main_gd.read_text(encoding="utf-8")

    expected_expression = (
        "var should_populate_editable_fields: bool = "
        "((not _character_lab_initialized) or selected_character_changed or "
        "_character_lab_should_rehydrate_after_save) and "
        "(not _is_user_editing_loadout)"
    )

    assert expected_expression in script_text
