#!/usr/bin/env python3
# tools/run_benchmark.py
"""
Nova-benchmark. Drie niveaus, puur symbolisch (tekst vergelijken, geen ML).

  Niveau 1 (standaard): ROUTING. Stuurt elke vraag door IntentRouter.route()
      en kijkt welke events de router publiceert (intent_definition, ...).
  Niveau 2 (--niveau 2): ANTWOORD. Bouwt een mini-Nova van vier onderdelen
      (echte EventBus + SemanticConceptsModule + ChatModule + IntentRouter)
      en vangt het echte antwoord op (chat_response / layer4_response).
      Er wordt GEEN ModuleLoader gestart: dus geen poort 8765, geen webcam,
      geen achtergrondlussen.
  Niveau 3 (--niveau 3): ANTWOORD, MET EXTRA MODULES. Zoals niveau 2, plus
      zone, time, calendar, holidays en math, zodat ook hun antwoord
      gecontroleerd kan worden. Een module die niet start geeft geen crash:
      de cases die hem nodig hebben worden "niet meetbaar" met een reden.
      Extra modules toevoegen kan met --module modules.map.naam (herhaalbaar).
      Weer (internet nodig) en groeten blijven bij een event-controle.

VEILIG
  - Het script maakt eerst een KOPIE van je project (zonder .git, engines
    en logs) in een tijdelijke map en draait daar.
  - Het controleert dat de geimporteerde modules en het concepts-bestand
    echt IN die kopie staan; zo niet, dan stopt het meteen.
  - Voor elke vraag wordt concepts.json in de kopie teruggezet, zodat een
    vraag nooit de volgende beinvloedt.
  - Het controlegetal (hash) van je ECHTE data/concepts.json wordt voor en
    na de run vergeleken; bij een verschil krijg je een waarschuwing.
  - Standaard staat het netwerk uit (zodat Wikipedia-opzoekingen de
    meting niet verstoren). Met --met-netwerk zet je het aan.
  - Enkel data/benchmark_resultaten.jsonl wordt in je echte project
    bijgeschreven (uitzetten kan met --geen-opslaan).

GEBRUIK (vanuit de projectmap, bv. /app)
  python tools/run_benchmark.py --ontdek               # niveau 1: events per vraag
  python tools/run_benchmark.py --niveau 2 --ontdek    # niveau 2: events + antwoorden
  python tools/run_benchmark.py --niveau 3 --ontdek    # niveau 3: idem, met extra modules
  python tools/run_benchmark.py --niveau 2             # score niveau 2
  python tools/run_benchmark.py --niveau 3             # score niveau 3
  python tools/run_benchmark.py --niveau 2 --categorie afgewezen_feit
  python tools/run_benchmark.py --niveau 2 --willekeurig 15          # 15 willekeurige is_a-ketens erbij
  python tools/run_benchmark.py --niveau 3 --ongezien                # de ongeziene set (aparte score)

CONTROLES IN EEN CASE (alle optioneel)
  moet_event                 lijst: minstens een gepubliceerd event begint met een van deze namen
  mag_event_niet             lijst: geen enkel event begint met een van deze namen
  moet_bevatten_een_van      lijst woorden (HELE woorden): minstens een staat in het ANTWOORD
  moet_bevatten_alle         lijst woorden (HELE woorden): ze staan ALLEMAAL in het ANTWOORD
  moet_overeenkomen_een_van  lijst reguliere expressies: minstens een komt voor in het ANTWOORD
  mag_niet_bevatten          lijst woorden (HELE woorden) die NIET in het ANTWOORD mogen staan
  niveau3                    object met extra controles die ALLEEN op niveau 3 gelden
                             (en die dezelfde sleutels van de case dan overschrijven)
  Placeholders in de lijsten: $vandaag_weekdag, $morgen_weekdag, $overmorgen_weekdag
  (worden bij het draaien ingevuld met de Nederlandse weekdag, tijdzone Brussel).
  Het ANTWOORD bestaat enkel uit events "chat_response" en "layer4_response".
  Niveau 1: tekstcontroles zijn dan nog niet meetbaar (geen fout).
  Niveau 2 en 3: een tekstcontrole zonder enig antwoord telt als gefaald
  (behalve op niveau 3 als een extra module niet startte: dan niet meetbaar).
"""

