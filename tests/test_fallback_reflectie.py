# tests/test_fallback_reflectie.py
"""
Tests voor modules/chat/fallback_reflectie.py.

Test tegen de ECHTE FallbackReflectie (geen nagebouwde kopie) --
zelfde aanpak als test_topic_suggestions.py / test_emergence_
screen_focus.py: get_project_root() gemonkeypatcht naar tmp_path,
zodat geen enkele test Kevin's echte data/fallback_reflectie_
patronen.json aanraakt. Elke test schrijft zijn eigen, gecontroleerde
patronenbestand naar tmp_path, zodat de tests niet afhangen van wat
er op dat moment in het echte databestand staat.

Nep-EventBus (publish/subscribe/.modules-dict), zelfde patroon als
test_variant_kiezer.py / test_variant_feedback_logger.py.
"""

import json

import pytest

from modules.chat import fallback_reflectie


# ----------------------------------------------------------------
# Hulpmiddelen
# ----------------------------------------------------------------
class NepEventBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []
        self._subscribers = {}

    def publish(self, event_type, data):
        self.gepubliceerd.append((event_type, data))
        for handler in self._subscribers.get(event_type, []):
            handler(data, event_type)
        # Zelfde wildcard-gedrag als de echte EventBus/memory.py --
        # nodig omdat sommige modules zich op "*" abonneren.
        for handler in self._subscribers.get("*", []):
            handler(data, event_type)

    def subscribe(self, event_type, handler):
        self._subscribers.setdefault(event_type, []).append(handler)

    def register_module(self, naam, instance):
        self.modules[naam] = instance


class NepVariantFeedbackLogger:
    """
    Simuleert variant_feedback_logger.py's get_gewichten()-interface
    zonder de echte logger te hoeven bouwen. Standaard: None
    (=gelijke kansen, want nog geen observaties) -- kan per test
    overschreven worden om gewogen keuze te forceren/testen.
    """
    def __init__(self, gewichten_per_sjabloon=None):
        self.gewichten_per_sjabloon = gewichten_per_sjabloon or {}

    def get_gewichten(self, sjabloon_naam, aantal_varianten):
        return self.gewichten_per_sjabloon.get(sjabloon_naam)


def _schrijf_patronen(tmp_path, data):
    """
    Bouwt de vaste project-structuur na die get_project_root()
    verwacht (een main.py-marker in de root) en schrijft het
    patronenbestand op de plek die FallbackReflectie verwacht.
    """
    (tmp_path / "main.py").write_text("# marker", encoding="utf-8")
    data_map = tmp_path / "data"
    data_map.mkdir(exist_ok=True)
    pad = data_map / "fallback_reflectie_patronen.json"
    pad.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return pad


STANDAARD_PATRONEN = {
    "decompositie": [
        {
            "patroon": r"\bik voel me (.+)",
            "sjabloon_naam": "reflectie_voel_me",
            "varianten": [
                "Sinds wanneer voel je je {1}?",
                "Wat maakt dat je je {1} voelt?",
            ],
        },
        {
            "patroon": r"\bik ben (.+)",
            "sjabloon_naam": "reflectie_ben",
            "varianten": ["Sinds wanneer ben je {1}?"],
        },
    ],
    "keywords": [
        {
            "trefwoorden": ["moe", "vermoeid"],
            "sjabloon_naam": "reflectie_kw_moe",
            "varianten": ["Klinkt alsof je moe bent."],
        },
        {
            "trefwoorden": ["druk", "stress"],
            "sjabloon_naam": "reflectie_kw_druk",
            "varianten": ["Klinkt behoorlijk druk allemaal."],
        },
    ],
}


@pytest.fixture
def maak_reflectie(tmp_path, monkeypatch):
    """
    Geeft een fabrieksfunctie terug: maak_reflectie(patronen_data) ->
    (instance, event_bus). Elke test bepaalt zelf welke patronen-data
    gebruikt wordt, i.p.v. 1 vaste globale fixture -- nodig omdat
    meerdere tests bewust MET ontbrekende/kapotte data willen testen.
    """
    def _fabriek(patronen_data=STANDAARD_PATRONEN, variant_logger=None):
        _schrijf_patronen(tmp_path, patronen_data)
        monkeypatch.setattr(
            fallback_reflectie, "get_project_root", lambda _: tmp_path
        )
        bus = NepEventBus()
        if variant_logger is not None:
            bus.register_module("variant_feedback_logger", variant_logger)
        instance = fallback_reflectie.init_module(bus)
        return instance, bus

    return _fabriek


