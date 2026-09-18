# test_vakanties.py
#
# Echte pytest-test voor de nieuwe module modules/time/vakanties.py
# (date_calendar_roadmap.md, Onderdeel 3): Vlaamse schoolvakanties.
#
# BELANGRIJK: in tegenstelling tot de oorspronkelijke roadmap-aanname
# (handmatige tabel nodig, want politieke/administratieve beslissing)
# blijken alle 5 vakanties in werkelijkheid een vaste, officieel
# vastgelegde REGEL te volgen (Besluit van de Vlaamse Regering). Dit
# testbestand verifieert elke regel tegen de officiële Vlaamse
# overheidsbron (vlaanderen.be/schoolvakanties) voor de schooljaren
# 2023-2024 t/m 2029-2030.
#
# Zelfde conventies als test_holidays.py: echte package-imports,
# DummyEventBus/DummyZone, vaste referentiedatum, geen I/O in __init__().
#
# Uitvoeren: pytest tests/test_vakanties.py -v

from datetime import date, datetime

import pytest

from modules.time.vakanties import (
    VakantiesModule,
    bereken_herfstvakantie,
    bereken_kerstvakantie,
    bereken_krokusvakantie,
    bereken_paasvakantie,
    bereken_zomervakantie,
    VAKANTIE_NAMEN,
    VAKANTIE_ALIASSEN,
)


# ------------------------------------------------------------
# Test-dubbels
# ------------------------------------------------------------
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
    return VakantiesModule(bus)


