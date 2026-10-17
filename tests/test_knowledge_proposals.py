"""Tests voor Semantic Fase 11.2 (knowledge_proposals)."""
import time

from modules.knowledge.knowledge_proposals import KnowledgeProposals


class FakeBus:
    def __init__(self):
        self.modules = {}
        self.subs = {}
        self.out = []

    def subscribe(self, e, f):
        self.subs.setdefault(e, []).append(f)

    def publish(self, e, d=None):
        self.out.append((e, d))
        for f in self.subs.get(e, []):
            f(d, e)

    def teksten(self):
        return [d["text"] for e, d in self.out if e == "chat_response"]


class FakeExtractor:
    def __init__(self, feiten, beschikbaar=True):
        self.feiten = feiten
        self.beschikbaar = beschikbaar
        self.reden_uit = None if beschikbaar else "spaCy is niet geinstalleerd"

    def is_beschikbaar(self):
        return self.beschikbaar

    def extract_from_text(self, tekst, zoekwoord=None):
        return self.feiten


class FakeTeach:
    def _normalize_plural_if_noun(self, woord, pos):
        return {"wielen": "wiel", "dieren": "dier"}.get(woord, woord)


class FakeStore:
    def __init__(self):
        self.concepts = {}

    def get_concept(self, w):
        return self.concepts.get(w)


class FakeSem:
    """Volgt de echte signaturen van semantic.py (add_relation geeft False
    bij een dubbele of afgewezen relatie; confirm/reject geven rel of None)."""
    def __init__(self):
        self.store = FakeStore()
        self.teach_engine = FakeTeach()

    def _sense(self, w):
        c = self.store.concepts.setdefault(w, {"senses": [
            {"sense_id": f"{w}#1", "relations": []}]})
        return c["senses"][0]

    def add_relation(self, subject, relation_type, target, sense_id=None,
                     source="user", confidence=1.0):
        s = self._sense(subject)
        for r in s["relations"]:
            if r["type"] == relation_type and r["target"] == target:
                return False
        s["relations"].append({"type": relation_type, "target": target,
                               "source": source, "confidence": confidence,
                               "status": "confirmed" if source == "user" else "unverified"})
        return True

    def _rel(self, w, sid, t, d):
        c = self.store.concepts.get(w)
        for s in (c or {}).get("senses", []):
            if s["sense_id"] == sid:
                for r in s["relations"]:
                    if r["type"] == t and r["target"] == d:
                        return r
        return None

    def confirm_relation(self, word, sense_id, relation_type, target):
        r = self._rel(word, sense_id, relation_type, target)
        if not r or r["status"] == "rejected":
            return None
        r["status"], r["confidence"] = "confirmed", 1.0
        return r

    def reject_relation(self, word, sense_id, relation_type, target, reason=""):
        r = self._rel(word, sense_id, relation_type, target)
        if not r:
            return None
        r["status"] = "rejected"
        return r


FEITEN = [
    {"onderwerp": "fiets", "relatie": "is_a", "doel": "voertuig", "zin": "z1"},
    {"onderwerp": "basisfiets", "relatie": "has_part", "doel": "wielen", "zin": "z2"},
    {"onderwerp": "basisfiets", "relatie": "has_part", "doel": "stuur", "zin": "z3"},
]


def maak(feiten=FEITEN, beschikbaar=True, tekst="Een fiets is een voertuig."):
    bus = FakeBus()
    sem = FakeSem()
    kp = KnowledgeProposals(bus, sem, extractor=FakeExtractor(feiten, beschikbaar),
                            fetch=lambda w: tekst)
    return bus, sem, kp


def vraag(bus, woord="fiets"):
    bus.publish("intent_kennis_extract", {"word": woord})


def keuze(bus, actie, nummer=None, alles=False):
    bus.publish("intent_kennis_keuze", {"actie": actie, "nummer": nummer, "alles": alles})


def test_lijst_wordt_getoond_zonder_iets_op_te_slaan():
    bus, sem, kp = maak()
    vraag(bus)
    t = bus.teksten()[-1]
    assert "1. fiets is een voertuig" in t
    assert "2. 'wiel' is onderdeel van 'basisfiets'" in t   # meervoud -> enkelvoud
    assert "nog niets opgeslagen" in t
    assert sem.store.concepts == {}                           # echt niets bewaard


def test_neem_over_slaat_op_en_bevestigt():
    bus, sem, kp = maak()
    vraag(bus)
    keuze(bus, "neem", 1)
    rel = sem.store.concepts["fiets"]["senses"][0]["relations"][0]
    assert rel["status"] == "confirmed" and rel["source"] == "wikipedia"
    assert "Opgeslagen en bevestigd" in bus.teksten()[-1]


