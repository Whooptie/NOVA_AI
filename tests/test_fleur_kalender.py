"""Tests voor modules/time/fleur_kalender.py (privé-logboek van Kevin en Fleur).

Alles met een nep-bus, een nep-klok en een tijdelijk bestand in tmp_path:
er wordt niets van de echte data/ aangeraakt.
Uitvoeren: pytest tests/test_fleur_kalender.py -v
"""

import json
from datetime import date, datetime, timedelta

import pytest

from modules.time import cyclus as c
from modules.time import fleur_kalender as fk


class NepBus:
    def __init__(self):
        self.gepubliceerd, self.modules = [], {}

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data or {}))

    def antwoorden(self):
        return [d["text"] for n, d in self.gepubliceerd if n == "chat_response"]


class Klok:
    def __init__(self, nu):
        self.nu = nu

    def __call__(self):
        return self.nu


@pytest.fixture
def opstelling(tmp_path):
    bus = NepBus()
    klok = Klok(datetime(2026, 11, 28, 13, 55))     # zaterdag
    pad = tmp_path / "fleur_kalender.json"
    module = fk.FleurKalender(bus, pad=str(pad), klok=klok)
    bus.modules["fleur_kalender"] = module
    return module, bus, klok, pad


def zeg(opstelling, zin):
    module, bus, _, _ = opstelling
    voor = len(bus.antwoorden())
    afgehandeld = module.verwerk_zin(zin)
    nieuw = bus.antwoorden()[voor:]
    return afgehandeld, (nieuw[-1] if nieuw else None)


def laatste_item(module):
    return module.status["items"][-1]


# ----------------------------------------------------------------------
# noteren: soort, wie begon, datum en uur
# ----------------------------------------------------------------------
def test_knuffelen_ik_begon_met_datum_en_uur_van_nu(opstelling):
    module = opstelling[0]
    afgehandeld, antw = zeg(opstelling, "fleur knuffelen ik begon")
    assert afgehandeld and "Genoteerd: knuffelen" in antw and "za 28 nov om 13:55" in antw
    assert "jij begon" in antw
    assert laatste_item(module) == {"datum": "2026-11-28", "tijd": "13:55", "soort": "knuffelen",
                                    "begon": "kevin", "afloop": "gedaan", "wilde_niet": None}


@pytest.mark.parametrize("zin, soort", [
    ("fleur poepie", "poepie"), ("fleur rug", "rug"), ("fleur tetjes", "tetjes"),
    ("fleur seks", "seks"), ("fleur knuffelen", "knuffelen"),
])
def test_alle_soorten_zonder_extra(opstelling, zin, soort):
    module = opstelling[0]
    assert zeg(opstelling, zin)[0]
    item = laatste_item(module)
    assert item["soort"] == soort and item["begon"] == "onbekend" and item["afloop"] == "gedaan"
    assert item["tijd"] == "13:55"


@pytest.mark.parametrize("zin, wie", [
    ("fleur rug zij begon", "fleur"), ("fleur rug ze begon", "fleur"),
    ("fleur rug fleur begon", "fleur"), ("fleur rug ik begon", "kevin"),
    ("fleur rug ik was begonnen", "kevin"), ("fleur rug begon ik", "kevin"),
    ("fleur rug samen", "samen"), ("fleur rug allebei", "samen"),
])
def test_wie_begon(opstelling, zin, wie):
    assert zeg(opstelling, zin)[0]
    assert laatste_item(opstelling[0])["begon"] == wie


def test_synoniemen(opstelling):
    zeg(opstelling, "fleur knuffel")
    assert laatste_item(opstelling[0])["soort"] == "knuffelen"
    zeg(opstelling, "fleur tetje ik begon")
    assert laatste_item(opstelling[0])["soort"] == "tetjes"


def test_datum_zonder_uur_laat_uur_leeg(opstelling):
    zeg(opstelling, "fleur seks gisteren")
    item = laatste_item(opstelling[0])
    assert item["datum"] == "2026-11-27" and item["tijd"] is None


def test_uur_zonder_datum_is_vandaag(opstelling):
    zeg(opstelling, "fleur seks om 21:30")
    item = laatste_item(opstelling[0])
    assert item["datum"] == "2026-11-28" and item["tijd"] == "21:30"


