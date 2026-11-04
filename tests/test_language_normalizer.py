# tests/test_language_normalizer.py
"""
Tests voor core/language_normalizer.py en de aansluiting in IntentRouter
(punt 62a, 4 november 2026). Geen mini-Nova nodig: de router krijgt een
nep-EventBus.
"""
import pytest

import core.intent_router as ir
from core.intent_router import IntentRouter
from core.language_normalizer import normaliseer


class DummyBus:
    def __init__(self):
        self.events = []
        self.modules = {}

    def subscribe(self, naam, functie):
        pass

    def publish(self, naam, data=None, *args, **kwargs):
        self.events.append((naam, data))

    def namen(self):
        return [n for n, _ in self.events]


def maak_router():
    bus = DummyBus()
    return IntentRouter(bus), bus


# ---------------------------------------------------------------------------
# De regels: zin in, verwachte zin + regelnaam uit
# ---------------------------------------------------------------------------
POSITIEF = [
    # definitie
    ("kun je me vertellen wat een hond is", "wat is een hond", "definitie_bijzin"),
    ("kan je me vertellen wat een hond is", "wat is een hond", "definitie_bijzin"),
    ("weet jij wat een zebra is", "wat is een zebra", "definitie_bijzin"),
    ("leg eens uit wat een stoel is", "wat is een stoel", "definitie_bijzin"),
    ("vertel me wat een paard is", "wat is een paard", "definitie_bijzin"),
    ("kun je uitleggen wat een auto is", "wat is een auto", "definitie_bijzin"),
    ("zeg eens, wat is regen eigenlijk", "wat is regen", "definitie_kaal"),
    ("wat is een hond nou", "wat is een hond", "definitie_kaal"),
    ("wat betekent het woord vulkaan", "wat is vulkaan", "definitie_woord"),
    ("wat houdt het woord tijger in", "wat is tijger", "definitie_inhoud"),
    ("wat houdt regen in", "wat is regen", "definitie_inhoud"),
    # relatie
    ("klopt het dat een kat een zoogdier is", "is een kat een zoogdier", "relatie_klopt"),
    ("is het waar dat een walvis een zoogdier is", "is een walvis een zoogdier", "relatie_klopt"),
    ("ik wil graag weten of een paard een zoogdier is", "is een paard een zoogdier", "relatie_of"),
    ("weet jij of een vis een dier is", "is een vis een dier", "relatie_of"),
    ("een zebra, is dat een dier", "is een zebra een dier", "relatie_is_dat"),
    ("een zebra is dat ook een dier", "is een zebra een dier", "relatie_is_dat"),
    ("is een fiets ook een voertuig", "is een fiets een voertuig", "relatie_ook"),
    ("is een fiets een voertuig, denk ik", "is een fiets een voertuig", "relatie_kaal"),
    ("is een kat volgens jou een dier", "is een kat een dier", "relatie_kaal"),
    ("waarom is een zebra een dier", "is een zebra een dier", "relatie_waarom"),
    ("hoe komt het dat een tijger een dier is", "is een tijger een dier", "relatie_waarom_bijzin"),
    # oorzaak / gevolg
    ("waardoor ontstaat modder", "wat veroorzaakt modder", "oorzaak_waardoor"),
    ("waarom ontstaat modder", "wat veroorzaakt modder", "oorzaak_waarom"),
    ("wat is de oorzaak van modder", "wat veroorzaakt modder", "oorzaak_noemen"),
    ("wat zijn de oorzaken van modder", "wat veroorzaakt modder", "oorzaak_noemen"),
    ("wat is het effect van regen", "wat zijn de gevolgen van regen", "gevolg_effect"),
    # synoniem / antoniem
    ("welk woord betekent hetzelfde als zus", "wat is een synoniem van zus", "synoniem_hetzelfde"),
    ("wat is een synoniem voor zus", "wat is een synoniem van zus", "synoniem_voor"),
    ("wat is het omgekeerde van onthouden", "wat is het tegenovergestelde van onthouden", "antoniem_omgekeerd"),
]


@pytest.mark.parametrize("invoer,verwacht,regel", POSITIEF)
def test_herschrijft_naar_bekende_vorm(invoer, verwacht, regel):
    nieuw, naam = normaliseer(invoer)
    assert nieuw == verwacht
    assert naam == regel


@pytest.mark.parametrize("invoer,verwacht,regel", POSITIEF)
def test_is_idempotent(invoer, verwacht, regel):
    """Een al genormaliseerde zin verandert niet meer."""
    nieuw, _ = normaliseer(invoer)
    nog_eens, naam = normaliseer(nieuw)
    assert nog_eens == nieuw
    assert naam is None


def test_hoofdletters_en_vraagteken_geen_probleem():
    assert normaliseer("Kun je me vertellen wat een Hond is?")[0] == "wat is een hond"


def test_meerdere_vulwoorden_en_aanhef():
    assert normaliseer("Hé Nova, zeg eens even wat een zebra eigenlijk is")[0] == "wat is een zebra"


def test_term_van_twee_woorden():
    assert normaliseer("weet jij wat een levend wezen is")[0] == "wat is een levend wezen"


