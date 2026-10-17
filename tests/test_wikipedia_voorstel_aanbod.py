# tests/test_wikipedia_voorstel_aanbod.py -- Semantic Fase 11.3:
# na een geslaagde "wiki X" biedt Nova de voorstellen uit de inleiding aan
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules.knowledge.wikipedia_teacher import WikipediaTeacher


class FakeExtractor:
    def __init__(self, beschikbaar=True):
        self.beschikbaar = beschikbaar

    def is_beschikbaar(self):
        return self.beschikbaar


class FakeBus:
    def __init__(self, extractor=True, proposals=True, beschikbaar=True):
        self.subs = {}
        self.out = []
        self.modules = {}
        if extractor:
            self.modules["knowledge_extractor"] = FakeExtractor(beschikbaar)
        if proposals:
            self.modules["knowledge_proposals"] = object()

    def subscribe(self, e, f):
        self.subs.setdefault(e, []).append(f)

    def publish(self, e, d=None):
        self.out.append((e, d))
        for f in self.subs.get(e, []):
            f(d, e)

    def teksten(self):
        return [d["text"] for e, d in self.out if e == "chat_response"]

    def events(self, naam):
        return [d for e, d in self.out if e == naam]


STANDAARD = {"type": "standard", "extract": "Een fiets is een voertuig dat men trapt."}
DOORVERWIJS = {"type": "disambiguation", "extract": "Bank kan verwijzen naar:\nmeubel"}


def maak(bus=None, summary=STANDAARD, resultaat="Wikipedia: 'fiets' → Een fiets is een voertuig."):
    bus = bus or FakeBus()
    t = WikipediaTeacher(bus, None)
    t._fetch_summary = lambda w: summary
    t._teach_word = lambda *a, **k: resultaat
    return bus, t


def wiki(bus, woord="fiets", auto=False):
    bus.publish("intent_wiki", {"word": woord, "auto": auto})


# ---------- aanbod ----------
def test_aanbod_na_geslaagde_wiki():
    bus, t = maak()
    wiki(bus)
    assert "Wil je ook zien wat ik uit de Wikipedia-inleiding van 'fiets'" in bus.teksten()[-1]
    assert t._pending_voorstel["woord"] == "fiets"


def test_aanbod_ook_na_bijgewerkte_definitie():
    bus, t = maak(resultaat="Wikipedia-definitie van 'fiets' bijgewerkt → x")
    wiki(bus)
    assert t._pending_voorstel is not None


@pytest.mark.parametrize("resultaat", [
    "Semantic module niet beschikbaar.",
    "Fout bij opslaan van definitie: boem",
    "Ik ken 'fiets' al van jou — Wikipedia overschrijft dat niet.",
])
def test_geen_aanbod_bij_mislukte_opslag(resultaat):
    bus, t = maak(resultaat=resultaat)
    wiki(bus)
    assert t._pending_voorstel is None
    assert not any("Wil je ook zien" in x for x in bus.teksten())


def test_geen_aanbod_bij_automatische_opzoeking():
    bus, t = maak()
    wiki(bus, auto=True)
    assert t._pending_voorstel is None


def test_geen_aanbod_zonder_extractor():
    bus, t = maak(bus=FakeBus(extractor=False))
    wiki(bus)
    assert t._pending_voorstel is None


def test_geen_aanbod_als_extractor_uitstaat():
    bus, t = maak(bus=FakeBus(beschikbaar=False))
    wiki(bus)
    assert t._pending_voorstel is None


def test_geen_aanbod_zonder_voorstellenmodule():
    bus, t = maak(bus=FakeBus(proposals=False))
    wiki(bus)
    assert t._pending_voorstel is None


def test_geen_aanbod_via_doorverwijspagina():
    bus, t = maak(summary=DOORVERWIJS)
    # doorverwijspagina zonder bruikbare uitweg -> geen definitie, dus ook geen aanbod
    t._extract_first_disambiguation_target = lambda extract, w: "meubel"
    t._fetch_summary = lambda w: DOORVERWIJS if w in ("bank", "Bank") else STANDAARD
    wiki(bus, "bank")
    assert t._pending_voorstel is None


