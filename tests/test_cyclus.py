"""Tests voor modules/time/cyclus.py (maandstonden en cyclus van Fleur).

Alles met een nep-bus, een nep-klok en een tijdelijk bestand in tmp_path:
er wordt niets van de echte data/ aangeraakt en er start geen thread.
Uitvoeren: pytest tests/test_cyclus.py -v
"""

import json
from datetime import date, datetime, timedelta

import pytest

from modules.time import cyclus as c


class NepBus:
    def __init__(self):
        self.gepubliceerd = []

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data or {}))

    def antwoorden(self):
        return [d["text"] for n, d in self.gepubliceerd if n == "layer4_response"]


class Klok:
    def __init__(self, nu):
        self.nu = nu

    def __call__(self):
        return self.nu

    def dag(self, y, m, d, uur=9):
        self.nu = datetime(y, m, d, uur, 0)


@pytest.fixture
def opstelling(tmp_path):
    bus = NepBus()
    klok = Klok(datetime(2026, 11, 28, 9, 0))
    pad = tmp_path / "cyclus.json"
    module = c.CyclusModule(bus, pad=str(pad), klok=klok, start_loop=False)
    return module, bus, klok, pad


def zeg(module, bus, zin):
    voor = len(bus.antwoorden())
    afgehandeld = module.verwerk_zin(zin)
    nieuw = bus.antwoorden()[voor:]
    return afgehandeld, (nieuw[-1] if nieuw else None)


def vul(module, *datums):
    for d in datums:
        module.registreer_start(date.fromisoformat(d))


# ----------------------------------------------------------------------
# datums lezen
# ----------------------------------------------------------------------
VANDAAG = date(2026, 11, 28)


@pytest.mark.parametrize("zin, verwacht", [
    ("fleur is vandaag ongesteld geworden", date(2026, 11, 28)),
    ("sinds gisteren", date(2026, 11, 27)),
    ("eergisteren", date(2026, 11, 26)),
    ("3 dagen geleden", date(2026, 11, 25)),
    ("drie dagen geleden", date(2026, 11, 25)),
    ("op 12 november", date(2026, 11, 12)),
    ("op 12 nov", date(2026, 11, 12)),
    ("12/11", date(2026, 11, 12)),
    ("12-11-2026", date(2026, 11, 12)),
    ("12.11.26", date(2026, 11, 12)),
    ("2 december 2025", date(2025, 12, 2)),
    ("20 december", date(2025, 12, 20)),    # zonder jaar: de laatste keer dat dit voorbij was
])
def test_lees_datum(zin, verwacht):
    assert c.lees_datum(zin, VANDAAG) == verwacht


@pytest.mark.parametrize("zin", ["niets bijzonders", "31 februari", "op 15 december 2026", "30/02"])
def test_lees_datum_geen_of_ongeldig(zin):
    assert c.lees_datum(zin, VANDAAG) is None


# ----------------------------------------------------------------------
# leren: gemiddelde en schatting
# ----------------------------------------------------------------------
def test_zonder_cycli_standaard_28():
    gem, aantal, kort, lang = c.schat_cyclus([date(2026, 1, 1)])
    assert (gem, aantal, kort, lang) == (28.0, 0, None, None)


def test_gewogen_gemiddelde_nieuwste_weegt_zwaarder():
    starts = [date(2026, 1, 1), date(2026, 1, 29), date(2026, 2, 26), date(2026, 3, 30)]  # 28, 28, 32
    gem, aantal, kort, lang = c.schat_cyclus(starts)
    assert aantal == 3 and (kort, lang) == (28, 32)
    assert gem == pytest.approx((1 * 28 + 2 * 28 + 3 * 32) / 6)
    assert gem > (28 + 28 + 32) / 3          # zwaarder dan een gewoon gemiddelde