def test_has_part_wordt_part_of_deel_naar_geheel():
    bus, sem, kp = maak()
    vraag(bus)
    keuze(bus, "neem", 2)
    rel = sem.store.concepts["wiel"]["senses"][0]["relations"][0]
    assert (rel["type"], rel["target"]) == ("part_of", "basisfiets")


def test_neem_alles_over():
    bus, sem, kp = maak()
    vraag(bus)
    keuze(bus, "neem", alles=True)
    assert {"fiets", "wiel", "stuur"} <= set(sem.store.concepts)


def test_nummers_verschuiven_niet_en_dubbel_behandelen_mag_niet():
    bus, sem, kp = maak()
    vraag(bus)
    keuze(bus, "neem", 1)
    keuze(bus, "neem", 1)
    assert "al behandeld" in bus.teksten()[-1]
    keuze(bus, "neem", 3)          # nummer 3 bestaat nog steeds
    assert "stuur" in sem.store.concepts


def test_laat_vallen_maakt_tombstone_en_komt_niet_terug():
    bus, sem, kp = maak()
    vraag(bus)
    keuze(bus, "laat_vallen", 1)
    rel = sem.store.concepts["fiets"]["senses"][0]["relations"][0]
    assert rel["status"] == "rejected"
    vraag(bus)                      # opnieuw vragen
    t = bus.teksten()[-1]
    assert "fiets is een voertuig" not in t
    assert "had je eerder afgewezen" in t


def test_reeds_bekende_relatie_wordt_niet_voorgesteld():
    bus, sem, kp = maak()
    sem.add_relation("fiets", "is_a", "voertuig", source="user")
    vraag(bus)
    t = bus.teksten()[-1]
    assert "fiets is een voertuig" not in t
    assert "stond(en) er al" in t


def test_nummer_buiten_bereik():
    bus, sem, kp = maak()
    vraag(bus)
    keuze(bus, "neem", 9)
    assert "staat niet in de lijst" in bus.teksten()[-1]


def test_geen_lijst_actief():
    bus, sem, kp = maak()
    keuze(bus, "neem", 1)
    assert "geen actuele voorstellen" in bus.teksten()[-1]


def test_lijst_verloopt():
    bus, sem, kp = maak()
    vraag(bus)
    kp._lijst_tijd = time.time() - 10_000
    keuze(bus, "neem", 1)
    assert "geen actuele voorstellen" in bus.teksten()[-1]
    assert sem.store.concepts == {}


def test_alles_laten_vallen_bestaat_niet():
    bus, sem, kp = maak()
    vraag(bus)
    keuze(bus, "laat_vallen", alles=True)
    assert "bewust niet" in bus.teksten()[-1]
    assert sem.store.concepts == {}


def test_extractor_uit():
    bus, sem, kp = maak(beschikbaar=False)
    vraag(bus)
    assert "staat uit" in bus.teksten()[-1]


def test_wikipedia_niet_bereikbaar():
    bus, sem, kp = maak(tekst="")
    vraag(bus)
    assert "niet ophalen" in bus.teksten()[-1]


def test_geen_feiten():
    bus, sem, kp = maak(feiten=[])
    vraag(bus)
    assert "geen betrouwbare feiten" in bus.teksten()[-1]


def test_leeg_woord():
    bus, sem, kp = maak()
    vraag(bus, "  ")
    assert "Van welk woord" in bus.teksten()[-1]


def test_onbruikbare_feiten_worden_overgeslagen():
    feiten = [{"onderwerp": "x", "relatie": "causes", "doel": "y", "zin": ""},
              {"onderwerp": "hond", "relatie": "is_a", "doel": "hond", "zin": ""}]
    bus, sem, kp = maak(feiten=feiten)
    vraag(bus)
    assert "geen betrouwbare feiten" in bus.teksten()[-1] or "niets nieuws" in bus.teksten()[-1]


def test_vallen_laten_wijst_niets_af_dat_intussen_bevestigd_is():
    bus, sem, kp = maak()
    vraag(bus)
    sem.add_relation("fiets", "is_a", "voertuig", source="user")   # intussen bevestigd
    keuze(bus, "laat_vallen", 1)
    rel = sem.store.concepts["fiets"]["senses"][0]["relations"][0]
    assert rel["status"] == "confirmed"


def test_maximaal_tien_voorstellen():
    feiten = [{"onderwerp": "x", "relatie": "is_a", "doel": f"d{i}", "zin": ""} for i in range(13)]
    bus, sem, kp = maak(feiten=feiten)
    vraag(bus, "x")
    t = bus.teksten()[-1]
    assert "10. x is een d9" in t and "11." not in t and "nog 3 meer" in t