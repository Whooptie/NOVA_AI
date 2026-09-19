# test_on_this_day.py
#
# Echte pytest-test voor de nieuwe module modules/time/on_this_day.py
# (date_calendar_roadmap.md, Onderdeel 4): historische datums via
# Wikipedia's On This Day REST API.
#
# TAALKEUZE: de ENGELSE feed (en.wikipedia.org), niet Nederlands.
# Aanvankelijk werd de Nederlandse feed gebruikt (puur symbolisch,
# geen vertaling nodig), maar live testen op battleserver (18
# september 2026) bevestigde dat die feed structureel LEEG is --
# zelfs voor 11 september en 25 december kwamen alle categorieën
# leeg terug, terwijl de Engelse feed voor 25 december 70 events/
# 229 geboortes/133 sterfgevallen gaf. Zie on_this_day.py's eigen
# module-docstring voor de volledige geschiedenis van deze
# beslissing. De getoonde tekst is dus in het Engels; een lokaal
# vertaalmodel is een bewust apart, toekomstig werkpunt.
#
# BELANGRIJKE BEPERKING VAN DEZE TESTSUITE: de echte netwerkaanroep
# (_fetch_dag_data) kan hier niet tegen de ECHTE Wikipedia-API getest
# worden (geen internettoegang vanuit deze ontwikkelomgeving). Elke
# test hieronder die de API-respons nodig heeft, injecteert daarom
# een NAGEBOUWDE respons (gebaseerd op de bevestigde, officiële
# structuur: events/births/deaths, elk met year/text/pages) via
# monkeypatching van _fetch_dag_data zelf. Dit test dus de PARSING,
# FORMATTERING en FOUTAFHANDELING van de module grondig -- de
# taalkeuze zelf (welke URL aangeroepen wordt) is inmiddels wel
# live bevestigd, zie hierboven.
#
# Zelfde conventies als de andere time/-modules: echte package-
# imports, DummyEventBus/DummyZone, vaste referentiedatum, geen I/O
# in __init__().
#
# Uitvoeren: pytest tests/test_on_this_day.py -v

from datetime import date, datetime

import pytest

from modules.time.on_this_day import OnThisDayModule, MAX_FEITEN_PER_ANTWOORD


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
    return OnThisDayModule(bus)


# Nagebouwde, realistische API-respons -- structuur bevestigd via
# meerdere onafhankelijke bronnen tijdens de bouw van deze module.
NEPPE_RESPONS_RIJK = {
    "events": [
        {"year": 1793, "text": "De eerste steen van het Capitool wordt gelegd.", "pages": []},
        {"year": 1810, "text": "Chili verklaart zich onafhankelijk van Spanje.", "pages": []},
        {"year": 1948, "text": "Koningin Wilhelmina doet troonsafstand.", "pages": []},
        {"year": 2001, "text": "Een vierde gebeurtenis die niet getoond mag worden.", "pages": []},
    ],
    "births": [
        {"year": 1709, "text": "Samuel Johnson, Engels schrijver.", "pages": []},
    ],
    "deaths": [],
}

NEPPE_RESPONS_LEEG = {"events": [], "births": [], "deaths": []}

# Regressie-vastlegging van een ECHTE bug, live gevonden op
# battleserver (18 september 2026, Kevin): de echte Wikipedia-API
# geeft voor een lege categorie een LEGE DICT ({}) terug, NIET een
# lege lijst ([]) zoals de aanvankelijke, uit meerdere bronnen
# afgeleide aanname veronderstelde. Bevestigd met een live curl
# tegen nl.wikipedia.org/api/rest_v1/feed/onthisday/all/09/18.
# entries[:N] op een dict gaf "TypeError: unhashable type: 'slice'".
NEPPE_RESPONS_ECHTE_LEGE_DAG = {
    "selected": {},
    "births": {},
    "deaths": {},
    "events": {},
    "holidays": {},
}