# ---------------------------------------------------------------------------
# Veiligheid: dit moet ONGEWIJZIGD blijven
# ---------------------------------------------------------------------------
ONGEWIJZIGD = [
    "kun je me vertellen wie jij bent",
    "kun je me vertellen wat jij is",
    "weet jij hoe laat het is",
    "hoe laat is het",
    "kun je me vertellen hoe het weer is",
    "wat is het weer",
    "wat ben jij",
    "wat is 5 maal 3",
    "wat is dat",
    "wat is de tijd",
    "een hond is een dier",
    "een hond is een meubel",
    "dat is een hond",
    "waarom is de lucht blauw",
    "leg uit kracht",
    "zeg hallo",
    "vertel me een mop",
    "is het een goed idee",
    "klopt het dat ik een dier ben",
    "wat is een hond",
    "is een kat een dier",
    "wat veroorzaakt modder",
    "wat een heel erg groot stuk hond is",
    "hallo nova",
    "bedankt",
]


@pytest.mark.parametrize("invoer", ONGEWIJZIGD)
def test_blijft_ongewijzigd(invoer):
    nieuw, naam = normaliseer(invoer)
    assert nieuw == invoer
    assert naam is None


@pytest.mark.parametrize("leeg", ["", "   ", None])
def test_leeg_blijft_leeg(leeg):
    nieuw, naam = normaliseer(leeg)
    assert nieuw == leeg and naam is None


def test_geeft_bij_geen_match_de_originele_tekst_terug_met_hoofdletters():
    assert normaliseer("Wie Is Jij?") == ("Wie Is Jij?", None)


def test_voornaamwoord_als_onderwerp_wordt_niet_herschreven():
    assert normaliseer("weet jij wat ik ben")[1] is None
    assert normaliseer("weet jij wat nova is")[1] is None


def test_stopwoord_als_enig_onderwerp_wordt_niet_herschreven():
    assert normaliseer("weet jij wat dan is")[1] is None


# ---------------------------------------------------------------------------
# De router
# ---------------------------------------------------------------------------
def test_router_herschrijft_en_meldt_het_event():
    router, bus = maak_router()
    nieuw = router._normaliseer_omhulsel("weet jij wat een zebra is")
    assert nieuw == "wat is een zebra"
    gebeurd = [d for n, d in bus.events if n == "language_normalized"]
    assert gebeurd == [{"origineel": "weet jij wat een zebra is",
                        "genormaliseerd": "wat is een zebra",
                        "regel": "definitie_bijzin"}]


def test_router_publiceert_niets_als_er_niets_verandert():
    router, bus = maak_router()
    assert router._normaliseer_omhulsel("wat is een hond") == "wat is een hond"
    assert "language_normalized" not in bus.namen()


def test_router_valt_terug_op_origineel_bij_een_fout_in_de_module(monkeypatch):
    def kapot(_tekst):
        raise RuntimeError("boem")
    monkeypatch.setattr(ir, "_normaliseer_vraag", kapot)
    router, bus = maak_router()
    assert router._normaliseer_omhulsel("weet jij wat een zebra is") == "weet jij wat een zebra is"
    assert "language_normalized" not in bus.namen()


def test_router_werkt_zonder_de_module(monkeypatch):
    monkeypatch.setattr(ir, "_normaliseer_vraag", None)
    router, _ = maak_router()
    assert router._normaliseer_omhulsel("weet jij wat een zebra is") == "weet jij wat een zebra is"


def test_route_geeft_definitie_event_voor_een_omhulde_vraag():
    router, bus = maak_router()
    router.route({"text": "kun je me vertellen wat een hond is"}, "chat_message")
    gevonden = [d for n, d in bus.events if n == "intent_definition"]
    assert gevonden and gevonden[0]["word"] == "hond"
    assert "intent_fallback" not in bus.namen()


def test_route_geeft_relatie_event_voor_klopt_het_dat():
    router, bus = maak_router()
    router.route({"text": "klopt het dat een kat een zoogdier is"}, "chat_message")
    gevonden = [d for n, d in bus.events if n == "intent_relation_check"]
    assert gevonden and gevonden[0] == {"source": "kat", "target": "zoogdier"}


def test_route_geeft_causes_event_voor_waardoor_ontstaat():
    router, bus = maak_router()
    router.route({"text": "waardoor ontstaat modder"}, "chat_message")
    assert ("intent_causes", {"word": "modder"}) in bus.events


def test_raw_user_message_bevat_de_originele_zin():
    router, bus = maak_router()
    router.route({"text": "weet jij wat een zebra is"}, "chat_message")
    assert ("raw_user_message", {"text": "weet jij wat een zebra is"}) in bus.events


def test_persoonlijke_vraag_wordt_niet_als_kennisvraag_gelezen():
    router, bus = maak_router()
    router.route({"text": "kun je me vertellen wie jij bent"}, "chat_message")
    assert "language_normalized" not in bus.namen()
    assert "intent_definition" not in bus.namen()


# ---------------------------------------------------------------------------
# De 'waarom'-fout in detect_relation_check (patroon 2)
# ---------------------------------------------------------------------------
def test_waarom_is_nooit_het_onderwerp_van_een_relatie():
    router, bus = maak_router()
    assert router.detect_relation_check("waarom is een zebra een dier") is False
    assert "intent_relation_check" not in bus.namen()


@pytest.mark.parametrize("vraagwoord", ["waarom", "hoe", "waar", "wanneer", "welke", "waardoor"])
def test_vraagwoorden_zijn_geen_relatie_onderwerp(vraagwoord):
    router, bus = maak_router()
    assert router.detect_relation_check(f"{vraagwoord} is een zebra een dier") is False


def test_gewone_relatievraag_blijft_werken():
    router, bus = maak_router()
    assert router.detect_relation_check("is een zebra een dier") is True
    assert ("intent_relation_check", {"source": "zebra", "target": "dier"}) in bus.events


def test_stelling_x_is_een_y_blijft_werken():
    router, bus = maak_router()
    assert router.detect_relation_check("zebra is een dier") is True