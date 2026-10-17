"""Tests voor Semantic Fase 11.1 (knowledge_extractor)."""
import json
from pathlib import Path

import pytest

spacy = pytest.importorskip("spacy")
try:
    spacy.load("nl_core_news_sm", disable=["ner"])
except OSError:
    pytest.skip("model nl_core_news_sm ontbreekt", allow_module_level=True)

from modules.knowledge.knowledge_extractor import (
    KnowledgeExtractor, verwijder_haakjes, init_module)

REGELS = Path(__file__).resolve().parents[1] / "data" / "extractie_regels.json"


@pytest.fixture(scope="module")
def ex():
    return KnowledgeExtractor(regels_pad=REGELS)


def feiten(ex, tekst, zoek=None):
    return {(f["onderwerp"], f["relatie"], f["doel"])
            for f in ex.extract_from_text(tekst, zoek)}


def test_is_a_enkel(ex):
    assert ("gitaar", "is_a", "snaarinstrument") in feiten(
        ex, "Een gitaar is een snaarinstrument.", "gitaar")


def test_is_a_meerdere_doelen(ex):
    f = feiten(ex, "Een gitaar is een snaarinstrument en een muziekinstrument.", "gitaar")
    assert ("gitaar", "is_a", "snaarinstrument") in f
    assert ("gitaar", "is_a", "muziekinstrument") in f


def test_soort_vaartuig(ex):
    assert ("zeilboot", "is_a", "vaartuig") in feiten(
        ex, "Een zeilboot is een soort vaartuig.", "zeilboot")


def test_has_part(ex):
    f = feiten(ex, "Een fiets bestaat uit een frame, twee wielen en een stuur.", "fiets")
    assert {("fiets", "has_part", d) for d in ("frame", "wielen", "stuur")} <= f


def test_water_zuurstofatoom_niet(ex):
    t = "Water is een verbinding van twee waterstofatomen en een zuurstofatoom."
    assert ("water", "is_a", "zuurstofatoom") not in feiten(ex, t, "water")


def test_hond_de_eerste_zin(ex):
    # "ondersoort" staat sinds 17 oktober 2026 bij de vage woorden
    # (data/extractie_regels.json): "hond is een ondersoort" is geen
    # bruikbaar voorstel. Het echte doel is "wolf", maar dat vraagt een
    # eigen regel ("ondersoort van X") -- gepland voor Fase 11, deel 2B.
    t = "De hond is de gedomesticeerde ondersoort van de wolf."
    assert ("hond", "is_a", "ondersoort") not in feiten(ex, t, "hond")


def test_de_niet_in_tweede_zin(ex):
    t = "Een hond is een dier. De hond is de beste vriend van de mens."
    f = feiten(ex, t, "hond")
    assert ("hond", "is_a", "dier") in f
    assert ("hond", "is_a", "vriend") not in f


def test_voorbehoud_meestal(ex):
    assert feiten(ex, "Een kat is meestal een huisdier.", "kat") == set()


def test_ontkenning(ex):
    assert feiten(ex, "Een hond is niet altijd een huisdier.", "hond") == set()


def test_voorbehoud_in_bijzin_mag(ex):
    t = "Een fiets is een voertuig dat doorgaans met spierkracht wordt aangedreven."
    assert ("fiets", "is_a", "voertuig") in feiten(ex, t, "fiets")


def test_voornaamwoord_onderwerp(ex):
    assert feiten(ex, "Het is een dier dat blaft.") == set()


def test_verleden_tijd(ex):
    assert feiten(ex, "De hond was het eerste dier dat werd gedomesticeerd.", "hond") == set()


def test_in_opkomst(ex):
    t = "In het begin van de 21e eeuw is de elektrische fiets in opkomst."
    assert feiten(ex, t, "fiets") == set()


def test_voorbeeld_vaag(ex):
    assert feiten(ex, "Een geleidehond is een voorbeeld van een assistentiehond.", "geleidehond") == set()


def test_onderwerp_gelijk_aan_doel(ex):
    assert feiten(ex, "Een hond is een hond.", "hond") == set()


def test_onderwerp_moet_zoekwoord_bevatten(ex):
    assert feiten(ex, "Een gitaar is een snaarinstrument.", "piano") == set()


def test_haakjes():
    assert verwijder_haakjes("De hond (Canis (lupus)) is een dier.") == "De hond is een dier."


def test_haakjes_in_zin(ex):
    t = "Een gitaar (van het Grieks kithara) is een snaarinstrument."
    assert ("gitaar", "is_a", "snaarinstrument") in feiten(ex, t, "gitaar")


def test_doorverwijspagina(ex):
    assert feiten(ex, "Mercurius kan verwijzen naar: een planeet is een hemellichaam.") == set()


