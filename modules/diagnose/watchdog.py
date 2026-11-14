# modules/diagnose/watchdog.py
#
# Watchdog (14 november 2026): hoor je het als Nova helemaal wegvalt, en bereiken
# haar meldingen je gsm nog?
#
# HET PROBLEEM
#   De zelftest draait IN Nova. Valt Nova zelf weg (crash, container gestopt, server uit,
#   netwerk weg), dan draait de zelftest ook niet meer en meldt dus niemand iets. Je merkt het
#   pas als je het zelf probeert. Alleen een controle van BUITEN kan dat zien.
#
# WAT DOET DEZE MODULE?
#   1. LEVENSSIGNAAL ("ik leef"): elke paar minuten doet Nova een webaanvraag naar een adres
#      BUITEN de container. Blijft die aanvraag weg, dan slaat de externe dienst alarm bij jou.
#      Geschikte (gratis) diensten:
#        - healthchecks.io    maak een check, kopieer de "ping URL"
#        - Uptime Kuma        maak een "Push"-monitor, kopieer de push-URL
#        - een tweede ntfy-topic op een ANDERE plek dan Nova zelf (bv. ntfy.sh)
#      De dienst wacht op het signaal en stuurt jou een melding als het uitblijft. Nova zelf
#      hoeft dan niet meer te leven om je te waarschuwen.
#   2. WEKELIJKSE TESTMELDING: een testbericht via ntfy naar je gsm, zodat je zeker weet dat een
#      echt alarm je ook bereikt. Mislukt het, dan probeert Nova het elk uur opnieuw en zegt de
#      zelftest het (na 3 keer als fout).
#
# INSTELLINGEN (in .env, NIET in de code; alles staat standaard UIT):
#   NOVA_HARTSLAG_URL=https://hc-ping.com/jouw-uuid-hier     het adres dat Nova aanroept
#   NOVA_HARTSLAG_MINUTEN=10                                 om de zoveel minuten (1-1440, standaard 10)
#   NOVA_HARTSLAG_METHODE=get|post                           standaard get (past bij beide diensten)
#   NOVA_MELDINGSTEST=zondag 10:00                           dag en tijd, of alleen 10:00 = elke dag,
#                                                            of uit (standaard)
#   Het adres lijkt op een wachtwoord (wie het kent, kan 'ik leef' doen): het komt NOOIT in het
#   log of in een foutmelding.
#
# COMMANDO'S (via modules/debug/debug_commands.py):
#   zelftest hartslag      stuurt nu een levenssignaal en toont de stand
#   zelftest meldingstest  stuurt nu een testmelding naar je gsm
#
# VEILIGHEID
#   - Alles in een eigen achtergrondthread met een time-out van 10 seconden: een trage of
#     afwezige dienst houdt Nova nooit op.
#   - De stand staat in data/hartslag_status.json; de zelftest leest dat (controle "meldingen").
#   - Een testmelding gaat alleen tussen 08:00 en 22:00 (geen piepende gsm 's nachts).
#   - Tijdens een pytest-run wordt .env niet gelezen (een test mag nooit echt pingen).
#
# PUUR SYMBOLISCH: een webaanvraag en een klok. Geen ML.
# AUTO-DISCOVERY: staat in modules/diagnose/ en heeft init_module(event_bus, sem).
#
# TESTS: tests/test_watchdog.py

import json
import os
import re
import threading
from datetime import datetime, timedelta, time as dagtijd
from pathlib import Path

try:
    import requests
except ImportError:                       # zonder 'requests' kan de module niets sturen
    requests = None

URL_NAAM = "NOVA_HARTSLAG_URL"
MINUTEN_NAAM = "NOVA_HARTSLAG_MINUTEN"
METHODE_NAAM = "NOVA_HARTSLAG_METHODE"
TEST_NAAM = "NOVA_MELDINGSTEST"

