from pathlib import Path

from scripts.extract_prompt_inventory import collect_inventory, render_markdown


def test_prompt_inventory_script_collects_known_backend_prompts():
    entries = collect_inventory(Path("tir"))
    report = render_markdown(entries)

    assert entries
    assert "tir/reflection/journal.py" in report
    assert "This is your journal space." in report
    assert "tir/behavioral_guidance/review.py" in report
    assert "AI-proposed behavioral guidance candidates" in report
    assert "Review this selected chat conversation only." in report
    assert "tir/engine/context.py" in report
    assert "dormant_before_go_live" in report


def test_prompt_inventory_script_handles_absolute_root_path():
    entries = collect_inventory(Path("tir").resolve())
    report = render_markdown(entries)

    assert entries
    assert "tir/reflection/journal.py" in report
    assert "This is your journal space." in report
    assert "tir/behavioral_guidance/review.py" in report
    assert "AI-proposed behavioral guidance candidates" in report


def test_prompt_inventory_report_includes_categories_and_audit_notes():
    entries = collect_inventory(Path("tir"))
    report = render_markdown(entries)

    for category in [
        "Runtime context / identity",
        "Chat / agent loop",
        "Tool-use prompts",
        "Retrieval / memory framing",
        "Artifact / source framing",
        "Behavioral guidance review",
        "Reflection / journal",
        "Research / future automation",
        "Admin / review commands",
        "Other prompt-like strings",
    ]:
        assert f"## {category}" in report

    assert "Audit note options:" in report
    assert "`needs discussion`" in report
    assert "- Audit note: `needs discussion`" in report


def test_prompt_inventory_report_is_not_empty_in_every_category():
    entries = collect_inventory(Path("tir"))
    report = render_markdown(entries)

    assert entries
    assert report.count("No prompt-like strings found.") < 10
    assert "### 1. `tir/reflection/journal.py" in report
    assert "### 1. `tir/behavioral_guidance/review.py" in report


def test_prompt_inventory_report_flags_known_risky_wording():
    entries = collect_inventory(Path("tir"))
    report = render_markdown(entries)

    assert "Risk flags searched:" in report
    assert "`Project Anam`" in report
    assert "`do not`" in report
    assert "`personality`" in report


def test_runtime_behavioral_guidance_status_is_dormant():
    entries = collect_inventory(Path("tir"))
    matching = [
        entry for entry in entries
        if entry.path == "tir/engine/context.py"
        and entry.name == "BEHAVIORAL_GUIDANCE_DORMANT_STATUS"
    ]

    assert len(matching) == 1
    status_entry = matching[0]
    assert status_entry.flags == []
    assert "dormant_before_go_live" in status_entry.excerpt


def test_behavioral_guidance_review_system_prompt_has_reduced_risk_flags():
    entries = collect_inventory(Path("tir"))
    matching = [
        entry for entry in entries
        if entry.path == "tir/behavioral_guidance/review.py"
        and entry.name == "system"
        and "AI-proposed behavioral guidance candidates" in entry.excerpt
    ]

    assert len(matching) == 1
    system_entry = matching[0]
    assert system_entry.flags == []
    assert "Project Anam" not in system_entry.excerpt
    assert "personality" not in system_entry.excerpt
    assert "must" not in system_entry.excerpt.lower()


def test_generated_prompt_inventory_file_is_current():
    entries = collect_inventory(Path("tir"))
    expected = render_markdown(entries)
    actual = Path("docs/PROMPT_INVENTORY.md").read_text(encoding="utf-8")

    assert actual == expected
