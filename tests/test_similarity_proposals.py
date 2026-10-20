"""
Tests voor similarity_proposals.py (Fase 12, stap 2).

Geen echt ML-model en niet de echte semantic.py: een nep-kennisbank die
add_relation / confirm_relation / reject_relation nabootst zoals Nova's
RelationEngine (inclusief de duplicate-check, ook voor afgewezen relaties).
"""

import pytest

from modules.knowledge.similarity_proposals import SimilarityProposals, init_module


class Bus:
    def __init__(self):
        self.handlers = {}
        self.berichten = []
        self.modules = {}

    def subscribe(self, naam, fn):
        self.handlers[naam] = fn

    def publish(self, naam, data=None):
        if naam == "chat_response":
            self.berichten.append(data["text"])

    def register_module(self, naam, inst):
        self.modules[naam] = inst

    def laatste(self):
        return self.berichten[-1]


class NepStore:
    def __init__(self, concepten):
        self.concepts = concepten

    def get_concept(self, w):
        return self.concepts.get(w.lower().strip())

    def has_concept(self, w):
        return w.lower().strip() in self.concepts


class NepSem:
    def __init__(self, concepten):
        self.store = NepStore(concepten)

    def add_relation(self, subject, relation_type, target, sense_id=None,
                     source="user", confidence=1.0):
        sense = self.store.concepts[subject]["senses"][0]
        for rel in sense["relations"]:
            if rel["type"] == relation_type and rel["target"] == target:
                return False
        sense["relations"].append({
            "type": relation_type, "target": target, "confidence": confidence,
            "source": source,
            "status": "confirmed" if source == "user" else "unverified",
        })
        return True

    def confirm_relation(self, word, sense_id, relation_type, target):
        for s in self.store.concepts[word]["senses"]:
            if s["sense_id"] != sense_id:
                continue
            for rel in s["relations"]:
                if rel["type"] == relation_type and rel["target"] == target:
                    if rel["status"] == "rejected":
                        return None
                    rel["status"] = "confirmed"
                    rel["oorspronkelijke_bron"] = rel["source"]
                    rel["source"] = "user"
                    return rel
        return None

    def reject_relation(self, word, sense_id, relation_type, target, reason=""):
        for s in self.store.concepts[word]["senses"]:
            if s["sense_id"] != sense_id:
                continue
            for rel in s["relations"]:
                if rel["type"] == relation_type and rel["target"] == target:
                    rel["status"] = "rejected"
                    return rel
        return None

    def hard_delete_relation(self, word, sense_id, relation_type, target):
        """Zoals Nova: alleen toegestaan voor een al afgewezen relatie."""
        for s in self.store.concepts[word]["senses"]:
            if s["sense_id"] != sense_id:
                continue
            for i, rel in enumerate(s["relations"]):
                if rel["type"] == relation_type and rel["target"] == target:
                    if rel["status"] != "rejected":
                        return False
                    s["relations"].pop(i)
                    return True
        return False


class NepSpecialist:
    def __init__(self, resultaten, beschikbaar=True):
        self.resultaten = resultaten
        self.beschikbaar = beschikbaar
        self.reden_uit = None if beschikbaar else "model ontbreekt"
        self._cache = {"x": 1}

    def is_beschikbaar(self):
        return self.beschikbaar

    def find_similar(self, woord, top_k=5, min_score=0.0):
        return [r for r in self.resultaten if r["score"] >= min_score][:top_k]

    def find_all_pairs(self, min_score=0.5):
        return [p for p in getattr(self, "paren", []) if p["score"] >= min_score]


def concept(naam, relaties=()):
    return {"senses": [{"sense_id": f"{naam}#1", "definition": f"def {naam}",
                        "status": "confirmed", "relations": list(relaties)}]}


def res(woord, score):
    return {"woord": woord, "score": score, "bron": "embedding", "model": "nep"}


@pytest.fixture
def opstelling():
    concepten = {
        "fiets": concept("fiets", [
            {"type": "has_part", "target": "stuur", "status": "confirmed"},
        ]),
        "stuur": concept("stuur"),
        "rem": concept("rem"),
        "wiel": concept("wiel", [
            {"type": "part_of", "target": "fiets", "status": "confirmed"},
        ]),
        "wolf": concept("wolf"),
        "zadel": concept("zadel"),
    }
    concepten["fiets"]["senses"][0]["relations"].append(
        {"type": "is_a", "target": "wolf", "status": "rejected"})
    bus = Bus()
    sem = NepSem(concepten)
    spec = NepSpecialist([
        res("stuur", 0.80),   # staat al (fiets -> stuur): overslaan
        res("wiel", 0.70),    # staat al in omgekeerde richting: overslaan
        res("wolf", 0.65),    # eerder afgewezen: overslaan
        res("rem", 0.60),
        res("zadel", 0.55),
        res("laagscorer", 0.10),   # onder MIN_SCORE
    ])
    mod = SimilarityProposals(bus, sem, specialist=spec)
    return bus, sem, mod


