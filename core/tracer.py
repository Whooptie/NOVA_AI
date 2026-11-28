# core/tracer.py
#
# Tracer voor de live brein-weergave (nova_state.md, punt 79, stap 1).
#
# WAT DOET DIT?
#   Elke keer dat de EventBus een handler (een functie die op een event luistert)
#   aanroept, onthoudt de tracer welke module en functie dat was, hoelang het
#   duurde en of het binnen "een antwoord op Kevin" gebeurde. Zo kan een pagina
#   later lichtjes laten flitsen. Ook code die NIET via de bus loopt (de
#   achtergrondlussen in main.py) kan zich melden met tracer.trace("module.functie").
#
# KETEN:
#   Typt Kevin iets, dan publiceert main.py "chat_message". Alles wat daarbinnen
#   draait (ook wat die handlers zelf weer publiceren) krijgt hetzelfde keten-nummer.
#   Werk zonder keten-nummer is achtergrondwerk. Beperking: een handler die zelf een
#   nieuwe thread start, valt buiten de keten (de keten hoort bij een thread).
#
# PRIVACY:
#   Er wordt NOOIT tekst van Kevin of de inhoud van een event bewaard of
#   doorgegeven. Alleen namen, tijden en nummers.
#
# VEILIGHEID:
#   - Standaard UIT. Als hij uit staat kost het bijna niets.
#   - Een fout in de tracer of in een luisteraar van de tracer mag nooit een
#     handler of de bus stoppen: alles staat in try/except.
#
# PUUR SYMBOLISCH: tellen, tijd meten, namen onthouden. Geen ML.

import threading
import time
from collections import Counter, deque
from contextlib import contextmanager, nullcontext

# Events waarbij een nieuwe keten begint ("Kevin vraagt iets").
KETEN_EVENTS = ("chat_message",)

MAX_RECORDS = 5000


def _korte_module(pad):
    """'modules.activity.session_watcher' -> 'session_watcher'."""
    return str(pad).rsplit(".", 1)[-1] if pad else "?"


class Tracer:
    def __init__(self, max_records=MAX_RECORDS, klok=time.perf_counter, tijd=time.time):
        self.aan = False
        self.log = deque(maxlen=max_records)      # laatste records (thread-veilig)
        # Records binnen een antwoord op Kevin apart bewaard: het achtergrondwerk (honderden
        # kleine getters per minuut) mag ze niet uit self.log duwen.
        self.keten_log = deque(maxlen=max_records)
        self._luisteraars = []
        self._klok = klok
        self._tijd = tijd
        self._lokaal = threading.local()          # keten-nummer per thread
        self._slot = threading.Lock()
        self._keten_teller = 0
        self._geen = nullcontext()
        self.totaal = 0                           # alle records sinds het aanzetten
        self.per_module = Counter()               # korte modulenaam -> aantal records
        self.paden = set()                        # volledige modulepaden die we zagen

    # ---------- aan / uit / luisteraars ----------
    def zet(self, aan):
        self.aan = bool(aan)

    def leeg(self):
        self.log.clear()
        self.keten_log.clear()
        self.totaal = 0
        self.per_module = Counter()
        self.paden = set()

    def alle_records(self):
        """self.log en self.keten_log samengevoegd (zonder dubbelen), op tijd gesorteerd."""
        gezien, uit = set(), []
        for r in list(self.keten_log) + list(self.log):
            if id(r) not in gezien:
                gezien.add(id(r))
                uit.append(r)
        uit.sort(key=lambda r: r.get("t", 0.0))
        return uit

    def voeg_toe(self, functie):
        if functie not in self._luisteraars:
            self._luisteraars.append(functie)

    def verwijder(self, functie):
        if functie in self._luisteraars:
            self._luisteraars.remove(functie)

    # ---------- keten ----------
    def keten_id(self):
        return getattr(self._lokaal, "keten", None)

    def keten(self, event_type, data=None):
        """Context-manager rond publish(): start een keten bij 'chat_message'."""
        if (not self.aan or event_type not in KETEN_EVENTS
                or self.keten_id() is not None):
            return self._geen
        return self._nieuwe_keten(event_type)

    @contextmanager
    def _nieuwe_keten(self, event_type):
        with self._slot:
            self._keten_teller += 1
            nummer = self._keten_teller
        self._lokaal.keten = nummer
        self._uitzenden({"soort": "keten_start", "keten": nummer, "event": event_type})
        try:
            yield
        finally:
            self._lokaal.keten = None
            self._uitzenden({"soort": "keten_eind", "keten": nummer, "event": event_type})

    # ---------- handlers (aangeroepen door EventBus._roep_aan) ----------
    def begin(self):
        return self._klok()

    def eind(self, handler, event_type, start):
        try:
            duur = (self._klok() - start) * 1000.0
            module = getattr(handler, "__module__", None) or "?"
            naam = getattr(handler, "__qualname__", None) or repr(handler)
            self._uitzenden({
                "soort": "handler", "module": _korte_module(module), "pad": module,
                "handler": naam, "event": event_type,
                "duur_ms": round(duur, 3), "keten": self.keten_id(),
            })
        except Exception:
            pass                                  # de tracer mag nooit iets stoppen

    # ---------- code die niet via de bus loopt ----------
    def trace(self, naam, start=None, treffer=None, eigen_ms=None):
        """tracer.trace("session_watcher.check_pauze"): een signaal vanuit een lus."""
        if not self.aan:
            return
        try:
            module = str(naam).split(".", 1)[0]
            self._uitzenden({
                "soort": "trace", "module": module, "pad": module,
                "handler": str(naam), "event": None,
                "treffer": treffer, "eigen_ms": eigen_ms,
                "duur_ms": None if start is None else round((self._klok() - start) * 1000.0, 3),
                "keten": self.keten_id(),
            })
        except Exception:
            pass

    # ---------- intern ----------
    def _uitzenden(self, record):
        record["t"] = self._tijd()
        duur = record.get("duur_ms")
        # starttijd: een record wordt vastgelegd als de functie KLAAR is (binnenste eerst)
        record["start_t"] = record["t"] - (duur / 1000.0 if duur else 0.0)
        self.log.append(record)
        if record.get("keten") is not None:
            self.keten_log.append(record)
        if record["soort"] in ("handler", "trace"):
            self.totaal += 1
            self.per_module[record["module"]] += 1
            self.paden.add(record["pad"])
        for functie in list(self._luisteraars):
            try:
                functie(record)
            except Exception:
                pass

    # ---------- overzichten ----------
    def gezien(self):
        """Alle modulenamen (kort) die de tracer ooit zag."""
        return set(self.per_module)

    def dekking(self, geladen_modules):
        """
        geladen_modules: dict naam -> instantie (loader.loaded_modules).
        Geeft (gezien, ongezien): lijsten van modulenamen. Een module telt als
        gezien als haar naam, of de naam van het bestand van haar klasse, in de
        records voorkwam.
        """
        gezien_namen = self.gezien()
        gezien, ongezien = [], []
        for naam, instantie in sorted((geladen_modules or {}).items()):
            klasse_module = _korte_module(getattr(type(instantie), "__module__", None))
            if naam in gezien_namen or klasse_module in gezien_namen:
                gezien.append(naam)
            else:
                ongezien.append(naam)
        return gezien, ongezien