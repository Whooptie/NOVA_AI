# tests/test_last_context.py
"""
Test tegen de ECHTE LastContext (core/last_context.py) -- geen I/O in
__init__(), dus geen monkeypatch nodig, zelfde soort injecteerbaarheid
als PendingQuestion/IntentRouter/ChatModule (zie nova_state.md,
"Werkafspraak"-sectie).

time.time() wordt gemonkeypatcht via een kleine, lokale klok-helper
i.p.v. echte sleep()-aanroepen -- sneller en exact controleerbaar,
geen tijdgevoelige flakiness.
"""

import pytest
from core.last_context import LastContext


class NepKlok:
    """Kleine, lokale klok-helper: vervangt time.time() met een
    handmatig controleerbare waarde, zodat vervaltijden exact en
    zonder echte sleep() getest kunnen worden."""

    def __init__(self, start=1000.0):
        self.nu = start

    def __call__(self):
        return self.nu

    def verstrijk(self, seconden):
        self.nu += seconden


@pytest.fixture
def klok(monkeypatch):
    k = NepKlok()
    monkeypatch.setattr("core.last_context.time.time", k)
    return k


@pytest.fixture
def ctx():
    return LastContext()


# ------------------------------------------------------------
# set_concept() / get_concept() basisgedrag
# ------------------------------------------------------------

def test_leeg_bij_start(ctx):
    assert ctx.get_concept() is None
    assert ctx.get_antwoord_type() is None
    assert ctx.get_opties() is None
    assert ctx.is_geldig() is False


def test_set_concept_geeft_concept_terug(ctx, klok):
    ctx.set_concept("python")
    assert ctx.get_concept() == "python"
    assert ctx.is_geldig() is True


def test_set_concept_met_antwoord_type(ctx, klok):
    ctx.set_concept("python", antwoord_type="definitie_python")
    assert ctx.get_concept() == "python"
    assert ctx.get_antwoord_type() == "definitie_python"


def test_set_concept_leeg_string_doet_niets(ctx, klok):
    ctx.set_concept("")
    assert ctx.get_concept() is None
    assert ctx.is_geldig() is False


def test_set_concept_none_doet_niets(ctx, klok):
    ctx.set_concept(None)
    assert ctx.get_concept() is None


# ------------------------------------------------------------
# Veiligheidsklep: nieuw, expliciet concept overschrijft ALTIJD
# ------------------------------------------------------------

def test_nieuw_concept_overschrijft_oud_concept_onmiddellijk(ctx, klok):
    ctx.set_concept("python")
    # Nog ruim binnen de vervaltijd, maar een nieuw concept moet
    # ALTIJD overschrijven, ongeacht de klok (veiligheidsklep).
    klok.verstrijk(10)
    ctx.set_concept("java")
    assert ctx.get_concept() == "java"


def test_nieuw_concept_wist_oude_opties_lijst(ctx, klok):
    ctx.set_opties(["schaak", "dammen"])
    assert ctx.get_opties() == ["schaak", "dammen"]

    ctx.set_concept("python")
    # Een nieuw hoofdonderwerp betekent dat de oude keuzelijst niet
    # meer "het actuele" is om op te reageren.
    assert ctx.get_opties() is None
    assert ctx.get_concept() == "python"


def test_nieuw_concept_reset_ook_antwoord_type(ctx, klok):
    ctx.set_concept("python", antwoord_type="definitie_python")
    ctx.set_concept("java")
    assert ctx.get_antwoord_type() is None


# ------------------------------------------------------------
# set_opties() / get_opties()
# ------------------------------------------------------------

def test_set_opties_geeft_lijst_terug(ctx, klok):
    ctx.set_opties(["schaak", "dammen"])
    assert ctx.get_opties() == ["schaak", "dammen"]
    assert ctx.is_geldig() is True


def test_set_opties_laat_concept_ongewijzigd(ctx, klok):
    """Een opties-lijst kan naast een lopend gespreksonderwerp
    bestaan -- set_opties() mag het concept niet aanraken."""
    ctx.set_concept("python")
    ctx.set_opties(["schaak", "dammen"])
    assert ctx.get_concept() == "python"
    assert ctx.get_opties() == ["schaak", "dammen"]


def test_set_opties_kopieert_de_lijst(ctx, klok):
    """Interne state mag niet muteren als de aanroeper de originele
    lijst achteraf wijzigt."""
    origineel = ["schaak", "dammen"]
    ctx.set_opties(origineel)
    origineel.append("go")
    assert ctx.get_opties() == ["schaak", "dammen"]


def test_set_opties_leeg_doet_niets(ctx, klok):
    ctx.set_opties([])
    assert ctx.get_opties() is None


def test_set_opties_none_doet_niets(ctx, klok):
    ctx.set_opties(None)
    assert ctx.get_opties() is None


# ------------------------------------------------------------
# Vangnet: verval na VERVAL_SECONDEN
# ------------------------------------------------------------