import argparse
import datetime
import hashlib
import importlib
import json
import os
import random
import re
import shutil
import signal
import sys
import tempfile
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_PAD = os.path.join(PROJECT_ROOT, "tests", "benchmark", "benchmark_cases.json")
ONGEZIEN_PAD = os.path.join(PROJECT_ROOT, "tests", "benchmark", "benchmark_ongezien.json")
RESULTATEN_PAD = os.path.join(PROJECT_ROOT, "data", "benchmark_resultaten.jsonl")
ECHT_CONCEPTS_PAD = os.path.join(PROJECT_ROOT, "data", "concepts.json")

ANTWOORD_EVENTS = {"chat_response", "layer4_response"}
ANTWOORD_OPEN = "antwoord-controle nog open"
NEGEER_BIJ_KOPIE = (".git", "__pycache__", ".pytest_cache", "engines", "logs", "*.log", "*.pyc")
TIJDSLIMIET_SECONDEN = 20

# Volgorde telt: zone voor time (net als in module_loader.py).
STANDAARD_NIVEAU3_MODULES = [
    "modules.time.zone",
    "modules.time.time",
    "modules.time.calendar",
    "modules.time.holidays",
    "modules.math.math",
]

WEEKDAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
CATEGORIE_KETENS = "willekeurige_ketens"
KETEN_WOORD = re.compile(r"^[a-zà-ÿ][a-zà-ÿ \-]*$")


class BenchBus:
    """Minimale EventBus voor niveau 1: onthoudt alles wat gepubliceerd wordt."""

    def __init__(self):
        self.modules = {}
        self.events = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event_type, data=None, *args, **kwargs):
        self.events.append((event_type, data))


class _Tijdslimiet(BaseException):
    """BaseException, zodat een handler-try/except in de EventBus hem niet opeet."""


def _alarm(signum, frame):
    raise _Tijdslimiet()


def _verzamel_strings(waarde, uit):
    """Haalt alle tekstwaarden uit een (geneste) event-payload."""
    if isinstance(waarde, str):
        uit.append(waarde)
    elif isinstance(waarde, dict):
        for v in waarde.values():
            _verzamel_strings(v, uit)
    elif isinstance(waarde, (list, tuple)):
        for v in waarde:
            _verzamel_strings(v, uit)


def antwoord_tekst(events):
    """Neemt de zin uit het veld 'text'. Ontbreekt dat, dan alle tekstvelden (vangnet)."""
    stukken = []
    for naam, data in events:
        if naam in ANTWOORD_EVENTS:
            if isinstance(data, dict) and isinstance(data.get("text"), str):
                stukken.append(data["text"])
            else:
                _verzamel_strings(data, stukken)
    return " ".join(stukken).lower()


def bevat_woord(tekst, woord):
    return re.search(r"(?<!\w)" + re.escape(woord.lower()) + r"(?!\w)", tekst) is not None


def hash_bestand(pad):
    if not os.path.exists(pad):
        return None
    h = hashlib.sha256()
    with open(pad, "rb") as f:
        for blok in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blok)
    return h.hexdigest()


def maak_kopie():
    doel = tempfile.mkdtemp(prefix="nova_bench_")
    kopie = os.path.join(doel, "nova")
    shutil.copytree(PROJECT_ROOT, kopie, ignore=shutil.ignore_patterns(*NEGEER_BIJ_KOPIE))
    os.makedirs(os.path.join(kopie, "logs"), exist_ok=True)
    return doel, kopie


def zet_netwerk_uit():
    import socket

    def _geblokkeerd(*args, **kwargs):
        raise socket.gaierror("netwerk staat uit tijdens de benchmark (gebruik --met-netwerk)")

    socket.getaddrinfo = _geblokkeerd


def controleer_in_kopie(kopie, modules_en_paden):
    """Stopt het script als iets NIET uit de kopie komt. modules_en_paden: lijst (naam, pad)."""
    kopie_abs = os.path.realpath(kopie)
    for naam, pad in modules_en_paden:
        if not pad:
            continue
        if not os.path.realpath(pad).startswith(kopie_abs):
            print(f"\nSTOP: {naam} wijst naar '{pad}', buiten de tijdelijke kopie.")
            print("De benchmark zou dan in je echte bestanden kunnen schrijven. Er is niets uitgevoerd.")
            return False
    return True


