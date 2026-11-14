"""Load main.py on a computer with no screen: Kivy, jnius and android are replaced by harmless stand-ins.

Only for tests. It lets the answer path (prompts, routing, search, free AIs) run exactly as in the app.
"""
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
import types


class _Any:
    """A stand-in that accepts any call, attribute, maths or subclassing."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _Any()

    def __call__(self, *a, **k):
        return _Any()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __index__(self):
        return 0

    def __len__(self):
        return 0

    def __getitem__(self, k):
        return _Any()

    def __setitem__(self, k, v):
        pass

    def __add__(self, o):
        return o

    __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = __add__

    def __lt__(self, o):
        return False

    __gt__ = __le__ = __ge__ = __lt__

    def __str__(self):
        return ""


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _Any()


class _Widget(metaclass=_Meta):
    def __init__(self, *a, **k):
        self.children = []

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _Any()

    def bind(self, *a, **k):
        pass

    def add_widget(self, *a, **k):
        pass

    def remove_widget(self, *a, **k):
        pass


def _dp(v):
    try:
        return float(v)
    except Exception:
        return 0.0


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        if name in ("dp", "sp"):
            return _dp
        if name[:1].isupper():
            cls = type(name, (_Widget,), {})
            setattr(self, name, cls)
            return cls
        return _Any()


class _Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    ROOTS = ("kivy", "jnius", "android", "plyer", "pyjnius")

    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in self.ROOTS:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        m = _StubModule(spec.name)
        m.__path__ = []
        return m

    def exec_module(self, module):
        pass


def install():
    for k in list(sys.modules):
        if k.split(".")[0] in _Finder.ROOTS:
            del sys.modules[k]
    sys.meta_path.insert(0, _Finder())


def load_app(path, workdir):
    """Import an app file as a module (its __main__ block does not run). Files it writes go to workdir."""
    install()
    path = os.path.abspath(path)
    os.makedirs(workdir, exist_ok=True)
    os.chdir(workdir)
    name = "app_" + os.path.basename(os.path.dirname(os.path.abspath(path))).replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