# ---------- antwoord ----------
@pytest.mark.parametrize("antwoord", ["ja", "Ja!", "graag", "ja graag", "doe maar", "ok"])
def test_ja_start_extractie(antwoord):
    bus, t = maak()
    wiki(bus)
    assert t.verwerk_voorstel_antwoord(antwoord) is True
    assert bus.events("intent_kennis_extract") == [{"word": "fiets"}]
    assert t._pending_voorstel is None


@pytest.mark.parametrize("antwoord", ["nee", "wat is een hond", "neem 1 over", "jaloers", "ja ik denk dat het regent morgen"])
def test_ander_antwoord_laat_aanbod_vervallen_en_loopt_door(antwoord):
    bus, t = maak()
    wiki(bus)
    assert t.verwerk_voorstel_antwoord(antwoord) is False
    assert bus.events("intent_kennis_extract") == []
    assert t._pending_voorstel is None


def test_zonder_aanbod_doet_niets():
    bus, t = maak()
    assert t.verwerk_voorstel_antwoord("ja") is False
    assert bus.events("intent_kennis_extract") == []


def test_aanbod_verloopt():
    bus, t = maak()
    wiki(bus)
    t._pending_voorstel["tijd"] = time.time() - 10_000
    assert t.verwerk_voorstel_antwoord("ja") is False
    assert bus.events("intent_kennis_extract") == []


def test_ja_werkt_maar_een_keer():
    bus, t = maak()
    wiki(bus)
    assert t.verwerk_voorstel_antwoord("ja") is True
    assert t.verwerk_voorstel_antwoord("ja") is False
    assert len(bus.events("intent_kennis_extract")) == 1


def test_oude_regex_extractie_blijft_werken():
    bus, t = maak()
    rel = t._extract_relations("fiets", "Een fiets is een voertuig dat men trapt.")
    assert rel and rel[0]["target"] == "voertuig"


# ---------- Fase 11.4: aanbod ook na een keuze uit het wiki-menu ----------
def maak_keuze(resultaat="Wikipedia: 'regen' → Regen is neerslag."):
    bus = FakeBus()
    t = WikipediaTeacher(bus, None)
    t._fetch_summary = lambda w: {"type": "standard", "extract": "Regen is neerslag."}
    t._teach_word = lambda *a, **k: resultaat
    return bus, t


def test_aanbod_na_menukeuze_noemt_de_gekozen_titel():
    bus, t = maak_keuze()
    t._verwerk_gekozen_pagina("regen", "Regen (neerslag)")
    assert "'Regen (neerslag)'" in bus.teksten()[-1]
    assert t._pending_voorstel["titel"] == "Regen (neerslag)"


def test_ja_na_menukeuze_vraagt_de_gekozen_titel_op():
    bus, t = maak_keuze()
    t._verwerk_gekozen_pagina("regen", "Regen (neerslag)")
    assert t.verwerk_voorstel_antwoord("ja") is True
    assert bus.events("intent_kennis_extract") == [{"word": "Regen (neerslag)"}]


def test_geen_aanbod_na_menukeuze_van_een_ander_woord():
    # "Neerslag" gekozen bij "regen": de feiten zouden bij het verkeerde woord landen
    bus, t = maak_keuze()
    t._verwerk_gekozen_pagina("regen", "Neerslag")
    assert t._pending_voorstel is None


def test_geen_aanbod_na_mislukte_opslag_via_menu():
    bus, t = maak_keuze(resultaat="Semantic module niet beschikbaar.")
    t._verwerk_gekozen_pagina("regen", "Regen (neerslag)")
    assert t._pending_voorstel is None


def test_gewone_ja_zonder_titel_blijft_het_woord_gebruiken():
    bus, t = maak()
    wiki(bus)
    t.verwerk_voorstel_antwoord("ja")
    assert bus.events("intent_kennis_extract") == [{"word": "fiets"}]