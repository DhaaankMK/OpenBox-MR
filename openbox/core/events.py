"""Barramento de eventos simples (publish/subscribe)."""
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._subs = defaultdict(list)

    def on(self, name, fn):
        self._subs[name].append(fn)
        return fn

    def off(self, name, fn):
        if fn in self._subs.get(name, []):
            self._subs[name].remove(fn)

    def emit(self, name, **data):
        for fn in list(self._subs.get(name, [])):
            try:
                fn(**data)
            except Exception as exc:  # um ouvinte quebrado não derruba o app
                print(f"[events] erro em '{name}': {exc!r}")