def test_leeg(ex):
    assert ex.extract_from_text("", "x") == []
    assert ex.extract_from_text("   ", "x") == []


def test_geen_duplicaten(ex):
    t = "Een gitaar is een snaarinstrument. Een gitaar is een snaarinstrument."
    assert len(ex.extract_from_text(t, "gitaar")) == 1


def test_regels_ontbreken(tmp_path):
    e = KnowledgeExtractor(regels_pad=tmp_path / "bestaat_niet.json")
    assert not e.is_beschikbaar()
    assert e.extract_from_text("Een gitaar is een snaarinstrument.", "gitaar") == []


def test_regels_corrupt(tmp_path):
    p = tmp_path / "kapot.json"
    p.write_text("{ dit is geen json", encoding="utf-8")
    e = KnowledgeExtractor(regels_pad=p)
    assert not e.is_beschikbaar()
    assert e.extract_from_text("Een gitaar is een snaarinstrument.", "gitaar") == []


def test_regels_sleutel_mist(tmp_path):
    p = tmp_path / "onvolledig.json"
    p.write_text(json.dumps({"voorbehoud": []}), encoding="utf-8")
    e = KnowledgeExtractor(regels_pad=p)
    assert not e.is_beschikbaar()


def test_init_module():
    class Bus:
        def __init__(self): self.geregistreerd = {}
        def register_module(self, naam, inst): self.geregistreerd[naam] = inst
    bus = Bus()
    inst = init_module(bus)
    assert bus.geregistreerd["knowledge_extractor"] is inst

    
# ---- Fase 11, optie B: samenstellingen als "basisfiets" ----
def test_basisfiets_wordt_fiets(ex):
    t = "Een basisfiets bestaat uit een frame, twee wielen en een stuur."
    f = feiten(ex, t, "fiets")
    assert ("fiets", "has_part", "frame") in f
    assert not any(o == "basisfiets" for o, _, _ in f)


def test_basisfiets_is_a(ex):
    f = feiten(ex, "Een basisfiets is een voertuig.", "fiets")
    assert ("fiets", "is_a", "voertuig") in f


def test_tandwiel_blijft_tandwiel(ex):
    # geen bekend voorvoegsel: dit is iets anders dan 'wiel'
    f = feiten(ex, "Een tandwiel is een mechanisch onderdeel.", "wiel")
    assert not any(o == "wiel" for o, _, _ in f)


def test_racefiets_blijft_racefiets(ex):
    f = feiten(ex, "Een racefiets is een voertuig.", "fiets")
    assert ("racefiets", "is_a", "voertuig") in f
    assert not any(o == "fiets" for o, _, _ in f)


def test_basisfiets_is_een_fiets_wordt_niet_zichzelf(ex):
    f = feiten(ex, "Een basisfiets is een fiets zonder extra's.", "fiets")
    assert ("fiets", "is_a", "fiets") not in f


def test_voorvoegsels_zijn_aanpasbaar(tmp_path):
    p = tmp_path / "regels.json"
    d = json.loads(REGELS.read_text(encoding="utf-8"))
    d["samenstelling_voorvoegsels"] = ["race"]
    p.write_text(json.dumps(d), encoding="utf-8")
    e2 = KnowledgeExtractor(regels_pad=p)
    f = {(x["onderwerp"], x["relatie"], x["doel"])
         for x in e2.extract_from_text("Een racefiets is een voertuig.", "fiets")}
    assert ("fiets", "is_a", "voertuig") in f


def test_regelbestand_zonder_voorvoegsels_werkt_nog(tmp_path):
    p = tmp_path / "regels.json"
    d = json.loads(REGELS.read_text(encoding="utf-8"))
    d.pop("samenstelling_voorvoegsels", None)
    p.write_text(json.dumps(d), encoding="utf-8")
    e2 = KnowledgeExtractor(regels_pad=p)
    assert e2.is_beschikbaar()
    assert "basis" in e2.samenstelling_voorvoegsels
    

# ---- Fase 11, deel 2B: ondersoort van / part_of / causes ----
def test_ondersoort_van_geeft_is_a(ex):
    t = "De hond is de gedomesticeerde ondersoort van de wolf."
    assert ("hond", "is_a", "wolf") in feiten(ex, t, "hond")


def test_ondersoort_vraagt_een_in_latere_zin(ex):
    t = "Een hond is een dier. De bengaal is de ondersoort van de tijger."
    assert ("bengaal", "is_a", "tijger") not in feiten(ex, t, "bengaal")


def test_soort_van(ex):
    f = feiten(ex, "Een zeilboot is een soort van vaartuig.", "zeilboot")
    assert ("zeilboot", "is_a", "vaartuig") in f


def test_part_of_onderdeel_van(ex):
    f = feiten(ex, "Het stuur is een onderdeel van de fiets.", "fiets")
    assert ("stuur", "part_of", "fiets") in f