def draai_met_tijdslimiet(functie):
    """Voert functie() uit met een tijdslimiet (enkel Linux). Geeft (resultaat, fout)."""
    heeft_alarm = hasattr(signal, "SIGALRM")
    if heeft_alarm:
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(TIJDSLIMIET_SECONDEN)
    try:
        return functie(), None
    except _Tijdslimiet:
        return None, f"tijdslimiet van {TIJDSLIMIET_SECONDEN}s overschreden"
    except Exception as e:  # noqa: BLE001 - een crash is zelf een meetresultaat
        return None, f"{type(e).__name__}: {e}"
    finally:
        if heeft_alarm:
            signal.alarm(0)


# ---------------------------------------------------------------- niveau 1
def draai_vraag_niveau1(router_klasse, vraag):
    """Verse router + verse bus per vraag, zodat pending-vragen niet doorlekken."""
    bus = BenchBus()

    def _doe():
        router = router_klasse(bus)
        router.route({"text": vraag}, "chat_message")

    _, fout = draai_met_tijdslimiet(_doe)
    return bus.events, fout


# ---------------------------------------------------------------- niveau 2 en 3
def importeer_modules(namen):
    """
    Importeert de extra modules alvast (zo valt het zware importeren, bv.
    sympy, niet binnen de tijdslimiet van een vraag). Geeft {naam: reden}
    terug voor de modules die niet importeerden.
    """
    fouten = {}
    for naam in namen:
        try:
            importlib.import_module(naam)
        except Exception as e:  # noqa: BLE001 - een module die niet laadt is een meetresultaat
            fouten[naam] = f"{type(e).__name__}: {e}"
    return fouten


class Keten:
    """
    Bouwt per vraag een verse mini-Nova en zet concepts.json eerst terug.
    Met extra_modules (niveau 3) worden die per vraag ook gestart, op
    dezelfde manier als module_loader.py: init_module(bus, sem), en bij een
    TypeError init_module(bus).
    """

    def __init__(self, concepts_pad, extra_modules=None, voorfouten=None):
        from core.event_bus import EventBus
        from core.semantic import SemanticConceptsModule
        from modules.chat.chat import ChatModule
        from core.intent_router import IntentRouter

        class OpnemendeBus(EventBus):
            def publish(self, event_type, data=None, *args, **kwargs):
                self.opgenomen.append((event_type, data))
                return super().publish(event_type, data, *args, **kwargs)

        self._bus_klasse = OpnemendeBus
        self._semantic = SemanticConceptsModule
        self._chat = ChatModule
        self._router = IntentRouter
        self._concepts_pad = concepts_pad
        self._extra = list(extra_modules or [])
        self.mislukt = dict(voorfouten or {})
        with open(concepts_pad, "rb") as f:
            self._concepts_origineel = f.read() if os.path.exists(concepts_pad) else b"{}"

    def _laad_extra(self, bus, sem):
        for naam in self._extra:
            try:
                module = importlib.import_module(naam)
                if not hasattr(module, "init_module"):
                    self.mislukt.setdefault(naam, "geen init_module")
                    continue
                try:
                    instance = module.init_module(bus, sem)
                except TypeError:
                    instance = module.init_module(bus)
                bus.modules[naam.rsplit(".", 1)[-1]] = instance
            except Exception as e:  # noqa: BLE001
                self.mislukt.setdefault(naam, f"{type(e).__name__}: {e}")

    def draai(self, vraag):
        with open(self._concepts_pad, "wb") as f:
            f.write(self._concepts_origineel)

        bus = self._bus_klasse()
        bus.opgenomen = []

        def _doe():
            sem = self._semantic(bus)
            if not hasattr(bus, "modules"):
                bus.modules = {}
            bus.modules["semantic"] = sem
            if self._extra:
                self._laad_extra(bus, sem)
            self._chat(bus, semantic_module=sem)
            router = self._router(bus, semantic_module=sem)
            router.route({"text": vraag}, "chat_message")

        _, fout = draai_met_tijdslimiet(_doe)
        if not fout:
            handler_fouten = list(getattr(bus, "fouten", None) or [])
            if handler_fouten:
                fout = f"handler-fout in de EventBus: {handler_fouten[-1]}"
        return bus.opgenomen, fout


# ---------------------------------------------------------------- placeholders
def nu_brussel():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Brussels"))
    except Exception:  # noqa: BLE001 - geen tijdzonedata: lokale tijd
        return datetime.datetime.now()


