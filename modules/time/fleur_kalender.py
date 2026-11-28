# modules/time/fleur_kalender.py

"""
fleur_kalender.py -- een privé-logboek van Kevin en Fleur, met kalender,
tellers en wat Nova er zelf uit leert.

Met Fleur's toestemming. Alles blijft lokaal in data/fleur_kalender.json
(niet op GitHub). Nova stuurt hier NOOIT uit zichzelf een bericht over en
antwoordt alleen op wat Kevin zegt; de antwoorden gaan niet naar de gsm.

WAT KEVIN KAN ZEGGEN (voorbeelden, alles begint met "fleur")
  fleur knuffelen ik begon                   -> datum en uur van nu worden zelf ingevuld
  fleur rug zij begon
  fleur seks samen
  fleur seks ik probeerde maar ze wilde niet -> "niet doorgegaan"
  fleur seks zij probeerde maar ik wilde niet
  fleur tetjes gisteren om 21:30             -> datum en/of uur zelf opgeven
  fleur kalender / fleur kalender oktober    -> de maand, per dag
  fleur overzicht / fleur overzicht seks vorige maand   -> tellers en verhoudingen
  fleur inzichten                            -> wat Nova er uit leert
  fleur laatste / fleur laatste 10
  fleur soorten / fleur soort toevoegen massage / fleur soort verwijderen massage
  fleur kalender laatste ongedaan            -> de laatste notering weghalen

Een woord dat Nova nog niet kent ("fleur massage ik begon") vraagt ze eerst:
  ja                  -> nieuwe soort, en de notering wordt bewaard
  nee                 -> niets bewaard
  knuffelen           -> (een bestaande soort) dan wordt het woord een andere naam ervoor

HOE "LEERT" NOVA?
Puur tellen en vergelijken, geen ML en geen generatie:
  - woorden: een onbekend woord kan een nieuwe soort of een andere naam worden;
  - weekdag en dagdeel waarop dingen vaak vallen;
  - wie het vaakst begint en of dat verandert;
  - hoe vaak iets niet doorging en wanneer;
  - de gemiddelde tijd tussen twee keer;
  - het verband met Fleur's cyclusfase (uit cyclus.py): is iets rond de eisprong,
    voor de eisprong, erna of tijdens de maandstonden vaker of minder vaak dan
    je op basis van het aantal dagen zou verwachten.
Ze meldt pas iets vanaf genoeg gegevens (MIN_VOOR_INZICHT) en noemt het altijd
een telling, geen verklaring: bij weinig gegevens kan het gewoon toeval zijn.
Inzichten komen alleen als Kevin ze vraagt ("fleur inzichten").

Puur symbolisch: opslaan, tellen, procenten, vergelijken.
"""

import json
import os
import re
import threading
from datetime import date, datetime, timedelta

from modules.paths import get_project_root
from modules.time import cyclus as cyc

STANDAARD_SOORTEN = {
    "knuffelen": ["knuffel", "knuffels", "knuffeltje"],
    "poepie": ["poepje"],
    "rug": ["rugmassage"],
    "tetjes": ["tetje"],
    "seks": [],
}

KEVIN, FLEUR, SAMEN, ONBEKEND = "kevin", "fleur", "samen", "onbekend"
GEDAAN, NIET = "gedaan", "niet doorgegaan"

BEVESTIG_SECONDEN = 300
MIN_VOOR_INZICHT = 8          # minder noteringen = nog te weinig om iets op te merken
MIN_VOOR_CYCLUS_INZICHT = 12
STANDAARD_LAATSTE = 5

DAGEN_KORT = ["ma", "di", "wo", "do", "vr", "za", "zo"]
DAGEN_LANG = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAANDEN_LANG = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                "september", "oktober", "november", "december"]
DAGDELEN = [("nacht", 0, 6), ("ochtend", 6, 12), ("middag", 12, 18), ("avond", 18, 24)]

RESERVED = {
    "kalender", "overzicht", "statistieken", "tellers", "teller", "inzichten", "inzicht", "leren",
    "soorten", "soort", "categorie", "categorieen", "categorieën", "laatste",
    "is", "heeft", "wil", "wordt", "zit", "hoe", "wat", "wanneer", "welke", "waar", "wie", "kan",
    "moet", "mag", "ze", "zij", "haar", "de", "het", "een", "en", "maar", "ik", "jij", "je",
    "maandstonden", "cyclus", "melding", "ongesteld", "vruchtbaar", "fase", "help", "ja", "nee",
}
FILLER = {"maar", "en", "heb", "hebben", "had", "hadden", "gedaan", "net", "ook", "dan"}

