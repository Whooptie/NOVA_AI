#!/usr/bin/env python3
# tools/run_benchmark.py
"""
Nova-benchmark. Twee niveaus, puur symbolisch (tekst vergelijken, geen ML).

  Niveau 1 (standaard): ROUTING. Stuurt elke vraag door IntentRouter.route()
      en kijkt welke events de router publiceert (intent_definition, ...).
  Niveau 2 (--niveau 2): ANTWOORD. Bouwt een mini-Nova van vier onderdelen
      (echte EventBus + SemanticConceptsModule + ChatModule + IntentRouter)
      en vangt het echte antwoord op (chat_response / layer4_response).
      Er wordt GEEN ModuleLoader gestart: dus geen poort 8765, geen webcam,
      geen achtergrondlussen.

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
  python tools/run_benchmark.py                        # score niveau 1
  python tools/run_benchmark.py --niveau 2             # score niveau 2
  python tools/run_benchmark.py --niveau 2 --categorie afgewezen_feit

CONTROLES IN EEN CASE (alle optioneel)
  moet_event            lijst: minstens een gepubliceerd event begint met een van deze namen
  mag_event_niet        lijst: geen enkel event begint met een van deze namen
  moet_bevatten_een_van lijst woorden (HELE woorden) in het ANTWOORD
  mag_niet_bevatten     lijst woorden (HELE woorden) die NIET in het ANTWOORD mogen staan
  Het ANTWOORD bestaat enkel uit events "chat_response" en "layer4_response".
  Niveau 1: tekstcontroles zijn dan nog niet meetbaar (geen fout).
  Niveau 2: een tekstcontrole zonder enig antwoord telt als gefaald.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import sys
import tempfile
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_PAD = os.path.join(PROJECT_ROOT, "tests", "benchmark", "benchmark_cases.json")
RESULTATEN_PAD = os.path.join(PROJECT_ROOT, "data", "benchmark_resultaten.jsonl")
ECHT_CONCEPTS_PAD = os.path.join(PROJECT_ROOT, "data", "concepts.json")

ANTWOORD_EVENTS = {"chat_response", "layer4_response"}
ANTWOORD_OPEN = "antwoord-controle nog open"
NEGEER_BIJ_KOPIE = (".git", "__pycache__", ".pytest_cache", "engines", "logs", "*.log", "*.pyc")
TIJDSLIMIET_SECONDEN = 20


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


# ---------------------------------------------------------------- niveau 2
class Keten:
    """Bouwt per vraag een verse mini-Nova en zet concepts.json eerst terug."""

    def __init__(self, concepts_pad):
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
        with open(concepts_pad, "rb") as f:
            self._concepts_origineel = f.read() if os.path.exists(concepts_pad) else b"{}"

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
            self._chat(bus, semantic_module=sem)
            router = self._router(bus, semantic_module=sem)
            router.route({"text": vraag}, "chat_message")

        _, fout = draai_met_tijdslimiet(_doe)
        if not fout:
            handler_fouten = list(getattr(bus, "fouten", None) or [])
            if handler_fouten:
                fout = f"handler-fout in de EventBus: {handler_fouten[-1]}"
        return bus.opgenomen, fout


# ---------------------------------------------------------------- beoordelen
def beoordeel(case, events, fout, niveau=1):
    """Geeft (status, reden). status: geslaagd | gefaald | niet_meetbaar | fout"""
    if fout:
        return "fout", fout

    namen = [n for n, _ in events]
    redenen = []
    heeft_controle = False
    antwoord_ontbreekt_op_niveau1 = False

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
    mag_niet = case.get("mag_niet_bevatten")
    if moet or mag_niet:
        heeft_controle = True
        if not tekst:
            if niveau >= 2:
                redenen.append("geen antwoord ontvangen")
            else:
                antwoord_ontbreekt_op_niveau1 = True
        else:
            if moet and not any(bevat_woord(tekst, w) for w in moet):
                redenen.append(f"antwoord mist een van {moet} (antwoord: {tekst[:120]!r})")
            if mag_niet:
                gezien = [w for w in mag_niet if bevat_woord(tekst, w)]
                if gezien:
                    redenen.append(f"antwoord bevat verboden woord(en) {gezien} (antwoord: {tekst[:120]!r})")

    if redenen:
        return "gefaald", "; ".join(redenen)
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


def toon_ontdek(case, events, fout):
    print(f"\n[{case['id']}] ({case.get('categorie', '?')}) {case['vraag']}")
    if fout:
        print(f"   CRASH: {fout}")
    zichtbaar = [(n, d) for n, d in events if n != "raw_user_message"]
    if not zichtbaar:
        print("   (niets gepubliceerd)")
    for n, d in zichtbaar:
        print(f"   - {n}  {_korte_data(d)}")


def laad_cases(pad, categorie):
    with open(pad, encoding="utf-8") as f:
        inhoud = json.load(f)
    cases = inhoud["cases"] if isinstance(inhoud, dict) else inhoud
    if categorie:
        cases = [c for c in cases if c.get("categorie") == categorie]
    return cases


def main():
    ap = argparse.ArgumentParser(description="Nova-benchmark")
    ap.add_argument("--niveau", type=int, choices=(1, 2), default=1, help="1 = routing, 2 = antwoord")
    ap.add_argument("--ontdek", action="store_true", help="toon per vraag de events, geen score")
    ap.add_argument("--categorie", help="enkel deze categorie draaien")
    ap.add_argument("--cases", default=CASES_PAD, help="pad naar benchmark_cases.json")
    ap.add_argument("--geen-opslaan", action="store_true", help="schrijf niets naar data/benchmark_resultaten.jsonl")
    ap.add_argument("--bewaar-kopie", action="store_true", help="verwijder de tijdelijke kopie niet")
    ap.add_argument("--met-netwerk", action="store_true", help="laat netwerk (bv. Wikipedia) toe")
    args = ap.parse_args()

    cases = laad_cases(args.cases, args.categorie)
    if not cases:
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
        if args.niveau == 2:
            import core.semantic as semantic_module
            controles.append(("core.semantic", getattr(semantic_module, "__file__", None)))
            controles.append(("CONCEPTS_FILE", os.path.abspath(semantic_module.CONCEPTS_FILE)))
            controles.append(("CONCEPTS_LOG", os.path.abspath(semantic_module.CONCEPTS_LOG)))
        if not controleer_in_kopie(kopie, controles):
            return 2
        if args.niveau == 2:
            keten = Keten(os.path.abspath(semantic_module.CONCEPTS_FILE))

        resultaten = []
        for case in cases:
            if args.niveau == 2:
                events, fout = keten.draai(case["vraag"])
            else:
                events, fout = draai_vraag_niveau1(IntentRouter, case["vraag"])
            if args.ontdek:
                toon_ontdek(case, events, fout)
                continue
            status, reden = beoordeel(case, events, fout, args.niveau)
            resultaten.append((case, status, reden))

        if args.ontdek:
            print("\nKlaar. Kijk of de verwachte events/antwoorden in je cases kloppen met wat hierboven staat.")
            return controleer_echte_data(hash_voor)

        code = rapporteer(resultaten, args.geen_opslaan, args.niveau)
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


def rapporteer(resultaten, geen_opslaan, niveau):
    per_cat = {}
    for case, status, _ in resultaten:
        d = per_cat.setdefault(case.get("categorie", "?"),
                               {"geslaagd": 0, "gefaald": 0, "fout": 0, "niet_meetbaar": 0})
        d[status] += 1

    print(f"\n=== RESULTAAT (niveau {niveau}: {'routing' if niveau == 1 else 'antwoord'}) ===")
    print(f"{'categorie':<18}{'score':>8}{'goed':>6}{'fout':>6}{'crash':>7}{'n.m.':>6}")
    tot = {"geslaagd": 0, "gefaald": 0, "fout": 0, "niet_meetbaar": 0}
    for cat in sorted(per_cat):
        d = per_cat[cat]
        for k in tot:
            tot[k] += d[k]
        print(f"{cat:<18}{_score(d):>8}{d['geslaagd']:>6}{d['gefaald']:>6}{d['fout']:>7}{d['niet_meetbaar']:>6}")
    print("-" * 51)
    print(f"{'TOTAAL':<18}{_score(tot):>8}{tot['geslaagd']:>6}{tot['gefaald']:>6}{tot['fout']:>7}{tot['niet_meetbaar']:>6}")
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

    if not geen_opslaan:
        record = {
            "datum": datetime.datetime.now().isoformat(timespec="seconds"),
            "niveau": "routing" if niveau == 1 else "antwoord",
            "totaal": tot,
            "antwoord_open": antwoord_open,
            "per_categorie": per_cat,
            "mislukt": [c["id"] for c, _, _ in mislukt],
        }
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