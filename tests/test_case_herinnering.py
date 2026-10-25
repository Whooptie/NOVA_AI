# tests/test_case_herinnering.py -- Case-based reasoning / terugblikken (idee 3)
import gzip
import json
import time

import pytest

from core.memory import MemoryModule
from modules.knowledge.case_herinnering import (
    CaseHerinneringModule, inhoudssleutels, is_vergelijkbaar, is_vraag,
)

DAG = 86400
UUR = 3600
NU = time.mktime((2026, 10, 25, 12, 0, 0, 0, 0, -1))


class DummyEventBus:
    def __init__(self):
        self.modules = {}
        self.handlers = {}
        self.gepubliceerd = []

    def register_module(self, naam, instance):
        self.modules[naam] = instance

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))
        for h in self.handlers.get(event_type, []):
            h(data, event_type)

    def antwoorden(self):
        return [d["text"] for e, d in self.gepubliceerd if e == "chat_response"]


def zet(mem, ts, soort, data, tabel="interactions"):
    mem.conn.execute(
        f"INSERT INTO {tabel}(timestamp, month, year, event_type, data, created_at) "
        f"VALUES (?,?,?,?,?,?)",
        (ts, "2026-10", 2026, soort, json.dumps(data), ts))
    mem.conn.commit()


def vraag(mem, ts, tekst, antwoord=None, tabel="interactions"):
    zet(mem, ts, "raw_user_message", {"text": tekst}, tabel)
    if antwoord:
        zet(mem, ts + 2, "chat_response", {"text": antwoord}, tabel)


@pytest.fixture
def omgeving(tmp_path):
    bus = DummyEventBus()
    mem = MemoryModule(bus, save_path=tmp_path / "interactions.jsonl")
    mem.stop_maintenance()
    bus.register_module("memory", mem)
    klok = [NU]
    mod = CaseHerinneringModule(bus, pad=tmp_path / "case.json", klok=lambda: klok[0])
    bus.register_module("case_herinnering", mod)
    yield bus, mem, mod, klok, tmp_path
    mem.stop_maintenance()


def beurt(bus, mod, tekst, kennis=True, antwoord="Ja, een hond is een dier."):
    """Simuleert een bericht zoals route() het verwerkt."""
    mod.betreed_beurt()
    bus.publish("raw_user_message", {"text": tekst})
    if kennis:
        bus.publish("intent_relation_check", {"source": "x", "target": "y"})
    if antwoord:
        bus.publish("chat_response", {"text": antwoord})
    mod.verlaat_beurt()


# ---------------- sleutels en vergelijken ----------------
def test_meervoud_en_vraagwoorden():
    assert inhoudssleutels("Is een hond een dier?") == inhoudssleutels("zijn honden dieren")
    assert "wat" not in inhoudssleutels("wat is een hond")


def test_ontkenning_blijft_staan():
    assert "geen" in inhoudssleutels("is een hond geen dier")
    assert not is_vergelijkbaar(inhoudssleutels("is een hond een dier"),
                                inhoudssleutels("is een hond geen dier"))


def test_drempels():
    assert is_vergelijkbaar(inhoudssleutels("onderdelen van een auto"),
                            inhoudssleutels("welke onderdelen heeft een auto"))
    assert not is_vergelijkbaar(inhoudssleutels("is een hond een dier"),
                                inhoudssleutels("is een kat een dier"))
    # 1 inhoudswoord: enkel exact gelijk
    assert is_vergelijkbaar(inhoudssleutels("wat is een hond"), inhoudssleutels("hond"))
    assert not is_vergelijkbaar(inhoudssleutels("hond"), inhoudssleutels("hond en kat spelen"))
    assert not is_vergelijkbaar(frozenset(), frozenset({"hond"}))


