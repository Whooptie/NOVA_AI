"""
core/opstarttijd.py

Onthoudt het moment waarop Nova klaar was met opstarten (alle modules geladen).
main.py roept markeer_klaar() één keer aan, direct na loader.discover_and_load().
De zelftest vergelijkt dat moment met het tijdstip waarop het proces startte en
toont zo Nova's ECHTE opstarttijd.

Bewust een los hulpbestand zonder init_module(): de module_loader slaat het over.
"""

import time

_klaar = None     # epoch-seconden waarop Nova klaar was met opstarten


def markeer_klaar(nu=None):
    """Legt het 'klaar'-moment vast. Alleen de eerste aanroep telt."""
    global _klaar
    if _klaar is None:
        _klaar = time.time() if nu is None else nu
    return _klaar


def klaar_tijdstip():
    """Epoch-seconden waarop Nova klaar was met opstarten, of None als dat nog niet is gebeurd."""
    return _klaar