HARTSLAG_STANDAARD_MINUTEN = 10
TIMEOUT_SECONDEN = 10
TIK_SECONDEN = 30                         # hoe vaak de achtergrondthread kijkt of er iets moet
EERSTE_TIK_SECONDEN = 10                  # eerste keer vlak na het opstarten
HERPROBEER_HARTSLAG_MINUTEN = 5           # na een mislukte ping sneller opnieuw (maximaal het interval)
HERPROBEER_TEST_MINUTEN = 60              # na een mislukte testmelding elk uur opnieuw
TEST_VANAF_UUR, TEST_TOT_UUR = 8, 22      # testmeldingen alleen overdag

DAGEN = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")
DAG_AFKORTINGEN = {"ma": 0, "di": 1, "wo": 2, "do": 3, "vr": 4, "za": 5, "zo": 6}


# ----------------------------------------------------------------------------
# Kleine hulpfuncties (los te testen)
# ----------------------------------------------------------------------------

def parse_schema(tekst):
    """
    'zondag 10:00' -> (6, time(10, 0)); '10:00' of 'elke dag 10:00' -> (None, time(10, 0)).
    'uit', leeg of onzin -> None.
    """
    ruw = (tekst or "").strip().lower()
    if ruw in ("", "uit", "nee", "0", "false", "off"):
        return None
    uur_min = None
    m = re.search(r"(\d{1,2})[:.u](\d{2})", ruw)
    if m:
        uur, minuut = int(m.group(1)), int(m.group(2))
        if 0 <= uur <= 23 and 0 <= minuut <= 59:
            uur_min = dagtijd(uur, minuut)
    if uur_min is None:
        return None
    for woord in re.findall(r"[a-z]+", ruw):
        if woord in DAGEN:
            return DAGEN.index(woord), uur_min
        if woord in DAG_AFKORTINGEN:
            return DAG_AFKORTINGEN[woord], uur_min
    return None, uur_min


def schema_tekst(schema):
    if not schema:
        return "uit"
    dag, tijd = schema
    return f"{DAGEN[dag] if dag is not None else 'elke dag'} {tijd.strftime('%H:%M')}"


def laatste_moment(nu, schema):
    """Het meest recente tijdstip (<= nu) waarop de testmelding volgens het schema had moeten komen."""
    dag, tijd = schema
    kandidaat = datetime.combine(nu.date(), tijd)
    if dag is None:
        return kandidaat if kandidaat <= nu else kandidaat - timedelta(days=1)
    verschil = (nu.weekday() - dag) % 7
    kandidaat -= timedelta(days=verschil)
    return kandidaat if kandidaat <= nu else kandidaat - timedelta(days=7)


def _iso(tijd):
    return tijd.isoformat(timespec="seconds") if tijd else None


def _van_iso(tekst):
    try:
        return datetime.fromisoformat(tekst)
    except (TypeError, ValueError):
        return None


def _standaard_http(methode, url, timeout):
    return requests.request(methode.upper(), url, timeout=timeout)


# ----------------------------------------------------------------------------
# De module zelf
# ----------------------------------------------------------------------------