_BEGIN_WERKWOORD = (r"(?:begon|begonnen|startte|gestart|probeerde|geprobeerd|stelde voor|"
                    r"nam het initiatief)")
_WIE = r"(?P<wie>ik|zij|ze|fleur)"
_BEGIN_A = re.compile(rf"\b{_WIE}\s+(?:heb\s+|heeft\s+|had\s+|was\s+)?{_BEGIN_WERKWOORD}\b")
_BEGIN_B = re.compile(rf"\b{_BEGIN_WERKWOORD}\s+{_WIE}\b")
_SAMEN = re.compile(r"\b(?:samen|allebei|beiden|wederzijds)\b")
_NIET_A = re.compile(rf"\b(?:{_WIE}\s+)?(?:wilde|wou|wil)\s+(?:het\s+|dat\s+)?niet\b")
_NIET_B = re.compile(r"\b(?:niet doorgegaan|ging niet door|geweigerd|mislukt)\b")
_TIJD = re.compile(r"\b(?:om|rond|omstreeks)\s+(\d{1,2})(?:\s*[:.hu]\s*(\d{2}))?(?:\s*uur\b|\s*u\b|\s*h\b)?")
_TIJD_LOS = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_DATUM_WEG = re.compile(
    r"\b(?:op\s+|sinds\s+)?(?:eergisteren|gisteren|vandaag|daarnet|zonet|"
    r"(?:\d{1,3}|een|twee|drie|vier|vijf|zes|zeven|acht|negen|tien)\s+dagen?\s+geleden|"
    r"\d{1,2}\s*[/\-.]\s*\d{1,2}(?:\s*[/\-.]\s*\d{2,4})?|"
    r"\d{1,2}\s*(?:ste|de|e)?\s+(?:" + "|".join(sorted(cyc.MAANDEN, key=len, reverse=True)) + r")(?:\s+\d{4})?)\b")
_LEES_CIJFER = re.compile(r"\d")


# ======================================================================
# Pure hulpfuncties
# ======================================================================

def wie_label(wie):
    return {KEVIN: "jij", FLEUR: "Fleur", SAMEN: "jullie samen"}.get(wie, "")


def procent(deel, totaal):
    return round(100 * deel / totaal) if totaal else 0


def dagdeel(uur):
    for naam, van, tot in DAGDELEN:
        if van <= uur < tot:
            return naam
    return "nacht"


def lees_tijd(t):
    """Haalt een uur uit een zin ('om 21:30', 'om 9u', '21:30'). -> ((uur, min) | None, rest)."""
    for patroon in (_TIJD, _TIJD_LOS):
        m = patroon.search(t)
        if not m:
            continue
        uur = int(m.group(1))
        minuut = int(m.group(2)) if m.group(2) else 0
        if 0 <= uur <= 23 and 0 <= minuut <= 59:
            return (uur, minuut), (t[:m.start()] + " " + t[m.end():])
    return None, t


def lees_periode(spec, nu):
    """
    'deze maand' / 'vorige maand' / 'oktober' / 'oktober 2025' / 'dit jaar' / 'alles' ->
    (van, tot_exclusief, label, rest). Niets herkend = (None, None, 'alles', spec).
    """
    t = f" {spec.strip().lower()} "
    vandaag = nu.date()

    def maand(jaar, m):
        van = date(jaar, m, 1)
        tot = date(jaar + (m == 12), m % 12 + 1, 1)
        return van, tot, f"{MAANDEN_LANG[m - 1]} {jaar}"

    if " deze maand " in t:
        return (*maand(vandaag.year, vandaag.month), t.replace(" deze maand ", " ").strip())
    if " vorige maand " in t:
        j, m = (vandaag.year, vandaag.month - 1) if vandaag.month > 1 else (vandaag.year - 1, 12)
        return (*maand(j, m), t.replace(" vorige maand ", " ").strip())
    if " dit jaar " in t:
        return (date(vandaag.year, 1, 1), date(vandaag.year + 1, 1, 1), str(vandaag.year),
                t.replace(" dit jaar ", " ").strip())
    if " alles " in t:
        return None, None, "alles", t.replace(" alles ", " ").strip()
    for naam in sorted(cyc.MAANDEN, key=len, reverse=True):
        m = re.search(rf"\b{naam}\b(?:\s+(\d{{4}}))?", t)
        if m and len(naam) > 2:
            nr = cyc.MAANDEN[naam]
            if m.group(1):
                jaar = int(m.group(1))
            else:
                jaar = vandaag.year if nr <= vandaag.month else vandaag.year - 1
            rest = (t[:m.start()] + " " + t[m.end():]).strip()
            return (*maand(jaar, nr), rest)
    return None, None, "alles", t.strip()