# ============================================================
# 1. Init en registratie
# ============================================================
class TestInitModule:
    def test_init_module_geeft_onthisdaymodule_instantie(self, bus):
        from modules.time.on_this_day import init_module
        m = init_module(bus)
        assert isinstance(m, OnThisDayModule)

    def test_init_module_publiceert_module_loaded(self, bus):
        from modules.time.on_this_day import init_module
        init_module(bus)
        assert ("module_loaded", {"name": "on_this_day"}) in bus.gepubliceerd

    def test_abonneert_op_intent_on_this_day_query(self, bus):
        from modules.time.on_this_day import init_module
        init_module(bus)
        assert "intent_on_this_day_query" in bus.subscripties

    def test_geen_io_in_init(self, bus, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        m = OnThisDayModule(bus)
        assert m is not None


# ============================================================
# 2. _fetch_dag_data() -- URL-opbouw en foutafhandeling
# ============================================================
class TestOnThisDayApiConstante:
    """Regressietest voor een echte bug, live gevonden op battleserver
    (18 september 2026): een eerdere versie van on_this_day.py bevatte
    PER ONGELUK twee ON_THIS_DAY_API-toewijzingen (één midden in het
    module-docstring-commentaarblok geplakt, de andere op de juiste
    plek na de imports). Python gebruikt dan stilzwijgend de LAATSTE
    toewijzing -- die tweede was nog de oude, Nederlandse URL, dus de
    module bleef de (structureel lege) Nederlandse feed bevragen
    ondanks dat de wijziging naar Engels was doorgevoerd. Andere tests
    in dit bestand monkeypatchen _fetch_dag_data() zelf en riepen deze
    constante dus nooit echt op -- die blinde vlek wordt hier gedicht
    met een test die de constante zelf, rechtstreeks, controleert."""

    def test_gebruikt_de_engelse_feed_niet_de_nederlandse(self):
        from modules.time.on_this_day import ON_THIS_DAY_API

        assert "en.wikipedia.org" in ON_THIS_DAY_API
        assert "nl.wikipedia.org" not in ON_THIS_DAY_API

    def test_er_is_precies_1_toewijzing_aan_on_this_day_api_in_het_bestand(self):
        # Vangt specifiek het "twee toewijzingen, de verkeerde wint"-
        # patroon zelf, onafhankelijk van welke waarde er ooit in
        # zou staan -- een tweede, per ongeluk achtergebleven
        # toewijzing zou deze test laten falen, ook als de EERSTE
        # toewijzing toevallig al de juiste URL zou hebben.
        import ast
        import inspect
        import modules.time.on_this_day as otd_module

        bestandspad = inspect.getfile(otd_module)
        with open(bestandspad, "r", encoding="utf-8") as f:
            bron = f.read()

        boom = ast.parse(bron)
        toewijzingen = [
            knoop
            for knoop in ast.walk(boom)
            if isinstance(knoop, ast.Assign)
            for doel in knoop.targets
            if isinstance(doel, ast.Name) and doel.id == "ON_THIS_DAY_API"
        ]
        assert len(toewijzingen) == 1, (
            f"Verwacht precies 1 toewijzing aan ON_THIS_DAY_API, "
            f"gevonden {len(toewijzingen)} op regels "
            f"{[t.lineno for t in toewijzingen]}"
        )


class TestFetchDagData:
    def test_bouwt_correcte_url_met_voorloopnullen(self, mod, monkeypatch):
        # 5 maart moet 03/05 worden (voorloopnullen), niet 3/5.
        opgevangen_url = {}

        class NepResponse:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self):
                return b'{"events": []}'

        def nep_urlopen(req, timeout):
            opgevangen_url["url"] = req.full_url
            return NepResponse()

        import modules.time.on_this_day as otd_module
        monkeypatch.setattr(otd_module.urllib.request, "urlopen", nep_urlopen)

        mod._fetch_dag_data(3, 5)
        assert opgevangen_url["url"].endswith("/03/05")

    def test_urlopen_exceptie_geeft_none_geen_crash(self, mod, monkeypatch):
        import modules.time.on_this_day as otd_module

        def nep_urlopen_faalt(req, timeout):
            raise Exception("geen internet")

        monkeypatch.setattr(otd_module.urllib.request, "urlopen", nep_urlopen_faalt)
        assert mod._fetch_dag_data(9, 18) is None

    def test_httperror_geeft_none_geen_crash(self, mod, monkeypatch):
        import modules.time.on_this_day as otd_module

        def nep_urlopen_404(req, timeout):
            raise otd_module.urllib.error.HTTPError(
                req.full_url, 404, "Not Found", {}, None
            )

        monkeypatch.setattr(otd_module.urllib.request, "urlopen", nep_urlopen_404)
        assert mod._fetch_dag_data(9, 18) is None


