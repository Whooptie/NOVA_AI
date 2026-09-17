# test_calendar_datumrekenen.py
#
# Echte pytest-test voor de datumreken-uitbreiding van
# modules/time/calendar.py (date_calendar_roadmap.md, Onderdeel 1):
# "hoeveel dagen tot X", "hoeveel dagen geleden was X",
# "welke dag van de week is X", "wat is de datum over N dagen/weken".
#
# Zelfde conventies als test_calendar.py:
# - Echte package-import, geen importlib-omweg.
# - DummyEventBus als lokale class.
# - DummyZone met een vaste, injecteerbare datum (17 september 2026,
#   een donderdag) -- alle tests zijn onafhankelijk van de werkelijke
#   "vandaag".
#
# Uitvoeren: pytest tests/test_calendar_datumrekenen.py -v

from datetime import date, datetime

import pytest

from modules.time.calendar import CalendarModule, DAGNAMEN, MAANDNAMEN


# ------------------------------------------------------------
# Test-dubbels (zelfde als test_calendar.py)
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
    return CalendarModule(bus)


# ============================================================
# 1. _parse_datum() -- elk herkend patroon apart
# ============================================================
class TestParseDatumMorgenOvermorgenVandaag:
    def test_morgen(self, mod):
        assert mod._parse_datum("hoeveel dagen tot morgen") == date(2026, 9, 18)

    def test_overmorgen(self, mod):
        assert mod._parse_datum("hoeveel dagen tot overmorgen") == date(2026, 9, 19)

    def test_vandaag(self, mod):
        assert mod._parse_datum("hoeveel dagen tot vandaag") == date(2026, 9, 17)

    def test_overmorgen_wint_van_morgen_als_beide_woorden_erin_zitten(self, mod):
        # "overmorgen" bevat "morgen" als substring -- de check op
        # "overmorgen" moet EERST gebeuren, anders zou "morgen"
        # al matchen binnen "overmorgen" en het verkeerde antwoord geven.
        assert mod._parse_datum("overmorgen") == date(2026, 9, 19)


class TestParseDatumWeekdag:
    def test_weekdag_later_deze_week(self, mod):
        # 17 sept 2026 is een donderdag (weekday()==3). Zaterdag is
        # over 2 dagen.
        assert mod._parse_datum("hoeveel dagen tot zaterdag") == date(2026, 9, 19)

    def test_weekdag_vandaag_zelf_springt_naar_volgende_week(self, mod):
        # Vandaag is zelf donderdag -- "donderdag" moet NIET vandaag
        # betekenen, maar de donderdag over een week (zelfde regel als
        # weather.py's extract_day_offset()).
        assert mod._parse_datum("hoeveel dagen tot donderdag") == date(2026, 9, 24)

    def test_weekdag_eerder_deze_week_springt_naar_volgende_week(self, mod):
        # Maandag is al voorbij deze week (donderdag is later) ->
        # eerstvolgende maandag is over 4 dagen.
        assert mod._parse_datum("hoeveel dagen tot maandag") == date(2026, 9, 21)


class TestParseDatumOverNDagenWeken:
    def test_over_n_dagen(self, mod):
        assert mod._parse_datum("over 100 dagen") == date(2026, 12, 26)

    def test_over_1_dag_enkelvoud(self, mod):
        assert mod._parse_datum("over 1 dag") == date(2026, 9, 18)

    def test_over_n_weken(self, mod):
        assert mod._parse_datum("over 2 weken") == date(2026, 10, 1)

    def test_over_1_week_enkelvoud(self, mod):
        assert mod._parse_datum("over 1 week") == date(2026, 9, 24)

    def test_over_0_dagen_is_vandaag(self, mod):
        assert mod._parse_datum("over 0 dagen") == date(2026, 9, 17)


