# tests/test_uitleg_kracht.py
"""
Uitleg voor kracht(), energie_kinetisch(), energie_potentieel() en arbeid()
(15 november 2026). Vroeger gaf "leg uit kracht" niets terug, want er stond geen
tekst voor in modules/math/math_uitleg.py. Elke functie heeft een eigen, korte tekst.
"""
import pytest

from core.event_bus import EventBus
from core.intent_router import IntentRouter
from modules.math import math_uitleg as u
from modules.math.math import MathModule

FUNCTIES = ["kracht", "energie_kinetisch", "energie_potentieel", "arbeid"]

NAMEN = [
    ("kracht", "kracht"), ("Kracht", "kracht"), ("newtons tweede wet", "kracht"),
    ("tweede wet van newton", "kracht"),
    ("energie_kinetisch", "energie_kinetisch"), ("kinetische energie", "energie_kinetisch"),
    ("energie kinetisch", "energie_kinetisch"), ("bewegingsenergie", "energie_kinetisch"),
    ("energie_potentieel", "energie_potentieel"), ("potentiële energie", "energie_potentieel"),
    ("potentiele energie", "energie_potentieel"), ("energie potentieel", "energie_potentieel"),
    ("zwaarte-energie", "energie_potentieel"),
    ("arbeid", "arbeid"), ("  ARBEID  ", "arbeid"),
]


@pytest.mark.parametrize("naam,sleutel", NAMEN)
def test_elke_naam_geeft_de_uitleg_van_zijn_eigen_functie(naam, sleutel):
    assert u.canonieke_naam(naam) == sleutel
    assert u.get_uitleg(naam) == u.UITLEG_TEKSTEN[sleutel]


@pytest.mark.parametrize("functie", FUNCTIES)
def test_sleutel_staat_in_de_lijsten(functie):
    assert functie in u.beschikbare_functies()
    assert u.weergavenaam(functie) == functie


def test_er_is_geen_gecombineerde_tekst_meer():
    assert "kracht_energie_arbeid" not in u.UITLEG_TEKSTEN
    assert u.get_uitleg("kracht en energie") is None


@pytest.mark.parametrize("functie", FUNCTIES)
def test_elke_tekst_gaat_over_een_functie_en_blijft_kort(functie):
    tekst = u.get_uitleg(functie)
    assert tekst.startswith("⚙️")
    assert f"{functie}(" in tekst
    assert "Doorgerekend voorbeeld" in tekst
    assert len(tekst.splitlines()) <= 30


def test_de_vier_teksten_zijn_verschillend():
    teksten = {u.get_uitleg(f) for f in FUNCTIES}
    assert len(teksten) == 4


# De getallen in de uitleg moeten kloppen met wat math.py echt uitrekent.
@pytest.mark.parametrize("functie,uitdrukking,uitkomst,in_tekst", [
    ("kracht", "kracht(1000, 3)", "3000 N", "= 1000 × 3 = 3000 N"),
    ("kracht", "kracht(70, 9.81)", "686.7 N", "= 70 × 9,81 = 686,7 N"),
    ("energie_kinetisch", "energie_kinetisch(5, 10)", "250.0 J", "= 250 J"),
    ("energie_kinetisch", "energie_kinetisch(5, 20)", "1000.0 J", "= 1000 J"),
    ("energie_potentieel", "energie_potentieel(2, 10)", "196.2 J", "= 196,2 J"),
    ("energie_potentieel", "energie_potentieel(2, 10, 1.62)", "32.4 J", "= 32,4 J"),
    ("arbeid", "arbeid(50, 3)", "150 J", "= 150 J"),
    ("arbeid", "arbeid(3000, 20)", "60000 J", "= 60000 J"),
    ("arbeid", "kracht(1000, 3)", "3000 N", "kracht(1000, 3) = 3000 N"),
])
def test_voorbeelden_kloppen_met_math(functie, uitdrukking, uitkomst, in_tekst):
    assert str(MathModule(EventBus()).eval_expr(uitdrukking)) == uitkomst
    assert in_tekst in u.get_uitleg(functie)


def test_de_waarschuwingen_in_de_tekst_kloppen():
    wiskunde = MathModule(EventBus())
    for uitdrukking in ("kracht(0, 3)", "energie_kinetisch(0, 3)", "energie_potentieel(0, 3)"):
        with pytest.raises(ValueError, match="massa moet groter zijn dan 0"):
            wiskunde.eval_expr(uitdrukking)
    with pytest.raises(ValueError):
        wiskunde.eval_expr("arbeid(kracht(1000, 3), 20)")


@pytest.fixture
def router():
    bus = EventBus()
    bus.modules = {"math_uitleg": u.MathUitlegModule(bus)}
    antwoorden = []
    bus.subscribe("layer4_response", lambda d, *a, **k: antwoorden.append(d["text"]))
    return IntentRouter(bus), antwoorden


@pytest.mark.parametrize("zin,sleutel", [
    ("leg uit kracht", "kracht"), ("Leg uit Kracht", "kracht"), ("leg uit kracht?", "kracht"),
    ("leg me uit arbeid", "arbeid"),
    ("kan je uitleggen kinetische energie", "energie_kinetisch"),
    ("hoe werkt potentiële energie", "energie_potentieel"),
])
def test_router_geeft_alleen_de_gevraagde_uitleg(router, zin, sleutel):
    r, antwoorden = router
    assert r.detect_uitleg(zin) is True
    assert antwoorden == [u.UITLEG_TEKSTEN[sleutel]]
    assert r._laatste_uitleg_naam == sleutel


def test_router_laat_onbekende_namen_door(router):
    r, antwoorden = router
    assert r.detect_uitleg("leg uit zwaartekracht") is False
    assert antwoorden == []


def test_bestaande_uitleg_blijft_werken(router):
    r, antwoorden = router
    assert r.detect_uitleg("leg uit newton") is True
    assert antwoorden == [u.UITLEG_TEKSTEN["newton"]]