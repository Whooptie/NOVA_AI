# tests/test_on_this_day_vervolg.py
#
# date_calendar_roadmap.md Onderdeel 5 (26 september 2026): de
# vervolgvragen na een On This Day-antwoord.
#   - genummerde lijst (1-3), "meer" schuift door (4-6, 7-9, ...)
#   - een nummer toont een korte Wikipedia-samenvatting
#   - "ja" opent de volledige pagina op de laptop (via een NEP
#     client_bridge -- geen echte WebSocket, geen echte laptop nodig)
#   - de lijst vervalt bij een ander bericht of na verloop van tijd
#   - integratie: de ECHTE IntentRouter.route() stuurt een nummer/
#     "meer" naar deze module, en laat andere berichten gewoon door
#
# Geen internettoegang nodig: _fetch_dag_data() wordt telkens
# vervangen door een nagebouwde respons in het formaat van de echte
# Wikimedia "On This Day"-feed.

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.event_bus import EventBus
from core.intent_router import IntentRouter
import modules.time.on_this_day as otd_module
from modules.time.on_this_day import OnThisDayModule


# ---------------------------------------------------------------
# Nagebouwde data
# ---------------------------------------------------------------

def _pagina(titel, extract, url=True):
    pagina = {
        "title": titel.replace(" ", "_"),
        "normalizedtitle": titel,
        "titles": {"normalized": titel},
        "extract": extract,
    }
    if url:
        pagina["content_urls"] = {
            "desktop": {"page": f"https://en.wikipedia.org/wiki/{titel.replace(' ', '_')}"}
        }
    return pagina


def _maak_events(aantal):
    """'aantal' events, elk met een jaartal-pagina VOORAAN (die moet
    overgeslagen worden) en daarna een echte onderwerp-pagina."""
    events = []
    for i in range(1, aantal + 1):
        events.append({
            "year": 1900 + i,
            "text": f"Gebeurtenis nummer {i}.",
            "pages": [
                _pagina(str(1900 + i), f"{1900 + i} was a year."),
                _pagina(f"Onderwerp {i}", f"Onderwerp {i} is iets belangrijks. Tweede zin."),
            ],
        })
    return events


# ---------------------------------------------------------------
# Hulpmiddelen
# ---------------------------------------------------------------

class NepClientBridge:
    def __init__(self, verbonden=True, resultaat=None):
        self.verbonden = verbonden
        self.resultaat = resultaat if resultaat is not None else {"ok": True}
        self.verstuurd = []

    def is_laptop_verbonden(self):
        return self.verbonden

    def stuur_commando_naar_laptop(self, commando_type, payload, timeout_seconden=10):
        self.verstuurd.append((commando_type, payload))
        return self.resultaat


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def antwoorden(bus):
    ontvangen = []
    bus.subscribe("layer4_response", lambda data: ontvangen.append(data["text"]))
    return ontvangen


def _maak_module(bus, monkeypatch, data):
    module = OnThisDayModule(bus)
    monkeypatch.setattr(module, "_fetch_dag_data", lambda maand, dag: data)
    bus.register_module("on_this_day", module)
    return module


# ---------------------------------------------------------------
# 1. Genummerde lijst + "meer"
# ---------------------------------------------------------------

def test_eerste_antwoord_is_genummerd(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(7)})
    m.antwoord_events("wat is er gebeurd vandaag")

    msg = antwoorden[-1]
    assert msg.startswith("Op deze dag:")
    assert "1. 1901: Gebeurtenis nummer 1." in msg
    assert "3. 1903: Gebeurtenis nummer 3." in msg
    assert "4." not in msg
    assert "'meer'" in msg


def test_meer_toont_volgende_reeks_met_doorlopende_nummering(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(7)})
    m.antwoord_events("wat is er gebeurd vandaag")

    assert m.verwerk_vervolg("is er nog meer gebeurd?") is True
    msg = antwoorden[-1]
    assert "(vervolg)" in msg
    assert "4. 1904: Gebeurtenis nummer 4." in msg
    assert "6. 1906: Gebeurtenis nummer 6." in msg


def test_laatste_reeks_zonder_meer_hint_en_daarna_melding(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(4)})
    m.antwoord_events("wat is er gebeurd vandaag")
    m.verwerk_vervolg("meer")

    assert "4. 1904" in antwoorden[-1]
    assert "'meer'" not in antwoorden[-1]  # niets meer om door te schuiven

    assert m.verwerk_vervolg("meer") is True
    assert antwoorden[-1] == "Dat waren ze allemaal voor deze dag."


def test_geboren_en_overleden_gebruiken_eigen_kop(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {
        "births": _maak_events(2), "deaths": _maak_events(2),
    })
    m.antwoord_geboren("wie is er geboren vandaag")
    assert antwoorden[-1].startswith("Geboren op deze dag:")
    m.antwoord_overleden("wie is er overleden vandaag")
    assert antwoorden[-1].startswith("Overleden op deze dag:")


