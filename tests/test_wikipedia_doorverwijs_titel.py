# tests/test_wikipedia_doorverwijs_titel.py -- Semantic Fase 11.4:
# _extract_first_disambiguation_target mag het opgezochte woord zelf nooit
# als "alternatief" teruggeven (dat is de doorverwijspagina)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.knowledge.wikipedia_teacher import WikipediaTeacher


class FakeBus:
    def __init__(self):
        self.modules = {}

    def subscribe(self, e, f):
        pass

    def publish(self, e, d=None):
        pass


def maak():
    t = WikipediaTeacher(FakeBus(), None)
    t._fetch_summary = lambda w: None   # geen netwerk voor de suffix-vangnetten
    return t


# Echte uitvoer van 'wiki debug regen' (17 oktober 2026)
REGEN = ("Regen kan verwijzen naar:Regen (neerslag)\nLandkreis Regen, een Landkreis in Duitsland\n"
         "Regen (stad), een plaats in bovenstaand district\n"
         "Regen (rivier), een rivier in bovenstaand district\n"
         "Regen (film), een documentairefilm van Joris Ivens uit 1929")


def test_regen_geeft_de_titel_met_kwalificatie():
    assert maak()._extract_first_disambiguation_target(REGEN, "regen") == "Regen (neerslag)"


def test_woord_zelf_is_nooit_het_alternatief():
    tekst = "Regen kan verwijzen naar:\nRegen, een single van Lil' Kleine uit 2021"
    assert maak()._extract_first_disambiguation_target(tekst, "regen") is None


def test_titel_van_een_ander_woord_wordt_niet_blind_overgenomen():
    tekst = "Bank kan verwijzen naar:\nZitbank (meubel)"
    # geen titel van HETZELFDE woord -> oude logica blijft gelden
    assert maak()._extract_first_disambiguation_target(tekst, "bank") == "Zitbank"


def test_bestaande_logica_blijft_werken_fysica():
    tekst = ("Fysica kan verwijzen naar:natuurkunde\neen fysica, een leerboek "
             "over de fysica\nFysica, een tijdschrift")
    assert maak()._extract_first_disambiguation_target(tekst, "fysica") == "natuurkunde"