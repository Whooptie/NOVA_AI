"""
Tests voor ChatModule.on_related_to ("waarop lijkt X").

Sinds Fase 12 (19 oktober 2026) telt ook een relatie mee die van een ANDER
woord naar X wijst: related_to is wederzijds, en "koppel N" slaat een
voorstel maar aan een kant op (fiets -> motor).
"""

from modules.chat.chat import ChatModule


class Bus:
    def __init__(self):
        self.antwoorden = []
        self.modules = {}

    def subscribe(self, naam, fn):
        pass

    def publish(self, naam, data=None):
        if naam == "layer4_response":
            self.antwoorden.append(data["text"])


def rel(doel, type_="related_to", status="confirmed"):
    return {"type": type_, "target": doel, "status": status}


def concept(*relaties, status="confirmed"):
    return {"senses": [{"sense_id": "x#1", "status": status,
                        "relations": list(relaties)}]}


class NepStore:
    def __init__(self, concepten):
        self.concepts = concepten


class NepSemantic:
    """Bootst get_relations() na: alleen UITGAANDE, niet-afgewezen relaties."""
    def __init__(self, concepten):
        self.store = NepStore(concepten)

    def get_relations(self, word, relation_type=None):
        uit = []
        for s in self.store.concepts.get(word, {}).get("senses", []):
            if s.get("status") == "rejected":
                continue
            for r in s["relations"]:
                if r.get("status") == "rejected":
                    continue
                if relation_type is None or r["type"] == relation_type:
                    uit.append(r["target"])
        return uit


def vraag(concepten, woord):
    bus = Bus()
    ChatModule(bus, NepSemantic(concepten)).on_related_to({"word": woord})
    return bus.antwoorden[-1]


def test_uitgaande_relatie_blijft_werken():
    c = {"fiets": concept(rel("motor")), "motor": concept()}
    assert "fiets lijkt op: motor" in vraag(c, "fiets")


def test_binnenkomende_relatie_telt_mee():
    c = {"fiets": concept(rel("motor")), "motor": concept()}
    assert "motor lijkt op: fiets" in vraag(c, "motor")


def test_uitgaand_en_binnenkomend_samen_zonder_dubbelen():
    c = {
        "fiets": concept(rel("motor"), rel("step")),
        "motor": concept(rel("fiets")),          # wederzijds: fiets maar 1x
        "step": concept(),
        "brommer": concept(rel("motor")),
    }
    antwoord = vraag(c, "motor")
    assert antwoord.count("fiets") == 1
    assert "brommer" in antwoord and "step" not in antwoord


def test_afgewezen_relatie_telt_niet_mee():
    c = {"fiets": concept(rel("bil", status="rejected")), "bil": concept()}
    assert "Ik weet niet waarop bil lijkt" in vraag(c, "bil")


def test_afgewezen_sense_telt_niet_mee():
    c = {"fiets": concept(rel("motor"), status="rejected"), "motor": concept()}
    assert "Ik weet niet waarop motor lijkt" in vraag(c, "motor")


def test_ander_relatietype_telt_niet_mee():
    c = {"fiets": concept(rel("voertuig", type_="is_a")), "voertuig": concept()}
    assert "Ik weet niet waarop voertuig lijkt" in vraag(c, "voertuig")


def test_onbekend_woord():
    assert "Ik weet niet waarop zzz lijkt" in vraag({"fiets": concept()}, "zzz")


def test_zonder_store_crasht_niet():
    bus = Bus()

    class ZonderStore:
        def get_relations(self, word, relation_type=None):
            return ["motor"]

    ChatModule(bus, ZonderStore()).on_related_to({"word": "fiets"})
    assert "fiets lijkt op: motor" in bus.antwoorden[-1]