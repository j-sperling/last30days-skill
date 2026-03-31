# ruff: noqa: E402
import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import store
from lib import schema


def load_last30days_module():
    spec = importlib.util.spec_from_file_location("last30days_cli", SCRIPTS_DIR / "last30days.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SkillSurfaceV3Tests(unittest.TestCase):
    def test_cli_parser_accepts_store_flag(self):
        module = load_last30days_module()
        parser = module.build_parser()
        args = parser.parse_args(["test", "topic", "--store"])
        self.assertTrue(args.store)
        self.assertEqual(args.topic, ["test", "topic"])

    def test_store_finding_from_candidate_mentions_corroboration(self):
        candidate = schema.Candidate(
            candidate_id="c1",
            item_id="i1",
            source="reddit",
            sources=["reddit", "grounding"],
            title="Title",
            url="https://example.com",
            snippet="Snippet",
            subquery_labels=["primary"],
            native_ranks={"primary:reddit": 1},
            local_relevance=0.8,
            freshness=80,
            engagement=12,
            source_quality=0.8,
            rrf_score=0.2,
            final_score=88.0,
            explanation="Useful explanation",
            source_items=[
                schema.SourceItem(
                    item_id="i1",
                    source="reddit",
                    title="Title",
                    body="Primary body",
                    url="https://example.com",
                    author="alice",
                ),
                schema.SourceItem(
                    item_id="i2",
                    source="grounding",
                    title="Title",
                    body="Grounded body",
                    url="https://example.com",
                    author="newsroom",
                ),
            ],
        )
        finding = store.finding_from_candidate(candidate)
        self.assertEqual(finding["source"], "reddit")
        self.assertEqual(finding["author"], "alice")
        self.assertIn("Also seen in: grounding.", finding["summary"])

    def test_openclaw_variant_files_exist(self):
        for path in [
            REPO_ROOT / "variants" / "open" / "SKILL.md",
            REPO_ROOT / "variants" / "open" / "context.md",
            REPO_ROOT / "variants" / "open" / "references" / "watchlist.md",
            REPO_ROOT / "variants" / "open" / "references" / "briefing.md",
            REPO_ROOT / "variants" / "open" / "references" / "history.md",
            REPO_ROOT / "variants" / "open" / "references" / "research.md",
        ]:
            self.assertTrue(path.exists(), path)

    def test_skill_docs_and_sync_cover_openclaw(self):
        root_skill = (REPO_ROOT / "SKILL.md").read_text()
        open_skill = (REPO_ROOT / "variants" / "open" / "SKILL.md").read_text()
        sync_script = (REPO_ROOT / "scripts" / "sync.sh").read_text()
        self.assertIn("$HOME/.openclaw/skills/last30days", root_skill)
        self.assertLess(
            root_skill.index("$HOME/.openclaw/workspace/skills/last30days"),
            root_skill.index("$HOME/.openclaw/skills/last30days"),
        )
        self.assertLess(
            open_skill.index("$HOME/.openclaw/workspace/skills/last30days"),
            open_skill.index("$HOME/.openclaw/skills/last30days"),
        )
        self.assertIn("python3 \"${SKILL_ROOT}/scripts/last30days.py\" $ARGUMENTS --emit=compact", root_skill)
        self.assertIn("$HOME/.openclaw/skills/last30days", sync_script)
        self.assertIn("watchlist.py", sync_script)
        self.assertIn("briefing.py", sync_script)
        self.assertIn("store.py", sync_script)

    def test_gemini_extension_exposes_current_web_backend_settings(self):
        payload = json.loads((REPO_ROOT / "gemini-extension.json").read_text())
        settings = payload["settings"]
        env_vars = [setting["envVar"] for setting in settings]
        self.assertEqual(
            [
                "SCRAPECREATORS_API_KEY",
                "AUTH_TOKEN",
                "CT0",
                "BSKY_HANDLE",
                "BSKY_APP_PASSWORD",
                "TRUTHSOCIAL_TOKEN",
            ],
            env_vars[:6],
        )
        self.assertLess(env_vars.index("BRAVE_API_KEY"), env_vars.index("GOOGLE_API_KEY"))
        self.assertLess(env_vars.index("SERPER_API_KEY"), env_vars.index("GOOGLE_API_KEY"))
        self.assertLess(env_vars.index("GOOGLE_API_KEY"), env_vars.index("LAST30DAYS_REASONING_PROVIDER"))
        descriptions = {setting["envVar"]: setting["description"] for setting in settings}
        self.assertIn("Optional Gemini planner and reranker", descriptions["GOOGLE_API_KEY"])
        self.assertNotIn("required", descriptions["GOOGLE_API_KEY"].lower())
        self.assertIn("Advanced override", descriptions["LAST30DAYS_PLANNER_MODEL"])

    def test_readme_frontmatter_uses_v3_free_first_story(self):
        readme = (REPO_ROOT / "README.md").read_text()
        active = readme.split("## Historical release notes")[0]
        self.assertIn("# /last30days v3.0.0", readme)
        self.assertIn("what people are actually saying right now", active)
        self.assertIn("/last30days setup", active)
        self.assertIn("If you add one paid key, make it", active)
        self.assertIn("Brave or Serper", active)
        self.assertNotIn("PARALLEL_API_KEY", active)
        self.assertNotIn("OPENROUTER_API_KEY", active)
        self.assertIn("## Historical release notes", readme)

    def test_root_skill_restores_interactive_prompt_flow(self):
        root_skill = (REPO_ROOT / "SKILL.md").read_text()
        self.assertIn("allowed-tools: Bash, Read, Write, AskUserQuestion, WebSearch", root_skill)
        self.assertIn("what people are actually saying right now", root_skill)
        self.assertIn("works out of the box", root_skill)
        self.assertIn("`/last30days setup` is the recommended first upgrade path", root_skill)
        self.assertIn("QUERY_TYPE", root_skill)
        self.assertIn("Parsed intent:", root_skill)
        self.assertIn("- TOPIC = {TOPIC}", root_skill)
        self.assertIn('- TARGET_TOOL = {TARGET_TOOL or "unknown"}', root_skill)
        self.assertIn("Research typically takes 2-8 minutes. Starting now.", root_skill)
        self.assertIn("## Web fallback for plugin hosts", root_skill)
        self.assertIn('python3 "${SKILL_ROOT}/scripts/last30days.py" --diagnose', root_skill)
        self.assertIn("native_web_backend", root_skill)
        self.assertIn('`"grounding"` appears in `available_sources`', root_skill)
        self.assertIn("copy-paste-ready prompt", root_skill)
        self.assertIn("## Display contract", root_skill)
        self.assertNotIn("primaryEnv:", root_skill)
        self.assertNotIn("The runtime is a single v3 pipeline", root_skill)

    def test_openclaw_one_shot_reference_restores_guided_persistent_flow(self):
        open_skill = (REPO_ROOT / "variants" / "open" / "SKILL.md").read_text()
        research_ref = (REPO_ROOT / "variants" / "open" / "references" / "research.md").read_text()
        self.assertIn("allowed-tools: Bash, Read, Write, AskUserQuestion, WebSearch", open_skill)
        self.assertIn("last30days to remember what it found", open_skill)
        self.assertIn("watchlist topics", open_skill)
        self.assertIn("Brave and Serper are optional native web upgrades", open_skill)
        self.assertIn("Update it after meaningful", open_skill)
        self.assertNotIn("This variant keeps the v3 pipeline", open_skill)
        self.assertNotIn("One reasoning provider is required", open_skill)
        self.assertIn("Parsed intent:", research_ref)
        self.assertIn('WebSearch("{TOPIC} X twitter handle site:x.com")', research_ref)
        self.assertIn('--emit=compact --store', research_ref)
        self.assertIn('python3 "${SKILL_ROOT}/scripts/last30days.py" --diagnose', research_ref)
        self.assertIn("native_web_backend", research_ref)
        self.assertIn('`"grounding"` appears in `available_sources`', research_ref)
        self.assertIn("What I learned", research_ref)
        self.assertIn("Stats", research_ref)
        self.assertIn("AskUserQuestion", research_ref)
        self.assertIn("stay in expert mode", research_ref)

    def test_search_quality_artifacts_are_ignored_and_untracked(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text()
        self.assertIn("tmp/search-quality*/", gitignore)


if __name__ == "__main__":
    unittest.main()