def test_concept_verloopt_na_verval_seconden(ctx, klok):
    ctx.set_concept("python")
    klok.verstrijk(LastContext.VERVAL_SECONDEN + 1)
    assert ctx.get_concept() is None
    assert ctx.is_geldig() is False


def test_concept_blijft_geldig_net_onder_verval_seconden(ctx, klok):
    ctx.set_concept("python")
    klok.verstrijk(LastContext.VERVAL_SECONDEN - 1)
    assert ctx.get_concept() == "python"


def test_concept_verloopt_exact_op_de_grens(ctx, klok):
    """Grenswaarde-test: _is_verlopen() gebruikt '>', dus EXACT
    VERVAL_SECONDEN verstreken mag nog NET geldig zijn."""
    ctx.set_concept("python")
    klok.verstrijk(LastContext.VERVAL_SECONDEN)
    assert ctx.get_concept() == "python"


def test_opties_verlopen_ook_na_verval_seconden(ctx, klok):
    ctx.set_opties(["schaak", "dammen"])
    klok.verstrijk(LastContext.VERVAL_SECONDEN + 1)
    assert ctx.get_opties() is None


# ------------------------------------------------------------
# ververs_timestamp(): verlengt geldigheid ZONDER inhoud te wijzigen
# ------------------------------------------------------------

def test_ververs_timestamp_verlengt_geldigheid(ctx, klok):
    ctx.set_concept("python")
    klok.verstrijk(LastContext.VERVAL_SECONDEN - 10)
    # Nog net geldig -- een verwijzing werd hierop opgelost.
    assert ctx.get_concept() == "python"
    ctx.ververs_timestamp()

    # Zonder verversing zou dit nu verlopen zijn geweest.
    klok.verstrijk(LastContext.VERVAL_SECONDEN - 10)
    assert ctx.get_concept() == "python"


def test_ververs_timestamp_wijzigt_inhoud_niet(ctx, klok):
    """Kernpunt uit het ontwerp: een geslaagde referentie-resolutie
    mag de INHOUD niet vervangen, enkel de klok verlengen."""
    ctx.set_concept("python", antwoord_type="definitie_python")
    klok.verstrijk(50)
    ctx.ververs_timestamp()
    assert ctx.get_concept() == "python"
    assert ctx.get_antwoord_type() == "definitie_python"


def test_ververs_timestamp_op_lege_state_doet_niets(ctx, klok):
    """Randgeval: verversen zonder dat er ooit iets gezet is, mag
    niet alsnog 'geldig' maken uit het niets."""
    ctx.ververs_timestamp()
    assert ctx.get_concept() is None
    assert ctx.is_geldig() is False


def test_reeks_verwijzingen_valt_niet_stil_door_verversen(ctx, klok):
    """Simuleert 'die?' -> 'en dat?' -> 'ook die?' -- elke hit
    ververst de klok, dus het gesprek blijft geldig ondanks dat de
    TOTALE verstreken tijd de vervaltijd ruim overschrijdt."""
    ctx.set_concept("python")

    for _ in range(5):
        klok.verstrijk(LastContext.VERVAL_SECONDEN - 30)
        assert ctx.get_concept() == "python"
        ctx.ververs_timestamp()

    # Totale verstreken tijd is hier al ruim 5x VERVAL_SECONDEN,
    # maar het concept leeft nog dankzij de herhaalde verversing.
    assert ctx.get_concept() == "python"


def test_reeks_verwijzingen_stopt_wel_bij_echte_stilte(ctx, klok):
    """Tegenhanger van de vorige test: als er GEEN verversing meer
    gebeurt (Kevin stopt met vragen), moet het alsnog verlopen."""
    ctx.set_concept("python")
    klok.verstrijk(LastContext.VERVAL_SECONDEN - 30)
    ctx.ververs_timestamp()

    # Nu ECHT stilte, geen verdere verwijzingen meer.
    klok.verstrijk(LastContext.VERVAL_SECONDEN + 1)
    assert ctx.get_concept() is None


# ------------------------------------------------------------
# clear()
# ------------------------------------------------------------

def test_clear_wist_alles(ctx, klok):
    ctx.set_concept("python", antwoord_type="definitie_python")
    ctx.set_opties(["schaak", "dammen"])
    ctx.clear()
    assert ctx.get_concept() is None
    assert ctx.get_antwoord_type() is None
    assert ctx.get_opties() is None
    assert ctx.is_geldig() is False


# ------------------------------------------------------------
# init_module()
# ------------------------------------------------------------

def test_init_module_geeft_bruikbare_instance():
    from core.last_context import init_module
    instance = init_module()
    assert isinstance(instance, LastContext)
    assert instance.get_concept() is None


def test_init_module_accepteert_event_bus_param():
    from core.last_context import init_module
    nep_bus = object()
    instance = init_module(nep_bus)
    assert instance.event_bus is nep_bus