# ============================================================
# 3. _haal_feiten_op() -- afkap tot MAX_FEITEN_PER_ANTWOORD
# ============================================================
class TestHaalFeitenOp:
    def test_kapt_af_tot_max_feiten(self, mod):
        resultaat = mod._haal_feiten_op(NEPPE_RESPONS_RIJK, "events")
        assert len(resultaat) == MAX_FEITEN_PER_ANTWOORD
        assert len(resultaat) == 3

    def test_minder_dan_max_geeft_alles(self, mod):
        resultaat = mod._haal_feiten_op(NEPPE_RESPONS_RIJK, "births")
        assert len(resultaat) == 1

    def test_lege_categorie_geeft_lege_lijst(self, mod):
        resultaat = mod._haal_feiten_op(NEPPE_RESPONS_RIJK, "deaths")
        assert resultaat == []

    def test_data_is_none_geeft_lege_lijst(self, mod):
        assert mod._haal_feiten_op(None, "events") == []

    def test_ontbrekende_categorie_geeft_lege_lijst(self, mod):
        assert mod._haal_feiten_op({"events": []}, "births") == []

    def test_categorie_als_lege_dict_geeft_lege_lijst_geen_crash(self, mod):
        # Regressietest voor de ECHTE, live gevonden bug (18 september
        # 2026): Wikipedia's API geeft {} terug voor een lege
        # categorie, niet []. Vóór de fix gaf dit een TypeError bij
        # het slicen (entries[:N] op een dict). Zie
        # NEPPE_RESPONS_ECHTE_LEGE_DAG hierboven voor de volledige
        # context.
        for categorie in ("events", "births", "deaths"):
            resultaat = mod._haal_feiten_op(NEPPE_RESPONS_ECHTE_LEGE_DAG, categorie)
            assert resultaat == []


# ============================================================
# 4. _formatteer_entry()
# ============================================================
class TestFormatteerEntry:
    def test_normale_entry(self, mod):
        entry = {"year": 1948, "text": "Koningin Wilhelmina doet troonsafstand."}
        assert mod._formatteer_entry(entry) == "1948: Koningin Wilhelmina doet troonsafstand."

    def test_geen_jaar_geeft_enkel_tekst(self, mod):
        entry = {"text": "Iets zonder jaartal."}
        assert mod._formatteer_entry(entry) == "Iets zonder jaartal."

    def test_lege_tekst_geeft_none(self, mod):
        entry = {"year": 1948, "text": ""}
        assert mod._formatteer_entry(entry) is None

    def test_ontbrekende_tekst_geeft_none(self, mod):
        entry = {"year": 1948}
        assert mod._formatteer_entry(entry) is None


# ============================================================
# 5. Event-pad: on_this_day_intent() en de drie antwoord_*()
# ============================================================
class TestAntwoordEvents:
    def test_rijke_data_toont_max_3_feiten(self, bus, mod):
        mod._fetch_dag_data = lambda maand, dag: NEPPE_RESPONS_RIJK
        mod.on_this_day_intent({"text": "wat is er gebeurd vandaag", "type": "events"})
        tekst = bus.laatste_tekst()
        assert tekst.startswith("Op deze dag: ")
        assert "1793" in tekst
        assert "1810" in tekst
        assert "1948" in tekst
        assert "2001" not in tekst  # 4e event, moet afgekapt zijn

    def test_lege_data_geeft_eerlijke_weinig_gevonden_melding(self, bus, mod):
        mod._fetch_dag_data = lambda maand, dag: NEPPE_RESPONS_LEEG
        mod.on_this_day_intent({"text": "wat is er gebeurd vandaag", "type": "events"})
        assert bus.laatste_tekst() == (
            "Ik heb weinig gebeurtenissen gevonden voor deze dag op Wikipedia."
        )

    def test_fetch_faalt_geeft_nette_foutmelding(self, bus, mod):
        mod._fetch_dag_data = lambda maand, dag: None
        mod.on_this_day_intent({"text": "wat is er gebeurd vandaag", "type": "events"})
        assert bus.laatste_tekst() == (
            "Ik kon Wikipedia niet bereiken om dat op te zoeken. "
            "Probeer het straks nog eens."
        )

    def test_echte_lege_dag_met_lege_dicts_geeft_geen_crash(self, bus, mod):
        # End-to-end regressietest voor de live gevonden bug: het
        # VOLLEDIGE pad (on_this_day_intent -> antwoord_events ->
        # _haal_feiten_op) met de echte respons-vorm van een lege dag.
        mod._fetch_dag_data = lambda maand, dag: NEPPE_RESPONS_ECHTE_LEGE_DAG
        mod.on_this_day_intent({"text": "wat is er gebeurd vandaag", "type": "events"})
        assert bus.laatste_tekst() == (
            "Ik heb weinig gebeurtenissen gevonden voor deze dag op Wikipedia."
        )


