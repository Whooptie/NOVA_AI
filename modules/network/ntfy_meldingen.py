# modules/network/ntfy_meldingen.py

"""
Meldingen naar de gsm via ntfy (punt 55, stap 2a).

WAT LOST DIT OP?
Nova spreekt soms uit zichzelf (weerwaarschuwing, regen, pauze, ...). Zo'n
bericht verschijnt alleen in Nova's eigen terminal. Is je laptop dicht of in
standby, dan ziet niemand het. Deze module stuurt zulke berichten ERBIJ naar
je gsm, via ntfy (een klein meldingsprogramma dat op battleserver draait).

DE REGEL (kort)
- Een antwoord op iets wat JIJ typte gaat nooit naar de gsm.
- Een spontaan (proactief) bericht gaat naar de gsm, TENZIJ je op dat moment
  actief op de laptop bent. Dan zie je het toch in de terminal.
- "Actief op de laptop" betekent: de laptop is verbonden, NIET vergrendeld,
  en de laptop meldt de laatste 45 seconden dat je actief bent.
- Bij twijfel (geen data, fout, module niet gevonden) gaat het naar de gsm:
  liever een melding te veel dan een gemiste melding.
- De terminal verandert NIET: de berichten worden daar nog steeds getoond.
  De gsm komt er alleen bovenop.

HOE WEET DEZE MODULE WELK BERICHT PROACTIEF IS?
Hetzelfde als afwezigheid.py: een bericht dat NIET uit de hoofdthread komt,
is niet het antwoord op wat jij net typte, dus proactief.

HOE WORDT HET AUTOMATISCH GELADEN?
module_loader.py vindt dit bestand vanzelf (init_module onderaan). De module
abonneert zich zelf op "chat_response". In main.py hoeft niets te veranderen.

INSTELLINGEN (in je .env, NIET in de code):
    NTFY_URL=http://100.83.181.76:8090
    NTFY_TOPIC=nova-5qmu9k72l7q4
Ontbreekt een van beide, dan staat de module uit (Nova draait gewoon door).

OPSTARTMELDING
Elke keer dat Nova opstart, krijg je op je gsm "Nova is opgestart om HH:MM".
Zo merk je een herstart die je niet zelf deed (stroomstoring, crash, Docker).
Deze melding gaat ALTIJD naar je gsm, ook als je actief op de laptop zit (in
VS Code zie je Nova's terminal immers niet). Is ntfy nog niet klaar (na een
stroomstoring start Nova mogelijk eerder dan ntfy), dan probeert de module het
10 keer, telkens 30 seconden later. Uitzetten kan met in .env:
    NTFY_OPSTARTMELDING=uit

EEN LIVE-TEST (optioneel, tijdelijk):
    NTFY_ZELFTEST_NA_SECONDEN=90
Dan stuurt de module 90 seconden na het opstarten één testbericht langs
EXACT dezelfde beslissing als een echt proactief bericht. Zit je dan actief
op de laptop, dan staat er in het log "Niet naar de gsm: ...". Is de laptop
dicht of vergrendeld, dan krijg je het bericht op je gsm. Haal de regel na de
test weer weg uit .env.

VEILIGHEID
- Het versturen gebeurt in een aparte achtergrondthread met een time-out van
  5 seconden: een trage of afwezige ntfy houdt Nova nooit op.
- Maximaal 20 berichten per uur naar de gsm (een bug mag je telefoon niet
  volspammen).
- De kanaalnaam wordt nooit geprint (ook niet in foutmeldingen).
- Puur symbolisch: een gewone webaanvraag, geen ML.
"""

import os
import threading
import time

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import requests
except ImportError:
    requests = None


URL_NAAM = "NTFY_URL"
TOPIC_NAAM = "NTFY_TOPIC"
ZELFTEST_NAAM = "NTFY_ZELFTEST_NA_SECONDEN"
OPSTART_NAAM = "NTFY_OPSTARTMELDING"

# De opstartmelding probeert het zo vaak, met zoveel seconden ertussen.
OPSTART_POGINGEN = 10
OPSTART_WACHT_SECONDEN = 30

# De zelftest-wachttijd uit .env wordt tussen deze grenzen gehouden.
ZELFTEST_MIN_SECONDEN = 5
ZELFTEST_MAX_SECONDEN = 600

