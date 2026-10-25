# modules/context/handler_fouten.py
#
# Nova leest haar eigen foutenlogboek en vertelt het Kevin (25 oktober 2026).
# Vervolg op bug #46: de EventBus logt elke fout in een handler naar
# logs/handler_fouten.log en houdt de laatste 50 bij in bus.fouten.
#
# Twee dingen:
#   1. OP COMMANDO  -- "laatste fouten", "zijn er fouten", "wis de fouten"
#      (de IntentRouter herkent de zin, deze module antwoordt).
#   2. UIT ZICHZELF -- main.py's achtergrond_loop() roept elke paar minuten
#      check_nieuwe_fouten() aan. Is er iets nieuws misgegaan, dan zegt Nova
#      het EEN keer, kort, met een verwijzing naar "laatste fouten".
#
# PUUR SYMBOLISCH: een bestand lezen, regels herkennen, tellen en een zin
# bouwen. Geen ML.
#
# LET OP: dit bestand staat bewust NIET in modules/debug/: module_loader.py
# slaat die hele map over (debug_commands wordt daar handmatig geladen).
#
# LUS-BEVEILIGING: de melding gaat zelf via de EventBus. Faalt die route, dan
# ontstaat een nieuwe fout, die weer een melding zou geven, enzovoort. Daarom:
#   - minstens MIN_INTERVAL seconden tussen twee meldingen
#   - dezelfde fout (zelfde onderdeel + event + foutmelding) wordt
#     HEROPEN_NA seconden niet opnieuw gemeld
#   - nieuwe fouten wachten en worden gebundeld in een melding

import re
import time
from pathlib import Path

MIN_INTERVAL = 600       # seconden tussen twee spontane meldingen (10 min)
HEROPEN_NA = 3600        # dezelfde fout pas na 1 uur opnieuw melden
MAX_LEES_BYTES = 200_000  # we lezen enkel het EINDE van een groot logbestand
MAX_GETOOND = 5          # aantal verschillende fouten in een antwoord

_KOP = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\] event='(.*)' handler=(.*)$"
)


def _standaard_logpad():
    # Dynamisch opgehaald, zodat tests het pad kunnen omleiden.
    import core.event_bus as eb
    return Path(eb._LOGBESTAND)


def mooie_naam(handler):
    """'Klas.methode.<locals>.functie' -> 'Klas.methode.functie'."""
    return (handler or "onbekend").replace("<locals>.", "")


def lees_logbestand(pad, max_bytes=MAX_LEES_BYTES):
    """
    Leest handler_fouten.log en geeft een lijst fouten terug, oudste eerst:
    {"datum", "tijd", "event", "handler", "fout"}. 'fout' is de laatste
    regel van de traceback (bv. 'ValueError: oeps'). Geen bestand of
    onleesbaar -> lege lijst.
    """
    try:
        pad = Path(pad)
        if not pad.exists():
            return []
        grootte = pad.stat().st_size
        with open(pad, "rb") as f:
            if grootte > max_bytes:
                f.seek(grootte - max_bytes)
            tekst = f.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    fouten, huidig = [], None
    for regel in tekst.splitlines():
        m = _KOP.match(regel)
        if m:
            huidig = {"datum": m.group(1), "tijd": m.group(2),
                      "event": m.group(3), "handler": m.group(4), "fout": ""}
            fouten.append(huidig)
        elif huidig is not None and regel.strip():
            if (not regel[0].isspace() and not regel.startswith("Traceback")
                    and not regel.startswith("During handling")
                    and not regel.startswith("The above exception")):
                huidig["fout"] = regel.strip()
    return fouten


def groepeer(fouten):
    """Zelfde (handler, event, fout) samenvoegen. Nieuwste groep eerst."""
    groepen = {}
    for f in fouten:
        sleutel = (f["handler"], f["event"], f["fout"])
        g = groepen.get(sleutel)
        if g is None:
            g = {"handler": f["handler"], "event": f["event"], "fout": f["fout"],
                 "aantal": 0, "laatst": ""}
            groepen[sleutel] = g
        g["aantal"] += 1
        g["laatst"] = f"{f['datum']} {f['tijd']}"
    return sorted(groepen.values(), key=lambda g: g["laatst"], reverse=True)


def maak_overzicht(fouten):
    """De tekst die Nova zegt bij 'laatste fouten'."""
    if not fouten:
        return "Mijn foutenlogboek is leeg: er is niets misgegaan"
    groepen = groepeer(fouten)
    n, k = len(fouten), len(groepen)
    laatste = groepen[0]["laatst"]
    kop = (f"Ik heb {n} fout{'en' if n != 1 else ''} in mijn logboek"
           f" ({k} verschillend{'e' if k != 1 else ''}). "
           f"De laatste was op {laatste}.")
    regels = []
    for g in groepen[:MAX_GETOOND]:
        uur = g["laatst"][11:16]
        keer = f" ({g['aantal']}x)" if g["aantal"] > 1 else ""
        fout = g["fout"] or "onbekende fout"
        regels.append(f"• {uur}: {mooie_naam(g['handler'])} bij '{g['event']}' — {fout}{keer}")
    if k > MAX_GETOOND:
        regels.append(f"… en nog {k - MAX_GETOOND} andere.")
    return kop + "\n" + "\n".join(regels)