def test_part_of_deel_van_met_zoekwoord_als_deel(ex):
    f = feiten(ex, "Een wiel is een onderdeel van een fiets.", "wiel")
    assert ("wiel", "part_of", "fiets") in f


def test_part_of_maakt_deel_uit_van(ex):
    f = feiten(ex, "De trapas maakt deel uit van de aandrijving van een fiets.", "trapas")
    assert ("trapas", "part_of", "aandrijving") in f


def test_part_of_zonder_zoekwoord_in_zin_niet(ex):
    f = feiten(ex, "Het stuur is een onderdeel van de fiets.", "gitaar")
    assert f == set()


def test_part_of_zonder_een_niet(ex):
    f = feiten(ex, "De wielen zijn onderdelen van de fiets.", "fiets")
    assert not any(r == "part_of" for _, r, _ in f)


def test_causes_veroorzaakt(ex):
    f = feiten(ex, "Regen veroorzaakt overstromingen.", "regen")
    assert ("regen", "causes", "overstromingen") in f


def test_causes_meerdere_gevolgen(ex):
    f = feiten(ex, "Een vulkaanuitbarsting veroorzaakt aswolken en lavastromen.",
               "vulkaanuitbarsting")
    assert ("vulkaanuitbarsting", "causes", "aswolken") in f
    assert ("vulkaanuitbarsting", "causes", "lavastromen") in f


def test_causes_leidt_tot(ex):
    f = feiten(ex, "Droogte leidt tot misoogsten.", "droogte")
    assert ("droogte", "causes", "misoogsten") in f


def test_causes_passief_en_voltooid_niet(ex):
    assert feiten(ex, "Overstromingen worden veroorzaakt door regen.", "regen") == set()
    assert feiten(ex, "Regen heeft overstromingen veroorzaakt.", "regen") == set()


def test_causes_voorbehoud_niet(ex):
    assert feiten(ex, "Een aardbeving kan een tsunami veroorzaken.", "aardbeving") == set()
    assert feiten(ex, "Regen veroorzaakt soms overstromingen.", "regen") == set()


def test_causes_bijzin_met_voorzetsel_geeft_geen_extra_gevolg(ex):
    f = feiten(ex, "Een zware storm veroorzaakt schade aan gebouwen.", "storm")
    assert ("storm", "causes", "schade") in f
    assert ("storm", "causes", "gebouwen") not in f


def test_causes_zoekwoord_moet_voorkomen(ex):
    assert feiten(ex, "Een orkaan veroorzaakt veel schade.", "fiets") == set()
    

# ---- Echte Wikipedia-zinnen (inleidingen opgehaald op 17 oktober 2026) ----
def test_echt_overstroming_gebeurtenis(ex):
    t = ("Een overstroming is een gebeurtenis waarbij een aanzienlijke hoeveelheid "
         "water uit een meer, rivier of zee plaatsen bereikt die normaal gesproken "
         "niet onder water staan. Overstromingen kunnen voor de natuur en de "
         "landbouw ook positieve effecten hebben.")
    assert ("overstroming", "is_a", "gebeurtenis") in feiten(ex, t, "overstroming")


def test_echt_droogte_periode(ex):
    t = "Droogte is een langere periode waarin geen neerslag valt."
    assert ("droogte", "is_a", "periode") in feiten(ex, t, "droogte")


def test_echt_stuur_middel_is_te_vaag(ex):
    t = "Een stuur is een middel om een voertuig te navigeren over de weg."
    assert ("stuur", "is_a", "middel") not in feiten(ex, t, "stuur")


def test_echt_aardbeving_voorbehoud_blokkeert_causes(ex):
    t = ("Een zeebeving kan een vloedgolf of tsunami veroorzaken, maar dat is niet "
         "altijd het geval. Zware aardbevingen en tsunami's veroorzaken vaak veel "
         "slachtoffers en grote schade.")
    assert feiten(ex, t, "aardbeving") == set()


def test_echt_wiskundetekens_in_tekst_geven_geen_rommel(ex):
    t = ("De zwaarste aardbeving ooit gemeten was de aardbeving van Valdivia in "
         "Chili in 1960 (9,5\n  \n    M\n      w\n    {\\displaystyle M_{\\mathrm {w} }}\n  \n).")
    assert feiten(ex, t, "aardbeving") == set()

# ---- Fase 11.4: "X is een vorm van Y" ----
def test_vorm_van_geeft_is_a(ex):
    t = "Regen is een vorm van neerslag die ontstaat wanneer waterdamp condenseert."
    assert ("regen", "is_a", "neerslag") in feiten(ex, t, "regen")


def test_vorm_zonder_van_is_geen_feit(ex):
    assert feiten(ex, "Een cirkel is een vorm.", "cirkel") == set()