# ======================================================================
# De module
# ======================================================================

class FleurKalender:
    def __init__(self, event_bus, pad=None, klok=None):
        self.event_bus = event_bus
        self.klok = klok or cyc.nu_lokaal
        self.pad = pad or (get_project_root(__file__) / "data" / "fleur_kalender.json")
        self.lock = threading.RLock()
        self.wachtend = None     # {"woord", "regel", "tijdstip"} tijdens een bevestigingsvraag
        self.status = self._laad()

    # ------------------------------------------------------------------
    # opslag
    # ------------------------------------------------------------------
    @staticmethod
    def _leeg():
        return {"soorten": {k: list(v) for k, v in STANDAARD_SOORTEN.items()}, "items": []}

    def _laad(self):
        basis = self._leeg()
        try:
            with open(self.pad, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if isinstance(data.get("soorten"), dict) and data["soorten"]:
                    basis["soorten"] = {str(k): [str(a) for a in v if isinstance(a, str)]
                                        for k, v in data["soorten"].items() if isinstance(v, list)}
                if isinstance(data.get("items"), list):
                    basis["items"] = [i for i in data["items"]
                                      if isinstance(i, dict) and i.get("datum") and i.get("soort")]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[FLEUR_KALENDER] Kon {self.pad} niet lezen, ik begin leeg: {e}")
        return basis

    def _bewaar(self):
        try:
            os.makedirs(os.path.dirname(self.pad), exist_ok=True)
            tmp = f"{self.pad}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.status, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.pad)
        except Exception as e:
            print(f"[FLEUR_KALENDER] Opslaan mislukt: {e}")

    # ------------------------------------------------------------------
    # soorten
    # ------------------------------------------------------------------
    def soort_van(self, woord):
        """Het woord (of een bijnaam) -> de echte soortnaam, of None."""
        woord = woord.strip().lower()
        for soort, namen in self.status["soorten"].items():
            if woord == soort or woord in namen:
                return soort
        return None

    def voeg_soort_toe(self, woord):
        woord = woord.strip().lower()
        if self.soort_van(woord):
            return f"'{woord}' ken ik al."
        self.status["soorten"][woord] = []
        self._bewaar()
        return f"Nieuwe soort toegevoegd: {woord}."

    def voeg_bijnaam_toe(self, woord, soort):
        woord = woord.strip().lower()
        if woord not in self.status["soorten"][soort]:
            self.status["soorten"][soort].append(woord)
            self._bewaar()

    def verwijder_soort(self, woord):
        soort = self.soort_van(woord)
        if soort is None:
            return f"'{woord}' ken ik niet als soort."
        del self.status["soorten"][soort]
        self._bewaar()
        return f"Soort '{soort}' verwijderd. De oude noteringen blijven bewaard."

    def tekst_soorten(self):
        regels = []
        for soort, namen in self.status["soorten"].items():
            regels.append(f"  {soort}" + (f" (ook: {', '.join(namen)})" if namen else ""))
        return "Soorten die ik ken:\n" + "\n".join(regels)

    # ------------------------------------------------------------------
    # noteringen
    # ------------------------------------------------------------------
    def items(self):
        return sorted(self.status["items"], key=lambda i: (i["datum"], i.get("tijd") or "00:00"))

    @staticmethod
    def _datum(i):
        return date.fromisoformat(i["datum"])

    def noteer(self, regel):
        with self.lock:
            self.status["items"].append(regel)
            self._bewaar()
        return self._tekst_genoteerd(regel)

    def _tekst_genoteerd(self, regel):
        d = self._datum(regel)
        wanneer = cyc.datum_kort(d) + (f" om {regel['tijd']}" if regel.get("tijd") else "")
        soort = regel["soort"]
        if regel["afloop"] == NIET:
            wie = []
            if regel["begon"] in (KEVIN, FLEUR):
                wie.append(f"{wie_label(regel['begon'])} probeerde")
            if regel.get("wilde_niet") in (KEVIN, FLEUR):
                wie.append(f"{wie_label(regel['wilde_niet'])} wilde niet")
            extra = f" ({', '.join(wie)})" if wie else ""
            tel = sum(1 for i in self.status["items"] if i["soort"] == soort and i["afloop"] == NIET
                      and i["datum"][:7] == regel["datum"][:7])
            return (f"Genoteerd: {soort} niet doorgegaan{extra}, {wanneer}. "
                    f"Niet doorgegaan: {tel}x in {MAANDEN_LANG[d.month - 1]}.")
        wie = ""
        if regel["begon"] == KEVIN:
            wie = ", jij begon"
        elif regel["begon"] == FLEUR:
            wie = ", Fleur begon"
        elif regel["begon"] == SAMEN:
            wie = ", jullie samen"
        deze_maand = sum(1 for i in self.status["items"] if i["soort"] == soort and i["afloop"] == GEDAAN
                         and i["datum"][:7] == regel["datum"][:7])
        totaal = sum(1 for i in self.status["items"] if i["soort"] == soort and i["afloop"] == GEDAAN)
        return (f"Genoteerd: {soort}, {wanneer}{wie}. "
                f"{soort.capitalize()}: {deze_maand}x in {MAANDEN_LANG[d.month - 1]}, {totaal}x in totaal.")

    def laatste_ongedaan(self):
        with self.lock:
            if not self.status["items"]:
                return "Er is niets om ongedaan te maken."
            items = self.items()
            weg = items[-1]
            self.status["items"].remove(weg)
            self._bewaar()
        return f"Verwijderd: {weg['soort']} van {cyc.datum_kort(self._datum(weg))}."

    # ------------------------------------------------------------------
    # een zin lezen
    # ------------------------------------------------------------------
    def parse_log(self, rest, nu):
        """
        Leest 'knuffelen ik begon gisteren om 21:30' (zonder het voorste 'fleur').
        -> dict(soort_woord, begon, afloop, wilde_niet, datum, tijd, fout) of None als dit
        geen logzin is.
        """
        t = rest
        afloop, wilde_niet = GEDAAN, None

        m = _NIET_A.search(t)
        if m:
            afloop = NIET
            subject = m.group("wie")
            wilde_niet = KEVIN if subject == "ik" else (FLEUR if subject else None)
            t = t[:m.start()] + " " + t[m.end():]
        m = _NIET_B.search(t)
        if m:
            afloop = NIET
            t = t[:m.start()] + " " + t[m.end():]

        begon = ONBEKEND
        for patroon in (_BEGIN_A, _BEGIN_B):
            m = patroon.search(t)
            if m:
                begon = KEVIN if m.group("wie") == "ik" else FLEUR
                t = t[:m.start()] + " " + t[m.end():]
                break
        else:
            m = _SAMEN.search(t)
            if m:
                begon = SAMEN
                t = t[:m.start()] + " " + t[m.end():]

        tijd, t = lees_tijd(t)
        datum = cyc.lees_datum(t, nu.date()) if _DATUM_WEG.search(t) else None
        heeft_datumvorm = bool(_DATUM_WEG.search(t))
        t = _DATUM_WEG.sub(" ", t)

        woorden = [w for w in re.split(r"[\s,]+", t) if w and w not in FILLER]

        if len(woorden) != 1:
            return None
        woord = woorden[0]

        if afloop == NIET and wilde_niet is None and begon in (KEVIN, FLEUR):
            wilde_niet = FLEUR if begon == KEVIN else KEVIN

        return {"woord": woord, "begon": begon, "afloop": afloop, "wilde_niet": wilde_niet,
                "datum": datum, "tijd": tijd, "datumvorm": heeft_datumvorm}

    def _maak_regel(self, soort, p, nu):
        datum = p["datum"] or nu.date()
        if p["tijd"] is not None:
            tijd = f"{p['tijd'][0]:02d}:{p['tijd'][1]:02d}"
        elif p["datum"] is None:
            tijd = nu.strftime("%H:%M")     # geen datum en geen uur genoemd: nu
        else:
            tijd = None                     # wel een datum, geen uur: uur blijft leeg
        return {"datum": datum.isoformat(), "tijd": tijd, "soort": soort, "begon": p["begon"],
                "afloop": p["afloop"], "wilde_niet": p["wilde_niet"]}

    # ------------------------------------------------------------------
    # binnenkomend bericht
    # ------------------------------------------------------------------
    def verwerk_zin(self, tekst):
        if not isinstance(tekst, str):
            return False
        t = " ".join(tekst.lower().strip().split())
        vraagteken = t.endswith("?")
        t = t.rstrip("?!. ").strip()
        if not t:
            return False

        antwoord = self._antwoord_op_vraag(t)
        if antwoord is None:
            antwoord = self._lees(t, vraagteken)
        if antwoord is None:
            return False
        self.event_bus.publish("chat_response", {"text": antwoord, "instant": True})
        return True

    # --- ja/nee op onze eigen vraag -------------------------------------
    def _antwoord_op_vraag(self, t):
        w = self.wachtend
        if w is None:
            return None
        if (self.klok() - w["tijdstip"]).total_seconds() > BEVESTIG_SECONDEN:
            self.wachtend = None
            return None
        if t in ("ja", "jep", "jawel", "yes", "ok", "oke", "oké", "ja graag", "doe maar"):
            self.wachtend = None
            tekst = self.voeg_soort_toe(w["woord"])
            regel = dict(w["regel"], soort=w["woord"])
            return f"{tekst} {self.noteer(regel)}"
        if t in ("nee", "neen", "nope", "nee hoor", "niet doen"):
            self.wachtend = None
            return "Oké, niets toegevoegd en niets genoteerd."
        soort = self.soort_van(t)
        if soort:
            self.wachtend = None
            self.voeg_bijnaam_toe(w["woord"], soort)
            regel = dict(w["regel"], soort=soort)
            return f"Onthouden: '{w['woord']}' is een andere naam voor {soort}. {self.noteer(regel)}"
        self.wachtend = None      # iets anders gezegd: de vraag vervalt, een losse "ja" later doet niets
        return None

    # --- commando's en logzinnen ----------------------------------------
    def _lees(self, t, vraagteken):
        if not re.match(r"^fleur\b", t):
            return None
        rest = t[5:].strip()
        if not rest:
            return None
        nu = self.klok()

        if re.fullmatch(r"kalender laatste (?:ongedaan|weg|verwijderen)", rest):
            return self.laatste_ongedaan()
        m = re.fullmatch(r"kalender(?:\s+(.+))?", rest)
        if m:
            van, tot, label, _ = lees_periode(m.group(1) or "deze maand", nu)
            if van is None:
                van, tot, label, _ = lees_periode("deze maand", nu)
            return self.tekst_kalender(van, tot, label)
        m = re.fullmatch(r"(?:overzicht|statistieken|tellers?)(?:\s+(.+))?", rest)
        if m:
            return self._overzicht_uit_spec(m.group(1) or "", nu)
        if re.fullmatch(r"(?:inzichten?|leren)", rest):
            return self.tekst_inzichten(nu)
        m = re.fullmatch(r"laatste(?:\s+(\d{1,2}))?", rest)
        if m:
            return self.tekst_laatste(int(m.group(1) or STANDAARD_LAATSTE))
        if re.fullmatch(r"(?:soorten|categorie[eë]n)", rest):
            return self.tekst_soorten()
        m = re.fullmatch(r"(?:soort|categorie)\s+toevoegen\s+([a-zà-ÿ]{2,30})", rest)
        if m:
            return self.voeg_soort_toe(m.group(1))
        m = re.fullmatch(r"(?:soort|categorie)\s+(?:verwijderen|weg)\s+([a-zà-ÿ]{2,30})", rest)
        if m:
            return self.verwijder_soort(m.group(1))

        if vraagteken:
            return None
        p = self.parse_log(rest, nu)
        if p is None:
            return None

        if p["datumvorm"] and p["datum"] is None:
            # het ziet eruit als een datum, maar het is geen leesbare (of een toekomstige)
            if self.soort_van(p["woord"]):
                return ("Die datum kon ik niet lezen of hij ligt in de toekomst. "
                        "Probeer bijvoorbeeld '12 november', '12/11' of 'gisteren'.")
            return None

        soort = self.soort_van(p["woord"])
        regel_zonder_soort = self._maak_regel(p["woord"], p, nu)
        if soort:
            return self.noteer(dict(regel_zonder_soort, soort=soort))

        woord = p["woord"]
        if (woord in RESERVED or len(woord) < 3 or not re.fullmatch(r"[a-zà-ÿ]+", woord)):
            return None
        self.wachtend = {"woord": woord, "regel": regel_zonder_soort, "tijdstip": nu}
        return (f"'{woord}' ken ik nog niet als soort. Zeg 'ja' om het als nieuwe soort toe te voegen "
                f"en dit te noteren, 'nee' om niets te doen, of de naam van een bestaande soort "
                f"({', '.join(self.status['soorten'])}) als het een andere naam daarvoor is.")

    # ------------------------------------------------------------------
    # kalender, laatste, overzicht
    # ------------------------------------------------------------------
    def _in_periode(self, van, tot):
        uit = []
        for i in self.items():
            d = self._datum(i)
            if (van is None or d >= van) and (tot is None or d < tot):
                uit.append(i)
        return uit

    @staticmethod
    def _kort(i):
        tekst = (f"{i['tijd']} " if i.get("tijd") else "") + i["soort"]
        if i["afloop"] == NIET:
            tekst += " niet doorgegaan"
            wie = []
            if i["begon"] in (KEVIN, FLEUR):
                wie.append(f"{wie_label(i['begon'])} probeerde")
            if i.get("wilde_niet") in (KEVIN, FLEUR):
                wie.append(f"{wie_label(i['wilde_niet'])} wilde niet")
            if wie:
                tekst += f" ({', '.join(wie)})"
        elif i["begon"] in (KEVIN, FLEUR):
            tekst += f" ({wie_label(i['begon'])} begon)"
        elif i["begon"] == SAMEN:
            tekst += " (samen)"
        return tekst

    def tekst_kalender(self, van, tot, label):
        items = self._in_periode(van, tot)
        if not items:
            return f"Fleur-kalender {label}: er staat niets genoteerd."
        regels = [f"📅 Fleur-kalender {label}"]
        per_dag = {}
        for i in items:
            per_dag.setdefault(i["datum"], []).append(i)
        for dag, lijst in per_dag.items():
            d = date.fromisoformat(dag)
            regels.append(f"  {DAGEN_KORT[d.weekday()]} {d.day:>2}  " + " · ".join(self._kort(i) for i in lijst))
        gedaan = [i for i in items if i["afloop"] == GEDAAN]
        niet = len(items) - len(gedaan)
        regels.append(f"Totaal: {len(gedaan)}x gedaan" + (f", {niet}x niet doorgegaan." if niet else "."))
        per_soort = {}
        for i in gedaan:
            per_soort[i["soort"]] = per_soort.get(i["soort"], 0) + 1
        if per_soort:
            regels.append("Per soort: " + ", ".join(f"{s} {n}x" for s, n in sorted(per_soort.items(), key=lambda x: -x[1])))
        return "\n".join(regels)

    def tekst_laatste(self, aantal):
        items = self.items()[-max(1, min(aantal, 30)):]
        if not items:
            return "Er staat nog niets genoteerd."
        regels = [f"Laatste {len(items)} noteringen:"]
        for i in reversed(items):
            d = self._datum(i)
            regels.append(f"  {cyc.datum_kort(d)}  {self._kort(i)}")
        return "\n".join(regels)

    def _overzicht_uit_spec(self, spec, nu):
        van, tot, label, rest = lees_periode(spec, nu)
        soort = None
        for woord in rest.split():
            soort = self.soort_van(woord) or soort
        return self.tekst_overzicht(van, tot, label, soort)

    def tekst_overzicht(self, van=None, tot=None, label="alles", soort=None):
        items = self._in_periode(van, tot)
        if soort:
            items = [i for i in items if i["soort"] == soort]
        titel = f"📊 Overzicht Fleur ({label}{', ' + soort if soort else ''})"
        if not items:
            return f"{titel}: er staat niets genoteerd."
        eerste, laatste = self._datum(items[0]), self._datum(items[-1])
        regels = [titel, f"  {len(items)} noteringen tussen {cyc.datum_kort(eerste)} en {cyc.datum_kort(laatste)}."]
        soorten = sorted({i["soort"] for i in items},
                         key=lambda s: -sum(1 for i in items if i["soort"] == s))
        for s in soorten:
            regels.append("  " + self._regel_voor_soort(s, [i for i in items if i["soort"] == s]))
        if len(soorten) > 1:
            regels.append("  Totaal: " + self._regel_voor_soort(None, items))
        return "\n".join(regels)

    @staticmethod
    def _regel_voor_soort(soort, items):
        gedaan = sum(1 for i in items if i["afloop"] == GEDAAN)
        niet = len(items) - gedaan
        delen = [f"{gedaan}x gedaan"]
        if niet:
            pogingen = f"{len(items)} {'poging' if len(items) == 1 else 'pogingen'}"
            delen.append(f"{niet}x niet doorgegaan ({procent(niet, len(items))}% van {pogingen})")
        tellers = {KEVIN: 0, FLEUR: 0, SAMEN: 0}
        for i in items:
            if i["begon"] in tellers:
                tellers[i["begon"]] += 1
        bekend = sum(tellers.values())
        if bekend:
            delen.append(f"begon: jij {tellers[KEVIN]} ({procent(tellers[KEVIN], bekend)}%), "
                         f"Fleur {tellers[FLEUR]} ({procent(tellers[FLEUR], bekend)}%)"
                         + (f", samen {tellers[SAMEN]}" if tellers[SAMEN] else ""))
        voorvoegsel = f"{soort}: " if soort else ""
        return voorvoegsel + ", ".join(delen) + "."

    # ------------------------------------------------------------------
    # leren: inzichten
    # ------------------------------------------------------------------
    def _cyclus(self):
        bus_modules = getattr(self.event_bus, "modules", None)
        getter = getattr(bus_modules, "get", None)
        return getter("cyclus") if callable(getter) else None

    def _fase_groep(self, d):
        """Fase-groep van Fleur op dag d, of None als dat niet te zeggen valt."""
        module = self._cyclus()
        if module is None:
            return None
        try:
            starts = module.starts()
            vorige = [s for s in starts if s <= d]
            if not vorige:
                return None
            start = vorige[-1]
            volgende = [s for s in starts if s > d]
            schatting = module.schatting()
            if volgende:
                lengte = (volgende[0] - start).days
            else:
                lengte = schatting["cyclus"]
                if d >= start + timedelta(days=int(round(lengte))):
                    return None
            if not cyc.MIN_CYCLUS <= lengte <= cyc.MAX_CYCLUS:
                return None
            fase = cyc.bepaal_fase(d, start, lengte, schatting["periode"])["fase"]
        except Exception:
            return None
        return {"menstruatie": "tijdens de maandstonden",
                "folliculaire fase": "voor de eisprong",
                "vruchtbaar venster": "rond de eisprong",
                "eisprong": "rond de eisprong",
                "net na de eisprong": "rond de eisprong",
                "luteale fase": "na de eisprong"}.get(fase)

    def tekst_inzichten(self, nu):
        items = self.items()
        gedaan = [i for i in items if i["afloop"] == GEDAAN]
        regels = ["🧠 Wat ik eruit leer (alleen tellingen, geen verklaringen)"]
        if not items:
            return regels[0] + "\n  Er staat nog niets genoteerd."
        regels.append(f"  {len(items)} noteringen, {len(gedaan)} gedaan en {len(items) - len(gedaan)} niet doorgegaan.")

        # hoe lang geleden, en de gewone tussentijd, per soort
        for soort in sorted({i["soort"] for i in gedaan}):
            data = sorted({self._datum(i) for i in gedaan if i["soort"] == soort})
            geleden = (nu.date() - data[-1]).days
            tekst = f"  {soort}: laatst {self._geleden(geleden)}"
            if len(data) >= 3:
                gaten = sorted((b - a).days for a, b in zip(data, data[1:]))
                mediaan = gaten[len(gaten) // 2] if len(gaten) % 2 else (gaten[len(gaten) // 2 - 1] + gaten[len(gaten) // 2]) / 2
                tekst += f", meestal {cyc.getal_tekst(mediaan)} dagen ertussen"
            regels.append(tekst + ".")

        if len(items) < MIN_VOOR_INZICHT:
            regels.append(f"  Nog te weinig om patronen te zien ({len(items)} van minstens {MIN_VOOR_INZICHT}). "
                          "Ik leer mee zodra er meer staat.")
            return "\n".join(regels)

        regels.extend(self._inzicht_tijdstip(gedaan))
        regels.extend(self._inzicht_wie(items))
        regels.extend(self._inzicht_niet(items))
        regels.extend(self._inzicht_cyclus(gedaan, nu))
        regels.append("  Let op: dit zijn tellingen. Bij weinig gegevens kan een patroon gewoon toeval zijn.")
        return "\n".join(regels)

    @staticmethod
    def _geleden(dagen):
        if dagen <= 0:
            return "vandaag"
        return "gisteren" if dagen == 1 else f"{dagen} dagen geleden"

    def _inzicht_tijdstip(self, gedaan):
        uit = []
        if len(gedaan) >= MIN_VOOR_INZICHT:
            dagen = [self._datum(i).weekday() for i in gedaan]
            top = max(range(7), key=dagen.count)
            if dagen.count(top) / len(dagen) >= 0.30:
                uit.append(f"  Vaakst op {DAGEN_LANG[top]}: {dagen.count(top)} van {len(dagen)} keer "
                           f"({procent(dagen.count(top), len(dagen))}%; gelijk verdeeld zou ±14% zijn).")
        met_uur = [int(i["tijd"][:2]) for i in gedaan if i.get("tijd")]
        if len(met_uur) >= MIN_VOOR_INZICHT:
            delen = [dagdeel(u) for u in met_uur]
            top = max(set(delen), key=delen.count)
            if delen.count(top) / len(delen) >= 0.5:
                uit.append(f"  Meestal {self._dagdeel_zin(top)}: {delen.count(top)} van {len(delen)} keer "
                           f"({procent(delen.count(top), len(delen))}%).")
        return uit

    @staticmethod
    def _dagdeel_zin(deel):
        return {"nacht": "'s nachts", "ochtend": "'s ochtends", "middag": "'s middags", "avond": "'s avonds"}[deel]

    def _inzicht_wie(self, items):
        uit = []
        bekend = [i for i in items if i["begon"] in (KEVIN, FLEUR, SAMEN)]
        if len(bekend) >= MIN_VOOR_INZICHT:
            k = sum(1 for i in bekend if i["begon"] == KEVIN)
            f = sum(1 for i in bekend if i["begon"] == FLEUR)
            uit.append(f"  Wie begint: jij {k}x ({procent(k, len(bekend))}%), Fleur {f}x ({procent(f, len(bekend))}%).")
            if len(bekend) >= 20:
                recent = bekend[-10:]
                rk = sum(1 for i in recent if i["begon"] == KEVIN)
                if abs(procent(rk, 10) - procent(k, len(bekend))) >= 20:
                    uit.append(f"  De laatste 10 keer begon jij {rk}x: dat wijkt af van het geheel "
                               f"({procent(k, len(bekend))}%).")
        return uit

    def _inzicht_niet(self, items):
        niet = [i for i in items if i["afloop"] == NIET]
        if not niet:
            return []
        uit = [f"  Niet doorgegaan: {len(niet)} van {len(items)} pogingen ({procent(len(niet), len(items))}%)."]
        if len(niet) >= 4:
            wie = [i["begon"] for i in niet if i["begon"] in (KEVIN, FLEUR)]
            if len(wie) >= 4:
                k = wie.count(KEVIN)
                uit.append(f"  Daarvan probeerde jij {k}x en Fleur {len(wie) - k}x.")
            met_uur = [dagdeel(int(i["tijd"][:2])) for i in niet if i.get("tijd")]
            if len(met_uur) >= 4:
                top = max(set(met_uur), key=met_uur.count)
                if met_uur.count(top) / len(met_uur) >= 0.5:
                    uit.append(f"  Meestal {self._dagdeel_zin(top)}: {met_uur.count(top)} van {len(met_uur)}.")
        return uit

    def _inzicht_cyclus(self, gedaan, nu):
        module = self._cyclus()
        if module is None:
            return []
        groepen = [self._fase_groep(self._datum(i)) for i in gedaan]
        bekend = [g for g in groepen if g]
        if len(bekend) < MIN_VOOR_CYCLUS_INZICHT:
            return [f"  Verband met Fleur's cyclus: nog te weinig gegevens ({len(bekend)} van minstens "
                    f"{MIN_VOOR_CYCLUS_INZICHT} die in een bekende cyclus vallen)."]

        eerste = min(self._datum(i) for i in gedaan)
        verwacht = {}
        dag, totaal = eerste, 0
        while dag <= nu.date():
            g = self._fase_groep(dag)
            if g:
                verwacht[g] = verwacht.get(g, 0) + 1
                totaal += 1
            dag += timedelta(days=1)
        if not totaal:
            return []

        uit, opgemerkt = [], False
        for groep in ("tijdens de maandstonden", "voor de eisprong", "rond de eisprong", "na de eisprong"):
            waargenomen = bekend.count(groep)
            deel_dagen = verwacht.get(groep, 0) / totaal
            if deel_dagen <= 0:
                continue
            deel_keren = waargenomen / len(bekend)
            verhouding = deel_keren / deel_dagen
            if (verhouding >= 1.5 and waargenomen >= 3) or verhouding <= 0.67:
                opgemerkt = True
                richting = "vaker" if verhouding >= 1.5 else "minder vaak"
                uit.append(f"  {groep.capitalize()}: {waargenomen} van {len(bekend)} keer ({procent(waargenomen, len(bekend))}%), "
                           f"terwijl die dagen {procent(verwacht[groep], totaal)}% van de tijd zijn: {richting} dan gemiddeld.")
        if not opgemerkt:
            uit.append("  Verband met Fleur's cyclus: geen duidelijk verschil tussen de fases (tot nu toe).")
        else:
            uit.insert(0, "  Verband met Fleur's cyclus (kalenderschatting van de fases):")
        return uit


def init_module(event_bus, sem=None):
    instance = FleurKalender(event_bus)
    event_bus.publish("module_loaded", {"name": "fleur_kalender"})
    return instance