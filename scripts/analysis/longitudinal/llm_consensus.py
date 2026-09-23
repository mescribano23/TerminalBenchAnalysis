"""Shared LLM provider and consensus helpers for longitudinal labelers."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

import requests


ProviderNormalizer = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class LabelerSpec:
    provider: str
    model: str

    @property
    def id(self) -> str:
        return f"{self.provider}:{self.model}"


def parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def parse_labeler_specs(args: argparse.Namespace) -> list[LabelerSpec]:
    raw_specs = getattr(args, "labeler", None) or []
    if raw_specs:
        specs = []
        for raw in raw_specs:
            if ":" not in raw:
                raise ValueError(f"Labeler spec must use provider:model format: {raw!r}")
            provider, model = raw.split(":", 1)
            specs.append(LabelerSpec(provider=provider.strip(), model=model.strip()))
        return specs
    return [LabelerSpec(provider=args.provider, model=args.model)]


def add_provider_args(parser: argparse.ArgumentParser, default_model: str) -> None:
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "ollama", "openai-compatible"],
        default="openai",
        help="Single-label backend used when --labeler is not supplied.",
    )
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", default_model))
    parser.add_argument(
        "--labeler",
        action="append",
        default=[],
        metavar="PROVIDER:MODEL",
        help=(
            "Add one consensus voter, e.g. openai:gpt-4o-mini, "
            "anthropic:claude-haiku-4-5-20251001, or ollama:qwen2.5:7b-instruct. "
            "Repeat this option for multi-family consensus."
        ),
    )
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument(
        "--openai-compatible-base-url",
        default=os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:1234/v1"),
    )
    parser.add_argument(
        "--openai-compatible-api-key",
        default=os.environ.get("OPENAI_COMPATIBLE_API_KEY", "not-needed"),
    )


def preflight_provider(args: argparse.Namespace) -> None:
    specs = parse_labeler_specs(args)
    providers = {spec.provider for spec in specs}
    supported = {"openai", "anthropic", "ollama", "openai-compatible"}
    unknown = sorted(providers.difference(supported))
    if unknown:
        raise RuntimeError(f"Unsupported provider(s): {', '.join(unknown)}")
    if "openai" in providers:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY must be set for openai labelers.")
        try:
            import openai  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "The `openai` Python package is not installed. "
                "Run `python -m pip install -r requirements.txt`."
            ) from exc
    if "anthropic" in providers:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY must be set for anthropic labelers.")
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "The `anthropic` Python package is not installed. "
                "Run `python -m pip install -r requirements.txt`."
            ) from exc


def label_with_openai(prompt: str, model: str, system_prompt: str, max_tokens: int) -> str:
    from openai import OpenAI

    client = OpenAI()
    response = client.responses.create(
        model=model,
        instructions=system_prompt,
        input=prompt,
        temperature=0,
        max_output_tokens=max_tokens,
    )
    text = getattr(response, "output_text", "")
    return text or str(response)


def label_with_anthropic(prompt: str, model: str, system_prompt: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic()
    request = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": prompt}],
    }
    if "json" in system_prompt.lower():
        request["output_config"] = {
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "score": {"type": "integer"},
                        "confidence": {"type": "number"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["label", "confidence", "rationale"],
                    "additionalProperties": False,
                },
            },
        }
    try:
        response = client.messages.create(**request, temperature=0)
    except TypeError as exc:
        if "temperature" not in str(exc):
            raise
        response = client.messages.create(**request)
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts)


def label_with_ollama(prompt: str, model: str, base_url: str, system_prompt: str) -> str:
    response = requests.post(
        base_url.rstrip("/") + "/api/generate",
        json={
            "model": model,
            "prompt": f"{system_prompt}\n\n{prompt}",
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=180,
    )
    response.raise_for_status()
    return str(response.json().get("response", ""))


def label_with_openai_compatible(
    prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    system_prompt: str,
    max_tokens: int,
) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def call_labeler(prompt: str, spec: LabelerSpec, args: argparse.Namespace, system_prompt: str, max_tokens: int) -> str:
    if spec.provider == "openai":
        return label_with_openai(prompt, spec.model, system_prompt, max_tokens)
    if spec.provider == "anthropic":
        return label_with_anthropic(prompt, spec.model, system_prompt, max_tokens)
    if spec.provider == "ollama":
        return label_with_ollama(prompt, spec.model, args.ollama_url, system_prompt)
    if spec.provider == "openai-compatible":
        return label_with_openai_compatible(
            prompt,
            spec.model,
            args.openai_compatible_base_url,
            args.openai_compatible_api_key,
            system_prompt,
            max_tokens,
        )
    raise ValueError(f"Unknown provider: {spec.provider}")


def repair_json_response(raw: str, spec: LabelerSpec, args: argparse.Namespace, max_tokens: int) -> dict[str, Any]:
    repair_prompt = f"""The text below was intended to be a single JSON object, but it is malformed.

