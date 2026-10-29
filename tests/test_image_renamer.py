import os

from image_renamer import extract_date_suffix, safe_output_name, sanitize_caption


def test_extract_date_suffix():
    assert extract_date_suffix("IMG_2024_05_07.png") == "07-05-2024"
    assert extract_date_suffix("sample-03-12-2025.jpg") == "03-12-2025"


def test_sanitize_caption_filters_blocklist_and_generic_terms():
    result = sanitize_caption(
        "A photo of a red dragon on a wall",
        original_name="IMG_2024_06_01.png",
        max_words=4,
        min_words=2,
        blocklist=["a", "photo", "on", "wall"],
    )
    assert "Dragon" in result
    assert "Red" in result
    assert "Photo" not in result


def test_safe_output_name_handles_duplicates(tmp_path):
    first = safe_output_name("Cat", ".jpg", tmp_path)
    (tmp_path / first).write_text("fake", encoding="utf-8")
    second = safe_output_name("Cat", ".jpg", tmp_path)
    assert second.startswith("Cat_1")
    assert second.endswith(".jpg")


def test_sanitize_caption_keeps_date_suffix():
    result = sanitize_caption(
        "cute puppy",
        original_name="IMG_2023_11_02.jpg",
        max_words=3,
        min_words=2,
        blocklist=["cute"],
    )
    assert result.endswith("-02-11-2023") or "2023" in result
