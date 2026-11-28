# modules/time/cyclus.py

"""
cyclus.py -- maandstonden en cyclus van Fleur bijhouden, met meldingen.

WAT DOET DIT?
Kevin geeft door wanneer Fleur's maandstonden beginnen. Nova onthoudt elke
startdatum, rekent uit wanneer de volgende verwacht wordt, in welke fase
Fleur ongeveer zit, en meldt dat op tijd (op de gsm via ntfy, want ze
spreekt zoals alle proactieve berichten: ntfy_meldingen vangt dat op).

WAT KEVIN KAN ZEGGEN (voorbeelden)
  fleur is vandaag ongesteld geworden        -> startdatum vandaag
  fleur heeft haar maandstonden sinds gisteren
  maandstonden van fleur begonnen op 12 november
  ze is 3 dagen geleden ongesteld geworden
  fleur is niet meer ongesteld               -> einddatum (voor de periodelengte)
  ze is nog niet ongesteld                   -> na een melding: "ik vraag het morgen opnieuw"
  wanneer is fleur weer ongesteld
  in welke fase zit fleur / is ze vruchtbaar
  cyclus overzicht                           -> alle cycli + wat Nova eruit geleerd heeft
  fleur maandstonden laatste ongedaan        -> laatste datum verwijderen (typfout)
  fleur vruchtbaarheidsmeldingen aan|uit     -> melding bij begin vruchtbaar venster
  fleur melding 3 dagen vooraf               -> hoeveel dagen vooraf de melding komt
Komt ze vroeger of later dan verwacht, zeg dan gewoon dezelfde zin met de
echte datum: Nova past alles aan.

HOE "LEERT" NOVA?
Puur statistiek, geen ML: het gemiddelde van de laatste 6 cycli, waarbij de
nieuwste zwaarder tellen; de spreiding (kortste/langste); de gemiddelde
periodelengte; en hoeveel dagen Nova er gemiddeld naast zat bij haar
voorspelling. Met minder dan 3 cycli is het een grove schatting (standaard
28 dagen).

HOE WORDT DE FASE BEREKEND?
Kalendermethode: de eisprong valt ~14 dagen voor de volgende maandstonden.
Vruchtbaar venster = 5 dagen voor tot 1 dag na de eisprong, piek = de 3
dagen rond de eisprong. DIT IS EEN SCHATTING, GEEN METING. Bij een
onregelmatige cyclus kan het meerdere dagen afwijken. Niet gebruiken als
anticonceptie of om zwangerschap te plannen.

MELDINGEN (achtergrondthread, elke 5 min, enkel tussen 08:00 en 21:00)
  - X dagen vooraf (standaard 2), 1x per cyclus
  - op de verwachte dag zelf, 1x
  - elke dag dat ze over tijd is, tot Kevin een startdatum of "nog niet"
    doorgeeft (na 14 dagen nog 1 slotbericht, dan stopt het)
  - optioneel: begin vruchtbaar venster (standaard UIT)
Wat al gemeld is staat in het databestand, een herstart herhaalt dus niks.

PRIVACY
data/cyclus.json staat via .gitignore NIET op GitHub. Alles blijft lokaal.
Meldingen via ntfy gaan wel ongecodeerd over de server naar je gsm.

Puur symbolisch: datums, optellen, gemiddelden. Geen ML, geen generatie.
"""

import json
import os
import re
import threading
from datetime import date, datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

from modules.paths import get_project_root

NAAM_STANDAARD = "Fleur"

STANDAARD_CYCLUS = 28.0
STANDAARD_PERIODE = 5.0
LUTEAAL_DAGEN = 14          # eisprong ~14 dagen voor de volgende maandstonden
MIN_CYCLUS = 15             # kortere/langere tussenpozen tellen niet mee in het gemiddelde
MAX_CYCLUS = 60
MIN_TUSSENRUIMTE = 10       # minder dagen na de vorige start = waarschijnlijk een typfout
MAX_CYCLI_GEMIDDELDE = 6
GROVE_SCHATTING_ONDER = 3   # minder cycli dan dit = grove schatting
ONREGELMATIG_VANAF = 7      # verschil kortste/langste cyclus in dagen

