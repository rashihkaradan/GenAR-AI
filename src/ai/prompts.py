"""Prompt-template loading and fixed structured-output specification."""
from __future__ import annotations

from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"

SECTION_OUTPUT_SCHEMA = {
    "name": "pader_section",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "section": {"type": "string"},
            "content": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["section", "content", "evidence_ids"],
    },
}


def load_template(section: str) -> str:
    path = PROMPT_DIR / f"{section}.txt"
    if not path.is_file():
        raise ValueError(f"Prompt template not found for section {section!r}: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(section: str, evidence_packet_json: str) -> str:
    template = load_template(section)
    if "{{evidence_packet}}" not in template:
        raise ValueError(f"Prompt template {section!r} is missing the evidence-packet placeholder.")
    return template.replace("{{evidence_packet}}", evidence_packet_json)
