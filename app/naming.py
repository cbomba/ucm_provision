from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml


@dataclass(frozen=True)
class NamingProfile:
    data: dict
    dialplan: Optional[dict] = None

    @staticmethod
    def load(naming_path: str, dialplan_path: Optional[str] = None) -> "NamingProfile":
        naming_raw = yaml.safe_load(Path(naming_path).read_text(encoding="utf-8"))

        dialplan = None
        if dialplan_path:
            dialplan = yaml.safe_load(Path(dialplan_path).read_text(encoding="utf-8"))

        return NamingProfile(
            data=naming_raw,
            dialplan=dialplan
        )

    def render_name(self, obj_type: str, ctx: dict) -> str:
        tmpl = self.data["objects"][obj_type]["name"]
        return tmpl.format(**ctx)

    def render_description(self, obj_type: str, ctx: dict) -> str:
        tmpl = self.data["objects"][obj_type]["description"]
        return tmpl.format(**ctx)