# tests/test_brugs_filter.py
import random

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
    assert f.pas_toe("Dat is niet waar.") == "Da is nie woar."
    assert f.pas_toe("wat gaat dat snel") == "wa goat da rap"


def test_hele_woorden_enkel():
    f = _filter()
    # "jaar" bevat "ja", "natuurlijk" bevat "nu"-achtige delen: mogen niet geraakt worden
    assert f.pas_toe("Het jaar is mooi.") == "Het jaar is schoon."


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