def los_placeholders_op(case, nu):
    """Vervangt $vandaag_weekdag/$morgen_weekdag/$overmorgen_weekdag in de hele case."""
    dag = nu.weekday()
    waarden = {
        "$vandaag_weekdag": WEEKDAGEN[dag % 7],
        "$morgen_weekdag": WEEKDAGEN[(dag + 1) % 7],
        "$overmorgen_weekdag": WEEKDAGEN[(dag + 2) % 7],
    }

    def _vervang(x):
        if isinstance(x, str):
            return waarden.get(x, x)
        if isinstance(x, list):
            return [_vervang(i) for i in x]
        if isinstance(x, dict):
            return {k: _vervang(v) for k, v in x.items()}
        return x

    return _vervang(case)


# ---------------------------------------------------------------- willekeurige ketens
def maak_ketenvragen(concepts_pad, aantal, seed):
    """
    Trekt `aantal` willekeurige tweestaps-is_a-ketens (a is_a b, b is_a c) uit
    concepts.json en maakt er cases van: "is een a een c" moet "ja" geven.
    Alleen bevestigde relaties (status "confirmed" of zonder status); afgewezen
    of onbevestigde schakels doen niet mee. Zelfde seed = zelfde vragen.
    """
    if aantal <= 0 or not os.path.exists(concepts_pad):
        return []
    with open(concepts_pad, encoding="utf-8") as f:
        concepten = json.load(f)

    ouders = {}
    for woord, concept in concepten.items():
        for sense in concept.get("senses", []):
            if sense.get("status") == "rejected":
                continue
            for rel in sense.get("relations", []):
                if rel.get("type") != "is_a":
                    continue
                if rel.get("status") not in (None, "confirmed"):
                    continue
                doel = rel.get("target")
                if isinstance(doel, str):
                    ouders.setdefault(woord, set()).add(doel)

    ketens = set()
    for a in sorted(ouders):
        for b in sorted(ouders[a]):
            for c in sorted(ouders.get(b, ())):
                if len({a, b, c}) < 3:
                    continue
                if not (KETEN_WOORD.match(a) and KETEN_WOORD.match(c)):
                    continue
                ketens.add((a, c))

    ketens = sorted(ketens)
    rng = random.Random(seed)
    gekozen = rng.sample(ketens, min(aantal, len(ketens)))
    cases = []
    for i, (a, c) in enumerate(gekozen, start=1):
        cases.append({
            "id": f"ketting-{i:02d}",
            "categorie": CATEGORIE_KETENS,
            "vraag": f"is een {a} een {c}",
            "moet_event": ["intent_relation_check"],
            "moet_bevatten_een_van": ["ja"],
        })
    return cases


# ---------------------------------------------------------------- beoordelen
def effectieve_case(case, niveau):
    """Op niveau 3 overschrijven de sleutels in case['niveau3'] die van de case zelf."""
    eff = dict(case)
    extra = case.get("niveau3")
    if niveau >= 3 and isinstance(extra, dict):
        eff.update(extra)
    return eff