Convert it to valid JSON only. Preserve the intended fields and values as much
as possible. Do not add commentary, markdown, or explanations.

Malformed response:
{raw}
"""
    repaired = call_labeler(
        repair_prompt,
        spec,
        args,
        system_prompt="You repair malformed JSON. Return one valid JSON object only.",
        max_tokens=max(max_tokens, 500),
    )
    return parse_json_object(repaired)


def consensus_label(
    prompt: str,
    args: argparse.Namespace,
    *,
    system_prompt: str,
    max_tokens: int,
    normalize_response: ProviderNormalizer,
    label_key: str,
    confidence_key: str,
    rationale_key: str,
) -> dict[str, Any]:
    votes: list[dict[str, Any]] = []
    for spec in parse_labeler_specs(args):
        try:
            raw = call_labeler(prompt, spec, args, system_prompt, max_tokens)
            try:
                parsed = parse_json_object(raw)
            except Exception:
                parsed = repair_json_response(raw, spec, args, max_tokens)
            normalized = normalize_response(parsed)
            votes.append(
                {
                    "provider": spec.provider,
                    "model": spec.model,
                    "label": normalized[label_key],
                    "confidence": normalized.get(confidence_key, ""),
                    "rationale": normalized.get(rationale_key, ""),
                    "error": "",
                }
            )
        except Exception as exc:
            votes.append(
                {
                    "provider": spec.provider,
                    "model": spec.model,
                    "label": "",
                    "confidence": "",
                    "rationale": "",
                    "error": str(exc),
                }
            )

    valid_votes = [vote for vote in votes if vote["label"]]
    if len(valid_votes) != len(votes):
        raise RuntimeError("One or more labelers failed: " + json.dumps(votes, ensure_ascii=False))

    counts = Counter(str(vote["label"]) for vote in valid_votes)
    top_count = max(counts.values())
    top_labels = sorted(label for label, count in counts.items() if count == top_count)
    status = "unanimous" if len(top_labels) == 1 and top_count == len(votes) else "majority"
    if len(top_labels) > 1:
        status = "tie"
        final_label = ""
    else:
        final_label = top_labels[0]

    final_votes = [vote for vote in valid_votes if vote["label"] == final_label]
    confidences = [
        float(vote["confidence"])
        for vote in final_votes
        if str(vote["confidence"]).strip() not in {"", "nan", "None"}
    ]
    rationale = " | ".join(
        f"{vote['provider']}:{vote['model']}: {vote['rationale']}"
        for vote in valid_votes
        if str(vote.get("rationale", "")).strip()
    )
    if not final_label:
        rationale = f"No consensus among labels: {dict(counts)}. " + rationale

    return {
        label_key: final_label,
        confidence_key: sum(confidences) / len(confidences) if confidences else "",
        rationale_key: rationale,
        "llm_model": ";".join(f"{vote['provider']}:{vote['model']}" for vote in votes),
        "label_source": "consensus" if len(votes) > 1 else valid_votes[0]["provider"],
        "consensus_status": status,
        "consensus_vote_count": len(valid_votes),
        "consensus_votes_json": json.dumps(votes, ensure_ascii=False),
    }
