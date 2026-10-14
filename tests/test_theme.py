"""User colours retain readable text and controls, even for extreme choices."""

import pytest

pytest.importorskip("PySide6", reason="Install the gui group to run theme tests")

from cambridge_audio.theme import COLORS, contrast, theme_colors  # noqa: E402


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_default_colours_are_preserved(mode):
    colors = theme_colors(mode)
    assert all(colors[key] == value for key, value in COLORS[mode].items())
    invalid = theme_colors(mode, {"background": "invalid", "accent": "invalid"})
    assert invalid == colors


@pytest.mark.parametrize(
    "background",
    [
        "#000000",
        "#ffffff",
        "#777777",
        "#808080",
        "#ff0000",
        "#00ff00",
        "#0000ff",
        "#ffff00",
        "#543287",
    ],
)
@pytest.mark.parametrize("accent", ["#000000", "#ffffff", "#777777", "#ffff00", "#00ff00"])
def test_custom_colours_keep_text_icons_and_focus_readable(background, accent):
    colors = theme_colors("light", {"background": background, "accent": accent})
    assert colors["background"] == background
    assert colors["accent"] == accent
    for surface in ("background", "surface", "hover"):
        assert contrast(colors["text"], colors[surface]) >= 4.5
    for surface in ("background", "surface"):
        assert contrast(colors["muted"], colors[surface]) >= 4.5
        assert contrast(colors["focus"], colors[surface]) >= 3
    for surface in ("accent", "accent_hover"):
        assert contrast(colors["accent_text"], colors[surface]) >= 4.5