# ---------------- zoeken in alle bronnen ----------------
def test_zoekt_in_recent_archief_en_gzip(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - 2 * DAG, "is een hond een dier")
    vraag(mem, NU - 120 * DAG, "is een hond een dier?", tabel="interactions_old")
    archief = tmp / "archive"
    archief.mkdir()
    rij = {"timestamp": NU - 500 * DAG, "event_type": "raw_user_message",
           "data": json.dumps({"text": "is een hond een dier"})}
    with gzip.open(archief / "interactions_compressed_x.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write(json.dumps(rij) + "\n")
    gevonden = mod.zoek_vergelijkbaar("is een hond een dier", NU)
    assert len(gevonden) == 3
    assert [g[0] for g in gevonden] == sorted([g[0] for g in gevonden], reverse=True)


def test_niet_vergelijkbare_en_latere_vragen_tellen_niet(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - DAG, "is een kat een dier")
    vraag(mem, NU - DAG, "wat is het weer")
    vraag(mem, NU + 100, "is een hond een dier")   # nieuwer dan de grens
    assert mod.zoek_vergelijkbaar("is een hond een dier", NU) == []


def test_zonder_memory_geen_crash(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    del bus.modules["memory"]
    assert mod.zoek_vergelijkbaar("is een hond een dier", NU) == []
    beurt(bus, mod, "is een hond een dier")


# ---------------- automatisch ----------------
def test_auto_zelfde_antwoord(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - 2 * DAG, "is een hond een dier", "Ja, een hond is een dier.")
    beurt(bus, mod, "is een hond een dier")
    tekst = bus.antwoorden()[-1]
    assert tekst.startswith("(Je vroeg dit eerder al, 2 dagen geleden") and tekst.endswith(")")
    assert "hetzelfde" in tekst


def test_auto_ander_antwoord(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - 2 * DAG, "is een hond een dier", "Dat weet ik niet.")
    beurt(bus, mod, "is een hond een dier", antwoord="Ja, een hond is een dier.")
    tekst = bus.antwoorden()[-1]
    assert "Toen antwoordde ik: \"Dat weet ik niet.\"" in tekst


def test_auto_andere_formulering_wordt_getoond(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - DAG, "zijn honden dieren", "Ja.")
    beurt(bus, mod, "is een hond een dier")
    tekst = bus.antwoorden()[-1]
    assert "gisteren" in tekst and "als \"zijn honden dieren\"" in tekst


def test_auto_telt_keren(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    for i in (1, 2, 3):
        vraag(mem, NU - i * DAG, "is een hond een dier")
    beurt(bus, mod, "is een hond een dier")
    assert "3 keer. Laatst gisteren" in bus.antwoorden()[-1]


def test_auto_enkel_bij_kennisvraag(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - DAG, "is een hond een dier")
    beurt(bus, mod, "is een hond een dier", kennis=False)
    assert all("eerder al" not in t for t in bus.antwoorden())


def test_auto_niet_binnen_het_uur(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - 10 * 60, "is een hond een dier")
    beurt(bus, mod, "is een hond een dier")
    assert all("eerder al" not in t for t in bus.antwoorden())


def test_auto_een_keer_per_dag_en_onthouden_na_herstart(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - DAG, "is een hond een dier")
    beurt(bus, mod, "is een hond een dier")
    beurt(bus, mod, "is een hond een dier")
    assert sum("eerder al" in t for t in bus.antwoorden()) == 1
    # na een herstart (nieuwe instantie, zelfde bestand) nog steeds niet opnieuw
    bus2 = DummyEventBus()
    bus2.register_module("memory", mem)
    mod2 = CaseHerinneringModule(bus2, pad=tmp / "case.json", klok=lambda: klok[0])
    bus2.register_module("case_herinnering", mod2)
    beurt(bus2, mod2, "is een hond een dier")
    assert all("eerder al" not in t for t in bus2.antwoorden())
    # de volgende dag mag het weer
    klok[0] += DAG
    beurt(bus2, mod2, "is een hond een dier")
    assert any("eerder al" in t for t in bus2.antwoorden())


def test_auto_ontkenning_is_andere_vraag(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - DAG, "is een hond een dier")
    beurt(bus, mod, "is een hond geen dier")
    assert all("eerder al" not in t for t in bus.antwoorden())


def test_auto_niet_onder_aanname(omgeving):
    bus, mem, mod, klok, tmp = omgeving

    class Aanname:
        def heeft_aannames(self):
            return True
    bus.register_module("hypothese", Aanname())
    vraag(mem, NU - DAG, "is een hond een dier")
    beurt(bus, mod, "is een hond een dier")
    assert all("eerder al" not in t for t in bus.antwoorden())


def test_eigen_melding_en_haakjes_tellen_niet_als_antwoord(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    mod.betreed_beurt()
    bus.publish("chat_response", {"source": "hypothese", "text": "Oké, aangenomen."})
    bus.publish("chat_response", {"text": "(Let op: iets)"})
    assert getattr(mod._lokaal, "antwoord", None) is None
    mod.verlaat_beurt()


def test_spontane_melding_buiten_beurt_is_geen_antwoord(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    bus.publish("chat_response", {"text": "Het gaat regenen!"})
    assert mod._laatste_antwoord is None


# ---------------- aan / uit ----------------
def test_uit_en_aan_blijft_bewaard(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - DAG, "is een hond een dier")
    mod.betreed_beurt(); bus.publish("raw_user_message", {"text": "stop met terugblikken"})
    bus.publish("intent_case_herinnering_uit", {}); mod.verlaat_beurt()
    beurt(bus, mod, "is een hond een dier")
    assert all("eerder al" not in t for t in bus.antwoorden())
    # herstart: nog steeds uit
    mod2 = CaseHerinneringModule(DummyEventBus(), pad=tmp / "case.json", klok=lambda: klok[0])
    assert mod2.staat["aan"] is False
    mod.betreed_beurt(); bus.publish("raw_user_message", {"text": "blik weer terug"})
    bus.publish("intent_case_herinnering_aan", {}); mod.verlaat_beurt()
    beurt(bus, mod, "is een hond een dier")
    assert any("eerder al" in t for t in bus.antwoorden())


def test_kapot_statusbestand_geeft_standaard(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    (tmp / "case.json").write_text("{kapot", encoding="utf-8")
    mod2 = CaseHerinneringModule(DummyEventBus(), pad=tmp / "case.json")
    assert mod2.staat["aan"] is True and mod2.staat["getoond"] == {}


# ---------------- op vraag ----------------
def vorige_vraag_stellen(bus, mod, vraagtekst, antwoord="Ja, een hond is een dier."):
    beurt(bus, mod, vraagtekst, kennis=False, antwoord=antwoord)


def test_expliciet_ja(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - 3 * DAG, "is een hond een dier", "Ja, een hond is een dier.")
    vorige_vraag_stellen(bus, mod, "is een hond een dier")
    mod.betreed_beurt()
    bus.publish("raw_user_message", {"text": "heb ik dit al eens gevraagd"})
    bus.publish("intent_case_herinnering_vorige", {})
    mod.verlaat_beurt()
    tekst = bus.antwoorden()[-1]
    assert tekst.startswith("Ja, je vroeg dit al 1 keer eerder") and "3 dagen geleden" in tekst
    assert "hetzelfde" in tekst


def test_expliciet_eerste_keer(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vorige_vraag_stellen(bus, mod, "is een walvis een vis")
    mod.betreed_beurt()
    bus.publish("raw_user_message", {"text": "heb ik dit al eens gevraagd"})
    bus.publish("intent_case_herinnering_vorige", {})
    mod.verlaat_beurt()
    assert "eerste keer" in bus.antwoorden()[-1]


def test_expliciet_zonder_vorige_vraag(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    mod.betreed_beurt()
    bus.publish("raw_user_message", {"text": "heb ik dit al eens gevraagd"})
    bus.publish("intent_case_herinnering_vorige", {})
    mod.verlaat_beurt()
    assert "geen eerdere vraag" in bus.antwoorden()[-1]


def test_expliciet_twee_keer_na_elkaar_blijft_naar_de_vraag_verwijzen(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - DAG, "is een hond een dier")
    vorige_vraag_stellen(bus, mod, "is een hond een dier")
    for _ in range(2):
        mod.betreed_beurt()
        bus.publish("raw_user_message", {"text": "heb ik dit al eens gevraagd"})
        bus.publish("intent_case_herinnering_vorige", {})
        mod.verlaat_beurt()
    assert bus.antwoorden()[-1].startswith("Ja, je vroeg dit al 1 keer")
    assert bus.antwoorden()[-2].startswith("Ja, je vroeg dit al 1 keer")


def test_expliciet_geeft_geen_extra_auto_melding(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - DAG, "is een hond een dier")
    vorige_vraag_stellen(bus, mod, "is een hond een dier")
    aantal = len(bus.antwoorden())
    mod.betreed_beurt()
    bus.publish("raw_user_message", {"text": "wanneer vroeg ik dat laatst"})
    bus.publish("intent_case_herinnering_laatst", {})
    mod.verlaat_beurt()
    nieuw = bus.antwoorden()[aantal:]
    assert len(nieuw) == 1 and nieuw[0].startswith("Dat vroeg je laatst gisteren")


# ---------------- router ----------------
@pytest.fixture
def router(omgeving):
    from core.intent_router import IntentRouter
    bus, mem, mod, klok, tmp = omgeving
    return IntentRouter(bus, semantic_module=None), bus, mem, mod


@pytest.mark.parametrize("zin,event", [
    ("heb ik dit al eens gevraagd", "intent_case_herinnering_vorige"),
    ("Heb ik dat al eerder gevraagd?", "intent_case_herinnering_vorige"),
    ("heb ik dit gevraagd", "intent_case_herinnering_vorige"),
    ("vroeg ik dit al eens", "intent_case_herinnering_vorige"),
    ("vroeg ik dat al eerder?", "intent_case_herinnering_vorige"),
    ("hebben we dit al eens gehad", "intent_case_herinnering_vorige"),
    ("wanneer vroeg ik dat laatst", "intent_case_herinnering_laatst"),
    ("wanneer heb ik dit voor het laatst gevraagd?", "intent_case_herinnering_laatst"),
    ("stop met terugblikken", "intent_case_herinnering_uit"),
    ("geen terugblikken meer", "intent_case_herinnering_uit"),
    ("blik weer terug", "intent_case_herinnering_aan"),
    ("zet terugblikken weer aan", "intent_case_herinnering_aan"),
])
def test_detect_zinnen(router, zin, event):
    r, bus, mem, mod = router
    assert r.detect_case_herinnering(zin) is True
    assert bus.gepubliceerd[-1][0] == "topic_detected:terugblik" or any(e == event for e, _ in bus.gepubliceerd)
    assert any(e == event for e, _ in bus.gepubliceerd)


@pytest.mark.parametrize("zin", [
    "heb ik een hond", "wanneer is het weekend", "hallo", "is een hond een dier",
    "heb ik je al eens iets gevraagd over koffie",   # blijft van memory_query
])
def test_detect_negatief(router, zin):
    r, bus, mem, mod = router
    assert r.detect_case_herinnering(zin) is False


def test_detect_zonder_module(router):
    r, bus, mem, mod = router
    del bus.modules["case_herinnering"]
    assert r.detect_case_herinnering("heb ik dit al eens gevraagd") is False


def test_route_volledig(router):
    r, bus, mem, mod = router
    bus.subscribe("intent_relation_check",
                  lambda d, e=None: bus.publish("chat_response", {"text": "Ja, een hond is een dier."}))
    vraag(mem, NU - 2 * DAG, "is een hond een dier", "Ja, een hond is een dier.")
    r.route({"text": "is een hond een dier"})
    antwoorden = bus.antwoorden()
    assert antwoorden[0] == "Ja, een hond is een dier."
    assert antwoorden[1].startswith("(Je vroeg dit eerder al") and "hetzelfde" in antwoorden[1]
    # het terugblik-commando zelf
    r.route({"text": "heb ik dit al eens gevraagd"})
    assert bus.antwoorden()[-1].startswith("Ja, je vroeg dit al")
    assert mod._diepte() == 0


def test_route_wrapper_met_beide_modules(router):
    """hypothese en case_herinnering mogen samen in route() zitten."""
    r, bus, mem, mod = router

    class Stub:
        def __init__(self):
            self.log = []

        def betreed_beurt(self):
            self.log.append("in")

        def verlaat_beurt(self):
            self.log.append("uit")

        def heeft_aannames(self):
            return False
    stub = Stub()
    bus.register_module("hypothese", stub)
    r.route({"text": "hallo"})
    assert stub.log == ["in", "uit"]


def test_ontkenning_overleeft_een_stopwoordenlijst_die_haar_bevat(monkeypatch):
    """De echte core/nl_stopwoorden.py bevat o.a. 'geen'; dat mag de ontkenning niet wissen."""
    from modules.knowledge import case_herinnering as ch
    monkeypatch.setattr(ch, "_GEDEELDE_STOPWOORDEN", {"geen", "niet", "nooit", "niets", "niks", "dier"})
    assert "geen" in ch.inhoudssleutels("is een hond geen dier")
    assert "dier" not in ch.inhoudssleutels("is een hond geen dier")
    assert not ch.is_vergelijkbaar(ch.inhoudssleutels("is een hond een kat"),
                                   ch.inhoudssleutels("is een hond geen kat"))


def test_is_vraag():
    assert is_vraag("is een hond een dier")
    assert is_vraag("een hond een dier?")
    assert is_vraag("Wat is een tractor")
    assert not is_vraag("een hond is een dier")
    assert not is_vraag("")


def test_auto_oude_stelling_wordt_niet_als_vraag_genoemd(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - 3 * DAG, "een hond is een dier", "Mag ik onthouden dat 'hond' een soort van 'dier' is?")
    beurt(bus, mod, "is een hond een dier")
    tekst = bus.antwoorden()[-1]
    assert tekst.startswith("(Je zei eerder al iets vergelijkbaars") and "Je vroeg" not in tekst


def test_expliciet_oude_stelling(omgeving):
    bus, mem, mod, klok, tmp = omgeving
    vraag(mem, NU - 3 * DAG, "een hond is een dier")
    vorige_vraag_stellen(bus, mod, "is een hond een dier")
    mod.betreed_beurt()
    bus.publish("raw_user_message", {"text": "heb ik dit al eens gevraagd"})
    bus.publish("intent_case_herinnering_vorige", {})
    mod.verlaat_beurt()
    assert bus.antwoorden()[-1].startswith("Ja, iets vergelijkbaars kwam al 1 keer eerder voorbij")