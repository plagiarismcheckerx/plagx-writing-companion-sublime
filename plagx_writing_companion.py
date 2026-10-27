"""Plagx Writing Companion for Sublime Text: a thin layer over the Plagx Cite and Preflight cores."""
import html
import threading

import sublime
import sublime_plugin

from .plagx_writing.core import bibliography, check_bib, readiness, run_draft
from .vendor.plagx_cite import cite_in_text, format_reference, lookup_doi, normalize_doi

SETTINGS_FILE = "Plagx Writing Companion.sublime-settings"
STATUS_KEY = "plagx"
LEVELS = ("error", "warning", "info")
REGION_SCOPES = {"error": "region.redish", "warning": "region.yellowish", "info": "region.bluish"}
REGION_FLAGS = (sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SQUIGGLY_UNDERLINE
                | sublime.HIDE_ON_MINIMAP)

# view id -> {"result": draft result or None, "issues": {level: [issue, ...]}}
STATE = {}
PENDING = {}


def settings():
    return sublime.load_settings(SETTINGS_FILE)


def setting_dict():
    s = settings()
    keys = ("style", "min_words", "max_words", "required_headings", "checks", "selector", "check_on")
    return {k: s.get(k) for k in keys}


def is_bib(view):
    name = (view.file_name() or "").lower()
    return name.endswith(".bib") or view.match_selector(0, "text.bibtex")


def is_draft(view):
    if view.settings().get("is_widget") or is_bib(view):
        return False
    return view.match_selector(0, settings().get("selector") or "text.html.markdown, text.plain, text.tex")


def clear(view):
    for level in LEVELS:
        view.erase_regions("plagx." + level)
    view.erase_status(STATUS_KEY)
    STATE.pop(view.id(), None)


def show_issues(view, issues):
    """Draws issues ({level, start, end, message, ...}) as squiggly underlines."""
    by_level = {level: [] for level in LEVELS}
    for issue in issues:
        by_level.setdefault(issue["level"], []).append(issue)
    for level, items in by_level.items():
        regions = [sublime.Region(i["start"], max(i["end"], i["start"] + 1)) for i in items]
        view.add_regions("plagx." + level, regions, REGION_SCOPES.get(level, "region.bluish"), "", REGION_FLAGS)
    return by_level


def check_view(view):
    if not view.is_valid():
        return None
    result = run_draft(view.substr(sublime.Region(0, view.size())), setting_dict())
    STATE[view.id()] = {"result": result, "issues": show_issues(view, result["issues"])}
    r = readiness(result)
    icon = ("✓" if not r["warnings"] else "ℹ") if r["ready"] else "⚠"
    view.set_status(STATUS_KEY, "{} {:,} words · {} min · {}".format(icon, r["words"], r["minutes"], r["label"]))
    return result


def schedule(view, delay):
    vid = view.id()
    PENDING[vid] = PENDING.get(vid, 0) + 1
    ticket = PENDING[vid]

    def run():
        if PENDING.get(vid) == ticket:
            check_view(view)

    sublime.set_timeout_async(run, delay)


class PlagxListener(sublime_plugin.EventListener):
    def _auto(self, view, delay=0):
        if settings().get("check_on", "type") != "manual" and is_draft(view):
            schedule(view, delay)

    def on_load_async(self, view):
        self._auto(view)

    def on_activated_async(self, view):
        if view.id() not in STATE:
            self._auto(view)

    def on_modified_async(self, view):
        if settings().get("check_on", "type") == "type":
            self._auto(view, 600)

    def on_post_save_async(self, view):
        self._auto(view)

    def on_close(self, view):
        STATE.pop(view.id(), None)
        PENDING.pop(view.id(), None)

    def on_hover(self, view, point, hover_zone):
        if hover_zone != sublime.HOVER_TEXT or view.id() not in STATE:
            return
        rows = []
        for level in LEVELS:
            regions = view.get_regions("plagx." + level)
            issues = STATE[view.id()]["issues"].get(level, [])
            for index, region in enumerate(regions):
                if index < len(issues) and region.contains(point):
                    issue = issues[index]
                    row = "<b>{}</b> {}".format(level.capitalize(), html.escape(issue["message"]))
                    fix = issue.get("suggestion")
                    if fix is not None:
                        label = "Remove" if fix == "" else "Replace with “{}”".format(html.escape(fix))
                        row += ' <a href="fix:{}:{}">{}</a>'.format(level, index, label)
                    rows.append(row)
        if not rows:
            return

        def navigate(href):
            _, level, index = href.split(":")
            view.run_command("plagx_apply_fix", {"level": level, "index": int(index)})
            view.hide_popup()

        content = '<body id="plagx"><div>{}</div><div style="color: var(--foreground); opacity: 0.6">Plagx</div></body>'
        view.show_popup(content.format("<br>".join(rows)), sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                        point, max_width=600, on_navigate=navigate)


