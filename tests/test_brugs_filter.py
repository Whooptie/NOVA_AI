# tests/test_brugs_filter.py
import random

import pytest

from modules.chat.brugs_filter import BrugsFilter


def _filter(aan=True):
    f = BrugsFilter(event_bus=None, bewaar=False)
    f.aan = aan
    # Geen toeval in de tests: openers/sloten uitzetten tenzij een test ze nodig heeft.
    f.regels["opener_kans"] = 0.0
    f.regels["slot_kans"] = 0.0
    return f


def test_standaard_uit_laat_tekst_ongemoeid():
    f = BrugsFilter(event_bus=None, bewaar=False)
    assert f.aan is False
    assert f.pas_toe("Dat is niet waar.") == "Dat is niet waar."


def test_woorden_worden_vervangen_met_hoofdletter_behoud():
    f = _filter()
    assert f.pas_toe("Dat is niet waar.") == "Da's nie woar."
    assert f.pas_toe("wat gaat dat snel") == "wa goat da rap"


def test_hele_woorden_enkel():
    f = _filter()
    # "jasje" begint met "ja" en "dagelijks" bevat "dag"-achtige delen: mogen niet geraakt worden
    assert f.pas_toe("Het jasje is mooi.") == "Het jasje is schoon."


def test_citaten_en_plaatshouders_blijven_staan():
    f = _filter()
    assert f.pas_toe("Ik ken 'niet waar' niet.") == "Ik ken 'niet waar' nie."
    assert f.pas_toe('Hij zei "dat is mooi" en dat was het.') == 'Hij zei "dat is mooi" en da was het.'
    assert f.pas_toe("zie https://voorbeeld.be/niet nu") == "zie https://voorbeeld.be/niet nu"


def test_apostrof_in_woord_telt_niet_als_citaat():
    f = _filter()
    assert f.pas_toe("da's niet erg, dat zeg ik") == "da's nie erg, da zeg ik"


def test_opener_en_kleine_letter_maar_namen_blijven():
    f = _filter()
    f.regels["opener_kans"] = 1.0
    f.regels["openers"] = ["Ewa,"]
    assert f.pas_toe("Dat klopt.") == "Ewa, da klopt."
    assert f.pas_toe("Kevin, dat klopt.") == "Ewa, Kevin, da klopt."


def test_kort_krijgt_geen_opener_of_slot():
    f = _filter()
    f.regels["opener_kans"] = 1.0
    f.regels["slot_kans"] = 1.0
    assert f.pas_toe("Dat klopt.", response_style="kort") == "Da klopt."


def test_slotwoord_enkel_bij_een_korte_zin():
    f = _filter()
    f.regels["slot_kans"] = 1.0
    f.regels["slotwoorden"] = [", zeg."]
    assert f.pas_toe("Dat klopt.") == "Da klopt, zeg."
    assert f.pas_toe("Eerste zin. Tweede zin.") == "Eerste zin. Tweede zin."
    assert f.pas_toe("Wacht..") == "Wacht.."


def test_kapot_of_ontbrekend_regelbestand_geeft_originele_tekst():
    f = BrugsFilter(event_bus=None, bewaar=False, regels_pad="/bestaat/niet.json")
    f.aan = True
    assert f.pas_toe("Dat is niet waar.") == "Dat is niet waar."


def test_modus_in_geheugen_aan_en_uit():
    f = BrugsFilter(event_bus=None, bewaar=False)
    f.zet_modus(True)
    assert f.aan is True
    f.zet_modus(False)
    assert f.aan is False

# ---------------------------------------------------------------------------
# Woordenboek: vaste voorbeelden + vangnet tegen slordige vervangingen
# ---------------------------------------------------------------------------
import json as _json

from modules.chat.brugs_filter import REGELS_PAD


@pytest.mark.parametrize("invoer,verwacht", [
    ("Ik zie jou en jouw hond.", "Ik zie u en uw hond."),
    ("Ik heb geen tijd, jullie wel.", "Ik heb gien tijd, gullie wel."),
    ("Daar gaan we naartoe.", "Doar goan we naartoe."),
    ("Ben je klaar? Het jaar is bijna om.", "Ben je kloar? Het joar is bijna om."),
    ("We praten altijd over iets.", "We proaten altied over iet."),
    ("Wat is dat? Dat is een kat.", "Wa's da? Da's een kat."),
    ("Laat maar, we laten het.", "Loat moar, we loaten het."),
])
def test_woordenboek_voorbeelden(invoer, verwacht):
    assert _filter().pas_toe(invoer) == verwacht


def test_woordenboek_is_netjes():
    woorden = _json.load(open(REGELS_PAD, encoding="utf-8"))["woorden"]
    for sleutel, nieuw in woorden.items():
        assert sleutel == sleutel.lower() and sleutel.strip() == sleutel
        assert nieuw == nieuw.lower() and nieuw.strip() == nieuw and nieuw
        assert sleutel != nieuw
        # een vervanging mag zelf geen nieuwe sleutel zijn (anders hangt de uitkomst van de volgorde af)
        assert nieuw not in woorden


def test_kies_geeft_gewone_lijst_als_modus_uit_staat():
    f = BrugsFilter(bewaar=False)
    f.aan = False
    assert f.kies(["gewoon"], "groet") == (["gewoon"], "groet")


def test_kies_geeft_brugse_lijst_en_eigen_naam():
    f = BrugsFilter(bewaar=False)
    f.aan = True
    lijst, naam = f.kies(["gewoon"], "groet")
    assert lijst != ["gewoon"]
    assert naam == "groet_brugs"


def test_kies_valt_terug_bij_onbekend_sjabloon():
    f = BrugsFilter(bewaar=False)
    f.aan = True
    assert f.kies(["gewoon"], "bestaat_niet") == (["gewoon"], "bestaat_niet")


def test_kies_valt_terug_als_varianten_faalt(monkeypatch):
    f = BrugsFilter(bewaar=False)
    f.aan = True

    def stuk(naam):
        raise RuntimeError("stuk")

    monkeypatch.setattr(f, "varianten", stuk)
    assert f.kies(["gewoon"], "groet") == (["gewoon"], "groet")


def test_kies_brugs_of_gewoon_zonder_module():
    from modules.response_learning.variant_kiezer import kies_brugs_of_gewoon

    class Bus:
        modules = {}

    assert kies_brugs_of_gewoon(Bus(), ["gewoon"], "groet") == (["gewoon"], "groet")


def test_kies_brugs_of_gewoon_met_nep_object_zonder_kies():
    from modules.response_learning.variant_kiezer import kies_brugs_of_gewoon

    class Bus:
        modules = {"brugs_filter": object()}

    assert kies_brugs_of_gewoon(Bus(), ["gewoon"], "groet") == (["gewoon"], "groet")