def zoek(mod, woord="fiets"):
    mod.on_search({"word": woord})


def test_zoekt_en_filtert_bestaande_en_afgewezen(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)
    tekst = bus.laatste()
    assert "1. rem" in tekst and "2. zadel" in tekst
    for weg in ("stuur", "wiel", "wolf", "laagscorer"):
        assert f". {weg}" not in tekst
    assert "nog niets opgeslagen" in tekst
    assert "Ik heb gezocht" in tekst
    assert "1 had je eerder afgewezen" in tekst
    assert "hebben al een relatie" in tekst


def test_zoeken_slaat_niets_op(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)
    assert sem.store.concepts["rem"]["senses"][0]["relations"] == []
    assert len(sem.store.concepts["fiets"]["senses"][0]["relations"]) == 2


def test_koppel_standaard_is_related_to_en_bevestigd(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummer": 1, "type": None})
    rel = sem.store.concepts["fiets"]["senses"][0]["relations"][-1]
    assert (rel["type"], rel["target"], rel["status"]) == ("related_to", "rem", "confirmed")
    assert rel["oorspronkelijke_bron"] == "embedding"
    assert "Opgeslagen en bevestigd" in bus.laatste()


def test_koppel_met_type(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummer": 2, "type": "onderdeel"})
    rel = sem.store.concepts["fiets"]["senses"][0]["relations"][-1]
    assert (rel["type"], rel["target"]) == ("part_of", "zadel")


def test_negeer_maakt_tombstone_en_paar_komt_niet_terug(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)
    mod.on_keuze({"actie": "negeer", "nummer": 1, "type": None})
    rel = sem.store.concepts["fiets"]["senses"][0]["relations"][-1]
    assert (rel["target"], rel["status"]) == ("rem", "rejected")
    zoek(mod)
    assert ". rem" not in bus.laatste()


def test_nummer_twee_keer_behandelen_kan_niet(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummer": 1, "type": None})
    mod.on_keuze({"actie": "koppel", "nummer": 1, "type": None})
    assert "al behandeld" in bus.laatste()


def test_nummer_buiten_lijst(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummer": 9, "type": None})
    assert "staat niet in de lijst" in bus.laatste()


def test_keuze_zonder_lijst(opstelling):
    bus, sem, mod = opstelling
    mod.on_keuze({"actie": "koppel", "nummer": 1, "type": None})
    assert "geen actuele voorstellen" in bus.laatste()


def test_lijst_verloopt(opstelling, monkeypatch):
    bus, sem, mod = opstelling
    zoek(mod)
    mod._lijst_tijd -= 10_000
    mod.on_keuze({"actie": "koppel", "nummer": 1, "type": None})
    assert "geen actuele voorstellen" in bus.laatste()


def test_onbekend_type_wordt_genegeerd(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)
    aantal = len(bus.berichten)
    mod.on_keuze({"actie": "koppel", "nummer": 1, "type": "raar"})
    assert len(bus.berichten) == aantal
    assert sem.store.concepts["rem"]["senses"][0]["relations"] == []


def test_koppel_dat_intussen_bestaat(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)
    sem.add_relation("fiets", "related_to", "rem", source="user")
    mod.on_keuze({"actie": "koppel", "nummer": 1, "type": None})
    assert "bestaat al een relatie" in bus.laatste()


def test_onbekend_woord(opstelling):
    bus, sem, mod = opstelling
    zoek(mod, "bestaatniet")
    assert "nog niet" in bus.laatste()


def test_specialist_uit(opstelling):
    bus, sem, mod = opstelling
    mod._specialist = NepSpecialist([], beschikbaar=False)
    zoek(mod)
    assert "staat uit" in bus.laatste() and "model ontbreekt" in bus.laatste()


def test_specialist_ontbreekt_helemaal():
    bus = Bus()
    mod = SimilarityProposals(bus, NepSem({"fiets": concept("fiets")}))
    mod.on_search({"word": "fiets"})
    assert "staat uit" in bus.laatste()


def test_zonder_sem():
    bus = Bus()
    SimilarityProposals(bus, None).on_search({"word": "fiets"})
    assert "niet beschikbaar" in bus.laatste()


def test_init_module_abonneert():
    bus = Bus()
    init_module(bus, None)
    assert "intent_similarity_search" in bus.handlers
    assert "intent_similarity_keuze" in bus.handlers


# ---------------------------------------------------------------
# Meerdere nummers tegelijk, "negeer rest"
# ---------------------------------------------------------------
@pytest.fixture
def drie_voorstellen():
    concepten = {n: concept(n) for n in ["fiets", "rem", "zadel", "bel", "licht"]}
    bus, sem = Bus(), NepSem(concepten)
    spec = NepSpecialist([res("rem", 0.9), res("zadel", 0.8), res("bel", 0.7),
                          res("licht", 0.6)])
    return bus, sem, SimilarityProposals(bus, sem, specialist=spec)


def rels(sem, w="fiets"):
    return {(r["type"], r["target"], r["status"])
            for r in sem.store.concepts[w]["senses"][0]["relations"]}


def test_koppel_meerdere_nummers(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1, 3], "type": None})
    assert rels(sem) == {("related_to", "rem", "confirmed"),
                         ("related_to", "bel", "confirmed")}
    assert bus.laatste().count("Opgeslagen en bevestigd") == 2


def test_negeer_meerdere_nummers(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "negeer", "nummers": [2, 4]})
    assert rels(sem) == {("related_to", "zadel", "rejected"),
                         ("related_to", "licht", "rejected")}


def test_negeer_rest_slaat_behandelde_over(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})
    mod.on_keuze({"actie": "negeer", "rest": True})
    assert rels(sem) == {("related_to", "rem", "confirmed"),
                         ("related_to", "zadel", "rejected"),
                         ("related_to", "bel", "rejected"),
                         ("related_to", "licht", "rejected")}