MELDING_VAN_UUR = 8
MELDING_TOT_UUR = 21
LOOP_SECONDEN = 300
MAX_TE_LAAT_MELDINGEN = 14

VOORAF_STANDAARD = 2
VOORAF_MAX = 14

DAGEN_NL = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAANDEN_KORT = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]

MAANDEN = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2, "maart": 3, "mrt": 3,
    "april": 4, "apr": 4, "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
    "augustus": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
GETALWOORDEN = {"een": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7,
                "acht": 8, "negen": 9, "tien": 10}


# ======================================================================
# Pure hulpfuncties (alles hieronder is testbaar zonder bestanden of klok)
# ======================================================================

def nu_lokaal():
    """Huidige Belgische tijd (een container staat vaak op UTC)."""
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("Europe/Brussels")).replace(tzinfo=None)
        except Exception:
            pass
    return datetime.now()


def datum_kort(d):
    """date -> 'za 12 nov'."""
    return f"{DAGEN_NL[d.weekday()][:2]} {d.day} {MAANDEN_KORT[d.month - 1]}"


def dagen_tekst(n):
    n = abs(int(n))
    return f"{n} dag" if n == 1 else f"{n} dagen"


def getal_tekst(x):
    """27.0 -> '27', 27.64 -> '27,6'."""
    afgerond = round(x, 1)
    tekst = f"{int(afgerond)}" if afgerond == int(afgerond) else f"{afgerond:.1f}".replace(".", ",")
    return tekst


def lees_datum(tekst, vandaag):
    """
    Haalt een datum uit een zin. Kent: vandaag, gisteren, eergisteren,
    'N dagen geleden', '12 november', '12 nov 2026', '12/11', '12-11-2026'.
    Geeft een date terug, of None als er geen (geldige, niet-toekomstige) datum staat.
    Geen datum in de zin? Dan geeft de aanroeper zelf 'vandaag' als standaard.
    """
    t = tekst.lower()

    if re.search(r"\beergisteren\b", t):
        return vandaag - timedelta(days=2)
    if re.search(r"\bgisteren\b", t):
        return vandaag - timedelta(days=1)

    m = re.search(r"\b(\d{1,3}|" + "|".join(GETALWOORDEN) + r")\s+dagen?\s+geleden\b", t)
    if m:
        waarde = m.group(1)
        n = int(waarde) if waarde.isdigit() else GETALWOORDEN[waarde]
        return vandaag - timedelta(days=n)

    if re.search(r"\b(vandaag|daarnet|zonet)\b", t):
        return vandaag

    m = re.search(r"\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})(?:\s*[/\-.]\s*(\d{2,4}))?\b", t)
    if m:
        return _maak_datum(int(m.group(1)), int(m.group(2)), m.group(3), vandaag)

    m = re.search(r"\b(\d{1,2})\s*(?:ste|de|e)?\s+(" + "|".join(sorted(MAANDEN, key=len, reverse=True))
                  + r")\b(?:\s+(\d{4}))?", t)
    if m:
        return _maak_datum(int(m.group(1)), MAANDEN[m.group(2)], m.group(3), vandaag)

    return None


def _maak_datum(dag, maand, jaar_tekst, vandaag):
    """Bouwt een datum; zonder jaar kiezen we het meest recente verleden."""
    try:
        if jaar_tekst:
            jaar = int(jaar_tekst)
            if jaar < 100:
                jaar += 2000
            d = date(jaar, maand, dag)
        else:
            d = date(vandaag.year, maand, dag)
            if d > vandaag:
                d = date(vandaag.year - 1, maand, dag)
    except ValueError:
        return None
    return d if d <= vandaag else None


def cycluslengtes(starts):
    """Dagen tussen opeenvolgende startdatums (alle, ook buitenbeentjes)."""
    return [(b - a).days for a, b in zip(starts, starts[1:])]


def schat_cyclus(starts):
    """
    -> (gemiddelde, aantal_cycli, kortste, langste)
    Gewogen gemiddelde van de laatste 6 plausibele cycli (15-60 dagen); de
    nieuwste weegt het zwaarst. Geen cycli: (28, 0, None, None).
    """
    lengtes = [n for n in cycluslengtes(starts) if MIN_CYCLUS <= n <= MAX_CYCLUS]
    lengtes = lengtes[-MAX_CYCLI_GEMIDDELDE:]
    if not lengtes:
        return STANDAARD_CYCLUS, 0, None, None
    gewichten = list(range(1, len(lengtes) + 1))
    gemiddelde = sum(g * n for g, n in zip(gewichten, lengtes)) / sum(gewichten)
    return gemiddelde, len(lengtes), min(lengtes), max(lengtes)