def test_entries_zonder_tekst_tellen_niet_mee_in_de_nummering(bus, antwoorden, monkeypatch):
    events = _maak_events(3)
    events.insert(0, {"year": 1800, "text": "   ", "pages": []})
    m = _maak_module(bus, monkeypatch, {"events": events})
    m.antwoord_events("wat is er gebeurd vandaag")

    assert "1. 1901: Gebeurtenis nummer 1." in antwoorden[-1]


def test_lege_categorie_als_dict_blijft_eerlijk_weinig_gevonden(bus, antwoorden, monkeypatch):
    # Regressie op de lege-dict-bug van 18 september 2026.
    m = _maak_module(bus, monkeypatch, {"events": {}})
    m.antwoord_events("wat is er gebeurd vandaag")

    assert "weinig gebeurtenissen" in antwoorden[-1]
    assert m.verwerk_vervolg("1") is False  # geen lijst actief


def test_geen_data_geeft_nette_melding_en_geen_lijst(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, None)
    m.antwoord_events("wat is er gebeurd vandaag")

    assert "niet bereiken" in antwoorden[-1]
    assert m.verwerk_vervolg("meer") is False


def test_haal_feiten_op_blijft_op_drie_afgekapt(bus, monkeypatch):
    # Bestaande methode, gedrag ongewijzigd.
    m = _maak_module(bus, monkeypatch, None)
    assert len(m._haal_feiten_op({"events": _maak_events(10)}, "events")) == 3


# ---------------------------------------------------------------
# 2. Nummer kiezen -> samenvatting
# ---------------------------------------------------------------

def test_nummer_toont_samenvatting_en_slaat_jaartalpagina_over(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(3)})
    m.antwoord_events("wat is er gebeurd vandaag")

    assert m.verwerk_vervolg("2") is True
    msg = antwoorden[-1]
    assert msg.startswith("Onderwerp 2: Onderwerp 2 is iets belangrijks.")
    assert "1902 was a year" not in msg


def test_nummer_uit_vervolgreeks_werkt_ook(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(6)})
    m.antwoord_events("wat is er gebeurd vandaag")
    m.verwerk_vervolg("meer")

    m.verwerk_vervolg("5")
    assert antwoorden[-1].startswith("Onderwerp 5:")


def test_nummer_buiten_de_getoonde_lijst(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(7)})
    m.antwoord_events("wat is er gebeurd vandaag")

    # 5 bestaat wel in de data, maar is nog niet getoond.
    assert m.verwerk_vervolg("5") is True
    assert "van 1 tot 3" in antwoorden[-1]
    assert m.verwerk_vervolg("0") is True
    assert "van 1 tot 3" in antwoorden[-1]


def test_feit_zonder_bruikbare_pagina(bus, antwoorden, monkeypatch):
    events = [{"year": 1950, "text": "Iets zonder pagina's.", "pages": [
        _pagina("1950", "1950 was a year."),
    ]}]
    m = _maak_module(bus, monkeypatch, {"events": events})
    m.antwoord_events("wat is er gebeurd vandaag")

    m.verwerk_vervolg("1")
    assert "geen samenvatting" in antwoorden[-1]


def test_lange_samenvatting_wordt_netjes_afgekapt(bus, antwoorden, monkeypatch):
    lang = ("Dit is een zin van redelijke lengte. " * 20).strip()
    events = [{"year": 1950, "text": "Lang feit.", "pages": [_pagina("Lang", lang)]}]
    m = _maak_module(bus, monkeypatch, {"events": events})
    m.antwoord_events("wat is er gebeurd vandaag")

    m.verwerk_vervolg("1")
    samenvatting = antwoorden[-1].split(": ", 1)[1]
    assert len(samenvatting) <= otd_module.MAX_SAMENVATTING_LENGTE
    assert samenvatting.endswith(".")


def test_url_wordt_opgebouwd_als_content_urls_ontbreekt(bus, monkeypatch):
    m = _maak_module(bus, monkeypatch, None)
    pagina = m._kies_pagina({"pages": [_pagina("Louise Brown", "Iets.", url=False)]})
    assert pagina["url"] == "https://en.wikipedia.org/wiki/Louise_Brown"


# ---------------------------------------------------------------
# 3. "ja" -> openen op de laptop
# ---------------------------------------------------------------

def test_open_vraag_enkel_als_laptop_verbonden(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(3)})
    bus.register_module("client_bridge", NepClientBridge(verbonden=False))
    m.antwoord_events("wat is er gebeurd vandaag")

    m.verwerk_vervolg("1")
    assert "openen op je laptop" not in antwoorden[-1]
    # "ja" betekent nu niets voor deze module -> lijst vervalt, door naar routing
    assert m.verwerk_vervolg("ja") is False


