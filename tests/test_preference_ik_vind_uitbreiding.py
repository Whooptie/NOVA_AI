# tests/test_preference_ik_vind_uitbreiding.py
"""
Tests voor de "ik vind [onderwerp] [oordeel]"-uitbreiding van
IntentRouter._ontleed_voorkeur_zin() (21 september 2026).

Aanleiding: "ik vind koffie eigenlijk wel oké maar niet top" werd
voorheen NERGENS herkend (bevestigd via unmatched_intents.jsonl) --
viel gewoon door naar fallback i.p.v. als voorkeur opgeslagen te
worden. Deze uitbreiding herkent de vorm "ik vind X Y" (onderwerp
EERST, oordeel erna), naast de al bestaande "ik vind leuk X"-vorm
(oordeel eerst).

Test tegen de ECHTE IntentRouter (geen nagebouwde kopie), geen
monkeypatch nodig -- __init__ doet geen I/O die deze methode raakt.
Nep-EventBus zelfde patroon als test_referentie_resolutie.py /
test_intent_router_reactivatie_en_woordmatch.py.
"""

import pytest

from core.intent_router import IntentRouter


class NepEventBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []

    def subscribe(self, event_type, handler):
        pass

    def publish(self, event_type, data):
        self.gepubliceerd.append((event_type, data))

    def register_module(self, naam, instance):
        self.modules[naam] = instance


@pytest.fixture
def router():
    bus = NepEventBus()
    return IntentRouter(bus)


@pytest.fixture
def router_met_bus():
    bus = NepEventBus()
    return IntentRouter(bus), bus