class TestAntwoordGeboren:
    def test_toont_geboortes(self, bus, mod):
        mod._fetch_dag_data = lambda maand, dag: NEPPE_RESPONS_RIJK
        mod.on_this_day_intent({"text": "wie is er geboren vandaag", "type": "geboren"})
        assert bus.laatste_tekst() == "Geboren op deze dag: 1709: Samuel Johnson, Engels schrijver."

    def test_lege_data_geeft_eerlijke_melding(self, bus, mod):
        mod._fetch_dag_data = lambda maand, dag: NEPPE_RESPONS_LEEG
        mod.on_this_day_intent({"text": "wie is er geboren vandaag", "type": "geboren"})
        assert bus.laatste_tekst() == (
            "Ik heb weinig geboortes gevonden voor deze dag op Wikipedia."
        )


class TestAntwoordOverleden:
    def test_lege_data_geeft_eerlijke_melding(self, bus, mod):
        mod._fetch_dag_data = lambda maand, dag: NEPPE_RESPONS_RIJK  # deaths is leeg
        mod.on_this_day_intent({"text": "wie is er overleden vandaag", "type": "overleden"})
        assert bus.laatste_tekst() == (
            "Ik heb weinig sterfgevallen gevonden voor deze dag op Wikipedia."
        )


class TestOnbekendVraagType:
    def test_onbekend_type_valt_terug_op_events(self, bus, mod):
        # data.get("type", "events") + de else-tak in
        # on_this_day_intent(): een onbekend type geeft nooit een
        # crash, valt terug op de events-tak.
        mod._fetch_dag_data = lambda maand, dag: NEPPE_RESPONS_RIJK
        mod.on_this_day_intent({"text": "iets", "type": "onbekend_type_xyz"})
        assert bus.laatste_tekst().startswith("Op deze dag: ")


# ============================================================
# 6. _bepaal_maand_dag() -- datumherkenning, inclusief hergebruik
#    van calendar.py's bestaande _parse_datum() (en daarmee ook
#    de feestdag-koppeling met holidays.py)
# ============================================================
class TestBepaalMaandDag:
    def test_geen_datum_in_tekst_geeft_vandaag(self, mod):
        maand, dag, datum = mod._bepaal_maand_dag("wat is er gebeurd vandaag")
        assert (maand, dag) == (9, 18)

    def test_expliciete_datum_dag_maandnaam(self, mod):
        maand, dag, datum = mod._bepaal_maand_dag("wat is er gebeurd op 25 december")
        assert (maand, dag) == (12, 25)

    def test_cijfernotatie(self, mod):
        maand, dag, datum = mod._bepaal_maand_dag("wat is er gebeurd op 15/08")
        assert (maand, dag) == (8, 15)

    def test_morgen(self, mod):
        maand, dag, datum = mod._bepaal_maand_dag("wat is er gebeurd morgen")
        assert (maand, dag) == (9, 19)

    def test_feestdagnaam_via_calendar_holidays_koppeling(self, mod):
        # Bevestigt dat on_this_day.py automatisch profiteert van de
        # bestaande calendar.py<->holidays.py-koppeling (17/18
        # september 2026), zonder daar zelf iets voor te hoeven doen.
        maand, dag, datum = mod._bepaal_maand_dag("wat is er gebeurd op kerst")
        assert (maand, dag) == (12, 25)

    def test_onherkenbare_tekst_geeft_vandaag_geen_crash(self, mod):
        maand, dag, datum = mod._bepaal_maand_dag("iets willekeurigs zonder datum")
        assert (maand, dag) == (9, 18)


# ============================================================
# 7. Elk antwoord publiceert enkel via layer4_response
# ============================================================
class TestPublicatiekanaal:
    def test_alle_types_publiceren_enkel_layer4_response(self, bus, mod):
        mod._fetch_dag_data = lambda maand, dag: NEPPE_RESPONS_RIJK
        gevallen = [
            ("events", "wat is er gebeurd vandaag"),
            ("geboren", "wie is er geboren vandaag"),
            ("overleden", "wie is er overleden vandaag"),
        ]
        for vraag_type, tekst in gevallen:
            bus.gepubliceerd.clear()
            mod.on_this_day_intent({"text": tekst, "type": vraag_type})
            event_types = [e for e, _ in bus.gepubliceerd]
            assert event_types == ["layer4_response"], (
                f"type={vraag_type} publiceerde {event_types}"
            )