def test_open_vraag_zonder_client_bridge_module(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(3)})
    m.antwoord_events("wat is er gebeurd vandaag")

    m.verwerk_vervolg("1")
    assert "openen op je laptop" not in antwoorden[-1]


def test_ja_stuurt_open_url_naar_laptop(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(3)})
    bridge = NepClientBridge(verbonden=True)
    bus.register_module("client_bridge", bridge)
    m.antwoord_events("wat is er gebeurd vandaag")

    m.verwerk_vervolg("2")
    assert "Wil je de volledige pagina openen op je laptop? (ja/nee)" in antwoorden[-1]

    assert m.verwerk_vervolg("Ja graag!") is True
    assert bridge.verstuurd == [
        ("open_url", {"url": "https://en.wikipedia.org/wiki/Onderwerp_2"})
    ]
    assert antwoorden[-1] == "De pagina over Onderwerp 2 staat open op je laptop."


def test_mislukt_openen_geeft_reden_van_laptop_door(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(3)})
    bus.register_module("client_bridge", NepClientBridge(
        verbonden=True, resultaat={"ok": False, "reden": "Geen antwoord van de laptop binnen de tijd."}
    ))
    m.antwoord_events("wat is er gebeurd vandaag")
    m.verwerk_vervolg("1")
    m.verwerk_vervolg("ja")

    assert antwoorden[-1] == "Dat lukte niet: Geen antwoord van de laptop binnen de tijd."


def test_nee_opent_niets_maar_lijst_blijft_bruikbaar(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(3)})
    bridge = NepClientBridge(verbonden=True)
    bus.register_module("client_bridge", bridge)
    m.antwoord_events("wat is er gebeurd vandaag")
    m.verwerk_vervolg("1")

    assert m.verwerk_vervolg("nee") is True
    assert antwoorden[-1] == "Oké, geen probleem."
    assert bridge.verstuurd == []

    # Een ander nummer kiezen kan nog steeds.
    assert m.verwerk_vervolg("3") is True
    assert antwoorden[-1].startswith("Onderwerp 3:")


def test_ja_opent_maar_een_keer(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(3)})
    bridge = NepClientBridge(verbonden=True)
    bus.register_module("client_bridge", bridge)
    m.antwoord_events("wat is er gebeurd vandaag")
    m.verwerk_vervolg("1")
    m.verwerk_vervolg("ja")

    # Tweede "ja": geen open-vraag meer -> hoort niet bij deze module.
    assert m.verwerk_vervolg("ja") is False
    assert len(bridge.verstuurd) == 1


# ---------------------------------------------------------------
# 4. Vervallen van de lijst
# ---------------------------------------------------------------

def test_ander_bericht_laat_lijst_vervallen(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(6)})
    m.antwoord_events("wat is er gebeurd vandaag")

    assert m.verwerk_vervolg("wat is een gitaar") is False
    assert m.verwerk_vervolg("2") is False  # lijst is weg


def test_lijst_vervalt_na_verloop_van_tijd(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(6)})
    m.antwoord_events("wat is er gebeurd vandaag")

    m._vervolg["tijd"] -= otd_module.VERVOLG_VERVAL_SECONDEN + 1
    assert m.verwerk_vervolg("2") is False


def test_nieuwe_vraag_vervangt_oude_lijst(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {
        "events": _maak_events(6), "births": _maak_events(2),
    })
    m.antwoord_events("wat is er gebeurd vandaag")
    m.verwerk_vervolg("meer")
    m.antwoord_geboren("wie is er geboren vandaag")

    assert m._vervolg["categorie"] == "births"
    assert m._vervolg["getoond"] == 2


# ---------------------------------------------------------------
# 5. Integratie met de ECHTE IntentRouter.route()
# ---------------------------------------------------------------

def test_route_stuurt_nummer_en_meer_naar_on_this_day(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(6)})
    router = IntentRouter(bus)
    m.antwoord_events("wat is er gebeurd vandaag")

    router.route({"text": "meer"})
    assert "4. 1904" in antwoorden[-1]

    router.route({"text": "5"})
    assert antwoorden[-1].startswith("Onderwerp 5:")


def test_route_zonder_actieve_lijst_raakt_on_this_day_niet(bus, antwoorden, monkeypatch):
    m = _maak_module(bus, monkeypatch, {"events": _maak_events(6)})
    aangeroepen = []
    origineel = m.verwerk_vervolg

    def verklikker(text):
        resultaat = origineel(text)
        aangeroepen.append((text, resultaat))
        return resultaat

    monkeypatch.setattr(m, "verwerk_vervolg", verklikker)
    router = IntentRouter(bus)
    router.route({"text": "hallo"})

    assert aangeroepen == [("hallo", False)]