@pytest.mark.parametrize("zin, tijd", [
    ("fleur seks om 9u", "09:00"), ("fleur seks om 21u30", "21:30"),
    ("fleur seks om 22.15", "22:15"), ("fleur seks om 8 uur", "08:00"),
    ("fleur seks om 23:05", "23:05"),
])
def test_uur_formaten(opstelling, zin, tijd):
    zeg(opstelling, zin)
    assert laatste_item(opstelling[0])["tijd"] == tijd


def test_datum_en_uur_samen(opstelling):
    zeg(opstelling, "fleur tetjes op 12 november om 21:30 ik begon")
    item = laatste_item(opstelling[0])
    assert (item["datum"], item["tijd"], item["begon"]) == ("2026-11-12", "21:30", "kevin")


def test_drie_dagen_geleden(opstelling):
    zeg(opstelling, "fleur rug 3 dagen geleden")
    assert laatste_item(opstelling[0])["datum"] == "2026-11-25"


def test_onleesbare_of_toekomstige_datum_wordt_niet_opgeslagen(opstelling):
    afgehandeld, antw = zeg(opstelling, "fleur seks op 15 december 2026")
    assert afgehandeld and "kon ik niet lezen" in antw
    assert opstelling[0].status["items"] == []


# ----------------------------------------------------------------------
# wilde niet / niet doorgegaan
# ----------------------------------------------------------------------
def test_ik_probeerde_zij_wilde_niet(opstelling):
    afgehandeld, antw = zeg(opstelling, "fleur seks ik probeerde maar ze wilde niet")
    item = laatste_item(opstelling[0])
    assert item["afloop"] == "niet doorgegaan" and item["begon"] == "kevin" and item["wilde_niet"] == "fleur"
    assert "niet doorgegaan" in antw and "jij probeerde" in antw and "Fleur wilde niet" in antw


def test_zij_probeerde_ik_wilde_niet(opstelling):
    zeg(opstelling, "fleur seks zij probeerde maar ik wilde niet")
    item = laatste_item(opstelling[0])
    assert item["begon"] == "fleur" and item["wilde_niet"] == "kevin" and item["afloop"] == "niet doorgegaan"


def test_wilde_niet_zonder_onderwerp_is_de_ander(opstelling):
    zeg(opstelling, "fleur seks ik begon wilde niet")
    item = laatste_item(opstelling[0])
    assert item["wilde_niet"] == "fleur"


def test_niet_doorgegaan_zonder_details(opstelling):
    zeg(opstelling, "fleur seks niet doorgegaan")
    item = laatste_item(opstelling[0])
    assert item["afloop"] == "niet doorgegaan" and item["begon"] == "onbekend" and item["wilde_niet"] is None


# ----------------------------------------------------------------------
# tellertjes bij het noteren
# ----------------------------------------------------------------------
def test_teller_in_het_antwoord(opstelling):
    zeg(opstelling, "fleur knuffelen")
    zeg(opstelling, "fleur knuffelen")
    _, antw = zeg(opstelling, "fleur knuffelen gisteren")
    assert "Knuffelen: 3x in november, 3x in totaal" in antw


def test_teller_verschilt_per_maand(opstelling):
    zeg(opstelling, "fleur seks op 3 oktober")
    _, antw = zeg(opstelling, "fleur seks")
    assert "1x in november, 2x in totaal" in antw


def test_niet_doorgegaan_telt_apart(opstelling):
    zeg(opstelling, "fleur seks")
    _, antw = zeg(opstelling, "fleur seks ik probeerde maar ze wilde niet")
    assert "Niet doorgegaan: 1x in november" in antw


# ----------------------------------------------------------------------
# onbekend woord: vragen, bevestigen, leren
# ----------------------------------------------------------------------
def test_onbekend_woord_vraagt_en_bewaart_nog_niets(opstelling):
    module = opstelling[0]
    afgehandeld, antw = zeg(opstelling, "fleur massage ik begon")
    assert afgehandeld and "'massage' ken ik nog niet" in antw
    assert module.status["items"] == [] and "massage" not in module.status["soorten"]


def test_ja_voegt_soort_toe_en_noteert(opstelling):
    module = opstelling[0]
    zeg(opstelling, "fleur massage ik begon")
    _, antw = zeg(opstelling, "ja")
    assert "Nieuwe soort toegevoegd: massage" in antw and "Genoteerd: massage" in antw
    assert "massage" in module.status["soorten"]
    assert laatste_item(module)["soort"] == "massage" and laatste_item(module)["begon"] == "kevin"


