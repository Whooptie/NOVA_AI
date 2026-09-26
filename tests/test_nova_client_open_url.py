# tests/test_nova_client_open_url.py
#
# date_calendar_roadmap.md Onderdeel 5 (26 september 2026): de
# veiligheidscontrole in nova_client.py voordat een "open_url"-
# commando van battleserver uitgevoerd wordt.
#
# Zelfde aanpak als test_nova_client_app_controller.py: nova_client.py
# zelf kan hier niet geïmporteerd worden (Windows-only imports, en het
# bestand draait op de laptop, niet op battleserver). Daarom staat
# hieronder een LETTERLIJKE KOPIE van is_toegestane_url() en de twee
# constanten. Wijzig je die in nova_client.py, pas dan ook deze kopie
# aan. De laatste test hieronder controleert dat automatisch, zodra
# nova_client.py vanuit de projectmap bereikbaar is.

import ast
import os
from urllib.parse import urlparse

import pytest


# ---------------------------------------------------------------
# KOPIE uit nova_client.py -- niet los aanpassen
# ---------------------------------------------------------------
URL_WHITELIST_DOMEINEN = (
    "wikipedia.org",
)

MAX_URL_LENGTE = 2000


def is_toegestane_url(url):
    """
    Geeft True terug als 'url' een https-link naar een domein uit
    URL_WHITELIST_DOMEINEN is (of een subdomein ervan), anders False.

    Let op de subdomein-check: "en.wikipedia.org" eindigt op
    ".wikipedia.org" en is dus toegestaan, maar
    "wikipedia.org.slechte-site.com" eindigt NIET op ".wikipedia.org"
    en wordt dus geweigerd. urlparse() haalt bovendien de echte
    hostnaam eruit, ook als iemand trucjes als "gebruiker@..." in de
    link zou stoppen.
    """
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTE:
        return False

    try:
        delen = urlparse(url.strip())
    except ValueError:
        return False

    if delen.scheme != "https":
        return False

    host = (delen.hostname or "").lower()
    if not host:
        return False

    for domein in URL_WHITELIST_DOMEINEN:
        if host == domein or host.endswith("." + domein):
            return True
    return False
# ---------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://en.wikipedia.org/wiki/Louise_Brown",
    "https://nl.wikipedia.org/wiki/Fiets",
    "https://wikipedia.org/",
    "https://EN.WIKIPEDIA.ORG/wiki/Concorde",
    "https://en.wikipedia.org/wiki/Caf%C3%A9",
])
def test_wikipedia_links_zijn_toegestaan(url):
    assert is_toegestane_url(url) is True


@pytest.mark.parametrize("url", [
    "http://en.wikipedia.org/wiki/Fiets",                 # geen https
    "file:///C:/Windows/System32/cmd.exe",                # lokaal bestand
    "javascript:alert(1)",                                # script
    "https://wikipedia.org.slechte-site.com/",            # nep-subdomein
    "https://nepwikipedia.org/",                          # lijkt erop, is het niet
    "https://slechte-site.com/?wikipedia.org",            # domein enkel in de query
    "https://en.wikipedia.org@slechte-site.com/",         # gebruikersnaam-truc
    "https://",                                           # geen host
    "",                                                   # leeg
    None,                                                 # geen tekst
    "https://en.wikipedia.org/" + "a" * 3000,             # absurd lang
])
def test_andere_links_worden_geweigerd(url):
    assert is_toegestane_url(url) is False


def test_kopie_is_gelijk_aan_nova_client():
    """
    Vangnet tegen een verouderde kopie: als nova_client.py vanuit de
    projectmap bereikbaar is, moet is_toegestane_url() daar exact
    hetzelfde zijn als hierboven. Staat nova_client.py hier niet (bv.
    enkel op de laptop), dan wordt deze ene test overgeslagen.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kandidaten = [
        os.path.join(project_root, "nova_client.py"),
        os.path.join(project_root, "client", "nova_client.py"),
    ]
    pad = next((p for p in kandidaten if os.path.exists(p)), None)
    if pad is None:
        pytest.skip("nova_client.py niet gevonden in de projectmap")

    with open(pad, encoding="utf-8") as f:
        boom = ast.parse(f.read())
    echte = next(
        (n for n in boom.body if isinstance(n, ast.FunctionDef) and n.name == "is_toegestane_url"),
        None,
    )
    assert echte is not None, "is_toegestane_url() ontbreekt in nova_client.py"

    with open(__file__, encoding="utf-8") as f:
        eigen_boom = ast.parse(f.read())
    kopie = next(
        n for n in eigen_boom.body if isinstance(n, ast.FunctionDef) and n.name == "is_toegestane_url"
    )
    assert ast.dump(echte) == ast.dump(kopie)