# ----------------------------------------------------------------
# 1. Laden van het patronenbestand
# ----------------------------------------------------------------
class TestPatronenLaden:

    def test_geldig_bestand_laadt_correct(self, maak_reflectie):
        refl, _ = maak_reflectie()
        assert len(refl._decompositie_patronen) == 2
        assert len(refl._keyword_groepen) == 2

    def test_ontbrekend_bestand_geeft_lege_lijsten(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "main.py").write_text("# marker", encoding="utf-8")
        # Bewust GEEN data/-map/bestand aangemaakt.
        monkeypatch.setattr(
            fallback_reflectie, "get_project_root", lambda _: tmp_path
        )
        bus = NepEventBus()
        refl = fallback_reflectie.init_module(bus)

        assert refl._decompositie_patronen == []
        assert refl._keyword_groepen == []
        # reflecteer() moet dan gewoon altijd None geven, nooit crashen.
        assert refl.reflecteer("ik ben moe") is None

    def test_corrupt_json_geeft_lege_lijsten_geen_crash(self, tmp_path, monkeypatch):
        (tmp_path / "main.py").write_text("# marker", encoding="utf-8")
        data_map = tmp_path / "data"
        data_map.mkdir()
        pad = data_map / "fallback_reflectie_patronen.json"
        pad.write_text("{ dit is geen geldige JSON", encoding="utf-8")

        monkeypatch.setattr(
            fallback_reflectie, "get_project_root", lambda _: tmp_path
        )
        bus = NepEventBus()
        # Mag niet crashen tijdens init_module().
        refl = fallback_reflectie.init_module(bus)

        assert refl._decompositie_patronen == []
        assert refl._keyword_groepen == []

    def test_1_ongeldig_decompositie_patroon_blokkeert_andere_niet(self, maak_reflectie):
        """
        Een fout in EEN entry (hier: kapotte regex) mag de andere,
        wel geldige entries niet blokkeren -- elke entry wordt apart
        gevalideerd, niet het hele bestand in 1 keer.
        """
        data = {
            "decompositie": [
                {
                    "patroon": "(onafgesloten haakje",  # ongeldige regex
                    "sjabloon_naam": "kapot",
                    "varianten": ["x {1}"],
                },
                {
                    "patroon": r"\bik ben (.+)",
                    "sjabloon_naam": "reflectie_ben",
                    "varianten": ["Sinds wanneer ben je {1}?"],
                },
            ],
            "keywords": [],
        }
        refl, _ = maak_reflectie(data)

        assert len(refl._decompositie_patronen) == 1
        assert refl.reflecteer("ik ben blij") == "Sinds wanneer ben je blij?"

    def test_ontbrekend_veld_in_entry_wordt_overgeslagen(self, maak_reflectie):
        data = {
            "decompositie": [
                {"patroon": r"\bik ben (.+)", "sjabloon_naam": "reflectie_ben"},  # geen 'varianten'
            ],
            "keywords": [
                {"trefwoorden": ["moe"], "sjabloon_naam": "x"},  # geen 'varianten'
            ],
        }
        refl, _ = maak_reflectie(data)

        assert refl._decompositie_patronen == []
        assert refl._keyword_groepen == []


