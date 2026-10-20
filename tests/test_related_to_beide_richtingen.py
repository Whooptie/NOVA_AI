"""
Tests voor explain_related_to / related_to_chained in beide richtingen.

Sinds Fase 12 (20 oktober 2026) slaat "koppel N" een voorstel maar aan een kant
op (fiets -> motor), terwijl related_to wederzijds is. Dus moet ook de vraag
"is motor gerelateerd aan fiets" ja zeggen. Test tegen de ECHTE ReasoningEngine,
met een kleine nep-kennisbank en een nep-RelationEngine die alleen UITGAANDE,
niet-afgewezen relaties teruggeeft (zoals Nova's get_relations()).
"""

from core.semantic import ReasoningEngine


def concept(*relaties, status="confirmed"):
    return {"senses": [{"sense_id": "x#1", "status": status,
                        "relations": [{"type": t, "target": d, "status": s}
                                      for (t, d, s) in relaties]}]}


class NepStore:
    def __init__(self, concepten):
        self.concepts = concepten


class NepRelaties:
    def __init__(self, store):
        self.store = store

    def get_relations(self, woord, relation_type=None):
        uit = []
        for sense in self.store.concepts.get(woord, {}).get("senses", []):
            if sense.get("status") == "rejected":
                continue
            for r in sense["relations"]:
                if r["status"] != "rejected" and (relation_type is None or r["type"] == relation_type):
                    uit.append(r["target"])
        return list(dict.fromkeys(uit))


def engine(concepten):
    store = NepStore(concepten)
    return ReasoningEngine(store, NepRelaties(store))


def rt(doel, status="confirmed"):
    return ("related_to", doel, status)


def test_omgekeerde_richting_geeft_ja():
    e = engine({"fiets": concept(rt("motor")), "motor": concept()})
    assert e.explain_related_to("fiets", "motor") == "Ja, fiets is gerelateerd aan motor."
    assert e.explain_related_to("motor", "fiets") == "Ja, motor is gerelateerd aan fiets."


def test_keten_mag_door_beide_richtingen_lopen():
    # a -> b en c -> b: van a naar c kan alleen als je b -> c achterstevoren neemt
    e = engine({"a": concept(rt("b")), "b": concept(), "c": concept(rt("b"))})
    found, pad = e.related_to_chained("a", "c")
    assert found and pad == ["a", "b", "c"]


def test_kortste_pad_blijft_kortste():
    e = engine({"a": concept(rt("b"), rt("c")), "b": concept(rt("d")),
                "c": concept(), "d": concept(rt("c"))})
    found, pad = e.related_to_chained("a", "c")
    assert found and pad == ["a", "c"]


def test_afgewezen_relatie_telt_niet_mee_in_beide_richtingen():
    e = engine({"auto": concept(rt("motor", "rejected")), "motor": concept()})
    assert "geen verband" in e.explain_related_to("motor", "auto")
    assert "geen verband" in e.explain_related_to("auto", "motor")


def test_afgewezen_sense_telt_niet_mee():
    e = engine({"auto": concept(rt("motor"), status="rejected"), "motor": concept()})
    assert e.related_to_chained("motor", "auto") == (False, [])


def test_andere_relatietypes_tellen_niet_mee():
    e = engine({"wiel": concept(("part_of", "fiets", "confirmed")), "fiets": concept()})
    assert e.related_to_chained("fiets", "wiel") == (False, [])


def test_alternatief_bij_negatief_antwoord_noemt_ook_binnenkomende_relatie():
    e = engine({"fiets": concept(rt("motor")), "motor": concept(), "boot": concept()})
    tekst = e.explain_related_to("motor", "boot")
    assert "Ik zie geen verband tussen 'motor' en 'boot'" in tekst
    assert "motor gerelateerd is aan fiets" in tekst


def test_helemaal_geen_relatie_blijft_kaal_antwoord():
    e = engine({"boot": concept(), "tent": concept()})
    assert e.explain_related_to("boot", "tent") == "Ik zie geen verband tussen 'boot' en 'tent'."


def test_diepte_limiet_blijft_gelden():
    ketting = {f"w{i}": concept(rt(f"w{i + 1}")) for i in range(6)}
    ketting["w6"] = concept()
    e = engine(ketting)
    assert e.related_to_chained("w0", "w4")[0] is True      # 4 stappen: net toegestaan
    assert e.related_to_chained("w0", "w5")[0] is False     # 5 stappen: te ver
    assert e.related_to_chained("w5", "w0")[0] is False     # achterstevoren: ook 5 stappen = te ver
    assert e.related_to_chained("w4", "w0")[0] is True      # achterstevoren: 4 stappen mag