def test_koppel_rest_bestaat_niet(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    aantal = len(bus.berichten)
    mod.on_keuze({"actie": "koppel", "rest": True, "type": None})
    assert len(bus.berichten) == aantal
    assert rels(sem) == set()


def test_meerdere_nummers_met_ongeldige_en_dubbele(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1, 1, 9], "type": None})
    tekst = bus.laatste()
    assert tekst.count("Opgeslagen en bevestigd") == 1      # dubbel nummer 1x
    assert "Nummer 9 staat niet in de lijst" in tekst
    assert rels(sem) == {("related_to", "rem", "confirmed")}


def test_negeer_rest_zonder_open_voorstellen(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "negeer", "rest": True})
    mod.on_keuze({"actie": "negeer", "rest": True})
    assert "al behandeld" in bus.laatste()


# ---------------------------------------------------------------
# Wachtrij: "gelijkenissen overlopen" / "volgende gelijkenissen"
# ---------------------------------------------------------------
def rel(doel, type_="related_to", status="confirmed"):
    return {"type": type_, "target": doel, "status": status}


def met(*relaties):
    """Concept met deze relaties (naam doet er niet toe)."""
    return concept("x", list(relaties))


def paar(a, b, score):
    return {"woord_a": a, "woord_b": b, "score": score, "model": "nep"}


def maak_wachtrij(paren, concepten=None, extra=()):
    namen = {w for p in paren for w in (p["woord_a"], p["woord_b"])} | set(extra)
    c = {n: concept(n) for n in namen}
    c.update(concepten or {})
    bus, sem = Bus(), NepSem(c)
    spec = NepSpecialist([])
    spec.paren = paren
    return bus, sem, SimilarityProposals(bus, sem, specialist=spec)


@pytest.fixture
def wachtrij():
    # tien losse paren (elk woord maar een keer) + een dat al bestaat + een te lage score
    paren = [paar(f"a{i}", f"b{i}", round(0.95 - i * 0.03, 2)) for i in range(10)]
    paren.append(paar("fiets", "motor", 0.99))        # bestaat al
    paren.append(paar("zwaan", "geit", 0.30))         # onder OVERLOOP_MIN_SCORE
    conc = {"fiets": met(rel("motor")), "motor": met()}
    return maak_wachtrij(paren, conc)