# ----------------------------------------------------------------
# 1. Het nieuwe "ik vind [onderwerp] [oordeel]"-patroon zelf
# ----------------------------------------------------------------
class TestIkVindOordeelPatroon:

    def test_positief_oordeel_koffie_lekker(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind koffie lekker")
        assert sentiment == "positief"
        assert woord == "koffie"

    def test_negatief_oordeel_thee_niet_lekker(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind thee niet lekker")
        assert sentiment == "negatief"
        assert woord == "thee"

    def test_positief_oordeel_leuk_na_onderwerp(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind schaken heel leuk")
        assert sentiment == "positief"
        assert woord == "schaken"

    def test_negatief_oordeel_vervelend(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind wiskunde vervelend")
        assert sentiment == "negatief"
        assert woord == "wiskunde"

    def test_negatief_oordeel_niks(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind programmeren niks")
        assert sentiment == "negatief"
        assert woord == "programmeren"

    def test_positief_oordeel_top(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind programmeren top")
        assert sentiment == "positief"
        assert woord == "programmeren"

    def test_grove_sentiment_bij_gemengde_zin_blijft_positief(self, router):
        """
        _ontleed_voorkeur_zin() zelf hoeft de "maar niet top"-nuance
        niet te vangen -- dat is de taak van _verfijn_sentiment()
        (leest de VOLLEDIGE zin via de sentiment_classifier). Deze
        test bevestigt enkel dat het ONDERWERP correct wordt herkend
        en het GROVE sentiment "positief" blijft (het eerste
        matchende oordeelwoord, "oké", is positief).
        """
        sentiment, woord = router._ontleed_voorkeur_zin(
            "ik vind koffie eigenlijk wel oké maar niet top"
        )
        assert sentiment == "positief"
        assert woord == "koffie"


# ----------------------------------------------------------------
# 2. Negatieve oordelen gaan voor positieve (substring-valkuil)
# ----------------------------------------------------------------
class TestNegatiefVoorPositiefVolgorde:
    """
    "niet oké" bevat zelf de substring "oké" -- zonder de vaste
    volgorde (negatieve oordelen EERST checken) zou dit ten onrechte
    als positief herkend worden.
    """

    def test_niet_oke_wordt_negatief_niet_positief(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind koffie niet oké")
        assert sentiment == "negatief"
        assert woord == "koffie"

    def test_niet_lekker_wordt_negatief_niet_positief(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind thee niet lekker")
        assert sentiment == "negatief"
        assert woord == "thee"

    def test_niet_goed_wordt_negatief(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind deze aanpak niet goed")
        assert sentiment == "negatief"
        assert woord == "aanpak"


# ----------------------------------------------------------------
# 3. Lidwoorden/aanwijzende voornaamwoorden worden overgeslagen
# ----------------------------------------------------------------
class TestLidwoordOverslaan:

    def test_dit_wordt_overgeslagen_spelletje_is_onderwerp(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind dit spelletje niks")
        assert sentiment == "negatief"
        assert woord == "spelletje"

    def test_het_wordt_overgeslagen_weer_is_onderwerp(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind het weer mooi")
        assert sentiment == "positief"
        assert woord == "weer"

    def test_de_wordt_overgeslagen(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind de cursus goed")
        assert sentiment == "positief"
        assert woord == "cursus"

    def test_alleen_lidwoord_zonder_woord_erna_geeft_geen_woord(self, router):
        """
        Randgeval: na het lidwoord blijft alleen het oordeelwoord zelf
        over ("ik vind dit leuk") -- er is dan geen apart onderwerp,
        dit mag GEEN foutief woord opleveren.
        """
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind dit leuk")
        assert woord is None

    def test_bekende_grens_bijvoeglijk_naamwoord_tussen_lidwoord_en_onderwerp(self, router):
        """
        Vastgelegde, aanvaarde beperking (zie code-comment): een
        bijvoeglijk naamwoord TUSSEN lidwoord en onderwerp ("de
        NIEUWE cursus") wordt niet correct herkend -- de functie pakt
        het eerste woord na het lidwoord ("nieuwe"), niet het echte
        onderwerp ("cursus"). Dit is een bewuste, benoemde grens
        (vereist woordsoort-detectie om op te lossen), GEEN bug --
        deze test legt het huidige, geaccepteerde gedrag vast zodat
        een toekomstige wijziging dit niet stilzwijgend anders maakt
        zonder dat het opvalt.
        """
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind de nieuwe cursus goed")
        assert woord == "nieuwe"  # NIET "cursus" -- zie docstring


# ----------------------------------------------------------------
# 4. Geen enkel oordeelwoord matcht -> blijft ongewijzigd (None)
# ----------------------------------------------------------------
class TestGeenOordeelGevonden:

    def test_geen_bekend_oordeelwoord_geeft_geen_woord(self, router):
        """
        Een woord dat niet in de vaste oordeel-lijsten staat (bv.
        "interessant") wordt niet herkend -- eerlijke, bewuste
        symbolische grens, zelfde principe als de rest van deze
        functie.
        """
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind quantumfysica interessant")
        assert woord is None

    def test_kale_ik_vind_zonder_rest_geeft_geen_woord(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind")
        assert woord is None

    def test_zin_die_niet_met_ik_vind_begint_raakt_dit_pad_niet(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("wat vind jij van koffie")
        assert woord is None


# ----------------------------------------------------------------
# 5. Geen regressie op de BESTAANDE patronen
# ----------------------------------------------------------------
class TestBestaandePatronenBlijvenWerken:
    """
    Deze uitbreiding voegt een NIEUWE tak toe aan _ontleed_voorkeur_
    zin() -- de bestaande patronen (die eerder in de functie
    gecontroleerd worden) mogen hierdoor op geen enkele manier
    veranderen. Inclusief de "ik vind leuk X"-vorm, die qua
    voorvoegsel op de nieuwe tak zou kunnen lijken maar een aparte,
    eerder gecontroleerde tak is.
    """

    def test_ik_hou_van_blijft_werken(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik hou van koffie")
        assert sentiment == "positief"
        assert woord == "koffie"

    def test_ik_hou_niet_van_blijft_werken(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("ik hou niet van spruitjes")
        assert sentiment == "negatief"
        assert woord == "spruitjes"

    def test_mijn_favoriete_blijft_werken(self, router):
        sentiment, woord = router._ontleed_voorkeur_zin("mijn favoriete kleur is blauw")
        assert sentiment == "positief"
        assert woord == "blauw"

    def test_ik_vind_leuk_blijft_via_de_oude_tak_lopen(self, router):
        """
        "ik vind leuk X" wordt AL AFGEHANDELD door de bestaande
        positieve_patronen-lijst, vóór de nieuwe tak ooit bereikt
        wordt (de nieuwe tak checkt expliciet op NIET starten met
        "leuk "). Dit bevestigt dat er geen dubbele/conflicterende
        matching optreedt.
        """
        sentiment, woord = router._ontleed_voorkeur_zin("ik vind leuk om te schaken")
        assert sentiment == "positief"
        assert woord == "om te schaken"

    def test_afkap_signaal_maar_blijft_werken_bij_bestaand_patroon(self, router):
        """
        Regressietest voor de eerder gedocumenteerde bugfix (26 juli
        2026): "ik hou van koffie maar het is niet mijn favoriet"
        moet nog steeds correct afkappen tot enkel "koffie".
        """
        sentiment, woord = router._ontleed_voorkeur_zin(
            "ik hou van koffie maar het is niet mijn favoriet"
        )
        assert sentiment == "positief"
        assert woord == "koffie"

    def test_negatieve_patronen_gaan_nog_steeds_voor(self, router):
        """
        "ik haat "/"ik lust geen "/etc. worden AL AFGEHANDELD in de
        allereerste patroonlijst, ver vóór de nieuwe "ik vind"-tak --
        deze test bevestigt dat die volgorde intact blijft.
        """
        sentiment, woord = router._ontleed_voorkeur_zin("ik haat spruitjes")
        assert sentiment == "negatief"
        assert woord == "spruitjes"


# ----------------------------------------------------------------
# 6. Integratie: detect_preference() end-to-end via de EventBus
# ----------------------------------------------------------------
class TestDetectPreferenceIntegratie:
    """
    Bevestigt dat de nieuwe herkenning ook echt door de volledige
    detect_preference()-flow komt (niet enkel _ontleed_voorkeur_zin()
    in isolatie) -- publiceert intent_preference_detected met de
    juiste velden, zelfde contract als de bestaande patronen.
    """

    def test_detect_preference_herkent_nieuw_patroon(self, router_met_bus):
        router, bus = router_met_bus
        resultaat = router.detect_preference("ik vind koffie lekker")

        assert resultaat is True
        events = [e for e in bus.gepubliceerd if e[0] == "intent_preference_detected"]
        assert len(events) == 1
        assert events[0][1]["woord"] == "koffie"
        assert events[0][1]["sentiment"] == "positief"
        assert events[0][1]["volledige_zin"] == "ik vind koffie lekker"

    def test_detect_preference_geeft_false_bij_geen_match(self, router_met_bus):
        router, bus = router_met_bus
        resultaat = router.detect_preference("hoe laat is het")

        assert resultaat is False
        events = [e for e in bus.gepubliceerd if e[0] == "intent_preference_detected"]
        assert len(events) == 0

    def test_detect_preference_negatief_oordeel_end_to_end(self, router_met_bus):
        router, bus = router_met_bus
        resultaat = router.detect_preference("ik vind wiskunde vervelend")

        assert resultaat is True
        events = [e for e in bus.gepubliceerd if e[0] == "intent_preference_detected"]
        assert events[0][1]["woord"] == "wiskunde"
        assert events[0][1]["sentiment"] == "negatief"