def test_onrealistische_cycli_tellen_niet_mee():
    starts = [date(2026, 1, 1), date(2026, 1, 8), date(2026, 2, 5)]   # 7 en 28 dagen
    gem, aantal, _, _ = c.schat_cyclus(starts)
    assert aantal == 1 and gem == 28


def test_maximaal_laatste_zes_cycli():
    starts = [date(2025, 1, 1)]
    for lengte in [40, 40, 40, 28, 28, 28, 28, 28, 28]:
        starts.append(starts[-1] + timedelta(days=lengte))
    gem, aantal, _, _ = c.schat_cyclus(starts)
    assert aantal == 6 and gem == 28


def test_periodelengte_standaard_en_gewogen():
    assert c.schat_periode([]) == c.STANDAARD_PERIODE
    assert c.schat_periode([4, 6]) == pytest.approx((1 * 4 + 2 * 6) / 3)
    assert c.schat_periode([40, 0]) == c.STANDAARD_PERIODE   # onzin wordt genegeerd


# ----------------------------------------------------------------------
# fases (cyclus 28, periode 5, eisprong = dag 15 -> start + 14)
# ----------------------------------------------------------------------
START = date(2026, 11, 1)


def fase_op(dagen_na_start, cyclus=28, periode=5):
    return c.bepaal_fase(START + timedelta(days=dagen_na_start), START, cyclus, periode)


@pytest.mark.parametrize("dagen, fase, vrucht", [
    (0, "menstruatie", "niet vruchtbaar"),
    (4, "menstruatie", "niet vruchtbaar"),
    (5, "folliculaire fase", "minder vruchtbaar"),
    (8, "folliculaire fase", "minder vruchtbaar"),
    (9, "vruchtbaar venster", "vruchtbaar"),      # eisprong op dag +14, venster start 5 dagen eerder
    (11, "vruchtbaar venster", "vruchtbaar"),
    (12, "eisprong", "zeer vruchtbaar (piek)"),
    (14, "eisprong", "zeer vruchtbaar (piek)"),
    (15, "net na de eisprong", "minder vruchtbaar"),
    (16, "luteale fase", "niet vruchtbaar"),
    (27, "luteale fase", "niet vruchtbaar"),
])
def test_fases(dagen, fase, vrucht):
    f = fase_op(dagen)
    assert f["fase"] == fase and f["vruchtbaarheid"] == vrucht


def test_fase_te_laat_is_onzeker():
    f = fase_op(30)
    assert f["fase"] == "wachten op maandstonden"
    assert f["vruchtbaarheid"] == "onzeker"
    assert f["te_laat"] == 2


def test_fase_op_verwachte_dag_is_nog_niet_te_laat_maar_wachten():
    f = fase_op(28)
    assert f["fase"] == "wachten op maandstonden" and f["te_laat"] == 0


def test_eisprong_ligt_14_dagen_voor_verwacht():
    f = fase_op(3, cyclus=31)
    assert f["verwacht"] - f["eisprong"] == timedelta(days=14)


# ----------------------------------------------------------------------
# startdatums opslaan en leren van het verschil
# ----------------------------------------------------------------------
def test_eerste_start_opgeslagen_en_bewaard(opstelling):
    module, bus, klok, pad = opstelling
    afgehandeld, antw = zeg(module, bus, "Fleur is vandaag ongesteld geworden")
    assert afgehandeld and "Genoteerd" in antw and "za 28 nov" in antw
    assert "grove schatting" in antw
    opgeslagen = json.loads(pad.read_text(encoding="utf-8"))
    assert opgeslagen["perioden"][0]["start"] == "2026-11-28"


