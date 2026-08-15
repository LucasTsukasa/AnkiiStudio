from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Breakpoint(str, Enum):
    COMPACT = "compact"
    MEDIUM = "medium"
    WIDE = "wide"


class Breakpoints:
    COMPACT_MAX = 849
    MEDIUM_MAX = 1199

    @classmethod
    def for_width(cls, width: int) -> Breakpoint:
        if width <= cls.COMPACT_MAX:
            return Breakpoint.COMPACT
        if width <= cls.MEDIUM_MAX:
            return Breakpoint.MEDIUM
        return Breakpoint.WIDE


class Spacing:
    XXS = 2
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Radius:
    XS = 5
    SM = 7
    MD = 9
    LG = 12
    XL = 14
    PILL = 999


class Typography:
    CAPTION = 11
    FIELD = 12
    BODY = 13
    BODY_LARGE = 14
    SECTION = 16
    HEADING = 19
    TITLE = 25
    HERO = 28


class ControlSize:
    SM = 30
    MD = 38
    LG = 44


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    name: str
    background: str
    sidebar: str
    surface: str
    surface_raised: str
    hero: str
    input: str
    input_disabled: str
    text: str
    text_soft: str
    muted: str
    border: str
    border_hover: str
    primary: str
    primary_hover: str
    primary_text: str
    selected: str
    selected_border: str
    danger_bg: str
    danger_border: str
    danger_text: str
    warning_bg: str
    warning_text: str
    success_bg: str
    success_text: str
    scroll: str
    tooltip: str

    def legacy_mapping(self) -> dict[str, str]:
        """Mapeamento compatível com o stylesheet histórico do BenkyouStudio."""
        return {
            "bg": self.background,
            "sidebar": self.sidebar,
            "card": self.surface,
            "hero": self.hero,
            "input": self.input,
            "input_disabled": self.input_disabled,
            "text": self.text,
            "text_soft": self.text_soft,
            "muted": self.muted,
            "border": self.border,
            "border_hover": self.border_hover,
            "primary": self.primary,
            "primary_hover": self.primary_hover,
            "primary_text": self.primary_text,
            "selected": self.selected,
            "selected_border": self.selected_border,
            "danger_bg": self.danger_bg,
            "danger_border": self.danger_border,
            "danger_text": self.danger_text,
            "scroll": self.scroll,
            "tooltip": self.tooltip,
        }


THEMES: dict[str, ThemeTokens] = {
    "light": ThemeTokens(
        name="light", background="#F4F7F5", sidebar="#FFFFFF", surface="#FFFFFF",
        surface_raised="#FFFFFF", hero="#F4FBF7", input="#F8FAF9", input_disabled="#EDF1EF",
        text="#17211B", text_soft="#44534B", muted="#66756D", border="#D7E0DA",
        border_hover="#B7C8BE", primary="#18C96F", primary_hover="#12B863", primary_text="#FFFFFF",
        selected="#DDF6E8", selected_border="#8AD8AE", danger_bg="#FFF1F2", danger_border="#E8B9BE",
        danger_text="#A5323E", warning_bg="#FFF7E6", warning_text="#8A5A00", success_bg="#E8F8EF",
        success_text="#147A43", scroll="#C8D3CD", tooltip="#FFFFFF",
    ),
    "dark": ThemeTokens(
        name="dark", background="#080B0A", sidebar="#0A0F0C", surface="#0E1411",
        surface_raised="#111A15", hero="#0D1712", input="#0A100D", input_disabled="#090D0B",
        text="#F3F7F4", text_soft="#B9C7BF", muted="#84968C", border="#24332B",
        border_hover="#3A5144", primary="#19D978", primary_hover="#2BE88A", primary_text="#031109",
        selected="#123121", selected_border="#1FAF64", danger_bg="#241214", danger_border="#4A252B",
        danger_text="#F5A6AD", warning_bg="#241E10", warning_text="#F0C96B", success_bg="#10251A",
        success_text="#62E59F", scroll="#293A31", tooltip="#101813",
    ),
    "crimson": ThemeTokens(
        name="crimson", background="#1A1A1A", sidebar="#151515", surface="#202020",
        surface_raised="#262326", hero="#24191C", input="#181818", input_disabled="#141414",
        text="#F5F2F3", text_soft="#CEC5C8", muted="#9E9397", border="#3A3033",
        border_hover="#5A424A", primary="#A4133C", primary_hover="#C9184A", primary_text="#FFFFFF",
        selected="#351923", selected_border="#A4133C", danger_bg="#2A151A", danger_border="#703143",
        danger_text="#F5A1BA", warning_bg="#2B2417", warning_text="#F1C66D", success_bg="#17271F",
        success_text="#7AD6A4", scroll="#4A3A40", tooltip="#242020",
    ),
}


def get_theme_tokens(theme: str) -> ThemeTokens:
    return THEMES.get(theme, THEMES["dark"])
