"""Injecteerbare klok. Enige tijdsbron voor state-modules.

Standaard tijd.time; tests zetten een FakeClock. Geen enkele state-module
roept nog time.time() rechtstreeks aan.
"""

import time as _time

_provider = _time.time


def now() -> float:
    return _provider()


def now_int() -> int:
    return int(_provider())


def set_provider(fn) -> None:
    global _provider
    _provider = fn


def reset() -> None:
    global _provider
    _provider = _time.time


class FakeClock:
    """Alleen voor tests. Roepbaar als provider, met advance()/set()."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = float(start)

    def __call__(self) -> float:
        return self._t

    def advance(self, seconden: float) -> None:
        self._t += float(seconden)

    def set(self, t: float) -> None:
        self._t = float(t)