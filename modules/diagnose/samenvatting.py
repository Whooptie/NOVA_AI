# modules/diagnose/samenvatting.py
#
# Gesproken-achtige samenvatting van een zelftest (14 november 2026), zoals in de film:
# "Diagnose voltooid. Alle systemen functioneren normaal."
#
# WAT DOET DIT?
#   Bouwt uit het resultaat van een zelftest een paar korte zinnen in een vaste, rustige
#   stijl. Het is TEKST: Nova heeft geen stem. Een echte stem vraagt een spraakmotor
#   (tekst-naar-spraak); die staat bewust niet in Nova's kern (zie de projectregels voor
#   ML en externe specialisten).
#
# PUUR SYMBOLISCH: zinnen uit sjablonen. Geen generatie, geen ML. Alleen LEZEN.
# Elke zin komt uit een getal of een vaste uitkomst van de zelftest; niets wordt verzonnen
# en wat niet gemeten is, wordt niet genoemd.
#
# Dit bestand heeft bewust GEEN init_module(): het is een hulpbestand, geen module.
#
# TESTS: tests/test_zelftest_trend.py

from modules.diagnose import controles

MAX_PUNTEN = 3


def _opening(res):
    status = res.get("status")
    punten = res.get("punten") or []
    if status == "ok":
        return ["Diagnose voltooid.", "Alle systemen functioneren normaal."]
    if status == "fout":
        return ["Diagnose voltooid.", "Waarschuwing: er is iets mis."] + [f"Probleem: {p}." for p in punten[:MAX_PUNTEN]]
    if not punten:
        return ["Diagnose voltooid.", "Ik functioneer, maar er is iets om op te letten."]
    een = "er is een punt" if len(punten) == 1 else f"er zijn {len(punten)} punten"
    return ["Diagnose voltooid.", f"Ik functioneer, maar {een} dat aandacht verdient."] + \
           [f"Aandachtspunt: {p}." for p in punten[:MAX_PUNTEN]]


def _zin_tests(res):
    tests = res.get("pytest") or {}
    if not tests.get("gelukt"):
        return None
    return f"Al mijn {tests['geslaagd']} tests slagen."


def _zin_taal(res):
    taal = (res.get("benchmark") or {}).get("taal") or {}
    if not taal.get("gelukt") or not taal.get("router_totaal"):
        return None
    procent = 100.0 * taal["router_begrepen"] / taal["router_totaal"]
    return f"Ik begrijp {procent:.0f} procent van de zinnen die ik ken."


def _zin_geheugen(res):
    concepten = (res.get("consistentie") or {}).get("concepten")
    if concepten is None:
        return None
    return f"Mijn geheugen bevat {concepten} concepten."


def _zin_backup(res):
    backup = res.get("backup") or {}
    if not backup.get("gevonden") or backup.get("db_ok") is not True:
        return None
    return f"Mijn laatste back-up is {controles._tijdsduur(backup.get('leeftijd_uur') or 0)} oud en leesbaar."


def maak_samenvatting(res):
    """De samenvatting van een zelftest-resultaat als een paar korte zinnen op één regel."""
    if not res:
        return "Ik heb mezelf nog niet getest."
    zinnen = _opening(res)
    for maak_zin in (_zin_tests, _zin_taal, _zin_geheugen, _zin_backup):
        zin = maak_zin(res)
        if zin:
            zinnen.append(zin)
    return " ".join(zinnen)