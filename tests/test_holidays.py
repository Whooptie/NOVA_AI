# test_holidays.py
#
# Echte pytest-test voor de nieuwe module modules/time/holidays.py
# (date_calendar_roadmap.md, Onderdeel 2): vaste + bewegende
# feestdagen, berekend via het computus-algoritme voor Pasen.
#
# Zelfde conventies als test_calendar.py / test_calendar_datumrekenen.py:
# - Echte package-import, geen importlib-omweg.
# - DummyEventBus als lokale class.
# - DummyZone met een vaste, injecteerbare datum.
# - Geen I/O in __init__().
#
# Uitvoeren: pytest tests/test_holidays.py -v

from datetime import date, datetime

import pytest

from modules.time.holidays import (
    HolidaysModule,
    bereken_pasen,
    VASTE_FEESTDAGEN,
    BEWEGENDE_FEESTDAGEN_OFFSET,
    FEESTDAG_ALIASSEN,
)


# ------------------------------------------------------------
# Test-dubbels
# ------------------------------------------------------------
class DummyEventBus:
    def __init__(self, zone=None):
        self.gepubliceerd = []
        self.subscripties = {}
        self._zone = zone
        self.modules = {}

    def get_module(self, naam):
        if naam == "zone":
            return self._zone
        return self.modules.get(naam)

    def subscribe(self, event_type, handler):
        self.subscripties[event_type] = handler

    def publish(self, event_type, data):
        self.gepubliceerd.append((event_type, data))

    def laatste_tekst(self):
        for event_type, data in reversed(self.gepubliceerd):
            if event_type == "layer4_response":
                return data["text"]
        return None


class DummyZone:
    def __init__(self, vaste_datetime):
        self._vaste_datetime = vaste_datetime

    def now_local(self):
        return self._vaste_datetime


# ------------------------------------------------------------
# Fixtures -- vaste referentiedatum: donderdag 17 september 2026
# ------------------------------------------------------------
@pytest.fixture
def donderdag_17_sept_2026():
    return datetime(2026, 9, 17, 10, 0, 0)


@pytest.fixture
def bus(donderdag_17_sept_2026):
    zone = DummyZone(donderdag_17_sept_2026)
    return DummyEventBus(zone=zone)


@pytest.fixture
def mod(bus):
    return HolidaysModule(bus)