def beoordeel(case, events, fout, niveau=1, modules_mislukt=None):
    """Geeft (status, reden). status: geslaagd | gefaald | niet_meetbaar | fout"""
    if fout:
        return "fout", fout

    case = effectieve_case(case, niveau)
    namen = [n for n, _ in events]
    redenen = []
    heeft_controle = False
    antwoord_ontbreekt_op_niveau1 = False
    module_ontbreekt = False

    moet_event = case.get("moet_event")
    if moet_event:
        heeft_controle = True
        if not any(n.startswith(p) for n in namen for p in moet_event):
            redenen.append(f"geen event uit {moet_event} (kreeg: {_zonder_ruis(namen)})")

    mag_event_niet = case.get("mag_event_niet")
    if mag_event_niet:
        heeft_controle = True
        verboden = [n for n in namen if any(n.startswith(p) for p in mag_event_niet)]
        if verboden:
            redenen.append(f"verboden event gezien: {verboden}")

    tekst = antwoord_tekst(events)
    moet = case.get("moet_bevatten_een_van")
    alle = case.get("moet_bevatten_alle")
    regex = case.get("moet_overeenkomen_een_van")
    mag_niet = case.get("mag_niet_bevatten")
    if moet or alle or regex or mag_niet:
        heeft_controle = True
        if not tekst:
            if niveau >= 3 and modules_mislukt:
                module_ontbreekt = True
            elif niveau >= 2:
                redenen.append("geen antwoord ontvangen")
            else:
                antwoord_ontbreekt_op_niveau1 = True
        else:
            if moet and not any(bevat_woord(tekst, w) for w in moet):
                redenen.append(f"antwoord mist een van {moet} (antwoord: {tekst[:120]!r})")
            if alle:
                ontbreekt = [w for w in alle if not bevat_woord(tekst, w)]
                if ontbreekt:
                    redenen.append(f"antwoord mist {ontbreekt} (antwoord: {tekst[:120]!r})")
            if regex:
                gevonden = False
                for patroon in regex:
                    try:
                        if re.search(patroon, tekst):
                            gevonden = True
                            break
                    except re.error as e:
                        redenen.append(f"ongeldige reguliere expressie {patroon!r}: {e}")
                if not gevonden and not any("ongeldige reguliere" in r for r in redenen):
                    redenen.append(f"antwoord komt met geen van {regex} overeen (antwoord: {tekst[:120]!r})")
            if mag_niet:
                gezien = [w for w in mag_niet if bevat_woord(tekst, w)]
                if gezien:
                    redenen.append(f"antwoord bevat verboden woord(en) {gezien} (antwoord: {tekst[:120]!r})")

    if redenen:
        return "gefaald", "; ".join(redenen)
    if module_ontbreekt:
        return "niet_meetbaar", "module(s) niet geladen: " + ", ".join(sorted(modules_mislukt))
    heeft_event_controle = bool(moet_event or mag_event_niet)
    if antwoord_ontbreekt_op_niveau1 and not heeft_event_controle:
        return "niet_meetbaar", "alleen antwoord-controle, nog geen antwoord op niveau 1"
    if not heeft_controle:
        return "niet_meetbaar", "case heeft geen controles"
    if antwoord_ontbreekt_op_niveau1:
        return "geslaagd", ANTWOORD_OPEN
    return "geslaagd", ""


def _zonder_ruis(namen):
    return [n for n in namen if n != "raw_user_message"] or ["(geen)"]


def _korte_data(data, max_len=110):
    s = json.dumps(data, ensure_ascii=False, default=str)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def toon_ontdek(case, events, fout, niveau=1):
    print(f"\n[{case['id']}] ({case.get('categorie', '?')}) {case['vraag']}")
    if fout:
        print(f"   CRASH: {fout}")
    zichtbaar = [(n, d) for n, d in events if n != "raw_user_message"]
    if not zichtbaar:
        print("   (niets gepubliceerd)")
    for n, d in zichtbaar:
        print(f"   - {n}  {_korte_data(d)}")
    if niveau >= 2:
        tekst = antwoord_tekst(events)
        print(f"   ANTWOORD: {tekst[:300] if tekst else '(geen)'}")


def laad_cases(pad, categorie):
    with open(pad, encoding="utf-8") as f:
        inhoud = json.load(f)
    cases = inhoud["cases"] if isinstance(inhoud, dict) else inhoud
    if categorie:
        cases = [c for c in cases if c.get("categorie") == categorie]
    return cases


