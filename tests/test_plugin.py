"""Loads the package the way Sublime does, with a fake `sublime` API. Run: python -m unittest discover -s tests"""
import ast
import importlib
import importlib.util
import json
import os
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACKAGE = "Plagx Writing Companion"
sys.path.insert(0, HERE)

import fake_sublime  # noqa: E402

fake_sublime.install()

# Sublime imports each package folder as a namespace package named after the folder.
_spec = importlib.util.spec_from_loader(PACKAGE, loader=None, is_package=True)
_pkg = importlib.util.module_from_spec(_spec)
_pkg.__path__ = [ROOT]
sys.modules[PACKAGE] = _pkg
plugin = importlib.import_module(PACKAGE + ".plagx_writing_companion")
core = sys.modules[PACKAGE + ".plagx_writing.core"]


def read(name):
    with open(os.path.join(ROOT, "examples", name), encoding="utf-8") as f:
        return f.read()


class Python38Syntax(unittest.TestCase):
    def test_package_files_parse_as_python_38(self):
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in ("tests", ".git")]
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(base, name), encoding="utf-8") as f:
                        ast.parse(f.read(), filename=name, feature_version=(3, 8))


class Core(unittest.TestCase):
    def test_draft_options(self):
        opts = core.draft_options({"style": "mla", "min_words": None, "max_words": 500,
                                   "checks": [], "required_headings": []})
        self.assertEqual(opts, {"style": "mla", "max_words": 500})

    def test_utf16_offsets_become_string_indices(self):
        to_index = core.utf16_to_index("a\U0001F600b")
        self.assertEqual([to_index(0), to_index(1), to_index(3)], [0, 1, 2])

    def test_draft_finds_planted_problems(self):
        codes = {i["code"] for i in core.run_draft(read("sample-essay.md"), {})["issues"]}
        for code in ("double-space", "space-before-punctuation", "repeated-word", "lowercase-i",
                     "citation-no-reference"):
            self.assertIn(code, codes)

    def test_word_limit(self):
        codes = {i["code"] for i in core.run_draft(read("sample-essay.md"), {"max_words": 10})["issues"]}
        self.assertIn("word-count-high", codes)

    def test_bibliography_and_checks(self):
        refs, entries = core.bibliography(read("sample.bib"), "apa")
        self.assertEqual(len(refs), 4)
        self.assertTrue(any("Smith, J. (2020)" in e for e in entries))
        result = core.check_bib(read("sample.bib"))
        codes = {i["code"] for i in result["issues"]}
        self.assertTrue({"duplicate", "missing-title"} <= codes)
        missing = next(i for i in result["issues"] if i["code"] == "missing-title")
        self.assertGreater(missing["line"], 0)
        self.assertEqual(missing["line"], core.bib_key_line(read("sample.bib"), "notitle"))


class Plugin(unittest.TestCase):
    def setUp(self):
        fake_sublime.SETTINGS.clear()
        with open(os.path.join(ROOT, PACKAGE + ".sublime-settings"), encoding="utf-8") as f:
            defaults = json.loads("\n".join(l for l in f.read().splitlines() if not l.strip().startswith("//")))
        fake_sublime.SETTINGS.update(defaults)

    def test_draft_view_gets_underlines_status_and_quick_fix(self):
        view = fake_sublime.View(read("sample-essay.md"))
        plugin.PlagxListener().on_load_async(view)
        self.assertGreater(sum(len(view.get_regions("plagx." + lvl)) for lvl in plugin.LEVELS), 0)
        self.assertRegex(view.status["plagx"], r"words · \d+ min")

        issues = plugin.STATE[view.id()]["issues"]
        level, index = next((lvl, i) for lvl in plugin.LEVELS for i, x in enumerate(issues[lvl])
                            if x["code"] == "repeated-word")
        region = view.get_regions("plagx." + level)[index]
        plugin.PlagxListener().on_hover(view, region.begin(), 1)
        self.assertIn("fix:{}:{}".format(level, index), view.popups[-1][0])
        view.run_command("plagx_apply_fix", {"level": level, "index": index})
        self.assertNotIn("to to", view.text)

    def test_bib_files_are_not_draft_checked(self):
        view = fake_sublime.View(read("sample.bib"), scope="text.bibtex", file_name="refs.bib")
        plugin.PlagxListener().on_load_async(view)
        self.assertNotIn(view.id(), plugin.STATE)

    def test_manual_mode_waits_for_the_command(self):
        fake_sublime.SETTINGS["check_on"] = "manual"
        view = fake_sublime.View(read("sample-essay.md"))
        plugin.PlagxListener().on_load_async(view)
        self.assertNotIn(view.id(), plugin.STATE)
        view.run_command("plagx_check_draft")
        self.assertIn(view.id(), plugin.STATE)

    def test_check_bibliography_marks_entry_lines(self):
        view = fake_sublime.View(read("sample.bib"), scope="text.bibtex", file_name="refs.bib")
        jobs = []
        real_thread = threading.Thread
        threading.Thread = lambda target, **_: jobs.append(target) or type("T", (), {"start": lambda s: None})()
        try:
            fake_sublime.COMMANDS["plagx_check_bibliography"](view).on_pick(0)
        finally:
            threading.Thread = real_thread
        jobs[0]()
        self.assertTrue(view.get_regions("plagx.error") + view.get_regions("plagx.warning"))
        self.assertIn("4 references", view.status["plagx"])

    def test_palette_commands_exist(self):
        with open(os.path.join(ROOT, "Default.sublime-commands"), encoding="utf-8") as f:
            for entry in json.load(f):
                if entry["command"].startswith("plagx_"):
                    self.assertIn(entry["command"], fake_sublime.COMMANDS)


if __name__ == "__main__":
    unittest.main()