# ----------------------------------------------------------------
# 2. Decompositie-laag
# ----------------------------------------------------------------
class TestDecompositie:

    def test_ik_ben_patroon_matcht(self, maak_reflectie):
        refl, _ = maak_reflectie()
        resultaat = refl.reflecteer("ik ben moe vandaag")
        assert resultaat == "Sinds wanneer ben je moe vandaag?"

    def test_specifieker_patroon_wint_van_generieker_patroon(self, maak_reflectie):
        """
        'ik voel me *' staat VOOR 'ik ben *' in STANDAARD_PATRONEN --
        bij een zin die beide zou kunnen matchen, moet de eerste
        (specifiekere) regel winnen, niet de generieke.

        Controleert dit via het GEPUBLICEERDE sjabloon_naam-veld, niet
        via de letterlijke tekst -- reflectie_voel_me heeft meerdere
        varianten (via kies_variant()), dus een tekst-gebaseerde check
        (bv. .startswith() op 1 specifieke variant) is FLAKY: die zou
        maar bij een deel van de mogelijke variant-keuzes slagen. Het
        sjabloon_naam-veld identificeert WELK patroon matchte,
        onafhankelijk van welke variant daarbinnen gekozen werd --
        zelfde aanpak als test_variant_gekozen_event_gepubliceerd_met_
        juiste_sjabloon_naam hierboven.
        """
        refl, bus = maak_reflectie()
        resultaat = refl.reflecteer("ik voel me eigenlijk wel goed")

        events = [e for e in bus.gepubliceerd if e[0] == "variant_gekozen"]
        assert len(events) == 1
        assert events[0][1]["sjabloon_naam"] == "reflectie_voel_me"
        assert "goed" in resultaat

    def test_voornaamwoord_omkering_in_opgevangen_tekst(self, maak_reflectie):
        data = {
            "decompositie": [
                {
                    "patroon": r"\bik denk dat (.+)",
                    "sjabloon_naam": "reflectie_denk_dat",
                    "varianten": ["Waarom denk je dat {1}?"],
                }
            ],
            "keywords": [],
        }
        refl, _ = maak_reflectie(data)
        resultaat = refl.reflecteer("ik denk dat ik mijn examen niet haal")
        # "ik" -> "je", "mijn" -> "jouw" (binnen de opgevangen tekst)
        assert resultaat == "Waarom denk je dat je jouw examen niet haal?"

    def test_geen_match_geeft_none(self, maak_reflectie):
        refl, _ = maak_reflectie()
        assert refl.reflecteer("wat is de hoofdstad van Frankrijk") is None

    def test_hoofdletterongevoelig(self, maak_reflectie):
        refl, _ = maak_reflectie()
        resultaat = refl.reflecteer("IK BEN Erg Moe")
        assert resultaat == "Sinds wanneer ben je erg moe?"

    def test_lege_opvangst_wordt_overgeslagen(self, maak_reflectie):
        """
        "ik ben" zonder vervolg zou een lege group(1) geven na
        strip() -- dat mag geen kapotte "Sinds wanneer ben je ?"
        opleveren, en moet dus NIET als match tellen.
        """
        refl, _ = maak_reflectie()
        resultaat = refl.reflecteer("ik ben")
        assert resultaat is None

    def test_variant_gekozen_event_gepubliceerd_met_juiste_sjabloon_naam(self, maak_reflectie):
        refl, bus = maak_reflectie()
        refl.reflecteer("ik ben moe")

        events = [e for e in bus.gepubliceerd if e[0] == "variant_gekozen"]
        assert len(events) == 1
        assert events[0][1]["sjabloon_naam"] == "reflectie_ben"