def test_nee_bewaart_niets(opstelling):
    module = opstelling[0]
    zeg(opstelling, "fleur massage")
    _, antw = zeg(opstelling, "nee")
    assert "niets" in antw and module.status["items"] == [] and "massage" not in module.status["soorten"]


def test_naam_van_bestaande_soort_wordt_bijnaam(opstelling):
    module = opstelling[0]
    zeg(opstelling, "fleur kusjes")
    _, antw = zeg(opstelling, "knuffelen")
    assert "andere naam voor knuffelen" in antw
    assert "kusjes" in module.status["soorten"]["knuffelen"]
    zeg(opstelling, "fleur kusjes ik begon")
    assert laatste_item(module)["soort"] == "knuffelen"


def test_ja_zonder_openstaande_vraag_doet_niets(opstelling):
    afgehandeld, _ = zeg(opstelling, "ja")
    assert afgehandeld is False and opstelling[0].status["items"] == []


def test_vraag_vervalt_na_vijf_minuten(opstelling):
    module, bus, klok, pad = opstelling
    zeg(opstelling, "fleur massage")
    klok.nu += timedelta(minutes=6)
    assert module.verwerk_zin("ja") is False
    assert module.status["items"] == []


def test_vraag_vervalt_bij_een_ander_bericht(opstelling):
    module = opstelling[0]
    zeg(opstelling, "fleur massage")
    assert module.verwerk_zin("hoe laat is het") is False
    assert module.verwerk_zin("ja") is False
    assert module.status["items"] == []


@pytest.mark.parametrize("zin", [
    "fleur is lief", "fleur", "wat is seks", "hoe laat is het", "fleur wat denk je?",
    "ik hou van fleur", "fleur is vandaag mooi", "knuffelen", "", "fleur kalender2",
])
def test_vreemde_zinnen_worden_niet_opgepakt(opstelling, zin):
    assert opstelling[0].verwerk_zin(zin) is False
    assert opstelling[0].status["items"] == []


def test_gereserveerd_woord_wordt_niet_voorgesteld(opstelling):
    assert opstelling[0].verwerk_zin("fleur cyclus") is False
    assert opstelling[0].wachtend is None


def test_geen_string(opstelling):
    assert opstelling[0].verwerk_zin(None) is False


# ----------------------------------------------------------------------
# soorten beheren
# ----------------------------------------------------------------------
def test_soorten_tonen(opstelling):
    _, antw = zeg(opstelling, "fleur soorten")
    for s in ("knuffelen", "poepie", "rug", "tetjes", "seks"):
        assert s in antw


def test_soort_toevoegen_en_verwijderen(opstelling):
    module = opstelling[0]
    _, antw = zeg(opstelling, "fleur soort toevoegen massage")
    assert "massage" in module.status["soorten"] and "toegevoegd" in antw
    zeg(opstelling, "fleur massage")
    assert laatste_item(module)["soort"] == "massage"
    _, antw = zeg(opstelling, "fleur soort verwijderen massage")
    assert "massage" not in module.status["soorten"] and "oude noteringen blijven" in antw
    assert laatste_item(module)["soort"] == "massage"


def test_soort_dubbel_toevoegen_en_onbekend_verwijderen(opstelling):
    assert "ken ik al" in zeg(opstelling, "fleur soort toevoegen seks")[1]
    assert "ken ik niet" in zeg(opstelling, "fleur soort verwijderen bestaatniet")[1]


# ----------------------------------------------------------------------
# kalender, laatste, ongedaan
# ----------------------------------------------------------------------
def vul(module, *regels):
    for datum, tijd, soort, begon, afloop, wilde in regels:
        module.status["items"].append({"datum": datum, "tijd": tijd, "soort": soort, "begon": begon,
                                       "afloop": afloop, "wilde_niet": wilde})


def test_kalender_deze_maand(opstelling):
    module = opstelling[0]
    vul(module,
        ("2026-11-02", "21:30", "knuffelen", "kevin", "gedaan", None),
        ("2026-11-02", "22:10", "rug", "fleur", "gedaan", None),
        ("2026-11-15", None, "seks", "kevin", "niet doorgegaan", "fleur"),
        ("2026-10-31", "20:00", "seks", "samen", "gedaan", None))
    afgehandeld, antw = zeg(opstelling, "fleur kalender")
    assert afgehandeld and "november 2026" in antw
    assert "ma  2  21:30 knuffelen (jij begon) · 22:10 rug (Fleur begon)" in antw
    assert "zo 15  seks niet doorgegaan (jij probeerde, Fleur wilde niet)" in antw
    assert "31" not in antw.split("november 2026")[1].split("\n")[1]      # oktober staat er niet in
    assert "Totaal: 2x gedaan, 1x niet doorgegaan" in antw


