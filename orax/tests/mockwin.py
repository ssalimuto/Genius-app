"""Kivy headless window for local tests: mock GL, no display. Import before anything else from Kivy."""
import os

os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ["KIVY_WINDOW"] = ""
import kivy.core.window as kcw  # noqa: E402
from kivy.core.window import WindowBase  # noqa: E402


class WindowMock(WindowBase):
    def create_window(self, *a):
        super().create_window(*a)

    def flip(self):
        pass

    def mainloop(self):
        pass

    def screenshot(self, *a, **k):
        return None

    def _set_window_pos(self, *a):
        pass


if kcw.Window is None:
    kcw.Window = WindowMock()
