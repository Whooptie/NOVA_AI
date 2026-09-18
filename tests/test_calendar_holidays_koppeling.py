# test_calendar_holidays_koppeling.py
#
# Echte pytest-test voor de koppeling tussen modules/time/calendar.py
# en modules/time/holidays.py: calendar.py's _parse_datum() moet ook
# feestdagnamen ("kerst", "pasen", ...) herkennen door holidays.py te
# raadplegen (patroon 6, toegevoegd 18 september 2026).
#
# Dit test specifiek de SAMENWERKING tussen de twee modules, niet elke
# module apart -- dat gebeurt al in test_calendar.py,
# test_calendar_datumrekenen.py en test_holidays.py.
#
# Zelfde conventies: echte package-imports, DummyEventBus/DummyZone,
# vaste referentiedatum (vrijdag 18 september 2026).
#
# Uitvoeren: pytest tests/test_calendar_holidays_koppeling.py -v

from datetime import date, datetime

import pytest

from modules.time.calendar import CalendarModule


class DummyEventBus:
    def __init__(self, zone=None):
        self.gepubliceerd = []
        self.subscripties = {}
        self._zone = zone

    def get_module(self, naam):
        return self._zone if naam == "zone" else None

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


@pytest.fixture
def vrijdag_18_sept_2026():
    return datetime(2026, 9, 18, 10, 0, 0)


@pytest.fixture
def bus(vrijdag_18_sept_2026):
    return DummyEventBus(zone=DummyZone(vrijdag_18_sept_2026))


@pytest.fixture
def mod(bus):
    return CalendarModule(bus)


# ============================================================
# 1. Geen circulaire import -- calendar.py en holidays.py mogen
#    in elke volgorde importeerbaar zijn.
# ============================================================
class TestGeenCirculaireImport:
    def test_calendar_eerst_dan_holidays(self):
        from modules.time import calendar as _calendar_module  # noqa: F401
        from modules.time import holidays as _holidays_module  # noqa: F401

    def test_holidays_eerst_dan_calendar(self):
        from modules.time import holidays as _holidays_module  # noqa: F401
        from modules.time import calendar as _calendar_module  # noqa: F401


# ============================================================
# 2. _parse_datum() herkent feestdagnamen (patroon 6)
# ============================================================
class TestParseDatumFeestdagnamen:
    def test_kerst_via_alias(self, mod):
        assert mod._parse_datum("hoeveel dagen tot kerst") == date(2026, 12, 25)

    def test_kerstmis_officiele_naam(self, mod):
        assert mod._parse_datum("kerstmis") == date(2026, 12, 25)

    def test_pasen_springt_naar_volgend_jaar_als_al_voorbij(self, mod):
        # Pasen 2026 (5 april) is al voorbij op 18 sept 2026
        assert mod._parse_datum("pasen") == date(2027, 3, 28)

    def test_sinterklaas(self, mod):
        assert mod._parse_datum("sinterklaas") == date(2026, 12, 6)

    def test_onbekende_feestdagnaam_geeft_none(self, mod):
        assert mod._parse_datum("oktoberfest") is None


class TestPinksterenPinkstermaandagGeenVerwarring:
    """Regressietest voor een echte bug, gevonden tijdens live-testen
    18 september 2026: 'pinkstermaandag' bevat het woord 'maandag' als
    substring, en de bestaande weekdag-detectie (patroon 2) deed een
    kale substring-check (`if naam in t`) i.p.v. een woordgrens-check.
    Gevolg: 'hoeveel dagen tot pinkstermaandag' werd fout herkend als
    'de eerstvolgende gewone maandag' (21 sept 2026) i.p.v. de
    feestdag Pinkstermaandag (17 mei 2027). Fix: woordgrens (\\b) in
    de weekdag-regex. Deze klasse test zowel de fix als de eerder
    werkende gevallen, om een toekomstige regressie op te vangen."""

    def test_pinkstermaandag_geeft_de_feestdag_niet_een_gewone_maandag(self, mod):
        resultaat = mod._parse_datum("hoeveel dagen tot pinkstermaandag")
        assert resultaat == date(2027, 5, 17)
        # Expliciet NIET de eerstvolgende gewone maandag:
        assert resultaat != date(2026, 9, 21)

    def test_paasmaandag_bevat_ook_maandag_als_substring(self, mod):
        # Zelfde risico als pinkstermaandag -- ook Paasmaandag bevat
        # het woord "maandag".
        resultaat = mod._parse_datum("hoeveel dagen tot paasmaandag")
        assert resultaat == date(2027, 3, 29)
        assert resultaat != date(2026, 9, 21)

    def test_pinksteren_zonder_maandag_werkt_apart(self, mod):
        assert mod._parse_datum("hoeveel dagen tot pinksteren") == date(2027, 5, 16)

    def test_gewone_weekdag_maandag_werkt_nog_normaal(self, mod):
        # Regressie-check: de fix (woordgrens) mag het gewone
        # weekdag-pad zelf niet breken.
        assert mod._parse_datum("hoeveel dagen tot maandag") == date(2026, 9, 21)

    def test_gewone_weekdag_zaterdag_werkt_nog_normaal(self, mod):
        assert mod._parse_datum("hoeveel dagen tot zaterdag") == date(2026, 9, 19)


# ============================================================
# 3. Volledig event-pad: on_calendar_intent() met een feestdagnaam
# ============================================================
class TestVolledigEventPadMetFeestdag:
    def test_dagen_tot_kerst(self, bus, mod):
        mod.on_calendar_intent({"text": "hoeveel dagen tot kerst", "type": "dagen_tot"})
        assert bus.laatste_tekst() == "Nog 98 dagen tot 25 december 2026."

    def test_dagen_tot_pinkstermaandag(self, bus, mod):
        mod.on_calendar_intent(
            {"text": "hoeveel dagen tot pinkstermaandag", "type": "dagen_tot"}
        )
        assert bus.laatste_tekst() == "Nog 241 dagen tot 17 mei 2027."

    def test_dag_van_de_week_van_kerst(self, bus, mod):
        mod.on_calendar_intent(
            {"text": "welke dag van de week is kerst", "type": "dag_van_de_week"}
        )
        assert bus.laatste_tekst() == "25 december 2026 is een vrijdag."

    def test_onbekende_feestdagnaam_geeft_nette_tegenvraag(self, bus, mod):
        mod.on_calendar_intent(
            {"text": "hoeveel dagen tot oktoberfest", "type": "dagen_tot"}
        )
        assert "Welke datum bedoel je" in bus.laatste_tekst()