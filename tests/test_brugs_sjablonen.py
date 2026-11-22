# tests/test_brugs_sjablonen.py
"""
Brutale Brugse sjabloonvarianten (identity/expression/brugs_sjablonen.json).

Vangnet: elke variant moet met PRECIES de invulplekken van het gewone sjabloon
te formatteren zijn (anders faalt .format() midden in een gesprek), en de
varianten mogen enkel gebruikt worden als de Brugse modus aan staat.
"""
import json

import pytest

from core.event_bus import EventBus
from core.response_engine import ResponseEngine
from modules.chat.brugs_filter import BrugsFilter, SJABLONEN_PAD
from modules.chat.response_pipeline import ResponsePipeline

with open(SJABLONEN_PAD, "r", encoding="utf-8") as _f:
    SJABLONEN = json.load(_f)

PLAATSHOUDERS = SJABLONEN["_plaatshouders"]
SJABLOON_NAMEN = [n for n in SJABLONEN if not n.startswith("_")]


@pytest.mark.parametrize("naam", SJABLOON_NAMEN)
def test_minstens_drie_varianten_en_alle_formatteerbaar(naam):
    varianten = SJABLONEN[naam]
    assert len(varianten) >= 3
    waarden = {k: "x" for k in PLAATSHOUDERS[naam]}
    for zin in varianten:
        assert isinstance(zin, str) and zin.strip()
        zin.format(**waarden)  # KeyError/IndexError = kapotte variant


# Plaatshouders die de INHOUD van het antwoord dragen: een variant die ze weglaat zou
# informatie verliezen (de definitie, de associatie, het uur). {entity} en {sender}
# mogen wegvallen, net als bij de gewone sjablonen ("Hmm... dat zegt me niets.").
VERPLICHT = {
    "definitie": ["definition"],
    "met_associatie": ["definition", "associatie"],
    "is_a_fallback": ["parent"],
    "timing_hint": ["uur"],
}


@pytest.mark.parametrize("naam", sorted(VERPLICHT))
def test_varianten_behouden_de_inhoud(naam):
    for zin in SJABLONEN[naam]:
        for sleutel in VERPLICHT[naam]:
            assert "{" + sleutel + "}" in zin, f"{naam}: '{zin}' mist {{{sleutel}}}"


def _filter(aan):
    f = BrugsFilter(event_bus=None, bewaar=False)
    f.aan = aan
    return f


def test_varianten_alleen_als_modus_aan():
    assert _filter(False).varianten("groet") is None
    assert _filter(True).varianten("groet")
    assert _filter(True).varianten("bestaat_niet") is None


def test_filter_zonder_sjabloonbestand_geeft_none():
    f = BrugsFilter(event_bus=None, bewaar=False, sjablonen_pad="/bestaat/niet.json")
    f.aan = True
    assert f.varianten("groet") is None


def _engine(aan):
    bus = EventBus()
    bus.modules = getattr(bus, "modules", {})
    if aan is not None:
        bus.modules["brugs_filter"] = _filter(aan)
    return ResponseEngine(event_bus=bus)


def test_response_engine_gewoon_als_modus_uit_of_ontbreekt():
    gewone = {z.format(entity="python", definition="een slang")
              for z in ResponseEngine(event_bus=None).templates["definitie"]}
    for aan in (False, None):
        engine = _engine(aan)
        for _ in range(30):
            assert engine._kies_variant("definitie", entity="python", definition="een slang") in gewone


def test_response_engine_brugs_als_modus_aan():
    engine = _engine(True)
    brugs = {z.format(entity="python", definition="een slang") for z in SJABLONEN["definitie"]}
    gewone = {z.format(entity="python", definition="een slang")
              for z in engine.templates["definitie"]}
    for _ in range(30):
        zin = engine._kies_variant("definitie", entity="python", definition="een slang")
        assert zin in brugs and zin not in gewone


def test_response_engine_sjabloon_zonder_brugse_versie_blijft_gewoon():
    engine = _engine(True)
    gewone = set(engine.templates["interruption_vraag"])
    for _ in range(20):
        assert engine._kies_variant("interruption_vraag") in gewone


def _groet(aan):
    bus = EventBus()
    bus.modules = getattr(bus, "modules", {})
    if aan is not None:
        bus.modules["brugs_filter"] = _filter(aan)
    ResponsePipeline(bus)
    basis = []
    bus.subscribe("pipeline_response", lambda d, *a, **k: basis.append(d.get("base_text")))
    bus.publish("intent_greeting", {"sender": "Kevin"})
    return basis[-1]


