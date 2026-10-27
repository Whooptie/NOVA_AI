# tests/test_intent_router_vergeet_wis.py
"""
Tests voor 'vergeet:' (beeindigt) en 'wis definitief:' (wist echt) in
IntentRouter.handle_preference() (27 oktober 2026).

IntentRouter.__init__ gebruikt alleen event_bus.subscribe(); het profiel
is een stub, dus geen enkel echt databestand wordt aangeraakt.
"""

from core.intent_router import IntentRouter


class DummyBus:
    def __init__(self):
        self.events = []
        self.modules = {}

    def subscribe(self, naam, functie):
        pass

    def publish(self, naam, data=None):
        self.events.append((naam, data))

    def teksten(self):
        return [d["text"] for n, d in self.events if n == "chat_response"]


class StubProfiel:
    def __init__(self, beeindig=True, wis=True):
        self.beeindig_resultaat = beeindig
        self.wis_resultaat = wis
        self.beeindigd = []
        self.gewist = []
        self.verwijderd = []
        self.toegevoegd = []

    def beeindig_preference(self, woord):
        self.beeindigd.append(woord)
        return self.beeindig_resultaat

    def wis_definitief(self, woord):
        self.gewist.append(woord)
        return self.wis_resultaat

    def remove_preference(self, woord, bron=None):
        self.verwijderd.append(woord)
        return True

    def add_preference(self, woord, sentiment, bron="automatisch"):
        self.toegevoegd.append((woord, sentiment, bron))


def maak_router(profiel):
    bus = DummyBus()
    return IntentRouter(bus, kevin_profile=profiel), bus


class TestVergeet:
    def test_beeindigt_en_wist_niet(self):
        profiel = StubProfiel()
        router, bus = maak_router(profiel)
        assert router.handle_preference("vergeet: koffie") is True
        assert profiel.beeindigd == ["koffie"]
        assert profiel.verwijderd == []
        assert profiel.gewist == []

    def test_bevestiging_noemt_het_wis_commando(self):
        router, bus = maak_router(StubProfiel())
        router.handle_preference("vergeet: koffie")
        tekst = bus.teksten()[0]
        assert "koffie" in tekst
        assert "wis definitief" in tekst

    def test_zonder_dubbele_punt(self):
        profiel = StubProfiel()
        router, _ = maak_router(profiel)
        router.handle_preference("vergeet koffie")
        assert profiel.beeindigd == ["koffie"]

    def test_onbekend_woord(self):
        router, bus = maak_router(StubProfiel(beeindig=False))
        router.handle_preference("vergeet: bestaatniet")
        assert "niets onthouden" in bus.teksten()[0]

    def test_leeg_woord_geeft_gebruiksaanwijzing(self):
        profiel = StubProfiel()
        router, bus = maak_router(profiel)
        router.handle_preference("vergeet: ")
        assert profiel.beeindigd == []
        assert "Gebruik" in bus.teksten()[0]


class TestWisDefinitief:
    def test_wist_definitief(self):
        profiel = StubProfiel()
        router, bus = maak_router(profiel)
        assert router.handle_preference("wis definitief: koffie") is True
        assert profiel.gewist == ["koffie"]
        assert profiel.beeindigd == []
        assert "Gewist" in bus.teksten()[0]

    def test_zonder_dubbele_punt(self):
        profiel = StubProfiel()
        router, _ = maak_router(profiel)
        router.handle_preference("wis definitief koffie")
        assert profiel.gewist == ["koffie"]

    def test_onbekend_woord(self):
        router, bus = maak_router(StubProfiel(wis=False))
        router.handle_preference("wis definitief: bestaatniet")
        assert "niets onthouden" in bus.teksten()[0]

    def test_leeg_woord_geeft_gebruiksaanwijzing(self):
        profiel = StubProfiel()
        router, bus = maak_router(profiel)
        router.handle_preference("wis definitief:")
        assert profiel.gewist == []
        assert "Gebruik" in bus.teksten()[0]


class TestOnthoudBlijftWerken:
    def test_onthoud_slaat_expliciet_op(self):
        profiel = StubProfiel()
        router, _ = maak_router(profiel)
        assert router.handle_preference("onthoud: ik hou van koffie") is True
        assert profiel.toegevoegd == [("koffie", "positief", "expliciet")]