def test_overlopen_toont_acht_hoogste_nieuwe_paren(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    tekst = bus.laatste()
    assert "1. a0 en b0" in tekst
    assert "8. a7 en b7" in tekst
    assert "a8" not in tekst                     # komt in de volgende ronde
    assert "motor" not in tekst                  # bestond al
    assert "zwaan" not in tekst                  # te lage score
    assert "Nog niets opgeslagen" in tekst
    assert "Er staan er 10 in de wachtrij" in tekst
    assert rels(sem, "a0") == set()              # niets opgeslagen


def test_volgende_geeft_de_rest(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    mod.on_review({"actie": "volgende"})
    assert "1. a8 en b8" in bus.laatste() and "2. a9 en b9" in bus.laatste()
    mod.on_review({"actie": "volgende"})
    assert "wachtrij is leeg" in bus.laatste()


def test_volgende_zonder_start(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "volgende"})
    assert "Typ eerst" in bus.laatste()


def test_elk_woord_hooguit_een_keer_met_beste_partner():
    bus, sem, mod = maak_wachtrij([
        paar("auto", "bus", 0.90),
        paar("auto", "trein", 0.85),      # auto al gebruikt
        paar("tram", "bus", 0.80),        # bus al gebruikt
        paar("tram", "trein", 0.70),      # wel: tram en trein zijn nog vrij
    ])
    mod.on_review({"actie": "start"})
    tekst = bus.laatste()
    assert "1. auto en bus" in tekst and "2. tram en trein" in tekst
    assert "3." not in tekst


def test_paar_met_gedeelde_ouder_wordt_overgeslagen():
    conc = {
        "negen": met(rel("getal", "is_a")),
        "tien": met(rel("getal", "is_a")),
        "kies": met(rel("tand", "is_a")),
        "snijtand": met(rel("tand", "is_a")),
        "lederhuid": met(rel("huid", "part_of")),
        "opperhuid": met(rel("huid", "part_of")),
    }
    bus, sem, mod = maak_wachtrij([
        paar("negen", "tien", 0.99),
        paar("kies", "snijtand", 0.95),
        paar("lederhuid", "opperhuid", 0.93),
        paar("wenkbrauw", "wimper", 0.90),
    ], conc)
    mod.on_review({"actie": "start"})
    tekst = bus.laatste()
    assert "1. wenkbrauw en wimper" in tekst
    genummerd = [r for r in tekst.splitlines() if r[:1].isdigit()]
    assert len(genummerd) == 1                   # alleen wenkbrauw en wimper
    for weg in ("negen", "kies", "lederhuid"):
        assert weg not in genummerd[0]
    assert "Ik sla 3 paren over" in tekst


def test_verschillende_ouders_blijven_staan():
    conc = {"wenkbrauw": met(rel("gezicht", "part_of")),
            "wimper": met(rel("oog", "part_of"))}
    bus, sem, mod = maak_wachtrij([paar("wenkbrauw", "wimper", 0.90)], conc)
    mod.on_review({"actie": "start"})
    assert "1. wenkbrauw en wimper" in bus.laatste()
    assert "paren over" not in bus.laatste()


def test_afgewezen_ouder_telt_niet_als_gedeeld():
    conc = {"x": met(rel("groep", "is_a", status="rejected")),
            "y": met(rel("groep", "is_a"))}
    bus, sem, mod = maak_wachtrij([paar("x", "y", 0.90)], conc)
    mod.on_review({"actie": "start"})
    assert "1. x en y" in bus.laatste()


def test_koppel_in_wachtrij_slaat_op_als_verwant(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})
    assert rels(sem, "a0") == {("related_to", "b0", "confirmed")}


