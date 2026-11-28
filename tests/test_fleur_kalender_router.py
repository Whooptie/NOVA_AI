"""De HELE keten: echte IntentRouter + echte CyclusModule + echte FleurKalender op een nep-bus.

Controleert vooral de samenwerking: dat de cyclus-zinnen en de kalender-zinnen elkaar niet in de
weg zitten, dat "ja"/"nee" op de onbekend-woord-vraag aankomt, en dat gewone zinnen ongemoeid
blijven. Schrijft alleen in tmp_path.
Uitvoeren: pytest tests/test_fleur_kalender_router.py -v
"""

from datetime import date, datetime

import pytest

from core.intent_router import IntentRouter
from modules.time import cyclus as c
from modules.time import fleur_kalender as fk


class NepBus:
    def __init__(self):
        self.gepubliceerd, self.modules, self.abonnees = [], {}, {}

    def subscribe(self, naam, functie):
        self.abonnees.setdefault(naam, []).append(functie)

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data or {}))
        for f in self.abonnees.get(naam, []):
            f(data or {})

    def register_module(self, naam, instantie):
        self.modules[naam] = instantie

    def teksten(self):
        return [d["text"] for n, d in self.gepubliceerd if n in ("layer4_response", "chat_response")]


@pytest.fixture
def opstelling(tmp_path):
    bus = NepBus()
    klok = lambda: datetime(2026, 11, 28, 13, 55)
    cy = c.CyclusModule(bus, pad=str(tmp_path / "cyclus.json"), klok=klok, start_loop=False)
    kal = fk.FleurKalender(bus, pad=str(tmp_path / "kalender.json"), klok=klok)
    bus.register_module("cyclus", cy)
    bus.register_module("fleur_kalender", kal)
    return IntentRouter(bus), bus, cy, kal


def vraag(opstelling, tekst):
    router, bus, _, _ = opstelling
    bus.gepubliceerd.clear()
    router.route({"text": tekst})
    return bus.teksten()


def test_log_via_router(opstelling):
    antwoorden = vraag(opstelling, "fleur knuffelen ik begon")
    assert len(antwoorden) == 1 and "Genoteerd: knuffelen" in antwoorden[0]
    assert opstelling[3].status["items"][0]["begon"] == "kevin"


def test_wilde_niet_via_router(opstelling):
    antwoorden = vraag(opstelling, "fleur seks ik probeerde maar ze wilde niet")
    assert "niet doorgegaan" in antwoorden[0]


def test_onbekend_woord_ja_via_router(opstelling):
    eerste = vraag(opstelling, "fleur massage ik begon")
    assert "ken ik nog niet" in eerste[0]
    tweede = vraag(opstelling, "ja")
    assert len(tweede) == 1 and "Nieuwe soort toegevoegd: massage" in tweede[0]
    assert "massage" in opstelling[3].status["soorten"]


def test_onbekend_woord_nee_via_router(opstelling):
    vraag(opstelling, "fleur massage")
    antwoorden = vraag(opstelling, "nee")
    assert "niets toegevoegd" in antwoorden[0] and opstelling[3].status["items"] == []


def test_cyclus_en_kalender_naast_elkaar(opstelling):
    assert "Genoteerd: de maandstonden" in vraag(opstelling, "fleur is gisteren ongesteld geworden")[0]
    assert "Genoteerd: seks" in vraag(opstelling, "fleur seks")[0]
    assert "Fleur zit op dag" in vraag(opstelling, "in welke fase zit fleur?")[0]
    assert "Fleur-kalender" in vraag(opstelling, "fleur kalender")[0]
    assert len(opstelling[2].starts()) == 1 and len(opstelling[3].status["items"]) == 1


def test_laatste_ongedaan_raakt_de_andere_module_niet(opstelling):
    _, _, cy, kal = opstelling
    cy.registreer_start(date(2026, 10, 1))
    vraag(opstelling, "fleur seks")
    vraag(opstelling, "fleur kalender laatste ongedaan")
    assert kal.status["items"] == [] and cy.starts() == [date(2026, 10, 1)]
    vraag(opstelling, "fleur seks")
    vraag(opstelling, "fleur maandstonden laatste ongedaan")
    assert cy.starts() == [] and len(kal.status["items"]) == 1


def test_vruchtbaarheidsmelding_blijft_bij_cyclus(opstelling):
    vraag(opstelling, "fleur vruchtbaarheidsmeldingen aan")
    assert opstelling[2].status["vruchtbaar_melding"] is True
    assert opstelling[3].status["items"] == []


def test_gewone_zinnen_blijven_ongemoeid(opstelling):
    for zin in ("hoe laat is het", "wat is seks", "ik hou van fleur"):
        vraag(opstelling, zin)
    assert opstelling[3].status["items"] == []
    assert opstelling[2].status["perioden"] == []


def test_zonder_modules_valt_de_router_door(tmp_path):
    bus = NepBus()
    router = IntentRouter(bus)
    bus.gepubliceerd.clear()
    router.route({"text": "fleur seks"})
    assert not any("Genoteerd" in t for t in bus.teksten())


def test_kapotte_module_laat_router_niet_crashen(opstelling):
    router, bus, cy, kal = opstelling

    def stuk(_t):
        raise RuntimeError("boem")

    kal.verwerk_zin = stuk
    router.route({"text": "fleur seks"})          # mag niet crashen
    assert kal.status["items"] == []


def test_geen_topic_events_voor_persoonlijke_info(opstelling):
    vraag(opstelling, "fleur seks ik begon")
    topics = [n for n, _ in opstelling[1].gepubliceerd if n.startswith("topic_detected")]
    assert not any(w in t for t in topics for w in ("fleur", "seks", "kalender"))