class HandlerFoutenModule:
    def __init__(self, event_bus, logbestand=None, klok=time.time):
        self.event_bus = event_bus
        self._logbestand = logbestand            # None = standaardpad
        self._klok = klok
        self._gezien = getattr(event_bus, "fout_teller", 0)
        self._wachtend = []                      # nieuwe, nog niet gemelde fouten
        self._gemeld = {}                        # signatuur -> tijdstip van melding
        self._laatste_melding = 0.0

        event_bus.subscribe("intent_handler_fouten", self.on_fouten)
        event_bus.subscribe("intent_handler_fouten_wissen", self.on_wissen)

    def _pad(self):
        return Path(self._logbestand) if self._logbestand else _standaard_logpad()

    # ---------------------------------------------------------
    # 1. Op commando
    # ---------------------------------------------------------
    def on_fouten(self, data, event_type=None):
        fouten = lees_logbestand(self._pad())
        if not fouten:
            # logbestand onleesbaar/afwezig? Dan het geheugen van de bus.
            for f in list(getattr(self.event_bus, "fouten", [])):
                datum, _, uur = f["tijd"].partition(" ")
                fouten.append({"datum": datum, "tijd": uur, "event": f["event"],
                               "handler": f["handler"], "fout": f["fout"]})
        tekst = maak_overzicht(fouten)
        self.event_bus.publish("layer4_response", {"text": tekst})

    def on_wissen(self, data, event_type=None):
        pad = self._pad()
        aanwezig = bool(lees_logbestand(pad))
        try:
            if pad.exists():
                pad.write_text("", encoding="utf-8")
        except Exception as e:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik kon mijn foutenlogboek niet leegmaken: {e}"})
            return
        fouten = getattr(self.event_bus, "fouten", None)
        if fouten is not None:
            fouten.clear()
        self._gezien = getattr(self.event_bus, "fout_teller", 0)
        self._wachtend = []
        self.event_bus.publish("layer4_response", {
            "text": "Klaar, mijn foutenlogboek is leeg." if aanwezig
            else "Mijn foutenlogboek was al leeg."})

    # ---------------------------------------------------------
    # 2. Uit zichzelf (aangeroepen door main.py's achtergrond_loop)
    # ---------------------------------------------------------
    @staticmethod
    def _signatuur(f):
        return (f.get("handler"), f.get("event"), f.get("fout"))

    def check_nieuwe_fouten(self, nu=None):
        """
        Geeft de gepubliceerde zin terug, of None. Crasht nooit.
        """
        try:
            nu = self._klok() if nu is None else nu
            teller = getattr(self.event_bus, "fout_teller", 0)
            if teller > self._gezien:
                aantal_nieuw = teller - self._gezien
                self._gezien = teller
                try:
                    recent = list(self.event_bus.fouten)[-aantal_nieuw:]
                except RuntimeError:
                    recent = []
                for f in recent:
                    sig = self._signatuur(f)
                    if nu - self._gemeld.get(sig, -HEROPEN_NA) < HEROPEN_NA:
                        continue                  # recent al gemeld
                    self._wachtend.append(f)

            if not self._wachtend:
                return None
            if nu - self._laatste_melding < MIN_INTERVAL:
                return None                       # te snel na de vorige melding

            wachtend, self._wachtend = self._wachtend, []
            for f in wachtend:
                self._gemeld[self._signatuur(f)] = nu
            self._laatste_melding = nu

            laatste = wachtend[-1]
            onderdeel = mooie_naam(laatste["handler"])
            if len(wachtend) == 1:
                zin = (f"Even een technische melding: er ging net iets mis in "
                       f"'{onderdeel}' ({laatste['fout']}). "
                       f"Zeg 'laatste fouten' voor details.")
            else:
                zin = (f"Even een technische melding: er zijn {len(wachtend)} nieuwe "
                       f"fouten opgetreden, de laatste in '{onderdeel}'. "
                       f"Zeg 'laatste fouten' voor details.")
            self.event_bus.publish("layer4_response", {"text": zin})
            return zin
        except Exception as e:
            print(f"[handler_fouten] check mislukt: {e}")
            return None


def init_module(event_bus):
    instance = HandlerFoutenModule(event_bus)
    event_bus.publish("module_loaded", {"name": "handler_fouten"})
    return instance