def main():
    ap = argparse.ArgumentParser(description="Nova-benchmark")
    ap.add_argument("--niveau", type=int, choices=(1, 2, 3), default=1,
                    help="1 = routing, 2 = antwoord, 3 = antwoord met extra modules")
    ap.add_argument("--ontdek", action="store_true", help="toon per vraag de events, geen score")
    ap.add_argument("--categorie", help="enkel deze categorie draaien")
    ap.add_argument("--cases", default=CASES_PAD, help="pad naar benchmark_cases.json")
    ap.add_argument("--ongezien", action="store_true",
                    help="draai de ongeziene set (tests/benchmark/benchmark_ongezien.json), apart gescoord")
    ap.add_argument("--willekeurig", type=int, default=0, metavar="N",
                    help="voeg N willekeurige tweestaps-is_a-ketens uit concepts.json toe (niveau 2 of 3)")
    ap.add_argument("--seed", type=int, default=None,
                    help="seed voor --willekeurig (standaard: de datum van vandaag, dus per dag anders)")
    ap.add_argument("--module", action="append", default=[], metavar="PAD",
                    help="extra module op niveau 3, bv. modules.weather.rain (herhaalbaar)")
    ap.add_argument("--geen-opslaan", action="store_true", help="schrijf niets naar data/benchmark_resultaten.jsonl")
    ap.add_argument("--bewaar-kopie", action="store_true", help="verwijder de tijdelijke kopie niet")
    ap.add_argument("--met-netwerk", action="store_true", help="laat netwerk (bv. Wikipedia) toe")
    args = ap.parse_args()

    niveau = args.niveau
    cases_pad = ONGEZIEN_PAD if args.ongezien else args.cases
    verzameling = "ongezien" if args.ongezien else "vast"
    cases = laad_cases(cases_pad, args.categorie)
    if args.willekeurig and niveau < 2:
        print("Let op: --willekeurig werkt pas vanaf --niveau 2 (er is een antwoord nodig). Genegeerd.")
        args.willekeurig = 0
    if not cases and not args.willekeurig:
        print("Geen cases gevonden.")
        return 1

    hash_voor = hash_bestand(ECHT_CONCEPTS_PAD)

    print("Kopie van het project maken (je echte bestanden blijven onaangeroerd)...")
    t0 = time.time()
    tmp_root, kopie = maak_kopie()
    print(f"Kopie klaar in {time.time() - t0:.1f}s: {kopie}")

    try:
        sys.path.insert(0, kopie)
        os.chdir(kopie)
        if not args.met_netwerk:
            zet_netwerk_uit()

        import core.intent_router as router_module
        IntentRouter = router_module.IntentRouter
        controles = [("core.intent_router", getattr(router_module, "__file__", None))]

        keten = None
        seed = None
        if niveau >= 2:
            import core.semantic as semantic_module
            controles.append(("core.semantic", getattr(semantic_module, "__file__", None)))
            controles.append(("CONCEPTS_FILE", os.path.abspath(semantic_module.CONCEPTS_FILE)))
            controles.append(("CONCEPTS_LOG", os.path.abspath(semantic_module.CONCEPTS_LOG)))
        if not controleer_in_kopie(kopie, controles):
            return 2

        if niveau >= 2:
            concepts_kopie = os.path.abspath(semantic_module.CONCEPTS_FILE)
            extra, voorfouten = None, {}
            if niveau == 3:
                namen = list(STANDAARD_NIVEAU3_MODULES)
                namen += [m for m in args.module if m not in namen]
                voorfouten = importeer_modules(namen)
                extra = [n for n in namen if n not in voorfouten]
                if not controleer_in_kopie(
                    kopie,
                    [(n, getattr(sys.modules.get(n), "__file__", None)) for n in extra],
                ):
                    return 2
            keten = Keten(concepts_kopie, extra_modules=extra, voorfouten=voorfouten)

            if args.willekeurig:
                seed = args.seed if args.seed is not None else int(datetime.date.today().strftime("%Y%m%d"))
                ketens = maak_ketenvragen(concepts_kopie, args.willekeurig, seed)
                print(f"Willekeurige ketens: {len(ketens)} vragen (seed {seed}; zelfde seed = zelfde vragen).")
                cases = cases + ketens
                if not cases:
                    print("Geen cases gevonden.")
                    return 1
                if verzameling == "vast":
                    verzameling = "vast+willekeurig"

        nu = nu_brussel()
        resultaten = []
        for case in cases:
            case = los_placeholders_op(case, nu)
            if niveau >= 2:
                events, fout = keten.draai(case["vraag"])
            else:
                events, fout = draai_vraag_niveau1(IntentRouter, case["vraag"])
            if args.ontdek:
                toon_ontdek(case, events, fout, niveau)
                continue
            mislukt = dict(keten.mislukt) if keten else None
            status, reden = beoordeel(case, events, fout, niveau, mislukt)
            resultaten.append((case, status, reden))

        modules_mislukt = dict(keten.mislukt) if keten else {}
        if niveau == 3:
            if modules_mislukt:
                print("\nModules die niet startten (hun cases zijn 'niet meetbaar'):")
                for naam, reden in sorted(modules_mislukt.items()):
                    print(f"  - {naam}: {reden}")
            else:
                print("\nAlle extra modules startten zonder fout.")

        if args.ontdek:
            print("\nKlaar. Kijk of de verwachte events/antwoorden in je cases kloppen met wat hierboven staat.")
            return controleer_echte_data(hash_voor)

        code = rapporteer(resultaten, args.geen_opslaan, niveau, verzameling, seed, modules_mislukt)
        return controleer_echte_data(hash_voor) or code
    finally:
        os.chdir(PROJECT_ROOT)
        if args.bewaar_kopie:
            print(f"Kopie bewaard in {tmp_root}")
        else:
            shutil.rmtree(tmp_root, ignore_errors=True)