class TestMeerdereVanggroepen:
    """
    Regressietests voor de multi-groep-uitbreiding (21 september 2026):
    een patroon zoals "had ik (.+?) moeten (.+)" heeft TWEE vanggroepen
    ({1} en {2}), niet 1. _probeer_decompositie() moet dit generiek
    ondersteunen, ongeacht hoeveel groepen een patroon heeft.
    """

    PATROON_2_GROEPEN = {
        "decompositie": [
            {
                "patroon": r"\bhad ik (.+?) moeten (.+)",
                "sjabloon_naam": "reflectie_had_moeten",
                "varianten": [
                    "Wat maakt dat je denkt dat je {1} had moeten {2}?",
                ],
            }
        ],
        "keywords": [],
    }

    def test_twee_vanggroepen_komen_op_de_juiste_positie_terecht(self, maak_reflectie):
        refl, _ = maak_reflectie(self.PATROON_2_GROEPEN)
        resultaat = refl.reflecteer("had ik dat anders moeten aanpakken")
        # {1} = "dat anders" (groep 1), {2} = "aanpakken" (groep 2) --
        # NOOIT verwisseld.
        assert resultaat == "Wat maakt dat je denkt dat je dat anders had moeten aanpakken?"

    def test_een_lege_vanggroep_blokkeert_de_hele_match(self, maak_reflectie):
        """
        Als een van de meerdere groepen leeg zou uitvallen (na
        strip()), mag dit GEEN kapotte zin met een gat opleveren --
        de hele match telt dan niet, zelfde principe als bij 1 groep.
        """
        data = {
            "decompositie": [
                {
                    "patroon": r"\bhad ik (.*?) moeten (.+)",
                    "sjabloon_naam": "reflectie_had_moeten",
                    "varianten": ["{1} had moeten {2}"],
                }
            ],
            "keywords": [],
        }
        refl, _ = maak_reflectie(data)
        # groep 1 zou hier leeg zijn ("had ik moeten gaan")
        resultaat = refl.reflecteer("had ik moeten gaan")
        assert resultaat is None

    def test_sjabloon_met_te_hoge_group_index_crasht_niet(self, maak_reflectie):
        """
        Een sjabloon die {2} gebruikt terwijl het patroon maar 1 groep
        heeft (data-fout) mag de reflectie-laag nooit laten crashen --
        gewoon overslaan en verdergaan naar een eventuele volgende
        match/laag, niet de hele pipeline breken.
        """
        data = {
            "decompositie": [
                {
                    "patroon": r"\bik ben (.+)",
                    "sjabloon_naam": "kapotte_sjabloon",
                    "varianten": ["Sinds wanneer ben je {1} en {2}?"],
                }
            ],
            "keywords": [
                {
                    "trefwoorden": ["moe"],
                    "sjabloon_naam": "reflectie_kw_moe",
                    "varianten": ["Klinkt alsof je moe bent."],
                }
            ],
        }
        refl, _ = maak_reflectie(data)
        # Mag niet crashen -- valt door naar keyword-laag, matcht daar
        # wel via "moe".
        resultaat = refl.reflecteer("ik ben moe")
        assert resultaat == "Klinkt alsof je moe bent."


class TestNietVragendeReflectie:
    """
    Sommige keyword-groepen (bv. dank/waardering) zijn BEWUST GEEN
    tegenvraag -- "dankjewel" beantwoorden met "wat maakt dat je
    dankbaar bent?" zou vreemd/afwijzend aanvoelen. Deze tests
    bevestigen dat zulke groepen gewoon als normale keyword-entry
    werken (geen aparte code-tak nodig, puur data-kwestie), en dat
    de reflectie-laag zich niet bemoeit met TOON -- dat zit puur in
    de varianten-tekst zelf.
    """

    DATA_DANK = {
        "decompositie": [],
        "keywords": [
            {
                "trefwoorden": ["dankjewel", "bedankt", "dank"],
                "sjabloon_naam": "reflectie_kw_dank",
                "varianten": ["Graag gedaan!", "Fijn dat het helpt."],
            }
        ],
    }

    def test_dank_geeft_bevestiging_geen_vraag(self, maak_reflectie):
        refl, _ = maak_reflectie(self.DATA_DANK)
        resultaat = refl.reflecteer("dankjewel, dat helpt echt")
        assert resultaat in ("Graag gedaan!", "Fijn dat het helpt.")
        assert "?" not in resultaat

    def test_dank_matcht_ook_binnen_een_langere_zin(self, maak_reflectie):
        refl, _ = maak_reflectie(self.DATA_DANK)
        resultaat = refl.reflecteer("dank je, dat is duidelijk!")
        assert resultaat is not None


