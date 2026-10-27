"""Minimal stand-ins for the `sublime` and `sublime_plugin` modules, enough to drive the plugin."""
import sys
import types


class Region:
    def __init__(self, a, b=None):
        self.a, self.b = a, a if b is None else b

    def begin(self):
        return min(self.a, self.b)

    def end(self):
        return max(self.a, self.b)

    def contains(self, point):
        return self.begin() <= point <= self.end()

    def __repr__(self):
        return "Region({}, {})".format(self.a, self.b)


class Settings(dict):
    def get(self, key, default=None):
        return dict.get(self, key, default)

    def set(self, key, value):
        self[key] = value

    def add_on_change(self, *_):
        pass

    def clear_on_change(self, *_):
        pass


class View:
    _next = 1

    def __init__(self, text, scope="text.html.markdown", file_name=None):
        self._id, View._next = View._next, View._next + 1
        self.text, self.scope, self._file = text, scope, file_name
        self.regions, self.status, self.popups = {}, {}, []
        self._settings = Settings()
        self.window_obj = None

    def id(self):
        return self._id

    def is_valid(self):
        return True

    def size(self):
        return len(self.text)

    def substr(self, region):
        return self.text[region.begin():region.end()]

    def file_name(self):
        return self._file

    def settings(self):
        return self._settings

    def match_selector(self, _point, selector):
        return any(self.scope.startswith(s.strip()) for s in selector.split(","))

    def add_regions(self, key, regions, *_args):
        self.regions[key] = list(regions)

    def get_regions(self, key):
        return list(self.regions.get(key, []))

    def erase_regions(self, key):
        self.regions.pop(key, None)

    def set_status(self, key, value):
        self.status[key] = value

    def erase_status(self, key):
        self.status.pop(key, None)

    def replace(self, _edit, region, text):
        self.text = self.text[:region.begin()] + text + self.text[region.end():]

    def show_popup(self, content, *_args, **kwargs):
        self.popups.append((content, kwargs))

    def hide_popup(self):
        pass

    def text_point(self, row, col):
        lines = self.text.split("\n")
        return sum(len(line) + 1 for line in lines[:row]) + col

    def line(self, point):
        start = self.text.rfind("\n", 0, point) + 1
        end = self.text.find("\n", point)
        return Region(start, len(self.text) if end < 0 else end)

    def window(self):
        return self.window_obj

    def run_command(self, name, args=None):
        COMMANDS[name](self).run(None, **(args or {}))


COMMANDS = {}
SETTINGS = Settings()


def _fail(message):
    raise AssertionError(message)


def install():
    sublime = types.ModuleType("sublime")
    sublime.Region = Region
    for i, name in enumerate(["DRAW_NO_FILL", "DRAW_NO_OUTLINE", "DRAW_SQUIGGLY_UNDERLINE",
                              "HIDE_ON_MINIMAP", "HIDE_ON_MOUSE_MOVE_AWAY"]):
        setattr(sublime, name, 1 << i)
    sublime.HOVER_TEXT = 1
    sublime.load_settings = lambda _name: SETTINGS
    sublime.set_timeout_async = lambda fn, _delay=0: fn()
    sublime.set_timeout = lambda fn, _delay=0: fn()
    sublime.status_message = lambda _msg: None
    sublime.error_message = _fail
    sublime.windows = lambda: []

    plugin = types.ModuleType("sublime_plugin")

    class EventListener:
        pass

    class TextCommand:
        def __init__(self, view):
            self.view = view

        def __init_subclass__(cls, **kw):
            super().__init_subclass__(**kw)
            # PlagxApplyFixCommand -> plagx_apply_fix, as Sublime names commands
            name = "".join("_" + c.lower() if c.isupper() else c for c in cls.__name__[:-len("Command")])
            COMMANDS[name.lstrip("_")] = cls

    plugin.EventListener = EventListener
    plugin.TextCommand = TextCommand
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = plugin
