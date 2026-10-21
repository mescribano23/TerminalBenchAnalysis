"""Shared Next.js Flight reference parsing for the Terminal-Bench scrapers."""

from __future__ import annotations

import json
import re
from typing import Any


RSC_DEFINITION_RE = re.compile(r"(?m)^([0-9a-z]+):", re.IGNORECASE)
RSC_REFERENCE_RE = re.compile(r"^\$([0-9a-z]+)$", re.IGNORECASE)


def parse_json_prefix(text: str) -> Any | None:
    try:
        value, _ = json.JSONDecoder().raw_decode(text.lstrip())
    except json.JSONDecodeError:
        return None
    return value


def extract_rsc_references(payload_text: str) -> dict[str, Any]:
    references: dict[str, Any] = {}
    matches = list(RSC_DEFINITION_RE.finditer(payload_text))
    for index, match in enumerate(matches):
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(payload_text)
        value_text = payload_text[value_start:value_end].strip()
        parsed = parse_json_prefix(value_text)
        if parsed is not None:
            references[match.group(1)] = parsed
    return references


def extract_rsc_text_references(payload_strings: list[str]) -> dict[str, str]:
    """Resolve Next Flight text records like ``31:T<hex_length>,...``.

    Large text values can be split across multiple ``__next_f.push`` chunks, and
    a consumed chunk can itself contain another ``NUMBER:T...`` record. Scan the
    complete Flight stream so each text reference is discovered independently.
    """
    references: dict[str, str] = {}
    flight_stream = "".join(payload_strings)
    for match in re.finditer(
        r"(?<![0-9A-Za-z])([0-9a-z]+):T([0-9a-f]+),",
        flight_stream,
        flags=re.IGNORECASE,
    ):
        reference_id = match.group(1)
        expected_length = int(match.group(2), 16)
        content_start = match.end()
        references[reference_id] = flight_stream[
            content_start : content_start + expected_length
        ]

    return references


def build_rsc_reference_lookup(payload_strings: list[str]) -> dict[str, Any]:
    decoded_payload = "\n".join(payload_strings)
    references = extract_rsc_references(decoded_payload)
    references.update(extract_rsc_text_references(payload_strings))
    return references


def resolve_rsc_references(value: Any, references: dict[str, Any], seen: set[str] | None = None) -> Any:
    if seen is None:
        seen = set()

    if isinstance(value, str):
        match = RSC_REFERENCE_RE.fullmatch(value)
        if match:
            reference_id = match.group(1)
            if reference_id in references and reference_id not in seen:
                return resolve_rsc_references(
                    references[reference_id], references, seen | {reference_id}
                )
        return value

    if isinstance(value, list):
        return [resolve_rsc_references(item, references, seen) for item in value]

    if isinstance(value, dict):
        return {
            key: resolve_rsc_references(item, references, seen)
            for key, item in value.items()
        }

    return value