class TestParseDatumCijfernotatie:
    def test_slash_zonder_jaar_nog_te_komen(self, mod):
        assert mod._parse_datum("25/12") == date(2026, 12, 25)

    def test_streepje_zonder_jaar_nog_te_komen(self, mod):
        assert mod._parse_datum("25-12") == date(2026, 12, 25)

    def test_slash_zonder_jaar_al_voorbij_springt_naar_volgend_jaar(self, mod):
        # 15 augustus is al voorbij (vandaag is 17 sept) -> 2027
        assert mod._parse_datum("15/08") == date(2027, 8, 15)

    def test_slash_met_expliciet_jaar_blijft_dat_jaar_ook_in_verleden(self, mod):
        assert mod._parse_datum("15/08/2020") == date(2020, 8, 15)

    def test_streepje_met_expliciet_jaar(self, mod):
        assert mod._parse_datum("15-08-2027") == date(2027, 8, 15)

    def test_ongeldige_cijferdatum_geeft_none(self, mod):
        assert mod._parse_datum("32/13") is None

    def test_29_februari_niet_schrikkeljaar_geeft_none(self, mod):
        # 2026 is geen schrikkeljaar, 2027 ook niet -> None
        assert mod._parse_datum("29/02") is None


class TestParseDatumDagPlusMaandnaam:
    def test_dag_maand_zonder_jaar_nog_te_komen(self, mod):
        assert mod._parse_datum("hoeveel dagen tot 25 december") == date(2026, 12, 25)

    def test_dag_maand_zonder_jaar_al_voorbij_springt_naar_volgend_jaar(self, mod):
        assert mod._parse_datum("15 augustus") == date(2027, 8, 15)

    def test_dag_maand_vandaag_zelf_blijft_dit_jaar(self, mod):
        # Grensgeval: de genoemde datum IS vandaag -- mag niet naar
        # volgend jaar springen.
        assert mod._parse_datum("17 september") == date(2026, 9, 17)

    def test_dag_maand_met_expliciet_jaar(self, mod):
        assert mod._parse_datum("15 augustus 2027") == date(2027, 8, 15)

    def test_dag_maand_met_expliciet_jaar_in_verleden_blijft_verleden(self, mod):
        assert mod._parse_datum("15 augustus 2020") == date(2020, 8, 15)

    def test_31_april_bestaat_niet_geeft_none(self, mod):
        assert mod._parse_datum("31 april") is None

    def test_alle_12_maandnamen_worden_herkend(self, mod):
        for maandnummer, maandnaam in MAANDNAMEN.items():
            resultaat = mod._parse_datum(f"1 {maandnaam} 2027")
            assert resultaat == date(2027, maandnummer, 1)


class TestParseDatumOnherkend:
    def test_feestdagnaam_wordt_nog_niet_herkend(self, mod):
        # Bewuste scope-keuze: "kerst"/"pasen" als woord is
        # feestdagen-kennis (Onderdeel 2, nog niet gebouwd).
        assert mod._parse_datum("kerstmis") is None

    def test_willekeurige_tekst_geeft_none(self, mod):
        assert mod._parse_datum("wat een mooie dag vandaag niet") is not None
        # "vandaag" zit in de tekst en matcht terecht -- aparte test
        # met echt geen enkel patroon:
        assert mod._parse_datum("ik hou van python") is None


# ============================================================
# 2. dagen_tot() / antwoord_dagen_tot() -- puur rekenkundig + tekst
# ============================================================
class TestDagenTot:
    def test_dagen_tot_toekomst(self, mod):
        assert mod.dagen_tot(date(2026, 12, 25)) == 99

    def test_dagen_tot_vandaag_is_nul(self, mod):
        assert mod.dagen_tot(date(2026, 9, 17)) == 0

    def test_dagen_tot_verleden_is_negatief(self, mod):
        assert mod.dagen_tot(date(2026, 9, 10)) == -7


