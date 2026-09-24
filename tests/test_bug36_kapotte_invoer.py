# tests/test_bug36_kapotte_invoer.py
#
# Bug #36 (24 september 2026): tekst met een kapot teken (een "surrogaat"
# zoals \udcc3, typisch een terminal-encoding-hikje bij het typen)
# crashte de hele hoofdloop via wikipedia_teacher.py's _fetch_summary().
#
# De fix bestaat uit drie lagen, elk hier apart getest:
#   Laag 1 -- main.py's maak_invoer_veilig(): haalt kapotte tekens weg
#             meteen na input(), voor iets anders de tekst ziet.
#   Laag 2 -- wikipedia_teacher.py: de URL-opbouw staat nu BINNEN de
#             try, zodat een kapot woord gewoon "niet gevonden" geeft.
#   Laag 3 -- main.py's hoofdloop: een try/except-vangnet rond de
#             verwerking van elk bericht, zodat EEN fout in eender welke
#             module Nova niet meer volledig laat crashen.
#
# Geen internettoegang nodig: bij een kapot woord wordt de netwerk-
# aanroep nooit bereikt (dat wordt hieronder ook expliciet gecontroleerd).

import os
import sys
import builtins
import urllib.request

import pytest

# Projectroot (de map BOVEN tests/) op het importpad zetten, zodat
# "import main" en "from core... / modules..." werken, ongeacht
# vanuit welke map pytest gestart wordt.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import main as nova_main
from core.event_bus import EventBus
from modules.knowledge.wikipedia_teacher import WikipediaTeacher


# Het exacte kapotte teken uit de oorspronkelijke crash (nova_state.md,
# bug #36). "\udcc3" is de plaatshouder die Python gebruikt voor een
# losse byte 0xC3 -- de EERSTE helft van bv. een 'é' of 'ë', waarvan de
# tweede helft onderweg verloren ging.
KAPOT = "\udcc3"


# ---------------------------------------------------------------
# Laag 1 -- maak_invoer_veilig()
# ---------------------------------------------------------------

def test_originele_crashzin_wordt_schoongemaakt():
    zin = f"wat is er gebeurt op {KAPOT}9 september"
    assert nova_main.maak_invoer_veilig(zin) == "wat is er gebeurt op 9 september"


def test_resultaat_is_altijd_veilig_als_utf8():
    # De kern van de bug: zonder schoonmaak geeft dit een UnicodeEncodeError.
    schoon = nova_main.maak_invoer_veilig(f"test{KAPOT}woord")
    schoon.encode("utf-8")  # mag NIET crashen


def test_volledig_doorgekomen_teken_wordt_hersteld():
    # Kwamen BEIDE helften van 'é' (bytes C3 A9) als surrogaat door,
    # dan moet het echte teken terugkomen, niet weggegooid worden.
    assert nova_main.maak_invoer_veilig("caf\udcc3\udca9") == "café"


def test_gewone_tekst_blijft_exact_gelijk():
    for zin in ["wat is een gitaar", "café crème", "ik ben moe vandaag", "3+5", "9/11", ""]:
        assert nova_main.maak_invoer_veilig(zin) == zin


def test_surrogaat_dat_niet_van_het_inlezen_komt_wordt_weggelaten():
    # \ud800 valt buiten het bereik dat surrogateescape kan terugdraaien
    # -- moet via het except-pad gewoon weggelaten worden, niet crashen.
    assert nova_main.maak_invoer_veilig("a\ud800b") == "ab"


def test_geen_tekst_wordt_ongewijzigd_teruggegeven():
    assert nova_main.maak_invoer_veilig(None) is None


# ---------------------------------------------------------------
# Laag 2 -- wikipedia_teacher.py
# ---------------------------------------------------------------

@pytest.fixture
def teacher():
    return WikipediaTeacher(EventBus(), semantic_module=None)


