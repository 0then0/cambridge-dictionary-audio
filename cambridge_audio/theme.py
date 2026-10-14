"""Desktop design tokens and light/dark palettes; no GUI dependency in the CLI."""

import re
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

COLORS = {
    "light": {
        "background": "#f5f6f8",
        "surface": "#ffffff",
        "text": "#1d2733",
        "muted": "#626f7e",
        "border": "#d9dfe6",
        "accent": "#af3448",
        "accent_hover": "#952c3e",
        "accent_text": "#ffffff",
        "hover": "#edf0f4",
        "disabled": "#e8ecf0",
        "disabled_text": "#7d8895",
        "error": "#a82b3e",
        "scrollbar": "#b5bdc8",
        "scrollbar_hover": "#8995a3",
    },
    "dark": {
        "background": "#171b22",
        "surface": "#202630",
        "text": "#eff2f6",
        "muted": "#adb7c6",
        "border": "#3d4755",
        "accent": "#e38494",
        "accent_hover": "#efa0ac",
        "accent_text": "#171b22",
        "hover": "#2d3542",
        "disabled": "#2a313b",
        "disabled_text": "#85909c",
        "error": "#f09aaa",
        "scrollbar": "#505966",
        "scrollbar_hover": "#707b8a",
    },
}


def contrast(first: str, second: str) -> float:
    def luminance(value):
        color = QColor(value)
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    values = sorted((luminance(first), luminance(second)))
    return (values[1] + 0.05) / (values[0] + 0.05)


def foreground(background: str) -> str:
    return max(("#000000", "#ffffff"), key=lambda color: contrast(color, background))


def blend(first: str, second: str, amount: float) -> str:
    a, b = QColor(first), QColor(second)
    return QColor(
        *[round(x + (y - x) * amount) for x, y in zip(a.getRgb()[:3], b.getRgb()[:3], strict=True)]
    ).name()


def readable(color: str, backgrounds: tuple[str, ...], minimum: float = 4.5) -> str:
    if min(contrast(color, bg) for bg in backgrounds) >= minimum:
        return color
    target = foreground(backgrounds[0])
    for step in range(1, 21):
        candidate = blend(color, target, step / 20)
        if min(contrast(candidate, bg) for bg in backgrounds) >= minimum:
            return candidate
    return target


def stored_colors(settings: QSettings) -> dict[str, dict[str, str]]:
    return {
        mode: {
            token: str(settings.value(f"theme_colors/{mode}/{token}", ""))
            for token in ("background", "accent")
        }
        for mode in COLORS
    }


def theme_colors(mode: str, overrides: dict[str, str] | None = None) -> dict[str, str]:
    colors = COLORS[mode].copy()
    overrides = overrides or {}
    background = QColor(overrides.get("background", ""))
    if background.isValid():
        bg = background.name()
        text = foreground(bg)
        surface = blend(bg, text, 0.045)
        if contrast(text, surface) < 4.5:
            surface = blend(bg, foreground(text), 0.08)
        hover = blend(surface, text, 0.07)
        if contrast(text, hover) < 4.5:
            hover = blend(surface, foreground(text), 0.07)
        surfaces = (bg, surface)
        colors.update(
            background=bg,
            surface=surface,
            text=text,
            muted=readable(blend(bg, text, 0.65), surfaces),
            border=blend(surface, text, 0.22),
            hover=hover,
            disabled=surface,
            disabled_text=readable(blend(bg, text, 0.5), surfaces, 3),
            error=readable(colors["error"], surfaces),
            scrollbar=readable(blend(bg, text, 0.45), (bg,), 3),
            scrollbar_hover=readable(blend(bg, text, 0.65), (bg,), 3),
        )
    accent = QColor(overrides.get("accent", ""))
    if accent.isValid() or background.isValid():
        colors["accent"] = accent.name() if accent.isValid() else colors["accent"]
        colors["accent_text"] = foreground(colors["accent"])
        colors["accent_hover"] = blend(colors["accent"], colors["accent_text"], 0.08)
        if contrast(colors["accent_text"], colors["accent_hover"]) < 4.5:
            colors["accent_hover"] = colors["accent"]
    colors["focus"] = readable(colors["accent"], (colors["background"], colors["surface"]), 3)
    return colors


_ICON_DIRECTORY = TemporaryDirectory(prefix="cambridge-theme-icons-")


@lru_cache(maxsize=128)
def icon_path(name: str, color: str) -> str:
    """Tint the shared SVG geometry, including stylesheet icons, for any palette."""
    color = QColor(color).name()
    source = Path(__file__).resolve().parents[1] / "assets" / "ui" / f"{name}.svg"
    svg = re.sub(r'(?<=stroke=")#[0-9a-fA-F]{6}', color, source.read_text(encoding="utf-8"))
    destination = Path(_ICON_DIRECTORY.name) / f"{name}-{color[1:]}.svg"
    destination.write_text(svg, encoding="utf-8")
    return destination.as_posix()


def themed_icon(name: str, color: str) -> QIcon:
    return QIcon(icon_path(name, color))