class Watchdog:
    def __init__(self, event_bus, project_root=None, hartslag_url=None, hartslag_minuten=None,
                 methode=None, meldingstest=None, http=None, klok=None, achtergrond=None,
                 status_pad=None, drukaf=None, stuur_test=None):
        # Alles na event_bus bestaat vooral voor de tests. In Nova zelf wordt niets
        # meegegeven: dan komt alles uit .env.
        self.event_bus = event_bus
        if project_root is None:
            from modules.paths import get_project_root
            project_root = get_project_root(__file__)
        self.root = Path(project_root)
        self._status_pad = Path(status_pad) if status_pad else self.root / "data" / "hartslag_status.json"
        self._print = drukaf or print
        self._http = http or (_standaard_http if requests is not None else None)
        self._klok = klok or datetime.now
        self._stuur_test = stuur_test

        # module_loader laadt deze module vóór ntfy_meldingen, dus .env is op dit punt misschien
        # nog niet ingelezen. Niet tijdens pytest: dan mag een echt .env tests niet beïnvloeden.
        if not os.getenv("PYTEST_CURRENT_TEST"):
            self._laad_dotenv()
        zonder_omgeving = bool(os.getenv("PYTEST_CURRENT_TEST"))

        url = self._instelling(hartslag_url, URL_NAAM, zonder_omgeving)
        self._url = url if url.lower().startswith(("http://", "https://")) else ""
        if url and not self._url:
            self._print(f"[WATCHDOG] {URL_NAAM} moet met http:// of https:// beginnen: levenssignaal staat UIT.")
        self._minuten = self._lees_minuten(self._instelling(hartslag_minuten, MINUTEN_NAAM, zonder_omgeving))
        methode = self._instelling(methode, METHODE_NAAM, zonder_omgeving).lower()
        self._methode = methode if methode in ("get", "post") else "get"
        self._schema = parse_schema(self._instelling(meldingstest, TEST_NAAM, zonder_omgeving))
        self._hartslag_aan = bool(self._url and self._http)

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        nu = self._klok()
        self._status = {
            "versie": 1, "opgestart": _iso(nu), "bijgewerkt": _iso(nu),
            "hartslag": {"aan": self._hartslag_aan, "interval_min": self._minuten, "laatste_ok": None,
                         "laatste_poging": None, "fouten_op_rij": 0, "reden": None},
            "meldingstest": {"aan": self._schema is not None, "schema": schema_tekst(self._schema),
                             "laatste_ok": None, "laatste_poging": None, "fouten_op_rij": 0, "reden": None},
        }
        self._neem_vorige_stand_over()
        self._bewaar_status()

        if achtergrond is None:
            achtergrond = not os.getenv("PYTEST_CURRENT_TEST")
        if not (self._hartslag_aan or self._schema):
            self._print(f"[WATCHDOG] Staat UIT: {URL_NAAM} en {TEST_NAAM} ontbreken in .env "
                        "(levenssignaal en testmelding zijn optioneel).")
            return
        plan = []
        if self._hartslag_aan:
            plan.append(f"levenssignaal elke {self._minuten} minuten naar buiten")
        if self._schema:
            plan.append(f"testmelding {schema_tekst(self._schema)}")
        self._print("[WATCHDOG] Aan: " + " en ".join(plan) + ".")
        if achtergrond:
            self._thread = threading.Thread(target=self._lus, daemon=True, name="watchdog")
            self._thread.start()

    # -- instellingen --------------------------------------------------------

    def _laad_dotenv(self):
        try:
            from dotenv import load_dotenv
            load_dotenv(self.root / ".env")
        except Exception:
            pass

    @staticmethod
    def _instelling(waarde, naam, zonder_omgeving):
        """Een meegegeven waarde (tests), anders .env/omgeving. Tijdens pytest nooit de omgeving."""
        if waarde is not None:
            return str(waarde).strip()
        return "" if zonder_omgeving else os.getenv(naam, "").strip()

    @staticmethod
    def _lees_minuten(ruw):
        try:
            return min(max(int(ruw), 1), 1440)
        except (TypeError, ValueError):
            return HARTSLAG_STANDAARD_MINUTEN

    # -- de stand bewaren ----------------------------------------------------

    def _neem_vorige_stand_over(self):
        """Na een herstart onthouden we het laatste succes, zodat een testmelding niet opnieuw komt."""
        try:
            with open(self._status_pad, encoding="utf-8") as f:
                oud = json.load(f)
        except (OSError, ValueError):
            return
        for sleutel in ("hartslag", "meldingstest"):
            vorig = oud.get(sleutel) if isinstance(oud, dict) else None
            if isinstance(vorig, dict):
                for veld in ("laatste_ok", "laatste_poging", "fouten_op_rij", "reden"):
                    if veld in vorig:
                        self._status[sleutel][veld] = vorig[veld]

    def _bewaar_status(self):
        with self._lock:
            self._status["bijgewerkt"] = _iso(self._klok())
            try:
                self._status_pad.parent.mkdir(parents=True, exist_ok=True)
                tijdelijk = self._status_pad.with_name(self._status_pad.name + ".tmp")
                with open(tijdelijk, "w", encoding="utf-8") as f:
                    json.dump(self._status, f, ensure_ascii=False, indent=1)
                os.replace(tijdelijk, self._status_pad)
            except OSError:
                pass                                   # de stand is hulpinfo; nooit Nova ophouden

    # -- levenssignaal -------------------------------------------------------

    def _masker(self, tekst):
        """Haalt het adres (dat als wachtwoord werkt) uit een foutmelding."""
        tekst = str(tekst)
        for stuk in (self._url, self._url.split("://", 1)[-1], self._url.rsplit("/", 1)[-1]):
            if stuk and len(stuk) > 6:
                tekst = tekst.replace(stuk, "<adres>")
        return tekst

    def _hartslag_nodig(self, nu):
        h = self._status["hartslag"]
        laatste = _van_iso(h.get("laatste_poging"))
        if laatste is None:
            return True
        wacht = self._minuten if not h["fouten_op_rij"] else min(self._minuten, HERPROBEER_HARTSLAG_MINUTEN)
        return nu - laatste >= timedelta(minutes=wacht)

    def stuur_hartslag(self):
        """Eén levenssignaal. Geeft (gelukt, reden). Gooit nooit een fout naar buiten."""
        nu = self._klok()
        h = self._status["hartslag"]
        if not self._hartslag_aan:
            return False, "het levenssignaal staat uit"
        reden = None
        try:
            antwoord = self._http(self._methode, self._url, TIMEOUT_SECONDEN)
            status = getattr(antwoord, "status_code", None)
            gelukt = isinstance(status, int) and 200 <= status < 300
            if not gelukt:
                reden = f"de dienst antwoordde {status}"
        except Exception as e:
            gelukt, reden = False, self._masker(f"{type(e).__name__}: {e}")
        h["laatste_poging"] = _iso(nu)
        if gelukt:
            if h["fouten_op_rij"] >= 3:
                self._print("[WATCHDOG] Levenssignaal komt weer aan.")
            h["laatste_ok"], h["fouten_op_rij"], h["reden"] = _iso(nu), 0, None
        else:
            h["fouten_op_rij"] += 1
            h["reden"] = reden
            if h["fouten_op_rij"] == 3:
                self._print(f"[WATCHDOG] Levenssignaal mislukt ({reden}); ik probeer het elke "
                            f"{min(self._minuten, HERPROBEER_HARTSLAG_MINUTEN)} minuten opnieuw.")
        self._bewaar_status()
        return gelukt, reden

    # -- testmelding ---------------------------------------------------------

    def _vind_module(self, naam):
        for bron_naam in ("modules", "loaded_modules"):
            bron = getattr(self.event_bus, bron_naam, None)
            ophaal = getattr(bron, "get", None)
            if callable(ophaal):
                module = ophaal(naam)
                if module is not None:
                    return module
        return None

    def _stuur_via_ntfy(self, tekst):
        ntfy = self._vind_module("ntfy_meldingen")
        if ntfy is None or not getattr(ntfy, "aan", False):
            return False, "ntfy staat uit of is niet geladen"
        gelukt = ntfy._verstuur(tekst, meld_fout=False)
        return bool(gelukt), (None if gelukt else "de ntfy-server nam het bericht niet aan")

    def _test_nodig(self, nu):
        if not self._schema:
            return False
        if not (TEST_VANAF_UUR <= nu.hour < TEST_TOT_UUR):
            return False
        t = self._status["meldingstest"]
        moment = laatste_moment(nu, self._schema)
        laatste_ok = _van_iso(t.get("laatste_ok"))
        if laatste_ok is not None and laatste_ok >= moment:
            return False
        poging = _van_iso(t.get("laatste_poging"))
        if poging is not None and poging >= moment and nu - poging < timedelta(minutes=HERPROBEER_TEST_MINUTEN):
            return False
        return True

    def stuur_testmelding(self):
        """Eén testmelding naar je gsm. Geeft (gelukt, reden). Gooit nooit een fout naar buiten."""
        nu = self._klok()
        tekst = (f"Meldingstest van Nova ({nu.strftime('%d-%m %H:%M')}): "
                 "als je dit leest, bereiken mijn meldingen je gsm.")
        try:
            gelukt, reden = (self._stuur_test or self._stuur_via_ntfy)(tekst)
        except Exception as e:
            gelukt, reden = False, f"{type(e).__name__}"
        t = self._status["meldingstest"]
        t["laatste_poging"] = _iso(nu)
        if gelukt:
            t["laatste_ok"], t["fouten_op_rij"], t["reden"] = _iso(nu), 0, None
        else:
            t["fouten_op_rij"] += 1
            t["reden"] = reden
            self._print(f"[WATCHDOG] Testmelding naar de gsm mislukt ({reden}); ik probeer het over "
                        f"{HERPROBEER_TEST_MINUTEN} minuten opnieuw.")
        self._bewaar_status()
        return gelukt, reden

    # -- de lus --------------------------------------------------------------

    def tik(self):
        """Eén controleronde: stuurt wat nu moet. Wordt elke TIK_SECONDEN aangeroepen."""
        nu = self._klok()
        if self._hartslag_aan and self._hartslag_nodig(nu):
            self.stuur_hartslag()
        if self._test_nodig(nu):
            self.stuur_testmelding()

    def _lus(self):
        wacht = EERSTE_TIK_SECONDEN
        while not self._stop.wait(wacht):
            try:
                self.tik()
            except Exception as e:                      # de lus mag nooit sterven
                self._print(f"[WATCHDOG] Fout in de controleronde: {type(e).__name__}")
            wacht = TIK_SECONDEN

    # -- op commando ---------------------------------------------------------

    def ping_nu(self):
        if not self._hartslag_aan:
            return (f"Het levenssignaal staat uit. Zet {URL_NAAM} in .env (bv. een healthchecks.io-"
                    "ping-adres of een Uptime Kuma push-adres) en herstart me.")
        gelukt, reden = self.stuur_hartslag()
        kop = "Levenssignaal verstuurd." if gelukt else f"Levenssignaal MISLUKT: {reden}."
        return kop + "\n" + self.status_tekst()

    def meldingstest_nu(self):
        gelukt, reden = self.stuur_testmelding()
        return ("Testmelding verstuurd: kijk of hij op je gsm aankomt." if gelukt
                else f"Testmelding MISLUKT: {reden}.")

    def status_tekst(self):
        nu = self._klok()
        h, t = self._status["hartslag"], self._status["meldingstest"]

        def leeftijd(iso):
            tijd = _van_iso(iso)
            if tijd is None:
                return "nog nooit"
            minuten = (nu - tijd).total_seconds() / 60
            return f"{minuten:.0f} min geleden" if minuten < 120 else f"{minuten / 60:.0f} uur geleden"

        regels = []
        if h["aan"]:
            regels.append(f"Levenssignaal: elke {h['interval_min']} min, laatste gelukt {leeftijd(h['laatste_ok'])}"
                          + (f", {h['fouten_op_rij']} mislukt op rij" if h["fouten_op_rij"] else "") + ".")
        else:
            regels.append("Levenssignaal: uit.")
        if t["aan"]:
            regels.append(f"Testmelding: {t['schema']}, laatste gelukt {leeftijd(t['laatste_ok'])}.")
        else:
            regels.append("Testmelding: uit.")
        return "\n".join(regels)

    def shutdown(self):
        self._stop.set()


def init_module(event_bus, sem=None):
    """Standaard module_loader-conventie: init_module(event_bus, sem). 'sem' wordt niet gebruikt."""
    instance = Watchdog(event_bus)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "watchdog"})
    return instance