def test_groet_gewoon_als_modus_uit_of_ontbreekt():
    assert _groet(False) == "Hey Kevin, leuk dat je er bent"
    assert _groet(None) == "Hey Kevin, leuk dat je er bent"


def test_groet_brugs_als_modus_aan():
    verwacht = {z.format(sender="Kevin") for z in SJABLONEN["groet"]}
    for _ in range(20):
        assert _groet(True) in verwacht


# ---------------------------------------------------------------------------
# conversation_engine (stemming- en activiteitsopmerkingen)
# ---------------------------------------------------------------------------
from modules.chat.conversation_engine import ConversationEngine


class _NepBus:
    def __init__(self, modules):
        self.modules = modules

    def publish(self, *a, **k):
        pass

    def subscribe(self, *a, **k):
        pass


class _NepContext:
    def __init__(self, activiteit="coding", minuten=30):
        self.ctx = {"activity": activiteit, "activity_duration_minutes": minuten}

    def get_current(self):
        return self.ctx


class _NepPersoonlijkheid:
    def __init__(self, energie, overprikkeling):
        self.state = {"current_energy": energie, "overstimulation_level": overprikkeling}


def _conv(tmp_path, aan, **modules):
    mods = dict(modules)
    if aan is not None:
        mods["brugs_filter"] = _filter(aan)
    engine = ConversationEngine(_NepBus(mods), None)
    engine.state_pad = tmp_path / "state.json"   # nooit data/conversation_state.json raken
    engine.laatste_observatie_tijdstip = None
    return engine


def test_activiteit_observatie_gewoon_en_brugs(tmp_path):
    gewoon = ConversationEngine.ACTIVITEIT_AFSLUITINGEN
    brugs = SJABLONEN["activiteit_observatie_afsluiting"]
    for aan, toegestaan in ((False, gewoon), (None, gewoon), (True, brugs)):
        for _ in range(15):
            engine = _conv(tmp_path, aan, context_manager=_NepContext())
            tekst = engine.probeer_activiteit_observatie()
            assert tekst is not None
            assert any(tekst.endswith(z) for z in toegestaan)


def test_activiteit_observatie_brugs_zonder_duur_gebruikt_geen_duurzin(tmp_path):
    for _ in range(40):
        engine = _conv(tmp_path, True, context_manager=_NepContext(minuten=None))
        tekst = engine.probeer_activiteit_observatie()
        # zonder duur mag de {duur}-variant nooit gekozen worden (geen KeyError, geen "{")
        assert tekst is not None and "{" not in tekst
        assert not tekst.startswith("Pff… al ")


def test_mood_observatie_gewoon_en_brugs(tmp_path):
    persoon = _NepPersoonlijkheid(energie=0.9, overprikkeling=0.0)
    gewoon = ConversationEngine.MOOD_ENERGIEK_OPENINGEN
    brugs = SJABLONEN["mood_energiek_opening"]
    for aan, toegestaan in ((False, gewoon), (True, brugs)):
        for _ in range(15):
            engine = _conv(tmp_path, aan, personality=persoon)
            tekst = engine.probeer_mood_observatie()
            assert any(tekst.startswith(z) for z in toegestaan)


# ---------------------------------------------------------------------------
# wikipedia_teacher
# ---------------------------------------------------------------------------
from modules.knowledge.wikipedia_teacher import WikipediaTeacher


def _wiki(aan):
    mods = {}
    if aan is not None:
        mods["brugs_filter"] = _filter(aan)
    wt = WikipediaTeacher.__new__(WikipediaTeacher)   # geen netwerk/opslag in __init__ nodig
    wt.event_bus = _NepBus(mods)
    return wt


def test_wiki_zin_gewoon_als_modus_uit_of_ontbreekt():
    for aan in (False, None):
        assert _wiki(aan)._brugs_zin("wiki_zoeken", "gewoon", word="pijp") == "gewoon"


def test_wiki_zin_brugs_als_modus_aan_en_behoudt_het_teach_commando():
    wt = _wiki(True)
    toegestaan = {z.format(word="pijp") for z in SJABLONEN["wiki_niets_gevonden"]}
    for _ in range(20):
        zin = wt._brugs_zin("wiki_niets_gevonden", "gewoon", word="pijp")
        assert zin in toegestaan
        assert "teach pijp <betekenis>" in zin   # het commando moet blijven werken


def test_wiki_zin_onbekende_naam_valt_terug_op_gewoon():
    assert _wiki(True)._brugs_zin("bestaat_niet", "gewoon") == "gewoon"