# Hoe vers moet de data van de laptop zijn om "actief op de laptop" te geloven?
# De laptop stuurt elke 15 seconden, dus 45 = drie updates. Niet lager zetten
# dan ~30, anders zorgt één vertraagde update voor een melding op je gsm
# terwijl je gewoon zit te typen. (Dit raakt de 180 seconden van de rest van
# Nova NIET, zie client_bridge.py.)
FOCUS_MAX_LEEFTIJD_SECONDEN = 45

VERSTUUR_TIMEOUT_SECONDEN = 5

# Veiligheidsgrens tegen een spammende bug.
MAX_BERICHTEN_PER_UUR = 20

# ntfy staat berichten tot 4096 bytes toe. We knippen eerder af.
MAX_BYTES = 3800

TITEL = "Nova"


def _lees_instelling(naam):
    """Leest een instelling uit de omgeving of uit .env. Leeg = niet ingesteld."""
    if load_dotenv is not None:
        try:
            load_dotenv()
        except Exception:
            pass
    return (os.getenv(naam) or "").strip()


def kort_in(tekst, max_bytes=MAX_BYTES):
    """Knipt een tekst af op max_bytes (UTF-8), zonder een teken doormidden te breken."""
    ruw = tekst.encode("utf-8")
    if len(ruw) <= max_bytes:
        return tekst
    return ruw[:max_bytes].decode("utf-8", errors="ignore").rstrip() + "…"