# ----------------------------------------------------------------
# 3. Keyword-reflectie (vangnet-laag)
# ----------------------------------------------------------------
class TestKeywordReflectie:

    def test_keyword_matcht_als_decompositie_niets_vindt(self, maak_reflectie):
        refl, _ = maak_reflectie()
        resultaat = refl.reflecteer("pff, veel te druk geweest vandaag")
        assert resultaat == "Klinkt behoorlijk druk allemaal."

    def test_decompositie_gaat_altijd_voor_keyword(self, maak_reflectie):
        """
        Een zin die ZOWEL een decompositiepatroon als een keyword
        bevat, moet via decompositie afgehandeld worden -- dat is de
        specifiekere, eerste laag.
        """
        refl, _ = maak_reflectie()
        # "ik ben moe" matcht zowel "ik ben *" (decompositie) als
        # het keyword "moe".
        resultaat = refl.reflecteer("ik ben moe")
        assert resultaat == "Sinds wanneer ben je moe?"

    def test_geen_enkel_keyword_geeft_none(self, maak_reflectie):
        refl, _ = maak_reflectie()
        assert refl.reflecteer("de zon schijnt buiten") is None

    def test_keyword_matching_is_hoofdletterongevoelig(self, maak_reflectie):
        refl, _ = maak_reflectie()
        resultaat = refl.reflecteer("Ik ben MOE.")
        # Matcht via decompositie ("ik ben *"), niet via keyword --
        # dus dit bevestigt vooral dat de tekst_klein-normalisatie
        # correct wordt toegepast VOOR beide lagen.
        assert resultaat is not None

    def test_leesteken_aan_woord_blokkeert_keyword_match_niet(self, maak_reflectie):
        refl, _ = maak_reflectie()
        resultaat = refl.reflecteer("druk, druk, druk vandaag!")
        assert resultaat == "Klinkt behoorlijk druk allemaal."


# ----------------------------------------------------------------
# 4. Randgevallen op reflecteer() zelf
# ----------------------------------------------------------------
class TestRandgevallen:

    def test_lege_string_geeft_none(self, maak_reflectie):
        refl, _ = maak_reflectie()
        assert refl.reflecteer("") is None

    def test_none_geeft_none_geen_crash(self, maak_reflectie):
        refl, _ = maak_reflectie()
        assert refl.reflecteer(None) is None

    def test_alleen_witruimte_geeft_none(self, maak_reflectie):
        refl, _ = maak_reflectie()
        assert refl.reflecteer("   ") is None


# ----------------------------------------------------------------
# 5. Integratie met variant_feedback_logger (Response Variant Learning)
# ----------------------------------------------------------------
class TestVariantFeedbackIntegratie:

    def test_werkt_zonder_variant_feedback_logger(self, maak_reflectie):
        """
        variant_feedback_logger is optioneel (zelfde principe als
        variant_kiezer.py zelf) -- ontbreekt de module in
        event_bus.modules, dan moet dit gewoon blijven werken
        (gelijke-kansen-fallback), geen crash.
        """
        refl, bus = maak_reflectie()
        assert "variant_feedback_logger" not in bus.modules
        resultaat = refl.reflecteer("ik ben moe")
        assert resultaat is not None

    def test_gewogen_keuze_gebruikt_als_logger_beschikbaar_is(self, maak_reflectie):
        data = {
            "decompositie": [
                {
                    "patroon": r"\bik voel me (.+)",
                    "sjabloon_naam": "reflectie_voel_me",
                    "varianten": ["Variant A {1}", "Variant B {1}"],
                }
            ],
            "keywords": [],
        }
        # Gewicht 0 voor index 0 -> index 1 moet ALTIJD gekozen worden.
        logger = NepVariantFeedbackLogger(
            gewichten_per_sjabloon={"reflectie_voel_me": [0.0, 1.0]}
        )
        refl, _ = maak_reflectie(data, variant_logger=logger)

        for _ in range(10):
            resultaat = refl.reflecteer("ik voel me raar")
            assert resultaat.startswith("Variant B")

    def test_fout_in_get_gewichten_valt_terug_op_gelijke_kansen(self, maak_reflectie):
        """
        Zelfde fail-safe-principe als variant_kiezer.py zelf: een
        fout in een ondersteunende laag mag het antwoord nooit laten
        crashen.
        """
        class KapotteLogger:
            def get_gewichten(self, sjabloon_naam, aantal_varianten):
                raise RuntimeError("iets ging stuk")

        refl, _ = maak_reflectie(variant_logger=KapotteLogger())
        resultaat = refl.reflecteer("ik ben moe")
        assert resultaat is not None