def test_kalender_andere_maand(opstelling):
    module = opstelling[0]
    vul(module, ("2026-10-31", "20:00", "seks", "samen", "gedaan", None))
    _, antw = zeg(opstelling, "fleur kalender oktober")
    assert "oktober 2026" in antw and "20:00 seks (samen)" in antw


def test_kalender_vorige_maand_en_lege_maand(opstelling):
    module = opstelling[0]
    vul(module, ("2026-10-05", None, "rug", "kevin", "gedaan", None))
    assert "oktober 2026" in zeg(opstelling, "fleur kalender vorige maand")[1]
    assert "niets genoteerd" in zeg(opstelling, "fleur kalender maart")[1]


def test_kalender_maand_zonder_jaar_in_de_toekomst_is_vorig_jaar(opstelling):
    vul(opstelling[0], ("2025-12-24", None, "seks", "samen", "gedaan", None))
    assert "december 2025" in zeg(opstelling, "fleur kalender december")[1]


def test_laatste_toont_nieuwste_eerst(opstelling):
    module = opstelling[0]
    vul(module, ("2026-11-01", None, "rug", "kevin", "gedaan", None),
        ("2026-11-03", None, "seks", "fleur", "gedaan", None))
    _, antw = zeg(opstelling, "fleur laatste")
    assert antw.index("seks") < antw.index("rug")
    _, antw = zeg(opstelling, "fleur laatste 1")
    assert "Laatste 1 noteringen" in antw and "rug" not in antw


def test_laatste_zonder_data(opstelling):
    assert "nog niets" in zeg(opstelling, "fleur laatste")[1]


def test_kalender_laatste_ongedaan(opstelling):
    module = opstelling[0]
    zeg(opstelling, "fleur rug gisteren")
    zeg(opstelling, "fleur seks")
    _, antw = zeg(opstelling, "fleur kalender laatste ongedaan")
    assert "Verwijderd: seks" in antw
    assert [i["soort"] for i in module.status["items"]] == ["rug"]


def test_ongedaan_zonder_data(opstelling):
    assert "niets om ongedaan" in zeg(opstelling, "fleur kalender laatste ongedaan")[1]


def test_antwoorden_gaan_als_instant_chat_response(opstelling):
    zeg(opstelling, "fleur seks")
    naam, data = opstelling[1].gepubliceerd[-1]
    assert naam == "chat_response" and data["instant"] is True


# ----------------------------------------------------------------------
# tellers en verhoudingen
# ----------------------------------------------------------------------
def test_overzicht_tellers_en_verhoudingen(opstelling):
    module = opstelling[0]
    vul(module,
        ("2026-11-01", None, "seks", "kevin", "gedaan", None),
        ("2026-11-05", None, "seks", "kevin", "gedaan", None),
        ("2026-11-09", None, "seks", "fleur", "gedaan", None),
        ("2026-11-12", None, "seks", "kevin", "niet doorgegaan", "fleur"),
        ("2026-11-20", None, "knuffelen", "samen", "gedaan", None))
    _, antw = zeg(opstelling, "fleur overzicht")
    assert "5 noteringen" in antw
    assert "seks: 3x gedaan, 1x niet doorgegaan (25% van 4 pogingen)" in antw
    assert "begon: jij 3 (75%), Fleur 1 (25%)" in antw
    assert "knuffelen: 1x gedaan" in antw and "samen 1" in antw
    assert "Totaal: 4x gedaan, 1x niet doorgegaan" in antw


def test_overzicht_per_soort_en_periode(opstelling):
    module = opstelling[0]
    vul(module,
        ("2026-10-10", None, "seks", "kevin", "gedaan", None),
        ("2026-11-02", None, "seks", "fleur", "gedaan", None),
        ("2026-11-03", None, "rug", "kevin", "gedaan", None))
    _, antw = zeg(opstelling, "fleur overzicht seks deze maand")
    assert "november 2026, seks" in antw and "1x gedaan" in antw and "rug" not in antw
    _, antw = zeg(opstelling, "fleur overzicht oktober")
    assert "oktober 2026" in antw and "1x gedaan" in antw