def schat_periode(perioden):
    """Gewogen gemiddelde periodelengte uit de bekende (start, einde)-paren."""
    lengtes = [n for n in perioden if 1 <= n <= 14][-MAX_CYCLI_GEMIDDELDE:]
    if not lengtes:
        return STANDAARD_PERIODE
    gewichten = list(range(1, len(lengtes) + 1))
    return sum(g * n for g, n in zip(gewichten, lengtes)) / sum(gewichten)


def verwachte_start(laatste_start, cyclus):
    return laatste_start + timedelta(days=int(round(cyclus)))


def bepaal_fase(dag, laatste_start, cyclus, periode):
    """
    Fase en vruchtbaarheid voor één dag (kalendermethode).
    Geeft een dict met: cyclusdag, fase, vruchtbaarheid, eisprong, verwacht, te_laat.
    """
    cyclus_dagen = int(round(cyclus))
    periode_dagen = max(1, int(round(periode)))
    verwacht = laatste_start + timedelta(days=cyclus_dagen)
    eisprong = verwacht - timedelta(days=LUTEAAL_DAGEN)
    cyclusdag = (dag - laatste_start).days + 1

    uitslag = {"cyclusdag": cyclusdag, "eisprong": eisprong, "verwacht": verwacht, "te_laat": 0}

    if dag < laatste_start:
        uitslag.update(fase="onbekend", vruchtbaarheid="onbekend")
    elif dag >= verwacht:
        uitslag.update(fase="wachten op maandstonden", vruchtbaarheid="onzeker",
                       te_laat=(dag - verwacht).days)
    elif cyclusdag <= periode_dagen:
        uitslag.update(fase="menstruatie", vruchtbaarheid="niet vruchtbaar")
    elif dag < eisprong - timedelta(days=5):
        uitslag.update(fase="folliculaire fase", vruchtbaarheid="minder vruchtbaar")
    elif dag < eisprong - timedelta(days=2):
        uitslag.update(fase="vruchtbaar venster", vruchtbaarheid="vruchtbaar")
    elif dag <= eisprong:
        uitslag.update(fase="eisprong", vruchtbaarheid="zeer vruchtbaar (piek)")
    elif dag == eisprong + timedelta(days=1):
        uitslag.update(fase="net na de eisprong", vruchtbaarheid="minder vruchtbaar")
    else:
        uitslag.update(fase="luteale fase", vruchtbaarheid="niet vruchtbaar")
    return uitslag


# ======================================================================
# De module
# ======================================================================