def test_nieuwe_instantie_leest_het_bestand_terug(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-01", "2026-10-29")
    nieuw = c.CyclusModule(NepBus(), pad=str(pad), klok=klok, start_loop=False)
    assert nieuw.starts() == [date(2026, 10, 1), date(2026, 10, 29)]


def test_zelfde_datum_twee_keer(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-01")
    assert "had ik al" in module.registreer_start(date(2026, 10, 1))
    assert len(module.status["perioden"]) == 1


def test_te_korte_tussenruimte_wordt_geweigerd(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-01")
    antwoord = module.registreer_start(date(2026, 10, 5))
    assert "maar 4 dagen" in antwoord
    assert len(module.status["perioden"]) == 1


def test_vroeger_dan_verwacht_wordt_gemeld_en_geleerd(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-09-03", "2026-10-01")              # cyclus 28 -> verwacht 29 okt
    antwoord = module.registreer_start(date(2026, 10, 26))  # 3 dagen vroeger
    assert "3 dagen vroeger" in antwoord
    assert "cyclus van 25 dagen" in antwoord
    assert module.status["perioden"][-1]["voorspeld"] == "2026-10-29"
    assert module.schatting()["cyclus"] < 28


def test_later_dan_verwacht(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-09-03", "2026-10-01")
    assert "2 dagen later" in module.registreer_start(date(2026, 10, 31))


def test_precies_op_tijd(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-09-03", "2026-10-01")
    assert "precies wanneer ik ze verwachtte" in module.registreer_start(date(2026, 10, 29))


def test_gemiddelde_afwijking_pas_vanaf_twee_voorspellingen(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-07-09", "2026-08-06", "2026-09-03")     # 2e en 3e start hadden een voorspelling
    assert module.gemiddelde_afwijking() == 0
    module.registreer_start(date(2026, 10, 3))                # 30 dagen: 2 dagen later
    assert module.gemiddelde_afwijking() == pytest.approx(2 / 3)


def test_laatste_ongedaan(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-09-03", "2026-10-01")
    afgehandeld, antw = zeg(module, bus, "fleur maandstonden laatste ongedaan")
    assert afgehandeld and "Verwijderd" in antw
    assert module.starts() == [date(2026, 9, 3)]


def test_laatste_ongedaan_zonder_data(opstelling):
    module, bus, klok, pad = opstelling
    assert "niets" in module.laatste_ongedaan()


# ----------------------------------------------------------------------
# einde van de maandstonden
# ----------------------------------------------------------------------
def test_einde_noteren_en_periodelengte_leren(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-11-23")
    afgehandeld, antw = zeg(module, bus, "fleur is niet meer ongesteld")
    assert afgehandeld and "duurden 6 dagen" in antw
    assert module.schatting()["periode"] == 6


def test_einde_zonder_start(opstelling):
    module, bus, klok, pad = opstelling
    afgehandeld, antw = zeg(module, bus, "fleur is niet meer ongesteld")
    assert afgehandeld and "nog geen startdatum" in antw


def test_einde_onrealistisch_lang(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-01")
    assert "klopt waarschijnlijk niet" in module.registreer_einde(date(2026, 10, 25))


# ----------------------------------------------------------------------
# zinnen herkennen
# ----------------------------------------------------------------------
@pytest.mark.parametrize("zin, datum", [
    ("fleur is vandaag ongesteld geworden", "2026-11-28"),
    ("Fleur heeft haar maandstonden sinds gisteren", "2026-11-27"),
    ("de maandstonden van fleur zijn begonnen op 12 november", "2026-11-12"),
    ("ze is 3 dagen geleden ongesteld geworden", "2026-11-25"),
    ("ze is ongesteld geworden", "2026-11-28"),
    ("fleur is gisteren ongesteld geworden!", "2026-11-27"),
])
def test_startzinnen(opstelling, zin, datum):
    module, bus, klok, pad = opstelling
    afgehandeld, _ = zeg(module, bus, zin)
    assert afgehandeld
    assert module.status["perioden"][-1]["start"] == datum


def test_onleesbare_datum_slaat_niets_op(opstelling):
    module, bus, klok, pad = opstelling
    afgehandeld, antw = zeg(module, bus, "fleur is ongesteld geworden op 31 februari")
    assert afgehandeld and "kon ik niet lezen" in antw
    assert module.status["perioden"] == []


def test_toekomstige_datum_wordt_niet_opgeslagen(opstelling):
    module, bus, klok, pad = opstelling
    afgehandeld, antw = zeg(module, bus, "fleur is ongesteld geworden op 15 december 2026")
    assert afgehandeld and module.status["perioden"] == []


@pytest.mark.parametrize("zin", [
    "wat is ongesteld",
    "hoe laat is het",
    "toon de hele kennisgraaf",
    "wat is een cyclus van water",
    "ik ben ongesteld",             # gaat niet over Fleur/haar/ze
    "wat betekent vruchtbaar",
    "",
])
def test_vreemde_zinnen_worden_niet_opgepakt(opstelling, zin):
    module, bus, klok, pad = opstelling
    assert module.verwerk_zin(zin) is False
    assert bus.antwoorden() == []


def test_geen_string_geeft_false(opstelling):
    module, bus, klok, pad = opstelling
    assert module.verwerk_zin(None) is False
    assert module.verwerk_zin(123) is False


# ----------------------------------------------------------------------
# vragen
# ----------------------------------------------------------------------
def test_vraag_wanneer_weer_ongesteld(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")                       # verwacht 28 nov = vandaag
    _, antw = zeg(module, bus, "wanneer is fleur weer ongesteld?")
    assert "vandaag verwacht" in antw


def test_vraag_wanneer_in_de_toekomst(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-11-20")                       # verwacht 18 dec
    _, antw = zeg(module, bus, "wanneer is ze weer ongesteld")
    assert "vr 18 dec" in antw and "over 20 dagen" in antw


def test_vraag_wanneer_zonder_data(opstelling):
    module, bus, klok, pad = opstelling
    _, antw = zeg(module, bus, "wanneer is fleur weer ongesteld?")
    assert "nog geen startdatum" in antw


@pytest.mark.parametrize("zin", [
    "in welke fase zit fleur?",
    "welke fase zit ze nu in",
    "is ze vruchtbaar?",
    "is fleur vruchtbaar",
    "fleur fase",
])
def test_fasevragen(opstelling, zin):
    module, bus, klok, pad = opstelling
    vul(module, "2026-11-14")          # vandaag = dag 15, verwacht 12 dec, eisprong 28 nov
    afgehandeld, antw = zeg(module, bus, zin)
    assert afgehandeld
    assert "dag 15" in antw and "zeer vruchtbaar" in antw
    assert "geen anticonceptie" in antw


def test_fase_antwoord_noemt_eisprong_in_de_toekomst(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-11-22")          # vandaag dag 7; eisprong 6 dec
    _, antw = zeg(module, bus, "welke fase zit fleur")
    assert "folliculaire fase" in antw and "ma 7 dec" not in antw
    assert "Eisprong geschat rond" in antw and "(over" in antw


def test_fase_antwoord_over_tijd(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-25")          # verwacht 22 nov, vandaag 6 dagen te laat
    _, antw = zeg(module, bus, "in welke fase zit fleur?")
    assert "6 dagen over tijd" in antw and "onzeker" in antw


def test_grove_schatting_wordt_vermeld(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-11-14")
    tekst = module.tekst_fase()
    assert "grove schatting" in tekst and "nog geen volledige cyclus" in tekst


def test_onregelmatige_cyclus_wordt_vermeld(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-06-01", "2026-06-25", "2026-07-30", "2026-08-22", "2026-10-01")  # 24, 35, 23, 40
    assert "wisselt" in module.tekst_fase()


def test_overzicht(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-08-06", "2026-09-03", "2026-10-01")
    module.registreer_einde(date(2026, 10, 5))
    afgehandeld, antw = zeg(module, bus, "cyclus overzicht")
    assert afgehandeld
    assert "3 startdatum" in antw and "28, 28" in antw and "Gemiddelde cyclus: 28" in antw
    assert "5 dagen" in antw


def test_overzicht_leeg(opstelling):
    module, bus, klok, pad = opstelling
    assert "nog geen cycli" in module.tekst_overzicht()


# ----------------------------------------------------------------------
# instellingen
# ----------------------------------------------------------------------
def test_vooraf_instellen(opstelling):
    module, bus, klok, pad = opstelling
    afgehandeld, antw = zeg(module, bus, "fleur melding 3 dagen vooraf")
    assert afgehandeld and "3 dagen vooraf" in antw and module.status["vooraf_dagen"] == 3


def test_vooraf_buiten_grenzen(opstelling):
    module, bus, klok, pad = opstelling
    assert "tussen 1 en" in module.zet_vooraf(0)
    assert "tussen 1 en" in module.zet_vooraf(99)
    assert module.status["vooraf_dagen"] == c.VOORAF_STANDAARD


def test_vruchtbaarheidsmelding_aan_uit(opstelling):
    module, bus, klok, pad = opstelling
    zeg(module, bus, "fleur vruchtbaarheidsmeldingen aan")
    assert module.status["vruchtbaar_melding"] is True
    zeg(module, bus, "fleur vruchtbaarheidsmelding uit")
    assert module.status["vruchtbaar_melding"] is False


# ----------------------------------------------------------------------
# meldingen
# ----------------------------------------------------------------------
def test_geen_data_geen_melding(opstelling):
    module, bus, klok, pad = opstelling
    assert module.controleer() == []


def test_melding_vooraf_eenmalig_per_cyclus(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")                       # verwacht 28 nov
    klok.dag(2026, 11, 26)                          # 2 dagen vooraf
    eerste = module.controleer()
    assert len(eerste) == 1 and "over 2 dagen" in eerste[0] and "Fleur" in eerste[0]
    assert module.controleer() == []                # zelfde dag: niet nog eens
    klok.dag(2026, 11, 27)
    assert module.controleer() == []                # volgende dag: dezelfde cyclus al gemeld


def test_melding_op_de_dag_zelf(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")
    klok.dag(2026, 11, 28)
    teksten = module.controleer()
    assert any("vandaag verwacht" in t for t in teksten)
    assert module.controleer() == []


def test_melding_wordt_gepubliceerd_op_de_bus(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")
    klok.dag(2026, 11, 26)
    module.controleer()
    assert any("verwacht over 2 dagen" in t for t in bus.antwoorden())


def test_herstart_herhaalt_melding_niet(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")
    klok.dag(2026, 11, 26)
    module.controleer()
    nieuw = c.CyclusModule(NepBus(), pad=str(pad), klok=klok, start_loop=False)
    assert nieuw.controleer() == []


def test_vooraf_dagen_instelbaar(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")
    module.zet_vooraf(4)
    klok.dag(2026, 11, 24)
    assert "over 4 dagen" in module.controleer()[0]


def test_geen_melding_buiten_de_uren(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")
    klok.dag(2026, 11, 26, uur=3)
    assert module.controleer() == []
    klok.dag(2026, 11, 26, uur=22)
    assert module.controleer() == []
    klok.dag(2026, 11, 26, uur=8)
    assert len(module.controleer()) == 1


def test_te_laat_elke_dag_een_melding(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")                       # verwacht 28 nov
    klok.dag(2026, 11, 29)
    eerste = module.controleer()
    assert len(eerste) == 1 and "1 dag over tijd" in eerste[0]
    assert module.controleer() == []                # zelfde dag niet nog eens
    klok.dag(2026, 11, 30)
    assert "2 dagen over tijd" in module.controleer()[0]


def test_nog_niet_stelt_tot_morgen_uit(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")
    klok.dag(2026, 11, 30)
    zeg(module, bus, "ze is nog niet ongesteld")
    assert module.controleer() == []                # vandaag niets meer
    klok.dag(2026, 12, 1)
    assert "3 dagen over tijd" in module.controleer()[0]


def test_nog_niet_antwoord_noemt_dagen_te_laat(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")
    klok.dag(2026, 11, 30)
    _, antw = zeg(module, bus, "fleur heeft nog geen maandstonden gekregen")
    assert "nog niet ongesteld" in antw and "2 dagen over tijd" in antw and "morgen opnieuw" in antw


def test_nog_niet_zonder_data(opstelling):
    module, bus, klok, pad = opstelling
    assert "nog geen startdatum" in module.nog_niet()


def test_startdatum_stopt_de_te_laat_meldingen(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")
    klok.dag(2026, 11, 30)
    module.controleer()
    zeg(module, bus, "fleur is gisteren ongesteld geworden")     # 29 nov
    klok.dag(2026, 12, 1)
    assert module.controleer() == []                             # nieuwe cyclus, nog lang niet verwacht
    assert module.status["uitgesteld_tot"] is None


def test_te_laat_stopt_na_veertien_dagen_met_slotbericht(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-31")                       # verwacht 28 nov
    klok.dag(2026, 12, 12)                          # 14 dagen te laat
    assert "Ik stop met dagelijks melden" in module.controleer()[0]
    klok.dag(2026, 12, 13)
    assert module.controleer() == []


def test_vruchtbaar_venster_melding_staat_standaard_uit(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-11-01")                       # verwacht 29 nov, eisprong 15 nov, venster vanaf 10 nov
    klok.dag(2026, 11, 10)
    assert module.controleer() == []


def test_vruchtbaar_venster_melding_wanneer_aan(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-11-01")
    module.zet_vruchtbaar_melding(True)
    klok.dag(2026, 11, 10)
    teksten = module.controleer()
    assert len(teksten) == 1 and "vruchtbare venster begint vandaag" in teksten[0]
    assert module.controleer() == []


# ----------------------------------------------------------------------
# robuustheid
# ----------------------------------------------------------------------
def test_kapot_bestand_geeft_lege_start(tmp_path):
    pad = tmp_path / "cyclus.json"
    pad.write_text("{dit is geen json", encoding="utf-8")
    module = c.CyclusModule(NepBus(), pad=str(pad), klok=Klok(datetime(2026, 11, 28, 9)), start_loop=False)
    assert module.starts() == []


def test_vreemde_inhoud_in_bestand_wordt_genegeerd(tmp_path):
    pad = tmp_path / "cyclus.json"
    pad.write_text(json.dumps({"perioden": [1, "x", {"geen_start": 1}, {"start": "2026-10-01"}],
                               "onbekend": 5}), encoding="utf-8")
    module = c.CyclusModule(NepBus(), pad=str(pad), klok=Klok(datetime(2026, 11, 28, 9)), start_loop=False)
    assert module.starts() == [date(2026, 10, 1)]


def test_starts_worden_gesorteerd_bij_achteraf_invullen(opstelling):
    module, bus, klok, pad = opstelling
    vul(module, "2026-10-01")
    module.registreer_start(date(2026, 9, 3))       # oudere datum achteraf
    assert module.starts() == [date(2026, 9, 3), date(2026, 10, 1)]


def test_init_module_start_geen_thread_onder_pytest(monkeypatch, tmp_path):
    bus = NepBus()
    monkeypatch.setattr(c, "get_project_root", lambda _f: tmp_path)
    module = c.init_module(bus)
    assert isinstance(module, c.CyclusModule)
    assert ("module_loaded", {"name": "cyclus"}) in bus.gepubliceerd


def test_datum_en_getalhulpjes():
    assert c.datum_kort(date(2026, 11, 28)) == "za 28 nov"
    assert c.dagen_tekst(1) == "1 dag" and c.dagen_tekst(-3) == "3 dagen"
    assert c.getal_tekst(27.0) == "27" and c.getal_tekst(27.64) == "27,6"