class TestAntwoordDagenTot:
    def test_toekomstige_datum_meervoud(self, bus, mod):
        mod.on_calendar_intent({"text": "hoeveel dagen tot 25 december", "type": "dagen_tot"})
        assert bus.laatste_tekst() == "Nog 99 dagen tot 25 december 2026."

    def test_morgen_geeft_specifieke_zin(self, bus, mod):
        mod.on_calendar_intent({"text": "hoeveel dagen tot morgen", "type": "dagen_tot"})
        assert bus.laatste_tekst() == "Dat is morgen, 18 september 2026."

    def test_vandaag_geeft_specifieke_zin(self, bus, mod):
        mod.on_calendar_intent({"text": "hoeveel dagen tot vandaag", "type": "dagen_tot"})
        assert bus.laatste_tekst() == "Dat is vandaag, 17 september 2026!"

    def test_verleden_datum_geeft_geleden_formulering(self, bus, mod):
        mod.on_calendar_intent(
            {"text": "hoeveel dagen geleden was 15/08/2020", "type": "dagen_tot"}
        )
        assert bus.laatste_tekst() == "15 augustus 2020 was 2224 dagen geleden."

    def test_onherkende_datum_geeft_tegenvraag(self, bus, mod):
        mod.on_calendar_intent({"text": "hoeveel dagen tot kerstmis", "type": "dagen_tot"})
        tekst = bus.laatste_tekst()
        assert "Welke datum bedoel je" in tekst

    def test_ongeldige_datum_geeft_tegenvraag_geen_crash(self, bus, mod):
        mod.on_calendar_intent({"text": "hoeveel dagen tot 31 april", "type": "dagen_tot"})
        tekst = bus.laatste_tekst()
        assert "Welke datum bedoel je" in tekst


# ============================================================
# 3. dag_van_de_week() / antwoord_dag_van_de_week()
# ============================================================
class TestDagVanDeWeek:
    def test_bekende_datum(self, mod):
        assert mod.dag_van_de_week(date(2027, 8, 15)) == "zondag"

    def test_alle_7_dagen_consistent_met_weekday(self, mod):
        for i in range(7):
            d = date(2026, 1, 5 + i)  # 5 jan 2026 = maandag
            assert mod.dag_van_de_week(d) == DAGNAMEN[i]


class TestAntwoordDagVanDeWeek:
    def test_geldige_datum(self, bus, mod):
        mod.on_calendar_intent(
            {"text": "welke dag van de week is 15 augustus 2027", "type": "dag_van_de_week"}
        )
        assert bus.laatste_tekst() == "15 augustus 2027 is een zondag."

    def test_ongeldige_datum_geeft_tegenvraag(self, bus, mod):
        mod.on_calendar_intent(
            {"text": "welke dag van de week is 31 april", "type": "dag_van_de_week"}
        )
        assert "Welke datum bedoel je" in bus.laatste_tekst()


# ============================================================
# 4. datum_plus() / antwoord_datum_plus()
# ============================================================
class TestDatumPlus:
    def test_datum_plus_dagen(self, mod):
        assert mod.datum_plus(100) == date(2026, 12, 26)

    def test_datum_plus_nul_is_vandaag(self, mod):
        assert mod.datum_plus(0) == date(2026, 9, 17)


class TestAntwoordDatumPlus:
    def test_over_n_dagen(self, bus, mod):
        mod.on_calendar_intent({"text": "wat is de datum over 100 dagen", "type": "datum_plus"})
        assert bus.laatste_tekst() == "Dat is zaterdag 26 december 2026."

    def test_over_n_weken(self, bus, mod):
        mod.on_calendar_intent({"text": "wat is de datum over 2 weken", "type": "datum_plus"})
        assert bus.laatste_tekst() == "Dat is donderdag 1 oktober 2026."

    def test_geen_over_n_patroon_geeft_tegenvraag(self, bus, mod):
        mod.on_calendar_intent({"text": "wat is de datum", "type": "datum_plus"})
        assert "Welke datum bedoel je" in bus.laatste_tekst()


# ============================================================
# 5. Elk datumreken-antwoord publiceert via layer4_response
# ============================================================
class TestPublicatiekanaal:
    def test_alle_datumreken_types_publiceren_enkel_layer4_response(self, bus, mod):
        gevallen = [
            ("dagen_tot", "hoeveel dagen tot 25 december"),
            ("dag_van_de_week", "welke dag van de week is 25 december"),
            ("datum_plus", "wat is de datum over 10 dagen"),
        ]
        for vraag_type, tekst in gevallen:
            bus.gepubliceerd.clear()
            mod.on_calendar_intent({"text": tekst, "type": vraag_type})
            event_types = [e for e, _ in bus.gepubliceerd]
            assert event_types == ["layer4_response"], (
                f"type={vraag_type} publiceerde {event_types}"
            )