# ============================================================
# 1. Init en registratie
# ============================================================
class TestInitModule:
    def test_init_module_geeft_holidaysmodule_instantie(self, bus):
        from modules.time.holidays import init_module
        m = init_module(bus)
        assert isinstance(m, HolidaysModule)

    def test_init_module_publiceert_module_loaded(self, bus):
        from modules.time.holidays import init_module
        init_module(bus)
        assert ("module_loaded", {"name": "holidays"}) in bus.gepubliceerd

    def test_abonneert_op_intent_holiday_query(self, bus):
        from modules.time.holidays import init_module
        init_module(bus)
        assert "intent_holiday_query" in bus.subscripties

    def test_geen_io_in_init(self, bus, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        m = HolidaysModule(bus)
        assert m is not None


# ============================================================
# 2. bereken_pasen() -- geverifieerd tegen officieel bevestigde
#    paasdatums (computus-algoritme, Meeus/Jones/Butcher)
# ============================================================
class TestBerekenPasen:
    @pytest.mark.parametrize(
        "jaar, verwachte_datum",
        [
            (1900, date(1900, 4, 15)),
            (2000, date(2000, 4, 23)),
            (2024, date(2024, 3, 31)),
            (2025, date(2025, 4, 20)),
            (2026, date(2026, 4, 5)),
            (2027, date(2027, 3, 28)),
            (2028, date(2028, 4, 16)),
            (2030, date(2030, 4, 21)),
        ],
    )
    def test_bekende_paasdatums(self, jaar, verwachte_datum):
        assert bereken_pasen(jaar) == verwachte_datum


# ============================================================
# 3. bewegende_feestdagen() -- alle afgeleiden kloppen t.o.v.
#    Pasen, geverifieerd tegen de officiële Belgische kalender 2026
# ============================================================
class TestBewegendeFeestdagen:
    def test_2026_klopt_met_officiele_belgische_kalender(self, mod):
        resultaat = mod.bewegende_feestdagen(2026)
        assert resultaat["Pasen"] == date(2026, 4, 5)
        assert resultaat["Paasmaandag"] == date(2026, 4, 6)
        assert resultaat["Hemelvaart"] == date(2026, 5, 14)
        assert resultaat["Pinksteren"] == date(2026, 5, 24)
        assert resultaat["Pinkstermaandag"] == date(2026, 5, 25)
        assert resultaat["Carnaval"] == date(2026, 2, 17)

    def test_alle_offsets_correct_toegepast(self, mod):
        pasen = bereken_pasen(2027)
        resultaat = mod.bewegende_feestdagen(2027)
        for naam, offset in BEWEGENDE_FEESTDAGEN_OFFSET.items():
            from datetime import timedelta
            assert resultaat[naam] == pasen + timedelta(days=offset)


# ============================================================
# 4. datum_van_feestdag() -- opzoeken op naam
# ============================================================
class TestDatumVanFeestdag:
    def test_vaste_feestdag(self, mod):
        assert mod.datum_van_feestdag("Kerstmis", 2026) == date(2026, 12, 25)

    def test_vaste_feestdag_hoofdletterongevoelig(self, mod):
        assert mod.datum_van_feestdag("kerstmis", 2026) == date(2026, 12, 25)
        assert mod.datum_van_feestdag("KERSTMIS", 2026) == date(2026, 12, 25)

    def test_bewegende_feestdag(self, mod):
        assert mod.datum_van_feestdag("Pasen", 2026) == date(2026, 4, 5)

    def test_onbekende_naam_geeft_none(self, mod):
        assert mod.datum_van_feestdag("Oktoberfest", 2026) is None


# ============================================================
# 5. is_feestdag() -- datum -> (bool, naam)
# ============================================================
class TestIsFeestdag:
    def test_vaste_feestdag_wordt_herkend(self, mod):
        assert mod.is_feestdag(date(2026, 12, 25)) == (True, "Kerstmis")

    def test_bewegende_feestdag_wordt_herkend(self, mod):
        assert mod.is_feestdag(date(2026, 4, 5)) == (True, "Pasen")

    def test_gewone_dag_geeft_false(self, mod):
        assert mod.is_feestdag(date(2026, 9, 17)) == (False, None)

    def test_carnaval_negatieve_offset_wordt_herkend(self, mod):
        assert mod.is_feestdag(date(2026, 2, 17)) == (True, "Carnaval")


# ============================================================
# 6. alle_feestdagen_van_jaar() -- gesorteerd, vast + bewegend
# ============================================================
class TestAlleFeestdagenVanJaar:
    def test_aantal_feestdagen_klopt(self, mod):
        # 10 vaste + 6 bewegende = 16
        resultaat = mod.alle_feestdagen_van_jaar(2026)
        assert len(resultaat) == len(VASTE_FEESTDAGEN) + len(BEWEGENDE_FEESTDAGEN_OFFSET)

    def test_resultaat_is_gesorteerd_op_datum(self, mod):
        resultaat = mod.alle_feestdagen_van_jaar(2026)
        data = [d for d, _ in resultaat]
        assert data == sorted(data)

    def test_eerste_feestdag_van_het_jaar_is_nieuwjaar(self, mod):
        resultaat = mod.alle_feestdagen_van_jaar(2026)
        assert resultaat[0] == (date(2026, 1, 1), "Nieuwjaar")

    def test_laatste_feestdag_van_het_jaar_is_kerstmis(self, mod):
        resultaat = mod.alle_feestdagen_van_jaar(2026)
        assert resultaat[-1] == (date(2026, 12, 25), "Kerstmis")


# ============================================================
# 7. volgende_feestdag() -- inclusief jaargrens-doorzoeken
# ============================================================
class TestVolgendeFeestdag:
    def test_vanaf_17_september_is_halloween(self, mod):
        assert mod.volgende_feestdag(date(2026, 9, 17)) == (
            date(2026, 10, 31),
            "Halloween",
        )

    def test_na_kerst_zoekt_door_naar_volgend_jaar(self, mod):
        # 26 dec 2026 is na Kerstmis (25/12), de laatste feestdag
        # van 2026 -- moet doorzoeken naar Nieuwjaar 2027.
        assert mod.volgende_feestdag(date(2026, 12, 26)) == (
            date(2027, 1, 1),
            "Nieuwjaar",
        )

    def test_exact_op_een_feestdag_geeft_de_ERVOLGENDE_niet_zichzelf(self, mod):
        # Op Kerstmis zelf gevraagd -- "volgende" moet niet Kerstmis
        # zelf teruggeven (kandidaten filtert strikt > vanaf_datum).
        resultaat = mod.volgende_feestdag(date(2026, 12, 25))
        assert resultaat[0] > date(2026, 12, 25)


# ============================================================
# 8. Event-pad: on_holiday_intent() en de drie antwoord_*()
# ============================================================
class TestAntwoordWanneerIs:
    def test_kerst_via_alias(self, bus, mod):
        mod.on_calendar_intent = None  # niet van toepassing, sanity
        mod.on_holiday_intent({"text": "wanneer is kerst", "type": "wanneer_is"})
        assert bus.laatste_tekst() == "Kerstmis valt dit jaar op vrijdag 25 december 2026."

    def test_kerstmis_officiele_naam(self, bus, mod):
        mod.on_holiday_intent({"text": "wanneer is kerstmis", "type": "wanneer_is"})
        assert bus.laatste_tekst() == "Kerstmis valt dit jaar op vrijdag 25 december 2026."

    def test_pasen_springt_naar_volgend_jaar_als_al_voorbij(self, bus, mod):
        # Vandaag = 17 sept 2026, Pasen 2026 (5 april) is al voorbij
        mod.on_holiday_intent({"text": "wanneer valt pasen", "type": "wanneer_is"})
        assert bus.laatste_tekst() == "Pasen valt dit jaar op zondag 28 maart 2027."

    def test_pinksteren_matcht_niet_op_pinkstermaandag(self, bus, mod):
        mod.on_holiday_intent({"text": "wanneer is pinksteren", "type": "wanneer_is"})
        tekst = bus.laatste_tekst()
        assert tekst.startswith("Pinksteren valt")
        assert "Pinkstermaandag" not in tekst

    def test_pinkstermaandag_matcht_niet_op_pinksteren(self, bus, mod):
        mod.on_holiday_intent({"text": "wanneer is pinkstermaandag", "type": "wanneer_is"})
        tekst = bus.laatste_tekst()
        assert tekst.startswith("Pinkstermaandag valt")

    def test_onbekende_feestdag_geeft_tegenvraag(self, bus, mod):
        mod.on_holiday_intent({"text": "wanneer is oktoberfest", "type": "wanneer_is"})
        assert "Welke feestdag bedoel je" in bus.laatste_tekst()

    def test_alle_aliassen_worden_herkend(self, bus, mod):
        for alias in FEESTDAG_ALIASSEN:
            bus.gepubliceerd.clear()
            mod.on_holiday_intent({"text": f"wanneer is {alias}", "type": "wanneer_is"})
            tekst = bus.laatste_tekst()
            assert "Welke feestdag bedoel je" not in tekst, f"alias '{alias}' niet herkend"


class TestAntwoordIsVandaagFeestdag:
    def test_geen_feestdag_vandaag(self, bus, mod):
        mod.on_holiday_intent({"text": "is het vandaag een feestdag", "type": "is_vandaag_feestdag"})
        assert bus.laatste_tekst() == "Nee, vandaag is er geen feestdag."

    def test_wel_een_feestdag_vandaag(self, bus, mod):
        mod.today = lambda: date(2026, 12, 25)
        mod.on_holiday_intent({"text": "is het vandaag een feestdag", "type": "is_vandaag_feestdag"})
        assert bus.laatste_tekst() == "Ja, vandaag is het Kerstmis!"


class TestAntwoordVolgendeFeestdag:
    def test_meerdere_dagen_verwijderd(self, bus, mod):
        mod.on_holiday_intent({"text": "wat is de volgende feestdag", "type": "volgende_feestdag"})
        assert bus.laatste_tekst() == (
            "De volgende feestdag is Halloween, over 44 dagen (zaterdag 31 oktober 2026)."
        )

    def test_morgen_geeft_specifieke_formulering(self, bus, mod):
        mod.today = lambda: date(2026, 10, 30)
        mod.on_holiday_intent({"text": "wat is de volgende feestdag", "type": "volgende_feestdag"})
        assert bus.laatste_tekst() == (
            "De volgende feestdag is Halloween, morgen (zaterdag 31 oktober 2026)."
        )


class TestOnbekendVraagType:
    def test_onbekend_type_geeft_algemene_tegenvraag_geen_crash(self, bus, mod):
        mod.on_holiday_intent({"text": "iets", "type": "onbekend_type_xyz"})
        assert "Welke feestdag bedoel je" in bus.laatste_tekst()


# ============================================================
# 9. Elk antwoord publiceert enkel via layer4_response
# ============================================================
class TestPublicatiekanaal:
    def test_alle_types_publiceren_enkel_layer4_response(self, bus, mod):
        gevallen = [
            ("wanneer_is", "wanneer is kerst"),
            ("is_vandaag_feestdag", "is het vandaag een feestdag"),
            ("volgende_feestdag", "wat is de volgende feestdag"),
        ]
        for vraag_type, tekst in gevallen:
            bus.gepubliceerd.clear()
            mod.on_holiday_intent({"text": tekst, "type": vraag_type})
            event_types = [e for e, _ in bus.gepubliceerd]
            assert event_types == ["layer4_response"], (
                f"type={vraag_type} publiceerde {event_types}"
            )