class PlagxApplyFixCommand(sublime_plugin.TextCommand):
    def run(self, edit, level, index):
        state = STATE.get(self.view.id())
        regions = self.view.get_regions("plagx." + level)
        if not state or index >= len(regions):
            return
        fix = state["issues"][level][index].get("suggestion")
        if fix is not None:
            self.view.replace(edit, regions[index], fix)


class PlagxCheckDraftCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        check_view(self.view)


class PlagxShowReadinessCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        result = check_view(self.view)
        if not result:
            return
        r = readiness(result)
        text = ("<b>{label}</b><br>{words:,} words · {minutes} min read · Flesch {flesch}<br>"
                "{errors} errors · {warnings} warnings · {infos} notes").format(**r)
        self.view.show_popup('<body id="plagx-readiness">{}</body>'.format(text), max_width=500)

    def is_enabled(self):
        return not is_bib(self.view)


class PlagxClearCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        clear(self.view)


class PlagxFormatBibliographyCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        style = settings().get("style", "apa")
        _, entries = bibliography(self.view.substr(sublime.Region(0, self.view.size())), style)
        if not entries:
            sublime.status_message("Plagx: no BibTeX entries found")
            return
        heading = "Works Cited" if style == "mla" else "References"
        out = self.view.window().new_file()
        out.set_name(heading)
        out.assign_syntax("Packages/Markdown/Markdown.sublime-syntax")
        out.run_command("append", {"characters": "# {}\n\n{}\n".format(heading, "\n\n".join(entries))})

    def is_enabled(self):
        return is_bib(self.view)


class PlagxCheckBibliographyCommand(sublime_plugin.TextCommand):
    OPTIONS = [
        ["Offline checks", "Duplicates, missing authors, titles, years and invalid DOIs"],
        ["Also verify DOIs online", "Looks each DOI up on Crossref"],
    ]

    def run(self, edit):
        self.view.window().show_quick_panel(self.OPTIONS, self.on_pick)

    def on_pick(self, choice):
        if choice < 0:
            return
        view = self.view
        source = view.substr(sublime.Region(0, view.size()))
        sublime.status_message("Plagx: checking references…")

        def work():
            result = check_bib(source, check_dois=choice == 1)
            issues = []
            for issue in result["issues"]:
                line = view.line(view.text_point(issue["line"], 0))
                issues.append(dict(issue, start=line.begin(), end=line.end(),
                                   message="{}: {}".format(issue["ref"], issue["message"])))
            STATE[view.id()] = {"result": None, "issues": show_issues(view, issues)}
            summary = "Plagx: {} references · {} errors · {} warnings".format(
                result["references"], result["errors"], result["warnings"])
            view.set_status(STATUS_KEY, summary)
            sublime.status_message(summary)

        threading.Thread(target=work, daemon=True).start()

    def is_enabled(self):
        return is_bib(self.view)


class PlagxCiteDoiCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.window().show_input_panel("DOI or doi.org link:", "", self.on_done, None, None)

    def on_done(self, value):
        doi = normalize_doi(value.strip())
        if not doi:
            sublime.error_message("Plagx: enter a valid DOI, e.g. 10.1037/0003-066X.59.1.29")
            return
        sublime.status_message("Plagx: looking up DOI on Crossref…")
        threading.Thread(target=self.lookup, args=(doi,), daemon=True).start()

    def lookup(self, doi):
        try:
            ref = lookup_doi(doi)
        except Exception as err:  # noqa: BLE001 - shown to the user as is
            sublime.error_message("Plagx: DOI lookup failed. {}".format(err))
            return
        style = settings().get("style", "apa")
        choices = [
            [format_reference(ref, style=style), "Reference list entry"],
            [cite_in_text(ref, style=style), "In-text citation"],
            [cite_in_text(ref, style=style, narrative=True), "Narrative citation"],
        ]

        def insert(i):
            if i >= 0:
                self.view.run_command("insert", {"characters": choices[i][0]})

        sublime.set_timeout(lambda: self.view.window().show_quick_panel(choices, insert), 0)


def plugin_loaded():
    settings().add_on_change("plagx", lambda: [schedule(v, 0) for w in sublime.windows()
                                               for v in w.views() if is_draft(v)])
    for window in sublime.windows():
        for view in window.views():
            if is_draft(view) and settings().get("check_on", "type") != "manual":
                schedule(view, 0)


def plugin_unloaded():
    settings().clear_on_change("plagx")
    for window in sublime.windows():
        for view in window.views():
            clear(view)