class NtfyMeldingen:
    """Stuurt proactieve berichten ook naar de gsm als je niet actief op de laptop bent."""

    def __init__(self, event_bus, url=None, topic=None, http_post=None,
                 achtergrond=True, klok=None, zelftest_na_seconden=None,
                 opstart_melding=None, slaap=None):
        # url, topic, http_post, achtergrond, klok, zelftest_na_seconden,
        # opstart_melding en slaap bestaan vooral voor de tests. In Nova zelf
        # worden ze niet meegegeven (dan komt alles uit .env).
        self.event_bus = event_bus
        self.url = (url if url is not None else _lees_instelling(URL_NAAM)).strip().rstrip("/")
        self.topic = (topic if topic is not None else _lees_instelling(TOPIC_NAAM)).strip().strip("/")
        self._http_post = http_post or (requests.post if requests is not None else None)
        self._achtergrond = achtergrond
        self._klok = klok or time.time

        self._lock = threading.Lock()
        self._verstuurd = []          # tijdstippen van verstuurde berichten (uurlimiet)
        self._limiet_gemeld = False
        self._laatste_thread = None   # alleen handig voor tests
        self._zelftest_timer = None
        self._opstart_thread = None
        self._slaap = slaap or time.sleep

        self.aan = bool(self.url and self.topic and self._http_post)

        if not self.aan:
            print(
                f"[NTFY] Meldingen naar de gsm staan UIT: {URL_NAAM} en/of {TOPIC_NAAM} "
                "ontbreken in .env (of 'requests' is niet geïnstalleerd)."
            )
            return

        if self.event_bus is not None:
            self.event_bus.subscribe("chat_response", self._on_chat_response)
        print(f"[NTFY] Meldingen naar de gsm staan AAN (server: {self.url}).")

        wachttijd = self._bepaal_zelftest_wachttijd(zelftest_na_seconden)
        if wachttijd:
            self._zelftest_timer = threading.Timer(wachttijd, self._zelftest)
            self._zelftest_timer.daemon = True
            self._zelftest_timer.start()
            print(f"[NTFY] Zelftest: over {wachttijd} seconden komt er één testbericht.")

        if self._opstart_melding_aan(opstart_melding):
            self._opstart_thread = threading.Thread(target=self._opstartmelding, daemon=True)
            self._opstart_thread.start()

    # ------------------------------------------------------------
    # Opstartmelding
    # ------------------------------------------------------------

    def _opstart_melding_aan(self, waarde):
        """Standaard AAN. Uitzetten kan met NTFY_OPSTARTMELDING=uit (of nee/0/false/off)."""
        if waarde is not None:
            return bool(waarde)
        # Tijdens een pytest-run nooit een echte melding naar je gsm sturen,
        # ook niet als een test per ongeluk de hele module laadt.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return False
        ruw = _lees_instelling(OPSTART_NAAM).lower()
        return ruw not in ("uit", "nee", "0", "false", "off")

    def _opstartmelding(self):
        """
        Stuurt "Nova is opgestart om HH:MM" naar de gsm, ongeacht of je actief
        op de laptop bent. Probeert het opnieuw als ntfy nog niet bereikbaar is.
        Draait in een eigen thread en gooit nooit een fout naar buiten.
        """
        try:
            if not self._mag_nog_versturen():
                return False
            tekst = f"Nova is opgestart om {time.strftime('%H:%M')}."
            for poging in range(1, OPSTART_POGINGEN + 1):
                if self._verstuur(tekst, meld_fout=False):
                    print("[NTFY] Opstartmelding naar de gsm gestuurd.")
                    return True
                if poging < OPSTART_POGINGEN:
                    self._slaap(OPSTART_WACHT_SECONDEN)
            print(
                f"[NTFY] Opstartmelding niet gelukt na {OPSTART_POGINGEN} pogingen "
                "(ntfy niet bereikbaar)."
            )
            return False
        except Exception as e:
            print(f"[NTFY] Fout bij de opstartmelding (genegeerd): {e}")
            return False

    # ------------------------------------------------------------
    # Zelftest (optioneel, via .env)
    # ------------------------------------------------------------

    def _bepaal_zelftest_wachttijd(self, waarde):
        """
        Geeft het aantal seconden tot de zelftest, of 0 als er geen komt.
        'waarde' is de parameter uit de constructor (tests); is die None,
        dan komt de waarde uit .env, begrensd tussen 5 en 600 seconden.
        Rommel in .env betekent gewoon: geen zelftest.
        """
        if waarde is not None:
            try:
                return max(0, float(waarde))
            except (TypeError, ValueError):
                return 0
        ruw = _lees_instelling(ZELFTEST_NAAM)
        if not ruw:
            return 0
        try:
            seconden = int(ruw)
        except ValueError:
            return 0
        if seconden <= 0:
            return 0
        return min(max(seconden, ZELFTEST_MIN_SECONDEN), ZELFTEST_MAX_SECONDEN)

    def _zelftest(self):
        """Eén testbericht langs DEZELFDE beslissing als een echt proactief bericht."""
        try:
            self.verwerk_bericht(
                {"text": "Dit is een testbericht van Nova (ntfy-zelftest)."},
                is_hoofdthread=False,
            )
        except Exception as e:
            print(f"[NTFY] Fout tijdens de zelftest (genegeerd): {e}")

    # ------------------------------------------------------------
    # Binnenkomend bericht
    # ------------------------------------------------------------

    def _on_chat_response(self, data, event_type=None):
        """Wordt door de EventBus aangeroepen bij elk chat_response-event."""
        try:
            if not isinstance(data, dict):
                return
            is_hoofdthread = threading.current_thread() is threading.main_thread()
            self.verwerk_bericht(data, is_hoofdthread)
        except Exception as e:
            # Nooit de rest van Nova laten lijden onder een fout hier.
            print(f"[NTFY] Fout bij verwerken van een bericht (genegeerd): {e}")

    def verwerk_bericht(self, data, is_hoofdthread):
        """
        Beslist of dit bericht ook naar de gsm moet en verstuurt het.
        Geeft True terug als er een verzending is gestart, anders False.
        """
        tekst = data.get("text") or data.get("msg") or ""
        if not isinstance(tekst, str) or not tekst.strip():
            return False
        tekst = tekst.strip()

        naar_gsm, reden = self.beslis(is_hoofdthread)
        if not naar_gsm:
            if not is_hoofdthread:
                print(f"[NTFY] Niet naar de gsm: {reden}.")
            return False

        if not self._mag_nog_versturen():
            return False

        print(f"[NTFY] Naar de gsm ({reden}).")
        self._verstuur_in_achtergrond(tekst)
        return True

    # ------------------------------------------------------------
    # De beslissing
    # ------------------------------------------------------------

    def beslis(self, is_hoofdthread):
        """Geeft (naar_gsm, reden) terug."""
        if is_hoofdthread:
            return False, "antwoord op je eigen bericht"
        actief, reden = self.laptop_actief()
        if actief:
            return False, reden
        return True, reden

    def gsm_vangt_op(self):
        """
        Zou een proactief bericht NU op de gsm terechtkomen?
        True als de module aanstaat EN Kevin niet actief op de laptop is.
        main.py gebruikt dit (punt 55, stap 2b): als de gsm het bericht
        toch ontvangt, hoeft Layer 5 het niet meer tegen te houden.
        Bij elke twijfel of fout: False (dan blijft alles zoals voorheen).
        """
        if not self.aan:
            return False
        try:
            actief, _reden = self.laptop_actief()
        except Exception:
            return False
        return not actief

    def laptop_actief(self):
        """
        Is Kevin NU actief op de laptop? Geeft (True/False, reden) terug.
        Elke twijfel of fout betekent False (dus: naar de gsm).
        """
        bridge = self._vind_module("client_bridge")
        if bridge is None:
            return False, "client_bridge niet gevonden"

        try:
            if not bridge.is_laptop_verbonden():
                return False, "laptop niet verbonden"

            activiteit = bridge.get_laatste_activity(FOCUS_MAX_LEEFTIJD_SECONDEN)
            if not activiteit:
                return False, "geen verse activiteitsdata van de laptop"
            if activiteit.get("activity") == "afwezig":
                return False, "laptop vergrendeld"

            focus = bridge.get_laatste_focus(FOCUS_MAX_LEEFTIJD_SECONDEN)
            if not focus:
                return False, "geen verse focusdata van de laptop"
            if focus.get("focus_level") != "actief":
                return False, "je bent niet actief op de laptop"
        except Exception as e:
            return False, f"fout bij controle van de laptop: {e}"

        return True, "je bent actief op de laptop"

    def _vind_module(self, naam):
        """Zoekt een geladen module op naam (zelfde manier als de rest van Nova)."""
        for bron_naam in ("modules", "loaded_modules"):
            bron = getattr(self.event_bus, bron_naam, None)
            ophaal = getattr(bron, "get", None)
            if callable(ophaal):
                module = ophaal(naam)
                if module is not None:
                    return module
        return None

    # ------------------------------------------------------------
    # Versturen
    # ------------------------------------------------------------

    def _mag_nog_versturen(self):
        """Maximaal MAX_BERICHTEN_PER_UUR per uur."""
        nu = self._klok()
        with self._lock:
            self._verstuurd = [t for t in self._verstuurd if nu - t < 3600]
            if len(self._verstuurd) >= MAX_BERICHTEN_PER_UUR:
                if not self._limiet_gemeld:
                    print(
                        f"[NTFY] Limiet van {MAX_BERICHTEN_PER_UUR} berichten per uur bereikt: "
                        "verdere berichten gaan dit uur niet naar de gsm."
                    )
                    self._limiet_gemeld = True
                return False
            self._verstuurd.append(nu)
            self._limiet_gemeld = False
            return True

    def _verstuur_in_achtergrond(self, tekst):
        if not self._achtergrond:
            return self._verstuur(tekst)
        draad = threading.Thread(target=self._verstuur, args=(tekst,), daemon=True)
        self._laatste_thread = draad
        draad.start()
        return None

    def _verstuur(self, tekst, meld_fout=True):
        """De eigenlijke webaanvraag. Gooit nooit een fout naar buiten."""
        adres = f"{self.url}/{self.topic}"
        try:
            antwoord = self._http_post(
                adres,
                data=kort_in(tekst).encode("utf-8"),
                headers={"Title": TITEL},
                timeout=VERSTUUR_TIMEOUT_SECONDEN,
            )
            status = getattr(antwoord, "status_code", None)
            if status != 200:
                if meld_fout:
                    print(f"[NTFY] Versturen mislukt: de server antwoordde {status}.")
                return False
            return True
        except Exception as e:
            # De kanaalnaam werkt als wachtwoord: nooit in het log.
            if meld_fout:
                melding = str(e).replace(self.topic, "<kanaal>")
                print(f"[NTFY] Versturen mislukt: {melding}")
            return False

    def shutdown(self):
        """Niets op te ruimen; wel aanwezig voor de standaard-afsluitronde."""
        pass


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'sem' wordt hier niet gebruikt.
    """
    instance = NtfyMeldingen(event_bus)
    event_bus.publish("module_loaded", {"name": "ntfy_meldingen"})
    return instance