# ============================================================
# 1. Init en registratie
# ============================================================
class TestInitModule:
    def test_init_module_geeft_vakantiesmodule_instantie(self, bus):
        from modules.time.vakanties import init_module
        m = init_module(bus)
        assert isinstance(m, VakantiesModule)

    def test_init_module_publiceert_module_loaded(self, bus):
        from modules.time.vakanties import init_module
        init_module(bus)
        assert ("module_loaded", {"name": "vakanties"}) in bus.gepubliceerd

    def test_abonneert_op_intent_vakantie_query(self, bus):
        from modules.time.vakanties import init_module
        init_module(bus)
        assert "intent_vakantie_query" in bus.subscripties

    def test_geen_io_in_init(self, bus, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        m = VakantiesModule(bus)
        assert m is not None


# ============================================================
# 2. Elke bereken_*()-regel, geverifieerd tegen de officiële
#    Vlaamse overheidsbron (vlaanderen.be/schoolvakanties)
# ============================================================
class TestBerekenHerfstvakantie:
    @pytest.mark.parametrize(
        "jaar, verwacht",
        [
            (2023, (date(2023, 10, 30), date(2023, 11, 5))),
            (2024, (date(2024, 10, 28), date(2024, 11, 3))),
            (2025, (date(2025, 10, 27), date(2025, 11, 2))),
            (2026, (date(2026, 11, 2), date(2026, 11, 8))),
            (2027, (date(2027, 11, 1), date(2027, 11, 7))),
            (2028, (date(2028, 10, 30), date(2028, 11, 5))),
            (2029, (date(2029, 10, 29), date(2029, 11, 4))),
        ],
    )
    def test_officiele_data(self, jaar, verwacht):
        assert bereken_herfstvakantie(jaar) == verwacht


class TestBerekenKerstvakantie:
    @pytest.mark.parametrize(
        "jaar, verwacht",
        [
            (2023, (date(2023, 12, 25), date(2024, 1, 7))),
            (2024, (date(2024, 12, 23), date(2025, 1, 5))),
            (2025, (date(2025, 12, 22), date(2026, 1, 4))),
            (2026, (date(2026, 12, 21), date(2027, 1, 3))),
            (2027, (date(2027, 12, 27), date(2028, 1, 9))),
            (2028, (date(2028, 12, 25), date(2029, 1, 7))),
        ],
    )
    def test_officiele_data(self, jaar, verwacht):
        assert bereken_kerstvakantie(jaar) == verwacht

    def test_loopt_door_in_volgend_kalenderjaar(self):
        start, einde = bereken_kerstvakantie(2026)
        assert start.year == 2026
        assert einde.year == 2027


class TestBerekenKrokusvakantie:
    @pytest.mark.parametrize(
        "jaar_van_pasen, verwacht",
        [
            (2024, (date(2024, 2, 12), date(2024, 2, 18))),
            (2025, (date(2025, 3, 3), date(2025, 3, 9))),
            (2026, (date(2026, 2, 16), date(2026, 2, 22))),
            (2027, (date(2027, 2, 8), date(2027, 2, 14))),
            (2028, (date(2028, 2, 28), date(2028, 3, 5))),
        ],
    )
    def test_officiele_data(self, jaar_van_pasen, verwacht):
        assert bereken_krokusvakantie(jaar_van_pasen) == verwacht


class TestBerekenPaasvakantie:
    """Dekt alle drie de gevallen uit de officiële regel (Besluit van
    de Vlaamse Regering): Pasen in maart, het gangbare geval (eerste
    maandag van april), en Pasen na 15 april."""

    @pytest.mark.parametrize(
        "jaar_van_pasen, verwacht, geval",
        [
            (2024, (date(2024, 4, 1), date(2024, 4, 14)), "Pasen in maart (31/3)"),
            (2027, (date(2027, 3, 29), date(2027, 4, 11)), "Pasen in maart (28/3)"),
            (2026, (date(2026, 4, 6), date(2026, 4, 19)), "gangbaar geval (5/4)"),
            (2029, (date(2029, 4, 2), date(2029, 4, 15)), "gangbaar geval (1/4)"),
            (2025, (date(2025, 4, 7), date(2025, 4, 21)), "Pasen na 15/4 (20/4)"),
            (2028, (date(2028, 4, 3), date(2028, 4, 17)), "Pasen na 15/4 (16/4)"),
            (2030, (date(2030, 4, 8), date(2030, 4, 22)), "Pasen na 15/4 (21/4)"),
        ],
    )
    def test_officiele_data_alle_drie_gevallen(self, jaar_van_pasen, verwacht, geval):
        assert bereken_paasvakantie(jaar_van_pasen) == verwacht, f"geval: {geval}"

    def test_laat_pasen_geval_eindigt_op_paasmaandag_zelf(self):
        # Regressie-vastlegging: bij een laat Pasen (na 15 april) is
        # de vakantie 15 dagen lang (niet de gebruikelijke 14), omdat
        # ze doorloopt tot en met Paasmaandag zelf.
        start, einde = bereken_paasvakantie(2025)
        assert (einde - start).days == 14  # 15 dagen totaal (inclusief beide grenzen)


class TestBerekenZomervakantie:
    def test_altijd_1_juli_tot_31_augustus(self):
        for jaar in (2024, 2025, 2026, 2027, 2030):
            start, einde = bereken_zomervakantie(jaar)
            assert start == date(jaar, 7, 1)
            assert einde == date(jaar, 8, 31)


# ============================================================
# 3. VakantiesModule -- samengestelde methodes
# ============================================================
class TestAlleVakantiesVanJaar:
    def test_bevat_alle_5_vakanties(self, mod):
        resultaat = mod.alle_vakanties_van_jaar(2026)
        assert set(resultaat.keys()) == set(VAKANTIE_NAMEN)

    def test_krokus_en_paas_gebruiken_pasen_van_hetzelfde_kalenderjaar(self, mod):
        resultaat = mod.alle_vakanties_van_jaar(2026)
        # Pasen 2026 = 5 april -> krokus/paas van kalenderjaar 2026
        # moeten in 2026 zelf liggen (voor Pasen 2026), niet 2027.
        assert resultaat["Krokusvakantie"][0].year == 2026
        assert resultaat["Paasvakantie"][0].year == 2026


class TestDatumVanVakantie:
    def test_officiele_naam(self, mod):
        assert mod.datum_van_vakantie("Paasvakantie", 2026) == (
            date(2026, 4, 6),
            date(2026, 4, 19),
        )

    def test_alias(self, mod):
        assert mod.datum_van_vakantie("grote vakantie", 2026) == (
            date(2026, 7, 1),
            date(2026, 8, 31),
        )

    def test_hoofdletterongevoelig(self, mod):
        assert mod.datum_van_vakantie("KROKUSVAKANTIE", 2026) == bereken_krokusvakantie(2026)

    def test_onbekende_naam_geeft_none(self, mod):
        assert mod.datum_van_vakantie("skivakantie", 2026) is None


class TestIsVakantie:
    def test_gewone_dag_geeft_false(self, mod):
        assert mod.is_vakantie(date(2026, 9, 18)) == (False, None)

    def test_binnen_herfstvakantie(self, mod):
        assert mod.is_vakantie(date(2026, 11, 5)) == (True, "Herfstvakantie")

    def test_jaargrens_kerstvakantie_in_januari_wordt_herkend(self, mod):
        # 1 jan 2027 valt in de Kerstvakantie van kalenderjaar 2026
        # (die doorloopt tot 3 jan 2027) -- moet herkend worden ook al
        # zoekt alle_vakanties_van_jaar(2027) dit niet standaard op.
        assert mod.is_vakantie(date(2027, 1, 1)) == (True, "Kerstvakantie")

    def test_exact_op_eerste_dag_van_vakantie(self, mod):
        assert mod.is_vakantie(date(2026, 11, 2)) == (True, "Herfstvakantie")

    def test_exact_op_laatste_dag_van_vakantie(self, mod):
        assert mod.is_vakantie(date(2026, 11, 8)) == (True, "Herfstvakantie")

    def test_dag_na_vakantie_geeft_false(self, mod):
        assert mod.is_vakantie(date(2026, 11, 9)) == (False, None)


class TestVolgendeVakantie:
    def test_vanaf_18_september_is_herfstvakantie(self, mod):
        assert mod.volgende_vakantie(date(2026, 9, 18)) == (
            date(2026, 11, 2),
            date(2026, 11, 8),
            "Herfstvakantie",
        )

    def test_na_herfstvakantie_is_kerstvakantie(self, mod):
        assert mod.volgende_vakantie(date(2026, 11, 9)) == (
            date(2026, 12, 21),
            date(2027, 1, 3),
            "Kerstvakantie",
        )

    def test_na_zomervakantie_zoekt_door_naar_volgend_jaar(self, mod):
        # Na 31 augustus 2026 is de eerstvolgende vakantie de
        # herfstvakantie van kalenderjaar 2027 (niet 2026, want die is
        # al voorbij als startdatum-check: > vanaf_datum).
        resultaat = mod.volgende_vakantie(date(2026, 9, 1))
        assert resultaat[2] == "Herfstvakantie"
        assert resultaat[0].year == 2026


# ============================================================
# 4. Event-pad: on_vakantie_intent() en de vier antwoord_*()
# ============================================================
class TestAntwoordWanneerIs:
    def test_paasvakantie_springt_naar_volgend_jaar_als_al_voorbij(self, bus, mod):
        # Vandaag = 18 sept 2026, Paasvakantie 2026 is al voorbij
        mod.on_vakantie_intent(
            {"text": "wanneer is de paasvakantie", "type": "wanneer_is"}
        )
        assert bus.laatste_tekst() == (
            "Paasvakantie loopt van maandag 29 maart 2027 tot en met "
            "zondag 11 april 2027."
        )

    def test_herfstvakantie_nog_niet_voorbij_dit_jaar(self, bus, mod):
        mod.on_vakantie_intent(
            {"text": "wanneer is de herfstvakantie", "type": "wanneer_is"}
        )
        assert bus.laatste_tekst() == (
            "Herfstvakantie loopt van maandag 2 november 2026 tot en met "
            "zondag 8 november 2026."
        )

    def test_alias_grote_vakantie(self, bus, mod):
        mod.on_vakantie_intent({"text": "wanneer is de grote vakantie", "type": "wanneer_is"})
        tekst = bus.laatste_tekst()
        assert tekst.startswith("Zomervakantie loopt")

    def test_onbekende_vakantienaam_geeft_tegenvraag(self, bus, mod):
        mod.on_vakantie_intent({"text": "wanneer is de skivakantie", "type": "wanneer_is"})
        assert "Welke vakantie bedoel je" in bus.laatste_tekst()


class TestAntwoordIsNuVakantie:
    def test_geen_vakantie_nu(self, bus, mod):
        mod.on_vakantie_intent({"text": "zijn we nu in vakantie", "type": "is_nu_vakantie"})
        assert bus.laatste_tekst() == "Nee, momenteel is er geen schoolvakantie."

    def test_wel_vakantie_nu(self, bus, mod):
        mod.today = lambda: date(2026, 11, 5)
        mod.on_vakantie_intent({"text": "zijn we nu in vakantie", "type": "is_nu_vakantie"})
        assert bus.laatste_tekst() == "Ja, het is nu Herfstvakantie!"


class TestAntwoordVolgendeVakantie:
    def test_meerdere_dagen_verwijderd(self, bus, mod):
        mod.on_vakantie_intent(
            {"text": "wat is de volgende vakantie", "type": "volgende_vakantie"}
        )
        assert bus.laatste_tekst() == (
            "De volgende vakantie is Herfstvakantie, over 45 dagen "
            "(maandag 2 november 2026)."
        )

    def test_morgen_geeft_specifieke_formulering(self, bus, mod):
        mod.today = lambda: date(2026, 11, 1)
        mod.on_vakantie_intent(
            {"text": "wat is de volgende vakantie", "type": "volgende_vakantie"}
        )
        assert bus.laatste_tekst() == (
            "De volgende vakantie is Herfstvakantie, die morgen begint "
            "(maandag 2 november 2026)."
        )


class TestAntwoordDagenTotVakantie:
    def test_meerdere_dagen(self, bus, mod):
        mod.on_vakantie_intent(
            {"text": "hoeveel dagen tot de vakantie", "type": "dagen_tot_vakantie"}
        )
        assert bus.laatste_tekst() == (
            "Nog 45 dagen tot Herfstvakantie (maandag 2 november 2026)."
        )

    def test_al_middenin_een_vakantie_springt_bewust_door_naar_de_volgende(self, bus, mod):
        # Bewuste keuze (bevestigd met Kevin, 18 september 2026):
        # "hoeveel dagen tot de vakantie" springt ALTIJD door naar de
        # eerstvolgende vakantie die nog moet BEGINNEN (start > vandaag),
        # ook als je op dit moment al middenin een andere vakantie zit.
        # Geen "je zit er al in"-melding -- dat is een bewust andere
        # vraag ("zijn we nu in vakantie", zie TestAntwoordIsNuVakantie).
        mod.today = lambda: date(2026, 11, 2)  # eerste dag van de Herfstvakantie zelf
        mod.on_vakantie_intent(
            {"text": "hoeveel dagen tot de vakantie", "type": "dagen_tot_vakantie"}
        )
        assert bus.laatste_tekst() == (
            "Nog 49 dagen tot Kerstvakantie (maandag 21 december 2026)."
        )

    def test_morgen(self, bus, mod):
        mod.today = lambda: date(2026, 11, 1)
        mod.on_vakantie_intent(
            {"text": "hoeveel dagen tot de vakantie", "type": "dagen_tot_vakantie"}
        )
        assert bus.laatste_tekst() == "Nog 1 dag tot Herfstvakantie, die morgen begint."


class TestOnbekendVraagType:
    def test_onbekend_type_geeft_algemene_tegenvraag_geen_crash(self, bus, mod):
        mod.on_vakantie_intent({"text": "iets", "type": "onbekend_type_xyz"})
        assert "Welke vakantie bedoel je" in bus.laatste_tekst()


# ============================================================
# 5. Elk antwoord publiceert enkel via layer4_response
# ============================================================
class TestPublicatiekanaal:
    def test_alle_types_publiceren_enkel_layer4_response(self, bus, mod):
        gevallen = [
            ("wanneer_is", "wanneer is de paasvakantie"),
            ("is_nu_vakantie", "zijn we nu in vakantie"),
            ("volgende_vakantie", "wat is de volgende vakantie"),
            ("dagen_tot_vakantie", "hoeveel dagen tot de vakantie"),
        ]
        for vraag_type, tekst in gevallen:
            bus.gepubliceerd.clear()
            mod.on_vakantie_intent({"text": tekst, "type": vraag_type})
            event_types = [e for e, _ in bus.gepubliceerd]
            assert event_types == ["layer4_response"], (
                f"type={vraag_type} publiceerde {event_types}"
            )


# ============================================================
# 6. Geen circulaire import (vakanties.py <-> holidays.py <-> calendar.py)
# ============================================================
class TestGeenCirculaireImport:
    def test_vakanties_eerst(self):
        from modules.time import vakanties as _v  # noqa: F401
        from modules.time import holidays as _h  # noqa: F401
        from modules.time import calendar as _c  # noqa: F401

    def test_calendar_eerst(self):
        from modules.time import calendar as _c  # noqa: F401
        from modules.time import holidays as _h  # noqa: F401
        from modules.time import vakanties as _v  # noqa: F401

    def test_holidays_eerst(self):
        from modules.time import holidays as _h  # noqa: F401
        from modules.time import vakanties as _v  # noqa: F401
        from modules.time import calendar as _c  # noqa: F401