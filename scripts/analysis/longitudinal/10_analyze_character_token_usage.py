"""Export explicitly scoped RQ3.3 medians, populations and accounting coverage.

Uses canonical CSV extraction fields and source IDs. Does not fit models,
write figures, or overwrite the validated main effort/statistical exports.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.analysis.submission_task_balancing import SOURCE_SUBMISSION_ID, ensure_source_submission_id

effort = importlib.import_module("scripts.analysis.longitudinal.08_analyze_effort_changes")
LONG = ROOT / "data/processed_live/longitudinal"
SID = SOURCE_SUBMISSION_ID
CHAR_COLUMNS = ["message_chars", "reasoning_chars", "observation_chars"]
METRICS = {m["column"]: m["label"] for m in effort.METRICS}
METRICS.update({
    "logged_chars_positive_total": "Logged characters among finite positive total-token records",
    "logged_chars_per_total_token": "Per-trajectory logged characters / finite positive total tokens",
})
METHODS = ("pooled_all_retained", "pooled_shared_tasks", "hierarchical_shared_tasks")


def token_status(values: pd.Series) -> pd.Series:
    """Preserve missing, malformed, nonfinite and zero as distinct reasons."""
    numeric = pd.to_numeric(values, errors="coerce")
    return pd.Series(np.select(
        [values.isna(), numeric.isna(), ~np.isfinite(numeric), numeric.eq(0), numeric.lt(0)],
        ["missing", "nonnumeric", "nonfinite", "zero", "negative"], default="valid_positive",
    ), index=values.index)


def read_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    effort.require_columns(df, set(effort.REQUIRED_COLUMNS) | {SID, "benchmark", "rel_path", "scaffold", "model_dir"}, str(path))
    df = ensure_source_submission_id(df)
    if df.duplicated(["benchmark", "rel_path"]).any():
        raise ValueError(f"Duplicate trajectory records in {path}; do not count repeated rows as extra trials")
    if df["task_name"].isna().any() or df["task_name"].astype(str).str.strip().eq("").any():
        raise ValueError(f"Missing task identity in {path}")
    df["benchmark_version"] = df["benchmark_version"].astype(str)
    df["total_token_status"] = token_status(df["total_tokens"])
    for col in set(CHAR_COLUMNS) | {m["column"] for m in effort.METRICS}:
        if col == "logged_chars":
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce").where(lambda x: np.isfinite(x))
    for col in effort.TOKEN_COLUMNS:
        df[col] = df[col].where(df[col].gt(0))
    # Ordinary addition is deliberate: missing observations/reasoning invalidate
    # the sum instead of silently turning a partial log into a complete log.
    df["logged_chars"] = df.message_chars + df.reasoning_chars + df.observation_chars
    df["logged_chars_positive_total"] = df.logged_chars.where(df.total_tokens.notna())
    df["logged_chars_per_total_token"] = (df.logged_chars / df.total_tokens).replace([np.inf, -np.inf], np.nan)
    return df


def counts(df: pd.DataFrame, metric: str) -> dict:
    valid = df[np.isfinite(df[metric])]
    result = {
        "input_trajectories": len(df), "valid_trajectories": len(valid),
        "source_submissions": valid[SID].nunique(),
        "source_submission_task_pairs": len(valid[[SID, "task_name"]].drop_duplicates()),
        "tasks": valid.task_name.nunique(), "invalid_metric_records": len(df) - len(valid),
    }
    if "total_token_status" in df:
        for status in ["missing", "nonnumeric", "nonfinite", "zero", "negative", "valid_positive"]:
            result[f"total_tokens_{status}"] = int(df.total_token_status.eq(status).sum())
    return result


def median(df: pd.DataFrame, metric: str, hierarchical: bool) -> float:
    if df.benchmark_version.nunique() > 1:
        raise ValueError("Summarize one benchmark version at a time")
    valid = df[np.isfinite(df[metric])]
    if hierarchical:
        return float(valid.groupby([SID, "task_name"])[metric].median().groupby("task_name").median().median())
    return float(valid[metric].median())


def percentage(early: float, late: float) -> float:
    return float((late / early - 1) * 100) if np.isfinite(early) and early != 0 else np.nan


def version_comparisons(df: pd.DataFrame, old: str, new: str) -> pd.DataFrame:
    shared = set(df.loc[df.benchmark_version.eq(old), "task_name"]) & set(df.loc[df.benchmark_version.eq(new), "task_name"])
    if not shared:
        raise ValueError(f"No shared tasks for {old}->{new}")
    rows = []
    for metric, definition in METRICS.items():
        pairs = effort.task_metric_pairs(df, metric).dropna(subset=[old, new])
        matched = shared & set(pairs.index)
        for method in METHODS:
            pop = df if method == "pooled_all_retained" else df[df.task_name.isin(matched)]
            earlier, later = [pop[pop.benchmark_version.eq(v)] for v in [old, new]]
            a, b = [median(g, metric, method == "hierarchical_shared_tasks") for g in [earlier, later]]
            row = {"transition": f"{old}->{new}", "metric": metric, "definition": definition,
                   "aggregation": method, "submission_unit": SID if method.startswith("hierarchical") else "trajectory",
                   "old_version": old, "new_version": new, "old_value": a, "new_value": b,
                   "percentage_change": percentage(a, b), "expected_shared_tasks": len(shared),
                   "metric_paired_tasks": len(matched), "dropped_shared_tasks": ";".join(sorted(shared - matched))}
            for prefix, g in [("old", earlier), ("new", later)]:
                row.update({f"{prefix}_{k}": v for k, v in counts(g, metric).items()})
            rows.append(row)
    return pd.DataFrame(rows)


def configuration_rows(df: pd.DataFrame, diagnostic: str, metrics: dict[str, tuple[str, str]],
                       *, scope: str, population_n: int | None = None) -> list[dict]:
    """One configuration/version or explicitly named population per call."""
    if df.empty:
        return []
    rows = []
    for metric, (numerator, denominator) in metrics.items():
        for hierarchical in [False, True]:
            row = {"diagnostic": diagnostic, "benchmark_version": df.benchmark_version.iloc[0],
                   "scope": scope, "metric": metric, "numerator": numerator, "denominator": denominator,
                   "aggregation": "hierarchical_source_submission_task" if hierarchical else "pooled_trajectories",
                   "value": median(df, metric, hierarchical), **counts(df, metric)}
            row["population_trajectories"] = population_n if population_n is not None else len(df)
            row["valid_trajectory_share_pct"] = row["valid_trajectories"] / row["population_trajectories"] * 100
            rows.append(row)
    return rows


def configuration_comparisons(df: pd.DataFrame) -> list[dict]:
    rows = []
    ratio_spec = {"logged_chars_per_total_token": ("message_chars + reasoning_chars + observation_chars", "total_tokens > 0")}
    for scaffold, model in [("codex", "gpt-5.5"), ("terminus-2", "gpt-5.5"),
                             ("gemini-cli", "gemini-3.1-pro-preview"), ("terminus-2", "gemini-3.1-pro-preview")]:
        sub = df[df.benchmark_version.eq("2.1") & df.scaffold.eq(scaffold) & df.model_dir.eq(model)]
        rows.extend(configuration_rows(sub, scaffold + "/" + model, ratio_spec, scope="available tasks in TB2.1 configuration"))
    tb4 = df[df.benchmark_version.eq("4.0")]
    astra = tb4.scaffold.eq("codex") & tb4.model_dir.eq("gpt-6-astra")
    for name, sub in [("all_tb4", tb4), ("codex/gpt-6-astra", tb4[astra]), ("tb4_without_codex_gpt6_astra", tb4[~astra])]:
        rows.extend(configuration_rows(sub, name, {"total_tokens": ("reported input + completion tokens", "none")},
                                       scope="66 TB4.0 tasks; Astra removal excludes all five source IDs", population_n=len(tb4)))
    # Exact configuration and metric-valid shared-task support, not the
    # intersection of model names across changing configuration populations.
    tb34 = df[df.benchmark_version.isin(["3.0", "4.0"]) & df.total_tokens.notna()]
    for (scaffold, model), sub in tb34.groupby(["scaffold", "model_dir"]):
        tasks = [set(sub.loc[sub.benchmark_version.eq(v), "task_name"]) for v in ["3.0", "4.0"]]
        shared = tasks[0] & tasks[1]
        if shared:
            for v in ["3.0", "4.0"]:
                rows.extend(configuration_rows(sub[sub.benchmark_version.eq(v) & sub.task_name.isin(shared)],
                    "matched_tokens:" + scaffold + "/" + model,
                    {"total_tokens": ("reported input + completion tokens", "none")},
                    scope=f"same configuration; {len(shared)} metric-valid shared tasks"))
    return rows


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value)


def raw_accounting(row: dict, root: Path) -> dict:
    obj = json.loads((root / row["benchmark"] / Path(row["rel_path"].replace("\\", "/"))).read_text(encoding="utf-8"))
    if isinstance(obj, dict) and isinstance(obj.get("trajectory"), dict):
        obj = obj["trajectory"]
    if not isinstance(obj, dict) or not isinstance(obj.get("steps"), list):
        raise ValueError(f"Invalid raw trajectory: {row['rel_path']}")
    reason, completion_sum, elided = 0., 0., 0
    positive_calls = explicit = missing = invalid = 0
    relevant_calls = incomplete_calls = text_calls = text_mismatches = counter_fields = 0
    for step in obj["steps"]:
        if not isinstance(step, dict):
            continue
        metrics = step.get("metrics") or {}
        extra = metrics.get("extra") or {}
        details = extra.get("completion_tokens_details") or {}
        rt = details.get("reasoning_tokens")
        if rt is None:
            rt = (extra.get("output_tokens_details") or {}).get("thinking_tokens")
        if rt is None:
            rt = extra.get("reasoning_output_tokens")
        comp = metrics.get("completion_tokens")
        explicit += int(finite_number(rt))
        counter_fields += int("reasoning_tokens" in details or
                              "thinking_tokens" in (extra.get("output_tokens_details") or {}) or
                              "reasoning_output_tokens" in extra)
        # A missing completion counter (or an entirely unmetered agent step)
        # must not disappear from the coverage denominator. Zero is explicit.
        relevant = step.get("source") == "agent" or bool(metrics) or rt is not None
        if relevant:
            relevant_calls += 1
            valid_call = (finite_number(comp) and comp >= 0 and
                          finite_number(rt) and 0 <= rt <= comp)
            incomplete_calls += int(not valid_call)
            if valid_call:
                text = details.get("text_tokens")
                if finite_number(text) and text >= 0:
                    text_calls += 1
                    text_mismatches += int(abs(comp - text - rt) > 1e-6)
        if finite_number(comp) and comp > 0:
            positive_calls += 1
            completion_sum += comp
            if finite_number(rt) and 0 <= rt <= comp:
                reason += rt
            elif rt is None:
                missing += 1
            else:
                invalid += 1
        obs = step.get("observation") or {}
        for result in obs.get("results", []) if isinstance(obs, dict) else []:
            content = result.get("content", "") if isinstance(result, dict) else ""
            if isinstance(content, str) and "elided_chars" in content:
                try:
                    decoded = json.loads(content)
                except json.JSONDecodeError:
                    continue
                omitted = decoded.get("elided_chars") if isinstance(decoded, dict) else None
                if finite_number(omitted) and omitted >= 0:
                    elided += int(omitted)
    final_extra = (obj.get("final_metrics") or {}).get("extra") or {}
    final_reason = final_extra.get("total_reasoning_tokens")
    if final_reason is None:
        final_reason = final_extra.get("reasoning_output_tokens")
    return {"benchmark": row["benchmark"], "rel_path": row["rel_path"], "reasoning_tokens": reason,
            "final_reasoning_tokens": final_reason if finite_number(final_reason) else np.nan,
            "final_completion_tokens": (obj.get("final_metrics") or {}).get("total_completion_tokens"),
            "explicit_counters": explicit, "positive_completion_calls": positive_calls,
            "per_call_counter_fields": counter_fields,
            "relevant_calls": relevant_calls, "incomplete_calls": incomplete_calls,
            "text_accounting_calls": text_calls, "text_accounting_mismatches": text_mismatches,
            "missing_counters": missing, "invalid_counters": invalid,
            "call_completion_sum": completion_sum, "elided_chars": elided}


def read_raw_accounting(df: pd.DataFrame, root: Path, workers: int) -> pd.DataFrame:
    # Counter examples and known mini-swe-agent elision only. Other scaffolds'
    # unrecorded truncation is not reconstructed or presumed absent.
    selected = (df.scaffold.eq("mini-swe-agent") &
                (df.benchmark_version.ne("2.0") | df.model_dir.isin(["gpt-5", "gpt-5-mini", "gemini-2.5-pro"])))
    # Scan every TB4 scaffold before asserting how many configurations expose
    # counters; absence outside the known examples must not be assumed.
    selected |= df.benchmark_version.eq("4.0")
    records = df.loc[selected, ["benchmark", "rel_path"]].to_dict("records")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        def parse(row):
            return raw_accounting(row, root)
        rows = []
        for i, row in enumerate(pool.map(parse, records), 1):
            rows.append(row)
            if i % 1000 == 0:
                print(f"Read {i:,}/{len(records):,} raw diagnostic trajectories", flush=True)
    return pd.DataFrame(rows)


def reasoning_eligibility(df: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Select complete reported usage, independently of exact reconciliation.

    Prefer per-call sums where counters are exposed. Final-only telemetry is a
    separate source; it never repairs partially reported per-call counters.
    """
    merged = df.merge(raw, on=["benchmark", "rel_path"], how="left", validate="one_to_one")
    has = merged.explicit_counters.gt(0)
    comp = merged.completion_tokens
    positive_comp = np.isfinite(comp) & comp.gt(0)
    strict = has & merged.positive_completion_calls.gt(0) & merged.missing_counters.eq(0) & merged.invalid_counters.eq(0) & positive_comp
    strict &= merged.reasoning_tokens.le(comp)
    merged["explicit_complete"] = strict
    merged["completion_totals_reconcile"] = (merged.call_completion_sum - comp).abs().le(1e-6)
    final_present = merged.final_reasoning_tokens.notna()
    final_comp = pd.to_numeric(merged.final_completion_tokens, errors="coerce")
    final_valid = (np.isfinite(merged.final_reasoning_tokens) & merged.final_reasoning_tokens.ge(0) &
                   merged.final_reasoning_tokens.le(final_comp) & merged.final_completion_tokens.map(finite_number) & final_comp.gt(0) &
                   positive_comp & final_comp.eq(comp))
    merged["final_counter_valid"] = final_valid
    merged["final_counter_present"] = final_present
    merged["any_counter_present"] = has | final_present
    per_call = (has & merged.relevant_calls.gt(0) & merged.incomplete_calls.eq(0) & positive_comp &
                merged.reasoning_tokens.ge(0) & merged.reasoning_tokens.le(comp))
    merged["per_call_usage_valid"] = per_call
    merged["reported_reasoning_tokens"] = merged.reasoning_tokens.where(per_call)
    final_only = merged.per_call_counter_fields.eq(0) & final_valid
    merged.loc[final_only, "reported_reasoning_tokens"] = merged.loc[final_only, "final_reasoning_tokens"]
    merged["reasoning_counter_source"] = np.select([per_call, final_only], ["per_call", "final_only"], default="unusable")
    total = merged.total_tokens
    adjusted = total - merged.reported_reasoning_tokens
    merged["reasoning_eligible"] = ((per_call | final_only) & np.isfinite(total) & total.gt(0) &
                                    total.ge(comp) & np.isfinite(adjusted) & adjusted.gt(0) &
                                    np.isfinite(merged.logged_chars) & merged.logged_chars.ge(0))
    return merged