def apply_theme(
    app: QApplication,
    choice: str,
    *,
    custom_colors: dict[str, dict[str, str]] | None = None,
    update_scheme: bool = True,
) -> str:
    hints = app.styleHints()
    if update_scheme:
        if choice == "system":
            hints.unsetColorScheme()
        else:
            hints.setColorScheme(Qt.ColorScheme.Dark if choice == "dark" else Qt.ColorScheme.Light)
    dark = choice == "dark" or (choice == "system" and hints.colorScheme() == Qt.ColorScheme.Dark)
    mode = "dark" if dark else "light"
    c = theme_colors(mode, (custom_colors or {}).get(mode))
    chevron = icon_path("chevron", c["muted"])
    check = icon_path("check", c["accent_text"])
    palette = QPalette()
    for role, token in {
        QPalette.ColorRole.Window: "background",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "surface",
        QPalette.ColorRole.AlternateBase: "hover",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "surface",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.Highlight: "accent",
        QPalette.ColorRole.HighlightedText: "accent_text",
        QPalette.ColorRole.PlaceholderText: "muted",
        QPalette.ColorRole.ToolTipBase: "surface",
        QPalette.ColorRole.ToolTipText: "text",
    }.items():
        palette.setColor(role, QColor(c[token]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled_text"]))
    app.setPalette(palette)
    app.setStyleSheet(f"""
        QMainWindow, QDialog, QScrollArea, QWidget#page {{ background: {c["background"]}; }}
        QLabel {{ color: {c["text"]}; background: transparent; }}
        QLabel#muted, QLabel#status {{ color: {c["muted"]}; }}
        QLabel#heading {{ font-size: 20px; font-weight: 600; }}
        QLabel#word {{ font-size: 22px; font-weight: 600; }}
        QLabel#status[severity="error"] {{ color: {c["error"]}; }}
        QFrame#panel {{
            background: {c["surface"]}; border: 1px solid {c["border"]}; border-radius: 8px;
        }}
        QLineEdit, QComboBox {{
            background: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]};
            border-radius: 6px; padding: 8px 10px; min-height: 20px;
        }}
        QComboBox {{ padding-right: 24px; }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox::down-arrow {{ image: url("{chevron}"); width: 12px; height: 12px; }}
        QComboBox QAbstractItemView {{
            background: {c["surface"]}; color: {c["text"]};
            selection-background-color: {c["accent"]}; selection-color: {c["accent_text"]};
        }}
        QLineEdit:focus, QComboBox:focus {{ border: 2px solid {c["focus"]}; padding: 7px 9px; }}
        QComboBox:focus {{ padding-right: 23px; }}
        QPushButton {{
            background: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]};
            border-radius: 6px; padding: 9px 14px; min-height: 20px;
        }}
        QPushButton:hover {{ background: {c["hover"]}; }}
        QPushButton:focus {{ border: 2px solid {c["focus"]}; padding: 8px 13px; }}
        QPushButton#settingsButton {{
            padding: 0; min-height: 0; border: none; background: transparent;
        }}
        QPushButton#settingsButton:hover {{ background: {c["hover"]}; }}
        QPushButton#settingsButton:focus {{ border: 2px solid {c["focus"]}; }}
        QPushButton#downloadButton {{
            background: {c["accent"]}; color: {c["accent_text"]}; border-color: {c["accent"]};
            font-weight: 600;
        }}
        QPushButton#downloadButton:hover {{ background: {c["accent_hover"]}; }}
        QPushButton#downloadButton:focus {{
            border: 2px solid {c["accent_text"]}; padding: 8px 13px;
        }}
        QPushButton:disabled, QPushButton#downloadButton:disabled,
        QLineEdit:disabled, QComboBox:disabled {{
            background: {c["disabled"]}; color: {c["disabled_text"]}; border-color: {c["border"]};
        }}
        QCheckBox {{ color: {c["text"]}; spacing: 8px; background: transparent; }}
        QCheckBox::indicator {{
            width: 16px; height: 16px; border: 1px solid {c["muted"]};
            border-radius: 3px; background: {c["surface"]};
        }}
        QCheckBox::indicator:checked {{
            background: {c["accent"]}; border-color: {c["accent"]}; image: url("{check}");
        }}
        QCheckBox::indicator:focus {{ border-color: {c["focus"]}; }}
        QCheckBox:disabled {{ color: {c["disabled_text"]}; }}
        QProgressBar {{ border: none; background: {c["border"]}; height: 3px; border-radius: 1px; }}
        QProgressBar::chunk {{ background: {c["accent"]}; }}
        QScrollBar {{ background: transparent; border: none; }}
        QScrollBar:vertical {{ width: 12px; margin: 2px 4px; }}
        QScrollBar:horizontal {{ height: 12px; margin: 4px 2px; }}
        QScrollBar:vertical:hover {{ margin: 2px 2px; }}
        QScrollBar:horizontal:hover {{ margin: 2px 2px; }}
        QScrollBar::handle {{ background: {c["scrollbar"]}; border-radius: 2px; }}
        QScrollBar::handle:vertical {{ min-height: 32px; }}
        QScrollBar::handle:horizontal {{ min-width: 32px; }}
        QScrollBar::handle:hover, QScrollBar::handle:pressed {{
            background: {c["scrollbar_hover"]};
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0; height: 0; border: none; background: transparent;
        }}
        QScrollBar::up-arrow, QScrollBar::down-arrow,
        QScrollBar::left-arrow, QScrollBar::right-arrow {{ width: 0; height: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QToolTip {{
            color: {c["text"]}; background: {c["surface"]}; border: 1px solid {c["border"]};
        }}
    """)
    return mode
