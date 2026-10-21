"""Offline regression checks for shared scraper payload parsing."""

import importlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.mining import rsc_helpers as rsc


class RscHelperTests(unittest.TestCase):
    def test_json_prefix_allows_trailing_records_and_rejects_invalid_json(self):
        self.assertEqual(rsc.parse_json_prefix('  {"tasks": [1]}\nnext record'), {"tasks": [1]})
        self.assertIsNone(rsc.parse_json_prefix("not JSON"))

    def test_json_references_skip_non_json_records(self):
        payload = 'a:{"items": ["$b"]}\nb:[1, 2]\nc:not-json\n'
        self.assertEqual(rsc.extract_rsc_references(payload), {"a": {"items": ["$b"]}, "b": [1, 2]})

    def test_text_records_can_span_payload_chunks(self):
        payload = ['a:{"message":"$b"}\n', "b:T", "5,he", "llo"]
        references = rsc.build_rsc_reference_lookup(payload)
        self.assertEqual(references, {"a": {"message": "$b"}, "b": "hello"})
        self.assertEqual(rsc.resolve_rsc_references("$a", references), {"message": "hello"})

    def test_embedded_text_records_are_discovered_independently(self):
        content = "before b:T5,hello after"
        payload = [f"a:T{len(content):x},{content}"]
        self.assertEqual(rsc.extract_rsc_text_references(payload), {"a": content, "b": "hello"})

    def test_nested_references_preserve_unknown_values_and_stop_cycles(self):
        references = {"a": "$b", "b": "$a", "c": {"value": [1, "$d"]}, "d": "text"}
        self.assertEqual(rsc.resolve_rsc_references("$a", references), "$a")
        self.assertEqual(rsc.resolve_rsc_references(["$c", "$c", "$missing"], references), [
            {"value": [1, "text"]}, {"value": [1, "text"]}, "$missing",
        ])

    def test_both_scrapers_use_the_shared_parser(self):
        for name in ("00_scrape_terminal_bench_2_0_leaderboard", "02_scrape_terminal_bench_2_0_task_catalog"):
            module = importlib.import_module(f"scripts.mining.{name}")
            for helper in ("build_rsc_reference_lookup", "resolve_rsc_references"):
                self.assertIs(getattr(module, helper), getattr(rsc, helper))

    def test_trajectory_extraction_resolves_references_without_network_access(self):
        scraper = importlib.import_module("scripts.mining.00_scrape_terminal_bench_2_0_leaderboard")
        payload = '0:{"trajectory":{"messages":[{"content":"$a"}]}}\na:T5,hello'
        page = f"<script>self.__next_f.push({json.dumps([1, payload])})</script>"
        self.assertEqual(scraper.extract_trajectory(page), {"messages": [{"content": "hello"}]})

    def test_task_catalog_resolves_references_without_network_access(self):
        scraper = importlib.import_module("scripts.mining.02_scrape_terminal_bench_2_0_task_catalog")
        payload = '0:{"tasks":[{"id":"task","instruction":"$a","tags":"$b"}]}\na:T5,hello\nb:["shell"]'
        page = f"<script>self.__next_f.push({json.dumps([1, payload])})</script>"
        self.assertEqual(scraper.parse_tasks(page), [{
            "id": "task", "category": "", "difficulty": "", "description": "hello", "tags": ["shell"],
        }])

    def test_task_catalog_supports_direct_script_execution(self):
        scraper = importlib.import_module("scripts.mining.02_scrape_terminal_bench_2_0_task_catalog")
        script = Path(scraper.__file__).resolve()
        result = subprocess.run(
            [sys.executable, "-B", str(script), "--help"], cwd=script.parent,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--json-output", result.stdout)


if __name__ == "__main__":
    unittest.main()