def test_wachtrij_staat_synoniem_toe(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": "synoniem"})
    assert rels(sem, "a0") == {("synonym", "b0", "confirmed")}


def test_wachtrij_soort_volgt_de_volgorde_van_de_lijst(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": "soort"})
    assert rels(sem, "a0") == {("is_a", "b0", "confirmed")}
    assert "'a0' is een soort 'b0'" in bus.laatste()


def test_wachtrij_omgekeerd_draait_de_richting_om(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": "soort", "omgekeerd": True})
    assert rels(sem, "a0") == set()
    assert rels(sem, "b0") == {("is_a", "a0", "confirmed")}
    assert "'b0' is een soort 'a0'" in bus.laatste()


@pytest.mark.parametrize("type_nl,rel_type", [
    ("onderdeel", "part_of"), ("bevat", "has_part"), ("synoniem", "synonym")])
def test_wachtrij_alle_types_en_omgekeerd(wachtrij, type_nl, rel_type):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    mod.on_keuze({"actie": "koppel", "nummers": [2], "type": type_nl, "omgekeerd": True})
    assert rels(sem, "b1") == {(rel_type, "a1", "confirmed")}


def test_omgekeerd_werkt_ook_bij_zoeken_per_woord(opstelling):
    bus, sem, mod = opstelling
    zoek(mod)                                  # 1. rem, 2. zadel
    mod.on_keuze({"actie": "koppel", "nummers": [2], "type": "onderdeel",
                  "omgekeerd": True})
    assert rels(sem, "zadel") == {("part_of", "fiets", "confirmed")}
    assert rels(sem, "fiets") & {("part_of", "zadel", "confirmed")} == set()


def test_omgekeerd_op_bestaand_paar_slaat_niets_dubbel_op(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})
    mod.on_review({"actie": "start"})
    assert "a0 en b0" not in bus.laatste()     # paar komt niet meer terug


def test_negeer_in_wachtrij_en_paar_komt_niet_terug(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    mod.on_keuze({"actie": "negeer", "nummers": [1]})
    assert rels(sem, "a0") == {("related_to", "b0", "rejected")}
    mod.on_review({"actie": "start"})
    assert "a0 en b0" not in bus.laatste()


def test_lijst_klaar_geeft_hint_voor_volgende(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    mod.on_keuze({"actie": "negeer", "rest": True})
    assert "volgende gelijkenissen" in bus.laatste()


def test_wachtrij_paar_dat_intussen_een_relatie_kreeg_wordt_overgeslagen(wachtrij):
    bus, sem, mod = wachtrij
    mod.on_review({"actie": "start"})
    sem.add_relation("a8", "related_to", "b8", source="user")
    mod.on_review({"actie": "volgende"})
    assert "a8" not in bus.laatste() and "a9 en b9" in bus.laatste()


def test_review_met_specialist_uit(wachtrij):
    bus, sem, mod = wachtrij
    mod._specialist = NepSpecialist([], beschikbaar=False)
    mod.on_review({"actie": "start"})
    assert "staat uit" in bus.laatste()


def test_init_module_abonneert_ook_review():
    bus = Bus()
    init_module(bus, None)
    assert "intent_similarity_review" in bus.handlers


    # ---------------------------------------------------------------
# "maak ongedaan"
# ---------------------------------------------------------------
def test_ongedaan_zonder_iets_te_doen(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    mod.on_ongedaan({})
    assert "niets om ongedaan te maken" in bus.laatste()


def test_ongedaan_draait_koppel_terug_en_geeft_nummer_vrij(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": "soort", "omgekeerd": True})
    assert rels(sem, "rem") == {("is_a", "fiets", "confirmed")}
    assert "maak ongedaan" in bus.laatste()
    mod.on_ongedaan({})
    assert rels(sem, "rem") == set()              # echt weg, geen tombstone
    assert rels(sem) == set()
    assert "Ongedaan gemaakt" in bus.laatste()
    assert "Nummer 1 staat weer in de lijst" in bus.laatste()
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})   # opnieuw kan
    assert rels(sem) == {("related_to", "rem", "confirmed")}


def test_ongedaan_draait_hele_commando_terug(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1, 2, 3], "type": None})
    mod.on_ongedaan({})
    assert rels(sem) == set()
    assert "Nummer 1, 2, 3 staat weer" in bus.laatste()


def test_ongedaan_draait_negeer_terug_en_paar_komt_terug(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "negeer", "nummers": [2], "type": None})
    assert ("related_to", "zadel", "rejected") in rels(sem)
    mod.on_ongedaan({})
    assert rels(sem) == set()
    assert "niet meer afgewezen" in bus.laatste()
    zoek(mod)
    assert ". zadel" in bus.laatste()


def test_ongedaan_kan_maar_een_keer(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})
    mod.on_ongedaan({})
    mod.on_ongedaan({})
    assert "niets om ongedaan te maken" in bus.laatste()


def test_ongedaan_draait_alleen_het_laatste_commando_terug(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})
    mod.on_keuze({"actie": "koppel", "nummers": [2], "type": None})
    mod.on_ongedaan({})
    assert rels(sem) == {("related_to", "rem", "confirmed")}


def test_mislukt_commando_wist_de_ongedaan_info_niet(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})   # al behandeld
    mod.on_ongedaan({})
    assert rels(sem) == set()


def test_ongedaan_raakt_door_jou_aangepaste_relatie_niet_aan(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})
    r = sem.store.concepts["fiets"]["senses"][0]["relations"][-1]
    r["source"] = "user"
    r.pop("oorspronkelijke_bron", None)       # nu door jou zelf ingevoerd
    mod.on_ongedaan({})
    assert rels(sem) == {("related_to", "rem", "confirmed")}
    assert "intussen aangepast" in bus.laatste()


