# tests/test_datum_terugblik_testvragen.py
"""
3 november 2026: vragen en opdrachten aan Nova ("wat is bank", "zoek gelijkenissen
voor hond") zijn gereedschap gebruiken of testen, geen gesprek. Ze tellen niet mee
in de datum-terugblik. De eerste echte melding ging door zulke berichten over
'levenshtein', 'plus' en 'bank'.
"""

from datetime import date, datetime

import pytest

from modules.knowledge import datum_terugblik as dt


def ts(jaar, maand, dag, uur=12):
    return datetime(jaar, maand, dag, uur, 0).timestamp()


class TestIsTestvraag:
    @pytest.mark.parametrize("tekst", [
        "wat is bank",
        "Wat is een bank?",
        "WAT BETEKENT levenshtein",
        "wat zijn synoniemen",
        "wat bedoel je met plus",
        "definieer plus",
        "definitie van hond",
        "geef een voorbeeld van een zin",
        "geef de definitie van kat",
        "synoniem van groot",
        "antoniem van groot",
        "zoek gelijkenissen voor hond",
        "gelijkenissen overlopen",
        "waarop lijkt kat",
        "waar lijkt hond op",
        "extraheer hond",
        "nova, wat is bank",
        "  wat is bank",
    ])
    def test_vragen_aan_nova(self, tekst):
        assert dt.is_testvraag(tekst) is True

    @pytest.mark.parametrize("tekst", [
        "ik ga morgen mijn fietsband herstellen",
        "ik ben moe van het werk",
        "mijn bank heeft gebeld over de lening",
        "ik vroeg wat is bank",              # begint niet met het patroon
        "watisbank",
        "",
        None,
    ])
    def test_gewone_berichten_tellen_mee(self, tekst):
        assert dt.is_testvraag(tekst) is False

    def test_lang_bericht_dat_met_wat_is_begint_telt_mee(self):
        tekst = "wat is het toch fijn om na een lange werkdag thuis te komen en te koken voor iedereen"
        assert len(tekst.split()) > dt.MAX_WOORDEN_TESTVRAAG
        assert dt.is_testvraag(tekst) is False

    def test_precies_op_de_grens(self):
        op_grens = "wat is " + " ".join(["woord"] * (dt.MAX_WOORDEN_TESTVRAAG - 2))
        net_erover = op_grens + " woord"
        assert len(op_grens.split()) == dt.MAX_WOORDEN_TESTVRAAG
        assert dt.is_testvraag(op_grens) is True
        assert dt.is_testvraag(net_erover) is False


def _rijen(berichten_toen, berichten_nu):
    """Genoeg gewone dagen voor een basis, plus berichten rond 2 augustus en de laatste dagen."""
    rijen = []
    # 40 gewone dagen in september/oktober, elk met eigen, unieke woorden
    for i in range(40):
        maand, dag = (9, 1 + i) if i < 30 else (10, i - 29)
        rijen.append((ts(2026, maand, dag), f"gewoon bericht{i} zonderling{i}"))
    for (maand, dag), tekst in berichten_toen:
        rijen.append((ts(2026, maand, dag), tekst))
    for (maand, dag), tekst in berichten_nu:
        rijen.append((ts(2026, maand, dag), tekst))
    return rijen


TOEN = [((7, 31), "fietsband reparatie"), ((8, 1), "fietsband"), ((8, 2), "reparatie fietsband"),
        ((8, 3), "reparatie")]
NU = [((10, 30), "fietsband reparatie"), ((11, 1), "fietsband"), ((11, 2), "reparatie")]
NU_DATUM = date(2026, 11, 2)


def _voorvoeg(lijst, voorvoegsel):
    return [(d, f"{voorvoegsel} {t}") for d, t in lijst]


class TestInDeAnalyse:
    def test_controle_gewone_berichten_geven_wel_een_terugblik(self):
        analyse = dt.vind_terugblik(_rijen(TOEN, NU), NU_DATUM)
        assert analyse["kandidaten"], analyse
        woorden = analyse["kandidaten"][0]["woorden"]
        assert "fietsband" in woorden and "reparatie" in woorden
        assert analyse["testvragen_overgeslagen"] == 0

    def test_dezelfde_woorden_als_testvragen_geven_geen_terugblik(self):
        analyse = dt.vind_terugblik(
            _rijen(_voorvoeg(TOEN, "wat is"), _voorvoeg(NU, "wat is")), NU_DATUM
        )
        assert analyse["kandidaten"] == []
        assert analyse["testvragen_overgeslagen"] == len(TOEN) + len(NU)

    def test_enkel_de_testvragen_vallen_weg_gewone_berichten_blijven(self):
        toen = TOEN + [((8, 2), "wat is bank"), ((8, 3), "wat is levenshtein plus")]
        nu = NU + [((11, 2), "zoek gelijkenissen voor bank")]
        analyse = dt.vind_terugblik(_rijen(toen, nu), NU_DATUM)
        assert analyse["kandidaten"]
        woorden = analyse["kandidaten"][0]["woorden"]
        assert "bank" not in woorden and "levenshtein" not in woorden
        assert analyse["testvragen_overgeslagen"] == 3

    def test_het_voorbeeld_in_de_melding_is_nooit_een_testvraag(self):
        toen = TOEN + [((8, 2), "wat is fietsband reparatie")]
        analyse = dt.vind_terugblik(_rijen(toen, NU), NU_DATUM)
        assert analyse["kandidaten"]
        assert not dt.is_testvraag(analyse["kandidaten"][0]["voorbeeld"])

    def test_het_oorspronkelijke_geval_bank_plus_levenshtein(self):
        # Het geval van 2 november 2026: testsessies rond 2 augustus en de laatste dagen.
        toen = [((7, 31), "wat is bank"), ((8, 2), "wat is bank"), ((8, 2), "levenshtein plus"),
                ((8, 3), "wat betekent levenshtein")]
        nu = [((10, 30), "wat is bank"), ((11, 1), "levenshtein"), ((11, 2), "wat is plus")]
        analyse = dt.vind_terugblik(_rijen(toen, nu), NU_DATUM)
        for k in analyse["kandidaten"]:
            assert not {"bank", "plus", "levenshtein"} & set(k["woorden"])


class TestStatus:
    def test_status_noemt_het_aantal_overgeslagen_vragen(self):
        analyse = dt.vind_terugblik(
            _rijen(_voorvoeg(TOEN, "wat is"), _voorvoeg(NU, "wat is")), NU_DATUM
        )
        tekst = dt.formatteer_status(analyse, NU_DATUM)
        assert f"Overgeslagen: {len(TOEN) + len(NU)}" in tekst

    def test_status_zonder_testvragen_heeft_geen_extra_regel(self):
        analyse = dt.vind_terugblik(_rijen(TOEN, NU), NU_DATUM)
        assert "Overgeslagen" not in dt.formatteer_status(analyse, NU_DATUM)