class CyclusModule:
    def __init__(self, event_bus, pad=None, klok=None, start_loop=True):
        self.event_bus = event_bus
        self.klok = klok or nu_lokaal
        self.pad = pad or (get_project_root(__file__) / "data" / "cyclus.json")
        self.lock = threading.RLock()
        self.status = self._laad()

        if start_loop:
            draad = threading.Thread(target=self._loop, daemon=True)
            draad.start()

    # ------------------------------------------------------------------
    # opslag
    # ------------------------------------------------------------------
    @staticmethod
    def _leeg():
        return {
            "naam": NAAM_STANDAARD,
            "perioden": [],   # {"start": "2026-10-03", "einde": "2026-10-07"|None, "voorspeld": "..."|None}
            "vooraf_dagen": VOORAF_STANDAARD,
            "vruchtbaar_melding": False,
            "uitgesteld_tot": None,
            "gemeld": {},
        }

    def _laad(self):
        basis = self._leeg()
        try:
            with open(self.pad, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                basis.update({k: v for k, v in data.items() if k in basis})
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[CYCLUS] Kon {self.pad} niet lezen, ik begin leeg: {e}")
        if not isinstance(basis["perioden"], list):
            basis["perioden"] = []
        basis["perioden"] = [p for p in basis["perioden"] if isinstance(p, dict) and p.get("start")]
        basis["perioden"].sort(key=lambda p: p["start"])
        return basis

    def _bewaar(self):
        """Atomisch schrijven: eerst tijdelijk bestand, dan vervangen."""
        try:
            os.makedirs(os.path.dirname(self.pad), exist_ok=True)
            tmp = f"{self.pad}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.status, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.pad)
        except Exception as e:
            print(f"[CYCLUS] Opslaan mislukt: {e}")

    # ------------------------------------------------------------------
    # gegevens
    # ------------------------------------------------------------------
    @property
    def naam(self):
        return self.status.get("naam") or NAAM_STANDAARD

    def vandaag(self):
        return self.klok().date()

    def starts(self):
        return [date.fromisoformat(p["start"]) for p in self.status["perioden"]]

    def periodelengtes(self):
        uit = []
        for p in self.status["perioden"]:
            if p.get("einde"):
                uit.append((date.fromisoformat(p["einde"]) - date.fromisoformat(p["start"])).days + 1)
        return uit

    def schatting(self):
        """-> dict met cyclus, aantal, kortste, langste, periode, laatste_start, verwacht (of None)."""
        starts = self.starts()
        cyclus, aantal, kort, lang = schat_cyclus(starts)
        periode = schat_periode(self.periodelengtes())
        laatste = starts[-1] if starts else None
        return {
            "cyclus": cyclus, "aantal": aantal, "kortste": kort, "langste": lang,
            "periode": periode, "laatste_start": laatste,
            "verwacht": verwachte_start(laatste, cyclus) if laatste else None,
        }

    def gemiddelde_afwijking(self):
        """Hoeveel dagen Nova er gemiddeld naast zat; None bij minder dan 2 voorspellingen."""
        afw = []
        for p in self.status["perioden"]:
            if p.get("voorspeld"):
                afw.append(abs((date.fromisoformat(p["start"]) - date.fromisoformat(p["voorspeld"])).days))
        return (sum(afw) / len(afw)) if len(afw) >= 2 else None

    def _grove_schatting_tekst(self, s):
        delen = []
        if s["aantal"] < GROVE_SCHATTING_ONDER:
            if s["aantal"] == 0:
                bekend = "nog geen volledige cyclus"
            else:
                bekend = f"pas {s['aantal']} {'cyclus' if s['aantal'] == 1 else 'cycli'}"
            delen.append(f"Dit is nog een grove schatting: ik ken {bekend}.")
        elif s["langste"] - s["kortste"] > ONREGELMATIG_VANAF:
            delen.append(f"Haar cyclus wisselt ({s['kortste']} tot {s['langste']} dagen), "
                         "dus de schatting kan meerdere dagen afwijken.")
        delen.append("Het is een kalenderschatting, geen meting en geen anticonceptie.")
        return " ".join(delen)

    # ------------------------------------------------------------------
    # acties
    # ------------------------------------------------------------------
    def registreer_start(self, start):
        """Slaat een startdatum op. Geeft de antwoordtekst terug."""
        with self.lock:
            vandaag = self.vandaag()
            starts = self.starts()
            iso = start.isoformat()

            if start in starts:
                return f"Die startdatum ({datum_kort(start)}) had ik al voor {self.naam}."

            vorige = max((s for s in starts if s < start), default=None)
            if vorige is not None and (start - vorige).days < MIN_TUSSENRUIMTE:
                return (f"Dat is maar {dagen_tekst((start - vorige).days)} na de vorige start "
                        f"({datum_kort(vorige)}). Ik sla het niet op. Klopt de vorige datum niet, "
                        "zeg dan 'fleur maandstonden laatste ongedaan'.")

            voorspeld = None
            if vorige is not None and vorige == (starts[-1] if starts else None):
                voorspeld_dag = self.schatting()["verwacht"]
                if abs((start - voorspeld_dag).days) <= 20:
                    voorspeld = voorspeld_dag

            self.status["perioden"].append({
                "start": iso, "einde": None,
                "voorspeld": voorspeld.isoformat() if voorspeld else None,
            })
            self.status["perioden"].sort(key=lambda p: p["start"])
            self.status["uitgesteld_tot"] = None
            self._bewaar()

            s = self.schatting()
            regels = [f"Genoteerd: de maandstonden van {self.naam} begonnen op {datum_kort(start)}."]
            if vorige is not None:
                regels.append(f"Dat is een cyclus van {dagen_tekst((start - vorige).days)}.")
            if voorspeld is not None:
                verschil = (start - voorspeld).days
                if verschil == 0:
                    regels.append("Dat is precies wanneer ik ze verwachtte.")
                elif verschil < 0:
                    regels.append(f"Dat is {dagen_tekst(verschil)} vroeger dan ik verwachtte.")
                else:
                    regels.append(f"Dat is {dagen_tekst(verschil)} later dan ik verwachtte.")
            if s["aantal"]:
                regels.append(f"Haar gemiddelde cyclus is nu {getal_tekst(s['cyclus'])} dagen "
                              f"(over {s['aantal']} {'cyclus' if s['aantal'] == 1 else 'cycli'}).")
            verwacht = s["verwacht"]
            if verwacht >= vandaag:
                regels.append(f"De volgende verwacht ik rond {datum_kort(verwacht)}.")
            if s["aantal"] < GROVE_SCHATTING_ONDER:
                regels.append("Ik reken voorlopig met een grove schatting; vul nog wat cycli in "
                              "voor een betere.")
            return " ".join(regels)

    def registreer_einde(self, einde):
        with self.lock:
            if not self.status["perioden"]:
                return "Ik ken nog geen startdatum. Zeg eerst wanneer de maandstonden begonnen."
            laatste = self.status["perioden"][-1]
            start = date.fromisoformat(laatste["start"])
            if einde < start:
                return "Dat ligt voor de startdatum, dus ik laat het zo."
            lengte = (einde - start).days + 1
            if lengte > 14:
                return f"Dat zou {lengte} dagen duren, dat klopt waarschijnlijk niet. Ik sla het niet op."
            laatste["einde"] = einde.isoformat()
            self._bewaar()
            return (f"Genoteerd: de maandstonden duurden {dagen_tekst(lengte)}. "
                    f"Gemiddeld reken ik nu met {getal_tekst(self.schatting()['periode'])} dagen.")

    def nog_niet(self):
        with self.lock:
            s = self.schatting()
            if s["laatste_start"] is None:
                return "Ik ken nog geen startdatum, dus ik kan niets uitstellen."
            vandaag = self.vandaag()
            morgen = vandaag + timedelta(days=1)
            self.status["uitgesteld_tot"] = morgen.isoformat()
            self._bewaar()
            te_laat = (vandaag - s["verwacht"]).days
            extra = (f" Ze is nu {dagen_tekst(te_laat)} over tijd." if te_laat > 0 else "")
            return (f"Oké, {self.naam} is nog niet ongesteld.{extra} Ik vraag het morgen opnieuw, "
                    "tot je me een startdatum geeft.")

    def laatste_ongedaan(self):
        with self.lock:
            if not self.status["perioden"]:
                return "Er is niets om ongedaan te maken."
            weg = self.status["perioden"].pop()
            self.status["gemeld"] = {}
            self._bewaar()
            return f"Verwijderd: de startdatum {datum_kort(date.fromisoformat(weg['start']))}."

    def zet_vruchtbaar_melding(self, aan):
        with self.lock:
            self.status["vruchtbaar_melding"] = bool(aan)
            self._bewaar()
        return ("Ik meld nu ook wanneer het vruchtbare venster begint." if aan
                else "Ik meld het vruchtbare venster niet meer.")

    def zet_vooraf(self, dagen):
        if not 1 <= dagen <= VOORAF_MAX:
            return f"Kies een aantal tussen 1 en {VOORAF_MAX} dagen."
        with self.lock:
            self.status["vooraf_dagen"] = dagen
            self._bewaar()
        return f"Goed, ik meld de maandstonden voortaan {dagen_tekst(dagen)} vooraf."

    # ------------------------------------------------------------------
    # antwoorden op vragen
    # ------------------------------------------------------------------
    def tekst_fase(self):
        s = self.schatting()
        if s["laatste_start"] is None:
            return (f"Ik ken nog geen startdatum van {self.naam}. Zeg bijvoorbeeld: "
                    f"'{self.naam.lower()} is vandaag ongesteld geworden'.")
        vandaag = self.vandaag()
        f = bepaal_fase(vandaag, s["laatste_start"], s["cyclus"], s["periode"])
        regels = [f"{self.naam} zit op dag {f['cyclusdag']} van haar cyclus "
                  f"(gemiddeld {getal_tekst(s['cyclus'])} dagen)."]
        if f["te_laat"] or vandaag >= f["verwacht"]:
            regels.append(f"Fase: wachten op de maandstonden, ze is {dagen_tekst(f['te_laat'])} over "
                          f"tijd (verwacht {datum_kort(f['verwacht'])}). Vruchtbaarheid: onzeker, "
                          "de eisprong kan later geweest zijn dan de kalender denkt.")
        else:
            regels.append(f"Fase: {f['fase']}. Vruchtbaarheid: {f['vruchtbaarheid']}.")
            dagen_ov = (f["eisprong"] - vandaag).days
            if dagen_ov > 0:
                regels.append(f"Eisprong geschat rond {datum_kort(f['eisprong'])} (over {dagen_tekst(dagen_ov)}).")
            elif dagen_ov < 0:
                regels.append(f"Eisprong geschat rond {datum_kort(f['eisprong'])} (al geweest).")
            else:
                regels.append("De eisprong wordt vandaag geschat.")
            regels.append(f"Volgende maandstonden rond {datum_kort(f['verwacht'])} "
                          f"(over {dagen_tekst((f['verwacht'] - vandaag).days)}).")
        regels.append(self._grove_schatting_tekst(s))
        return " ".join(regels)

    def tekst_verwacht(self):
        s = self.schatting()
        if s["laatste_start"] is None:
            return f"Ik ken nog geen startdatum van {self.naam}."
        vandaag = self.vandaag()
        verschil = (s["verwacht"] - vandaag).days
        if verschil > 0:
            zin = f"{self.naam} wordt rond {datum_kort(s['verwacht'])} ongesteld (over {dagen_tekst(verschil)})."
        elif verschil == 0:
            zin = f"De maandstonden van {self.naam} worden vandaag verwacht."
        else:
            zin = (f"De maandstonden van {self.naam} werden rond {datum_kort(s['verwacht'])} verwacht; "
                   f"ze is {dagen_tekst(verschil)} over tijd.")
        return f"{zin} {self._grove_schatting_tekst(s)}"

    def tekst_overzicht(self):
        perioden = self.status["perioden"]
        if not perioden:
            return f"Ik heb nog geen cycli van {self.naam} opgeslagen."
        s = self.schatting()
        starts = self.starts()
        regels = [f"Cyclus van {self.naam}: {len(perioden)} startdatum(s) bekend."]
        laatste_vijf = starts[-6:]
        regels.append("Starts: " + ", ".join(datum_kort(d) for d in laatste_vijf) + ".")
        lengtes = cycluslengtes(starts)[-5:]
        if lengtes:
            regels.append("Laatste cycli (dagen): " + ", ".join(str(n) for n in lengtes) + ".")
        regels.append(f"Gemiddelde cyclus: {getal_tekst(s['cyclus'])} dagen"
                      + (f" (kortste {s['kortste']}, langste {s['langste']})." if s["aantal"] else " (standaard)."))
        regels.append(f"Gemiddelde maandstonden: {getal_tekst(s['periode'])} dagen"
                      + ("." if self.periodelengtes() else " (standaard, einddatums ken ik nog niet)."))
        afw = self.gemiddelde_afwijking()
        if afw is not None:
            regels.append(f"Mijn voorspelling zat er gemiddeld {getal_tekst(afw)} dagen naast.")
        regels.append(f"Melding: {self.status['vooraf_dagen']} dagen vooraf; "
                      f"vruchtbaarheidsmelding {'aan' if self.status['vruchtbaar_melding'] else 'uit'}.")
        return " ".join(regels)

    # ------------------------------------------------------------------
    # zinnen herkennen
    # ------------------------------------------------------------------
    _PERSOON = re.compile(r"\b(fleur|haar|ze|zij|vriendin)\b")
    _KEY = re.compile(r"\b(maandstonden?|ongesteld|menstruatie)\b")
    _VRAAG = re.compile(r"^(wanneer|welke|wat|hoe|hoelang|is|zit|moet|kan|wordt|hebben|heeft|in welke)\b")

    def verwerk_zin(self, tekst):
        """
        Probeert een zin als cyclus-commando te lezen. Geeft True terug als de zin
        van deze module was (het antwoord is dan al gepubliceerd), anders False.
        Alleen zinnen die over Fleur/haar/ze gaan worden opgepakt: een algemene
        vraag als "wat is ongesteld" blijft gewoon voor de rest van Nova.
        """
        if not isinstance(tekst, str):
            return False
        t = " ".join(tekst.lower().strip().split())
        is_vraag = t.endswith("?")
        t = t.rstrip("?!. ").strip()
        if not t:
            return False

        antwoord = self._lees_commando(t, is_vraag)
        if antwoord is None:
            return False
        self.event_bus.publish("layer4_response", {"text": antwoord})
        return True

    def _lees_commando(self, t, is_vraag):
        naam = self.naam.lower()
        persoon = bool(self._PERSOON.search(t))
        vandaag = self.vandaag()
        heeft_key = bool(self._KEY.search(t))

        # --- instellingen en beheer (moeten Fleur/maandstonden/cyclus noemen) ---
        if re.search(rf"\b{naam}\b|\bmaandstonden\b|\bcyclus\b", t):
            if (re.search(r"\blaatste\b.*\bongedaan\b|\bongedaan\b.*\blaatste\b|\bverwijder\b.*\blaatste\b", t)
                    and re.search(r"\bmaandstonden?\b|\bcyclus\b|\bongesteld\b|\bmenstruatie\b", t)):
                return self.laatste_ongedaan()
            m = re.search(r"vruchtbaarheid\w*\s*melding\w*\s*(aan|uit)|vruchtbaar\w*\s*melding\w*\s*(aan|uit)", t)
            if m:
                return self.zet_vruchtbaar_melding((m.group(1) or m.group(2)) == "aan")
            m = re.search(r"\bmelding\w*\s+(\d{1,2})\s+dagen?\s+vooraf\b", t)
            if m:
                return self.zet_vooraf(int(m.group(1)))
            if re.search(r"\bcyclus\b.*\b(overzicht|statistieken?|geschiedenis)\b|"
                         r"\b(overzicht|statistieken?|geschiedenis)\b.*\bcyclus\b|"
                         r"\bhoe lang is (haar|de|fleur\w*) cyclus\b|\bcyclus van " + naam + r"\b", t):
                return self.tekst_overzicht()

        if not (persoon and heeft_key) and not re.search(rf"\b{naam}\b.*\b(fase|vruchtbaar\w*|eisprong)\b", t) \
                and not re.search(r"\b(ze|zij|fleur)\b.*\b(vruchtbaar\w*|eisprong)\b|"
                                  r"\b(welke|in welke) fase\b.*\b(ze|zij|fleur|haar)\b", t):
            return None

        # --- nog niet ongesteld ---
        if re.search(r"\bnog (niet|geen)\b", t) and heeft_key:
            return self.nog_niet()

        # --- einde maandstonden ---
        if heeft_key and (re.search(r"\bniet meer ongesteld\b", t)
                          or re.search(r"\b(gedaan|gestopt|voorbij|afgelopen|klaar|over)\b", t)) and not is_vraag:
            einde = lees_datum(t, vandaag) or vandaag
            return self.registreer_einde(einde)

        # --- vragen ---
        vraagachtig = is_vraag or bool(self._VRAAG.match(t))
        if vraagachtig:
            if re.search(r"\bfase\b|vruchtbaar|eisprong|\bzit\b", t):
                return self.tekst_fase()
            if re.search(r"\bwanneer\b|\bverwacht\b|\bhoe lang\b|\bhoeveel dagen\b", t):
                return self.tekst_verwacht()
            if heeft_key:
                return self.tekst_fase()
            return None

        # --- fase/vruchtbaarheid zonder vraagteken ("fleur fase", "fleur vruchtbaar") ---
        if not heeft_key:
            return self.tekst_fase()

        # --- startdatum ---
        if heeft_key:
            start = lees_datum(t, vandaag)
            if start is None:
                if re.search(r"\d", t):
                    # er staat een cijfer in de zin, maar het is geen datum die ik kan lezen
                    # (of hij ligt in de toekomst): liever vragen dan een verkeerde datum opslaan
                    return ("Die datum kon ik niet lezen of hij ligt in de toekomst. "
                            "Probeer bijvoorbeeld '12 november', '12/11' of 'gisteren'.")
                start = vandaag   # geen datum genoemd: "ze is ongesteld geworden" = vandaag
            return self.registreer_start(start)
        return None

    # ------------------------------------------------------------------
    # meldingen (achtergrondthread)
    # ------------------------------------------------------------------
    def _loop(self):
        import time
        time.sleep(30)
        while True:
            try:
                self.controleer()
            except Exception as e:
                print(f"[CYCLUS] Fout in de meldingenlus (genegeerd): {e}")
            time.sleep(LOOP_SECONDEN)

    def controleer(self, nu=None):
        """
        Kijkt of er nu een melding moet komen en verstuurt ze (via layer4_response,
        dat ntfy_meldingen naar de gsm doorstuurt). Geeft de verstuurde teksten terug.
        """
        nu = nu or self.klok()
        if not (MELDING_VAN_UUR <= nu.hour < MELDING_TOT_UUR):
            return []

        with self.lock:
            s = self.schatting()
            if s["laatste_start"] is None:
                return []

            vandaag = nu.date()
            gemeld = self.status["gemeld"]
            verwacht = s["verwacht"]
            verwacht_iso = verwacht.isoformat()
            dagen_tot = (verwacht - vandaag).days
            vooraf = int(self.status.get("vooraf_dagen") or VOORAF_STANDAARD)
            teksten = []

            if 0 < dagen_tot <= vooraf and gemeld.get("voor") != verwacht_iso:
                teksten.append(f"{self.naam}: maandstonden verwacht over {dagen_tekst(dagen_tot)} "
                               f"({datum_kort(verwacht)}).")
                gemeld["voor"] = verwacht_iso

            if dagen_tot == 0 and gemeld.get("op") != verwacht_iso:
                teksten.append(f"{self.naam}: de maandstonden worden vandaag verwacht.")
                gemeld["op"] = verwacht_iso

            if dagen_tot < 0:
                teksten.extend(self._melding_te_laat(vandaag, verwacht, -dagen_tot, gemeld))

            if self.status.get("vruchtbaar_melding"):
                eisprong = verwacht - timedelta(days=LUTEAAL_DAGEN)
                if vandaag == eisprong - timedelta(days=5) and gemeld.get("vruchtbaar") != verwacht_iso:
                    teksten.append(f"{self.naam}: het vruchtbare venster begint vandaag "
                                   f"(eisprong geschat rond {datum_kort(eisprong)}).")
                    gemeld["vruchtbaar"] = verwacht_iso

            if teksten:
                self._bewaar()

        for tekst in teksten:
            self.event_bus.publish("layer4_response", {"text": tekst})
        return teksten

    def _melding_te_laat(self, vandaag, verwacht, dagen_te_laat, gemeld):
        uitgesteld = self.status.get("uitgesteld_tot")
        if uitgesteld and vandaag.isoformat() < uitgesteld:
            return []
        if gemeld.get("te_laat_dag") == vandaag.isoformat():
            return []
        if dagen_te_laat > MAX_TE_LAAT_MELDINGEN:
            return []
        gemeld["te_laat_dag"] = vandaag.isoformat()
        if dagen_te_laat == MAX_TE_LAAT_MELDINGEN:
            return [f"{self.naam} is al {dagen_tekst(dagen_te_laat)} over tijd. Ik stop met dagelijks "
                    "melden. Zeg het als de maandstonden begonnen zijn."]
        return [f"{self.naam} is {dagen_tekst(dagen_te_laat)} over tijd (verwacht {datum_kort(verwacht)}). "
                f"Zeg 'ze is nog niet ongesteld' of geef de startdatum door."]


def init_module(event_bus, sem=None):
    start_loop = not os.getenv("PYTEST_CURRENT_TEST")
    instance = CyclusModule(event_bus, start_loop=start_loop)
    event_bus.publish("module_loaded", {"name": "cyclus"})
    return instance