@pytest.fixture
def netwerk_verklikker(monkeypatch):
    """Houdt bij of urlopen() ooit aangeroepen wordt (hoort NIET te gebeuren)."""
    aanroepen = []

    def nep_urlopen(*args, **kwargs):
        aanroepen.append(args)
        raise RuntimeError("geen netwerk in tests")

    monkeypatch.setattr(urllib.request, "urlopen", nep_urlopen)
    return aanroepen


def test_fetch_summary_crasht_niet_op_kapot_woord(teacher, netwerk_verklikker):
    # Voor de fix: UnicodeEncodeError op urllib.parse.quote().
    assert teacher._fetch_summary(f"test{KAPOT}") is None
    assert netwerk_verklikker == []  # faalt al vóór de netwerkstap


def test_links_api_crasht_niet_op_kapot_woord(teacher, netwerk_verklikker):
    # Zelfde probleem, andere plek: urllib.parse.urlencode().
    assert teacher._fetch_disambiguation_links_meerdere(f"test{KAPOT}") == []
    assert netwerk_verklikker == []


def test_on_wiki_met_kapot_woord_geeft_nette_melding(teacher, netwerk_verklikker):
    # End-to-end via het echte event: geen crash, wel een normale
    # "niet gevonden"-melding, net als bij elk ander onvindbaar woord.
    antwoorden = []
    teacher.event_bus.subscribe("chat_response", lambda data: antwoorden.append(data["text"]))

    teacher.on_wiki({"word": f"{KAPOT}9 september", "auto": False})

    assert any("niet vinden op Wikipedia" in a for a in antwoorden)


# ---------------------------------------------------------------
# Laag 3 -- vangnet in de hoofdloop van main.py
# ---------------------------------------------------------------

class _NepLoader:
    """
    Vervangt de echte ModuleLoader, zodat main() kan draaien zonder
    alle ~100 modules te laden. discover_and_load() hangt een bewust
    crashende handler aan "chat_message" -- dat bootst na wat er bij
    bug #36 gebeurde (een fout diep in een module, via bus.publish).
    """

    laatst_ontvangen = []

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.loaded_modules = {}

    def discover_and_load(self):
        def crashende_handler(data):
            _NepLoader.laatst_ontvangen.append(data["text"])
            if data["text"] == "crash":
                raise ValueError("bewust veroorzaakte testfout")

        self.event_bus.subscribe("chat_message", crashende_handler)


def _draai_main_met_invoer(monkeypatch, invoer_regels):
    _NepLoader.laatst_ontvangen = []
    monkeypatch.setattr(nova_main, "ModuleLoader", _NepLoader)
    regels = iter(invoer_regels)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(regels))
    nova_main.main()


def test_hoofdloop_overleeft_fout_in_een_module(monkeypatch, capsys):
    # Voor de fix: de ValueError zou uit main() ontsnappen en Nova stoppen.
    # Na de fix: fout getoond, en het VOLGENDE bericht komt nog gewoon aan.
    _draai_main_met_invoer(monkeypatch, ["crash", "hallo", "exit"])

    assert _NepLoader.laatst_ontvangen == ["crash", "hallo"]
    uitvoer = capsys.readouterr()
    assert "Onverwachte fout" in uitvoer.out
    assert "bewust veroorzaakte testfout" in uitvoer.err  # traceback blijft zichtbaar


def test_hoofdloop_maakt_invoer_schoon_voor_de_eventbus(monkeypatch):
    # De tekst die modules te zien krijgen, bevat geen kapot teken meer.
    _draai_main_met_invoer(monkeypatch, [f"wat is er gebeurt op {KAPOT}9 september", "exit"])

    assert _NepLoader.laatst_ontvangen == ["wat is er gebeurt op 9 september"]


def test_exit_werkt_ook_met_kapot_teken_erachter(monkeypatch):
    # "exit" + verdwaalde toetsaanslag moet Nova nog steeds stoppen.
    _draai_main_met_invoer(monkeypatch, [f"exit{KAPOT}"])
    assert _NepLoader.laatst_ontvangen == []