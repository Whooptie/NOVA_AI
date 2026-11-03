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


# ---------------------------------------------------------
# Punt 60e (3 november 2026): einddatum bij 'vergeet:'
# ---------------------------------------------------------

class StubProfielMetDatum(StubProfiel):
    """Zoals het echte profiel: beeindig_preference(woord, datum=None)."""

    def __init__(self, beeindig=True, wis=True):
        super().__init__(beeindig, wis)
        self.datums = []

    def beeindig_preference(self, woord, datum=None):
        self.beeindigd.append(woord)
        self.datums.append(datum)
        return self.beeindig_resultaat


class TestVergeetMetDatum:
    def test_iso_datum_wordt_doorgegeven(self):
        profiel = StubProfielMetDatum()
        router, bus = maak_router(profiel)
        router.handle_preference("vergeet: koffie per 2025-06-01")
        assert profiel.beeindigd == ["koffie"]
        assert profiel.datums == ["2025-06-01"]
        assert "2025-06-01" in bus.teksten()[0]
        assert "wis definitief" in bus.teksten()[0]

    def test_europese_datum_wordt_omgezet(self):
        profiel = StubProfielMetDatum()
        router, _ = maak_router(profiel)
        router.handle_preference("vergeet: koffie per 01-06-2025")
        assert profiel.datums == ["2025-06-01"]

    def test_schuine_streep_mag_ook(self):
        profiel = StubProfielMetDatum()
        router, _ = maak_router(profiel)
        router.handle_preference("vergeet koffie per 1/6/2025")
        assert profiel.beeindigd == ["koffie"]
        assert profiel.datums == ["2025-06-01"]

    def test_meerwoordig_woord_met_datum(self):
        profiel = StubProfielMetDatum()
        router, _ = maak_router(profiel)
        router.handle_preference("vergeet: zwarte koffie per 2025-06-01")
        assert profiel.beeindigd == ["zwarte koffie"]

    def test_zonder_datum_geen_tweede_argument(self):
        profiel = StubProfielMetDatum()
        router, _ = maak_router(profiel)
        router.handle_preference("vergeet: koffie")
        assert profiel.datums == [None]

    def test_woord_met_per_maar_zonder_datum_blijft_het_woord(self):
        profiel = StubProfielMetDatum()
        router, _ = maak_router(profiel)
        router.handle_preference("vergeet: per se")
        assert profiel.beeindigd == ["per se"]
        assert profiel.datums == [None]

    def test_onbestaande_datum_wordt_geweigerd(self):
        profiel = StubProfielMetDatum()
        router, bus = maak_router(profiel)
        router.handle_preference("vergeet: koffie per 2025-13-45")
        assert profiel.beeindigd == []
        assert "snap ik niet" in bus.teksten()[0]

    def test_toekomstige_datum_wordt_geweigerd(self):
        profiel = StubProfielMetDatum()
        router, bus = maak_router(profiel)
        router.handle_preference("vergeet: koffie per 2999-01-01")
        assert profiel.beeindigd == []
        assert "toekomst" in bus.teksten()[0]


class TestVergeetMetDatumEindTotEind:
    """Router + ECHT KevinProfile (in tmp_path): de einddatum komt als
    valid_until in de historiek terecht."""

    def test_valid_until_is_de_opgegeven_datum(self, tmp_path, monkeypatch):
        from modules.preferences import kevin_profile as kp
        monkeypatch.setattr(kp, "get_project_root", lambda _f: tmp_path)
        profiel = kp.KevinProfile(DummyBus())
        profiel._vandaag = lambda: "2025-01-01"  # voorkeur begint in januari 2025
        profiel.add_preference("koffie", "positief", bron="expliciet")
        router, _ = maak_router(profiel)

        router.handle_preference("vergeet: koffie per 2025-06-01")

        historiek = profiel.data["historiek"]["koffie"]
        assert historiek[-1]["valid_until"] == "2025-06-01"
        assert "koffie" not in profiel.data.get("voorkeuren", {})

    def test_einddatum_voor_het_begin_wordt_geweigerd(self, tmp_path, monkeypatch):
        from modules.preferences import kevin_profile as kp
        monkeypatch.setattr(kp, "get_project_root", lambda _f: tmp_path)
        profiel = kp.KevinProfile(DummyBus())
        profiel._vandaag = lambda: "2026-11-03"
        profiel.add_preference("thee", "positief", bron="expliciet")
        router, bus = maak_router(profiel)

        router.handle_preference("vergeet: thee per 2025-06-01")

        assert "pas sinds 2026-11-03" in bus.teksten()[0]
        assert "thee" in profiel.data["voorkeuren"]          # nog actueel
        assert "thee" not in profiel.data.get("historiek", {})

    def test_einddatum_op_de_begindag_mag(self, tmp_path, monkeypatch):
        from modules.preferences import kevin_profile as kp
        monkeypatch.setattr(kp, "get_project_root", lambda _f: tmp_path)
        profiel = kp.KevinProfile(DummyBus())
        profiel._vandaag = lambda: "2025-06-01"
        profiel.add_preference("thee", "positief", bron="expliciet")
        router, _ = maak_router(profiel)

        router.handle_preference("vergeet: thee per 2025-06-01")

        assert profiel.data["historiek"]["thee"][-1]["valid_until"] == "2025-06-01"

    def test_onbekend_begin_wordt_niet_geblokkeerd(self, tmp_path, monkeypatch):
        """Oude voorkeuren hebben valid_from = None: dan weten we het begin niet."""
        from modules.preferences import kevin_profile as kp
        monkeypatch.setattr(kp, "get_project_root", lambda _f: tmp_path)
        profiel = kp.KevinProfile(DummyBus())
        profiel.add_preference("kou", "negatief", bron="expliciet")
        for blok in profiel.data["afkeuren"]["kou"].values():
            blok["valid_from"] = None
        assert profiel.laatste_begindatum("kou") is None
        router, _ = maak_router(profiel)

        router.handle_preference("vergeet: kou per 2020-01-01")

        assert profiel.data["historiek"]["kou"][-1]["valid_until"] == "2020-01-01"