def controleer_echte_data(hash_voor):
    hash_na = hash_bestand(ECHT_CONCEPTS_PAD)
    if hash_voor != hash_na:
        print("\n!!! WAARSCHUWING: je ECHTE data/concepts.json is veranderd tijdens de benchmark.")
        print("!!! Herstel hem uit je back-up/git en meld dit, want de isolatie lekt ergens.")
        return 3
    return 0


NIVEAU_NAMEN = {1: "routing", 2: "antwoord", 3: "antwoord met extra modules"}


def rapporteer(resultaten, geen_opslaan, niveau, verzameling="vast", seed=None, modules_mislukt=None):
    per_cat = {}
    for case, status, _ in resultaten:
        d = per_cat.setdefault(case.get("categorie", "?"),
                               {"geslaagd": 0, "gefaald": 0, "fout": 0, "niet_meetbaar": 0})
        d[status] += 1

    print(f"\n=== RESULTAAT (niveau {niveau}: {NIVEAU_NAMEN[niveau]}; set: {verzameling}) ===")
    print(f"{'categorie':<20}{'score':>8}{'goed':>6}{'fout':>6}{'crash':>7}{'n.m.':>6}")
    tot = {"geslaagd": 0, "gefaald": 0, "fout": 0, "niet_meetbaar": 0}
    for cat in sorted(per_cat):
        d = per_cat[cat]
        for k in tot:
            tot[k] += d[k]
        print(f"{cat:<20}{_score(d):>8}{d['geslaagd']:>6}{d['gefaald']:>6}{d['fout']:>7}{d['niet_meetbaar']:>6}")
    print("-" * 53)
    print(f"{'TOTAAL':<20}{_score(tot):>8}{tot['geslaagd']:>6}{tot['gefaald']:>6}{tot['fout']:>7}{tot['niet_meetbaar']:>6}")
    print("(n.m. = niet meetbaar op dit niveau, telt niet mee in de score)")
    antwoord_open = sum(1 for _, s, r in resultaten if s == "geslaagd" and r == ANTWOORD_OPEN)
    if niveau == 1:
        print(f"De score hierboven is ROUTING-niveau. Bij {antwoord_open} geslaagde cases wacht ook nog "
              f"een antwoord-controle (niveau 2).")

    mislukt = [(c, s, r) for c, s, r in resultaten if s in ("gefaald", "fout")]
    if mislukt:
        print("\nMislukte cases:")
        for c, s, r in mislukt:
            print(f"  [{c['id']}] {c['vraag']!r}\n      {s}: {r}")

    nm = [(c, r) for c, s, r in resultaten if s == "niet_meetbaar"]
    if nm and niveau == 3:
        print("\nNiet meetbaar:")
        for c, r in nm:
            print(f"  [{c['id']}] {c['vraag']!r}: {r}")

    if not geen_opslaan:
        record = {
            "datum": datetime.datetime.now().isoformat(timespec="seconds"),
            "niveau": NIVEAU_NAMEN[niveau],
            "verzameling": verzameling,
            "totaal": tot,
            "antwoord_open": antwoord_open,
            "per_categorie": per_cat,
            "mislukt": [c["id"] for c, _, _ in mislukt],
        }
        if seed is not None:
            record["seed"] = seed
        if modules_mislukt:
            record["modules_mislukt"] = sorted(modules_mislukt)
        os.makedirs(os.path.dirname(RESULTATEN_PAD), exist_ok=True)
        with open(RESULTATEN_PAD, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"\nResultaat toegevoegd aan {os.path.relpath(RESULTATEN_PAD, PROJECT_ROOT)}")
    return 0


def _score(d):
    meetbaar = d["geslaagd"] + d["gefaald"] + d["fout"]
    return "-" if meetbaar == 0 else f"{100 * d['geslaagd'] / meetbaar:.0f}%"


if __name__ == "__main__":
    sys.exit(main())