def accounting_outputs(df: pd.DataFrame, raw: pd.DataFrame) -> tuple[list[dict], pd.DataFrame]:
    merged = reasoning_eligibility(df, raw)
    coverage = []
    for keys, g in merged[merged.explicit_counters.notna()].groupby(["benchmark_version", "scaffold", "model_dir"]):
        coverage.append({"benchmark_version": keys[0], "scaffold": keys[1], "model": keys[2],
                         "aggregation": "record_counts", "records": len(g), "records_exposing_counters": int(g.explicit_counters.gt(0).sum()),
                         "records_with_final_counter": int(g.final_counter_present.sum()),
                         "records_with_any_counter": int(g.any_counter_present.sum()),
                         "records_with_valid_final_counter": int(g.final_counter_valid.sum()),
                         "explicit_complete": int(g.explicit_complete.sum()),
                         "explicit_complete_and_final_totals_reconcile": int((g.explicit_complete & g.completion_totals_reconcile).sum()),
                         "eligible_trajectories": int(g.reasoning_eligible.sum()),
                         "eligible_per_call": int((g.reasoning_eligible & g.reasoning_counter_source.eq("per_call")).sum()),
                         "eligible_final_only": int((g.reasoning_eligible & g.reasoning_counter_source.eq("final_only")).sum()),
                         "eligible_per_call_and_completion_totals_reconcile": int((g.reasoning_eligible & g.reasoning_counter_source.eq("per_call") & g.completion_totals_reconcile).sum()),
                         "explicit_complete_but_primary_ineligible": int((g.explicit_complete & ~g.reasoning_eligible).sum()),
                         "calls_with_text_accounting": int(g.text_accounting_calls.sum()),
                         "calls_failing_text_plus_reasoning_reconciliation": int(g.text_accounting_mismatches.sum()),
                         "eligible_with_full_text_accounting": int((g.reasoning_eligible & g.relevant_calls.gt(0) & g.text_accounting_calls.eq(g.relevant_calls)).sum()),
                         "eligible_full_text_accounting_reconciles": int((g.reasoning_eligible & g.relevant_calls.gt(0) & g.text_accounting_calls.eq(g.relevant_calls) & g.text_accounting_mismatches.eq(0)).sum()),
                         "source_submissions": g[SID].nunique(), "tasks": g.task_name.nunique()})
    rows = []
    specs = {
        "message_chars_per_completion_token": ("message_chars", "completion_tokens > 0"),
        "message_chars_per_nonreason_completion_token": ("message_chars", "completion_tokens - reported reasoning > 0"),
        "reasoning_share_of_completion": ("sum of reported reasoning on positive-completion calls", "completion_tokens > 0"),
        "logged_chars_per_total_token": ("message_chars + reasoning_chars + observation_chars", "total_tokens > 0"),
        "logged_chars_per_nonreason_total_token": ("message_chars + reasoning_chars + observation_chars", "total_tokens - reported reasoning > 0"),
    }
    complete = merged[merged.explicit_complete].copy()
    complete["message_chars_per_completion_token"] = complete.message_chars / complete.completion_tokens
    visible = (complete.completion_tokens - complete.reasoning_tokens).where(lambda x: x > 0)
    complete["message_chars_per_nonreason_completion_token"] = complete.message_chars / visible
    complete["reasoning_share_of_completion"] = complete.reasoning_tokens / complete.completion_tokens
    nonreason_total = (complete.total_tokens - complete.reasoning_tokens).where(lambda x: x > 0)
    complete["logged_chars_per_nonreason_total_token"] = complete.logged_chars / nonreason_total
    for (v, scaffold, model), g in complete.groupby(["benchmark_version", "scaffold", "model_dir"]):
        rows.extend(configuration_rows(g, "reasoning:" + scaffold + "/" + model, specs,
                    scope="strict explicit-counter coverage; ratios use final reported denominators"))
    # Primary paired population: every original and adjusted ratio uses exactly
    # these records. Keep legacy per-call/final variants separately labeled.
    primary = merged[merged.reasoning_eligible & merged.benchmark_version.eq("4.0")].copy()
    primary["reasoning_share_of_completion"] = primary.reported_reasoning_tokens / primary.completion_tokens
    primary["logged_chars_per_total_token"] = primary.logged_chars / primary.total_tokens
    primary["logged_chars_per_nonreason_total_token"] = primary.logged_chars / (primary.total_tokens - primary.reported_reasoning_tokens)
    for (v, scaffold, model), g in primary.groupby(["benchmark_version", "scaffold", "model_dir"]):
        rows.extend(configuration_rows(g, "primary_reasoning:" + scaffold + "/" + model,
                    {"reasoning_share_of_completion": ("explicit reasoning sum across relevant calls, or final-only reported total", "completion_tokens > 0"),
                     "logged_chars_per_total_token": specs["logged_chars_per_total_token"],
                     "logged_chars_per_nonreason_total_token": specs["logged_chars_per_nonreason_total_token"]},
                    scope="eligible explicit per-call totals, or final-only totals; identical ratio population; reconciliation is QC only"))
    final = merged[merged.final_counter_valid].copy()
    final["message_chars_per_completion_token"] = final.message_chars / final.completion_tokens
    final["final_reasoning_share_of_completion"] = final.final_reasoning_tokens / final.completion_tokens
    visible_final = (final.completion_tokens - final.final_reasoning_tokens).where(lambda x: x > 0)
    final["message_chars_per_final_nonreason_completion_token"] = final.message_chars / visible_final
    nonreason_final = (final.total_tokens - final.final_reasoning_tokens).where(lambda x: x > 0)
    final["logged_chars_per_final_nonreason_total_token"] = final.logged_chars / nonreason_final
    for (v, scaffold, model), g in final.groupby(["benchmark_version", "scaffold", "model_dir"]):
        rows.extend(configuration_rows(g, "final_reasoning:" + scaffold + "/" + model, {
            "message_chars_per_completion_token": ("message_chars", "completion_tokens > 0"),
            "final_reasoning_share_of_completion": ("final_metrics.extra reported reasoning", "completion_tokens > 0"),
            "message_chars_per_final_nonreason_completion_token": ("message_chars", "completion_tokens - final reported reasoning > 0"),
            "logged_chars_per_total_token": ("message_chars + reasoning_chars + observation_chars", "total_tokens > 0"),
            "logged_chars_per_final_nonreason_total_token": ("message_chars + reasoning_chars + observation_chars", "total_tokens - final reported reasoning > 0"),
        }, scope="valid final reported reasoning total; no per-call completeness inference"))
    # Elision summaries preserve all main records, adding only explicitly
    # recorded mini-swe-agent omissions. They do not impute hidden text.
    known_elision = merged.elided_chars.where(merged.scaffold.eq("mini-swe-agent"), 0).fillna(0)
    merged["logged_chars_plus_known_elision"] = merged.logged_chars + known_elision
    merged["logged_chars_plus_known_elision_per_total_token"] = merged.logged_chars_plus_known_elision / merged.total_tokens
    for old, new in [("2.0", "2.1"), ("3.0", "4.0")]:
        shared = set(merged.loc[merged.benchmark_version.eq(old), "task_name"]) & set(merged.loc[merged.benchmark_version.eq(new), "task_name"])
        for v in [old, new]:
            for label, g in [("all_retained", merged[merged.benchmark_version.eq(v)]),
                             ("shared_tasks", merged[merged.benchmark_version.eq(v) & merged.task_name.isin(shared)]),
                             ("mini_swe_agent", merged[merged.benchmark_version.eq(v) & merged.scaffold.eq("mini-swe-agent")])]:
                # TB2.0 elision was not scanned beyond the counter examples.
                if v == "2.0":
                    continue
                rows.extend(configuration_rows(g, "known_mini_swe_elision:" + label, {
                    "logged_chars": ("stored logged characters", "none"),
                    "logged_chars_plus_known_elision": ("stored logged characters + explicit mini-swe elided_chars", "none"),
                    "logged_chars_per_total_token": ("stored logged characters", "total_tokens > 0"),
                    "logged_chars_plus_known_elision_per_total_token": ("stored logged characters + explicit mini-swe elided_chars", "total_tokens > 0"),
                }, scope=label + "; known mini-swe-agent omissions only"))
    return rows, pd.DataFrame(coverage)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tb2-csv", type=Path, default=LONG / "trajectory_longitudinal.csv")
    parser.add_argument("--tb34-csv", type=Path, default=LONG / "tb3_tb4/trajectory_longitudinal.csv")
    parser.add_argument("--trajectory-root", type=Path, default=ROOT / "data/trajectories")
    parser.add_argument("--out-dir", type=Path, default=LONG)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.out_dir.resolve().is_relative_to(args.trajectory_root.resolve()):
        parser.error("Diagnostic outputs must be outside original trajectories")
    a, b = read_dataset(args.tb2_csv), read_dataset(args.tb34_csv)
    for df, old, new, expected in [(a, "2.0", "2.1", 89), (b, "3.0", "4.0", 66)]:
        shared = set(df.loc[df.benchmark_version.eq(old), "task_name"]) & set(df.loc[df.benchmark_version.eq(new), "task_name"])
        if len(shared) != expected:
            raise ValueError(f"{old}->{new}: expected {expected} shared tasks, got {len(shared)}")
    df = pd.concat([a, b], ignore_index=True)
    versions = pd.concat([version_comparisons(a, "2.0", "2.1"), version_comparisons(b, "3.0", "4.0")], ignore_index=True)
    configurations = configuration_comparisons(df)
    raw = read_raw_accounting(df, args.trajectory_root, max(1, args.workers))
    accounting, coverage = accounting_outputs(df, raw)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for filename, table in [
        ("rq3_3_aggregation_diagnostics.csv", versions),
        ("rq3_3_configuration_diagnostics.csv", pd.DataFrame(configurations + accounting)),
        ("rq3_3_reasoning_coverage.csv", coverage),
    ]:
        table.to_csv(args.out_dir / filename, index=False, float_format="%.17g")
        print(f"Wrote {filename}: {len(table)} rows", flush=True)


if __name__ == "__main__":
    main()