def test_ongedaan_na_nieuwe_lijst_zet_niets_terug_in_de_verkeerde_lijst(drie_voorstellen):
    bus, sem, mod = drie_voorstellen
    zoek(mod)
    mod.on_keuze({"actie": "koppel", "nummers": [1], "type": None})
    zoek(mod)                                  # nieuwe lijst zonder rem
    nieuwe = list(mod._lijst)
    mod.on_ongedaan({})
    assert rels(sem) == set()
    assert mod._lijst == nieuwe                # niet vervuild
    assert "staat weer in de lijst" not in bus.laatste()


def test_ongedaan_zonder_sem_en_abonnement():
    bus = Bus()
    mod = SimilarityProposals(bus, None, specialist=NepSpecialist([]))
    mod.on_ongedaan({})
    assert "niet beschikbaar" in bus.laatste()
    assert "intent_similarity_ongedaan" in bus.handlers

    # ---------------------------------------------------------------
# Wachtrij: paren die al via een keten bekend zijn
# ---------------------------------------------------------------
def keten_wachtrij(paren, concepten):
    bus, sem, mod = maak_wachtrij(paren, concepten)
    mod.on_review({"actie": "start"})
    return bus, mod


def test_keten_is_a_wordt_overgeslagen_en_geteld():
    # jurk -> kledingstuk -> kleding: jurk/kleding is al bekend
    conc = {"jurk": met(rel("kledingstuk", "is_a")),
            "kledingstuk": met(rel("kleding", "is_a")),
            "kleding": met()}
    bus, mod = keten_wachtrij([paar("jurk", "kleding", 0.9),
                               paar("tent", "kamp", 0.8)], conc)
    tekst = bus.laatste()
    assert "jurk en kleding" not in tekst
    assert "1. tent en kamp" in tekst
    assert "1 paren over waarvan het ene woord al een voorouder" in tekst


def test_keten_werkt_ook_andersom_in_de_paarvolgorde():
    conc = {"jurk": met(rel("kledingstuk", "is_a")),
            "kledingstuk": met(rel("kleding", "is_a")), "kleding": met()}
    bus, mod = keten_wachtrij([paar("kleding", "jurk", 0.9)], conc)
    assert "geen nieuwe paren" in bus.laatste()


def test_keten_part_of_en_has_part_als_omgekeerde():
    # romp has_part buik, buik has_part maag: maag part_of buik part_of romp
    conc = {"romp": met(rel("buik", "has_part")),
            "buik": met(rel("maag", "has_part")), "maag": met()}
    bus, mod = keten_wachtrij([paar("maag", "romp", 0.9)], conc)
    assert "geen nieuwe paren" in bus.laatste()


def test_keten_via_synoniem_blijft_staan():
    # meubelstuk = meubel, stoel is_a meubel: Nova volgt geen synoniemen, dus nieuw
    conc = {"meubelstuk": met(rel("meubel", "synonym")),
            "stoel": met(rel("meubel", "is_a")), "meubel": met()}
    bus, mod = keten_wachtrij([paar("meubelstuk", "stoel", 0.9)], conc)
    assert "1. meubelstuk en stoel" in bus.laatste()


def test_is_a_en_part_of_ketens_worden_niet_door_elkaar_gehaald():
    conc = {"a": met(rel("b", "is_a")), "b": met(rel("c", "part_of")), "c": met()}
    bus, mod = keten_wachtrij([paar("a", "c", 0.9)], conc)
    assert "1. a en c" in bus.laatste()


def test_afgewezen_stap_in_keten_telt_niet_mee():
    conc = {"a": met(rel("b", "is_a")),
            "b": met(rel("c", "is_a", status="rejected")), "c": met()}
    bus, mod = keten_wachtrij([paar("a", "c", 0.9)], conc)
    assert "1. a en c" in bus.laatste()


def test_keten_met_kringverwijzing_loopt_niet_vast():
    conc = {"a": met(rel("b", "is_a")), "b": met(rel("a", "is_a")), "x": met()}
    bus, mod = keten_wachtrij([paar("a", "x", 0.9)], conc)
    assert "1. a en x" in bus.laatste()


def test_geen_ketenmelding_als_er_niets_is_overgeslagen():
    bus, mod = keten_wachtrij([paar("tent", "kamp", 0.9)], {})
    assert "voorouder" not in bus.laatste()