"""Controlled LLM section generation from approved evidence packets only."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .context_builder import ContextBuilder, SectionEvidencePacket
from .model_client import ModelClient
from .prompts import SECTION_OUTPUT_SCHEMA, render_prompt


SYSTEM_RULES = """You are drafting a PADER-style report section. Use only the supplied evidence packet.
Do not calculate statistics, alter supplied numbers, invent facts, invent patient narratives, or infer missing clinical information.
Do not infer System Organ Class. Do not determine expectedness without a product label/CCDS. Do not invent regulatory actions.
Never describe a numerical pattern as a confirmed safety signal. Use neutral regulatory language and distinguish observation from interpretation.
Return JSON conforming to the required schema. The evidence_ids array must contain only IDs in allowed_evidence_ids and only IDs actually used in content.
"""


@dataclass(frozen=True)
class GeneratedSection:
    section: str
    content: str
    evidence_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"section": self.section, "content": self.content, "evidence_ids": self.evidence_ids}


class SectionGenerator:
    """Generates a section, then enforces evidence-ID provenance after model output."""

    def __init__(self, context_builder: ContextBuilder, model_client: ModelClient) -> None:
        self.context_builder = context_builder
        self.model_client = model_client

    @staticmethod
    def _validate_response(response: dict[str, Any], packet: SectionEvidencePacket) -> GeneratedSection:
        required = {"section", "content", "evidence_ids"}
        if set(response) != required:
            raise ValueError(f"Model response must contain exactly {sorted(required)}.")
        if response["section"] != packet.section:
            raise ValueError("Model response section does not match requested section.")
        if not isinstance(response["content"], str) or not response["content"].strip():
            raise ValueError("Model response content must be a non-empty string.")
        ids = response["evidence_ids"]
        if not isinstance(ids, list) or not ids or any(not isinstance(item, str) for item in ids):
            raise ValueError("Model response must cite at least one evidence ID.")
        if len(ids) != len(set(ids)):
            raise ValueError("Model response contains duplicate evidence IDs.")
        unauthorized = set(ids) - set(packet.evidence_ids)
        if unauthorized:
            raise ValueError(f"Model response invented or used unauthorized evidence IDs: {sorted(unauthorized)}")
        return GeneratedSection(section=response["section"], content=response["content"], evidence_ids=ids)

    def generate(self, section: str) -> GeneratedSection:
        packet = self.context_builder.build(section)
        prompt = render_prompt(section, packet.to_prompt_json())
        response = self.model_client.generate(system_prompt=SYSTEM_RULES, user_prompt=prompt, response_schema=SECTION_OUTPUT_SCHEMA)
        return self._validate_response(response, packet)