def test_enkelvoud_poging(opstelling):
    vul(opstelling[0], ("2026-11-12", None, "seks", "kevin", "niet doorgegaan", "fleur"))
    assert "100% van 1 poging)" in zeg(opstelling, "fleur overzicht")[1]


def test_overzicht_leeg(opstelling):
    assert "niets genoteerd" in zeg(opstelling, "fleur overzicht")[1]


def test_overzicht_aliassen(opstelling):
    vul(opstelling[0], ("2026-11-01", None, "rug", "kevin", "gedaan", None))
    for zin in ("fleur statistieken", "fleur tellers"):
        assert "Overzicht Fleur" in zeg(opstelling, zin)[1]


# ----------------------------------------------------------------------
# leren: inzichten
# ----------------------------------------------------------------------
def test_inzichten_zonder_data(opstelling):
    assert "nog niets genoteerd" in zeg(opstelling, "fleur inzichten")[1]


def test_inzichten_met_weinig_data_zegt_dat(opstelling):
    vul(opstelling[0], ("2026-11-20", "21:00", "seks", "kevin", "gedaan", None))
    _, antw = zeg(opstelling, "fleur inzichten")
    assert "Nog te weinig om patronen te zien (1 van minstens 8)" in antw
    assert "seks: laatst 8 dagen geleden" in antw


def test_inzichten_tussentijd_per_soort(opstelling):
    module = opstelling[0]
    for d in ("2026-11-01", "2026-11-05", "2026-11-09", "2026-11-13"):
        vul(module, (d, None, "seks", "kevin", "gedaan", None))
    _, antw = zeg(opstelling, "fleur inzichten")
    assert "meestal 4 dagen ertussen" in antw


def test_inzichten_weekdag_en_dagdeel(opstelling):
    module = opstelling[0]
    vrijdagen = [date(2026, 10, 2) + timedelta(days=7 * n) for n in range(6)]       # alle vrijdagen
    for d in vrijdagen:
        vul(module, (d.isoformat(), "22:00", "seks", "kevin", "gedaan", None))
    vul(module, ("2026-10-05", "22:30", "rug", "fleur", "gedaan", None),
        ("2026-10-21", "09:00", "rug", "fleur", "gedaan", None))
    _, antw = zeg(opstelling, "fleur inzichten")
    assert "Vaakst op vrijdag: 6 van 8" in antw
    assert "Meestal 's avonds: 7 van 8" in antw
    assert "toeval" in antw


def test_inzichten_wie_begint(opstelling):
    module = opstelling[0]
    for n in range(10):
        vul(module, (f"2026-10-{n + 1:02d}", None, "rug", "kevin" if n < 7 else "fleur", "gedaan", None))
    _, antw = zeg(opstelling, "fleur inzichten")
    assert "Wie begint: jij 7x (70%), Fleur 3x (30%)" in antw


def test_inzichten_niet_doorgegaan(opstelling):
    module = opstelling[0]
    for n in range(6):
        vul(module, (f"2026-10-{n + 1:02d}", "22:00", "seks", "kevin", "gedaan", None))
    for n in range(4):
        vul(module, (f"2026-10-{n + 10:02d}", "23:00", "seks", "kevin", "niet doorgegaan", "fleur"))
    _, antw = zeg(opstelling, "fleur inzichten")
    assert "Niet doorgegaan: 4 van 10 pogingen (40%)" in antw
    assert "Daarvan probeerde jij 4x en Fleur 0x" in antw
    assert "Meestal 's avonds: 4 van 4" in antw


def test_inzichten_cyclus_te_weinig_gegevens(opstelling):
    module, bus, klok, pad = opstelling
    cy = c.CyclusModule(bus, pad=str(pad) + ".cyclus", klok=klok, start_loop=False)
    bus.modules["cyclus"] = cy
    cy.registreer_start(date(2026, 10, 1))
    for n in range(9):
        vul(module, (f"2026-10-{n + 3:02d}", None, "rug", "kevin", "gedaan", None))
    _, antw = zeg(opstelling, "fleur inzichten")
    assert "nog te weinig gegevens" in antw


def test_inzichten_cyclus_verband_wordt_opgemerkt(opstelling):
    module, bus, klok, pad = opstelling
    cy = c.CyclusModule(bus, pad=str(pad) + ".cyclus", klok=klok, start_loop=False)
    bus.modules["cyclus"] = cy
    starts = [date(2026, 8, 1) + timedelta(days=28 * n) for n in range(4)]     # 1 aug ... 24 okt
    for s in starts:
        cy.registreer_start(s)
    # elke cyclus 4x op dag 12 t/m 15 (rond de eisprong, die op dag 15 valt)
    for s in starts[:3]:
        for dag in (11, 12, 13, 14):
            vul(module, ((s + timedelta(days=dag)).isoformat(), "22:00", "seks", "kevin", "gedaan", None))
    _, antw = zeg(opstelling, "fleur inzichten")
    assert "Verband met Fleur's cyclus" in antw
    assert "Rond de eisprong: 12 van 12" in antw and "vaker dan gemiddeld" in antw
    assert "Tijdens de maandstonden" in antw and "minder vaak dan gemiddeld" in antw


def test_inzichten_zonder_cyclusmodule_geen_crash(opstelling):
    module = opstelling[0]
    for n in range(10):
        vul(module, (f"2026-10-{n + 1:02d}", None, "rug", "kevin", "gedaan", None))
    assert "Verband met Fleur's cyclus" not in zeg(opstelling, "fleur inzichten")[1]


# ----------------------------------------------------------------------
# opslag en robuustheid
# ----------------------------------------------------------------------
def test_wordt_bewaard_en_teruggelezen(opstelling):
    module, bus, klok, pad = opstelling
    zeg(opstelling, "fleur seks ik begon")
    zeg(opstelling, "fleur soort toevoegen massage")
    nieuw = fk.FleurKalender(NepBus(), pad=str(pad), klok=klok)
    assert len(nieuw.status["items"]) == 1 and "massage" in nieuw.status["soorten"]


def test_kapot_bestand_geeft_lege_start(tmp_path):
    pad = tmp_path / "x.json"
    pad.write_text("{geen json", encoding="utf-8")
    module = fk.FleurKalender(NepBus(), pad=str(pad), klok=Klok(datetime(2026, 11, 28, 9)))
    assert module.status["items"] == [] and "seks" in module.status["soorten"]


def test_vreemde_inhoud_wordt_genegeerd(tmp_path):
    pad = tmp_path / "x.json"
    pad.write_text(json.dumps({"soorten": {"seks": [], "kapot": "x"},
                               "items": [1, "x", {"datum": "2026-10-01"},
                                         {"datum": "2026-10-01", "soort": "seks", "afloop": "gedaan", "begon": "kevin"}]}),
                   encoding="utf-8")
    module = fk.FleurKalender(NepBus(), pad=str(pad), klok=Klok(datetime(2026, 11, 28, 9)))
    assert len(module.status["items"]) == 1 and list(module.status["soorten"]) == ["seks"]


def test_init_module(monkeypatch, tmp_path):
    bus = NepBus()
    monkeypatch.setattr(fk, "get_project_root", lambda _f: tmp_path)
    module = fk.init_module(bus)
    assert isinstance(module, fk.FleurKalender)
    assert ("module_loaded", {"name": "fleur_kalender"}) in bus.gepubliceerd


def test_hulpfuncties():
    assert fk.procent(1, 3) == 33 and fk.procent(0, 0) == 0
    assert fk.dagdeel(3) == "nacht" and fk.dagdeel(7) == "ochtend" and fk.dagdeel(15) == "middag" and fk.dagdeel(23) == "avond"
    assert fk.lees_tijd("seks om 21:30")[0] == (21, 30)
    assert fk.lees_tijd("seks om 25:00")[0] is None
    nu = datetime(2026, 1, 15, 10, 0)
    assert fk.lees_periode("vorige maand", nu)[2] == "december 2025"
    assert fk.lees_periode("niets", nu)[2] == "alles"


def test_voorbeelden_uit_de_fleur_help_worden_herkend(tmp_path):
    from modules.help.topics import fleur as help_fleur
    for commando in help_fleur.alle_commandos("fleur_kalender"):
        module = fk.FleurKalender(NepBus(), pad=str(tmp_path / f"{abs(hash(commando))}.json"),
                                  klok=Klok(datetime(2026, 11, 28, 13, 55)))
        assert module.verwerk_zin(commando) is True, f"niet herkend: {commando!r}"