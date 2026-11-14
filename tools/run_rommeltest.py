#!/usr/bin/env python3
# tools/run_rommeltest.py
"""
Rommel-invoertest (14 november 2026): gooit rare, lege, enorme en willekeurige zinnen op Nova
en kijkt of er iets crasht of blijft hangen.

WAAROM?
  Tests controleren wat jij bedacht hebt. Een echte gebruiker (of een typfout, of een plakactie
  met een vreemd teken) levert invoer die je NIET bedacht had. Deze test zoekt precies die
  gaten: lege tekst, 100.000 tekens, emoji, besturingstekens, rekenopgaven die kapot zijn,
  "SQL"-tekst, en een reeks willekeurige zinnen (met een vaste seed, dus herhaalbaar).

HOE?
  Hetzelfde als tools/run_benchmark.py (niveau 3): een KOPIE van het project in een tijdelijke
  map, daarin een mini-Nova (EventBus, semantiek, chat, router, tijd, kalender, rekenmodule).
  Je echte bestanden en data blijven onaangeroerd; het netwerk staat uit. Elke invoer krijgt
  een verse mini-Nova. Een CRASH is: een fout uit de code, een handler-fout in de EventBus of
  een tijdslimiet. Een goed of fout ANTWOORD telt niet: alleen of Nova overeind blijft.

GEBRUIK (vanuit de projectmap, bv. /app)
  python tools/run_rommeltest.py              # vaste rare invoer + 60 willekeurige
  python tools/run_rommeltest.py --aantal 200 --seed 7
  python tools/run_rommeltest.py --toon       # print ook elke invoer die goed ging

De laatste regel is "ROMMELTEST: ..."; die leest de zelftest (modules/diagnose/controles_robuust.py).
Exitcode 1 als er iets crashte of te traag was, 2 als de kopie niet veilig was.

PUUR SYMBOLISCH: tekst in, kijken of er een fout uitkomt. Geen ML.
"""

import argparse
import datetime
import os
import random
import shutil
import statistics
import string
import sys
import time

TOOLS_MAP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_MAP)
import run_benchmark as rb  # noqa: E402

TIJDSLIMIET = 10          # seconden per invoer
MAX_TOONBAAR = 40         # tekens van een invoer in het rapport

NEDERLANDSE_WOORDEN = (
    "wat", "is", "een", "kat", "hond", "weer", "morgen", "regen", "hoe", "laat", "het", "ik", "jij",
    "heet", "leer", "vergeet", "niet", "wel", "en", "of", "dan", "omdat", "plus", "min", "keer",
    "gedeeld", "door", "dag", "vandaag", "gisteren", "feestdag", "zon", "huis", "boom",
)
RARE_TEKENS = "éèëïöüñçßøåæœ€£¥§±×÷°™©®¿¡«»‰†‡•…—–“”‘’ĳ"


def vaste_invoer():
    """Handgemaakte lastige invoer. Elke regel is iets wat in het echt kan gebeuren."""
    return [
        "", " ", "\n", "\t\t", "   \n  ", ".", "?", "!!!???", "....", "a", "ä", "-", "--", "'", '"', "\\", "/",
        "()", "((((((((((", "))))))))", "[]", "{}", "{{}}", "{0}", "%s", "%d %s %x", "${x}", "$(ls)", "`ls`",
        "<script>alert(1)</script>", "'; DROP TABLE interactions;--", "../../etc/passwd", "\x00", "a\x00b",
        "\x1b[31mrood\x1b[0m", "\r\n\r\n", "\x7f\x08", "🙂", "🙂" * 500, "\u202eachterstevoren", "e\u0301" * 200,
        "\u200b" * 100, "\ufeffhallo", "٣٤٥", "１２３", "日本語のテキスト", "Привет мир", "שלום עולם",
        "0", "-1", "3.14", "1e999", "-1e999", "nan", "inf", "9" * 400, "1/0", "0/0", "0**0", "sqrt(-1)",
        "log(0)", "1+" * 200 + "1", "(" * 300 + "1" + ")" * 300, "2**10000", "1000000 keer 1000000", "9**9**9",
        "hoeveel is 99999999999**99999999", "factorial(99999999)", "hoeveel is 10 tot de macht 10000000",
        "x" * 10000, "x" * 100000, "a " * 5000, "wat is " + "een " * 2000 + "kat",
        "ik heet " + "a" * 5000, "weer " + "?" * 1000, "teach", "teach a", "teach a is_a", "wat is",
        "wat is een", "is een kat een", "en?", "en een", "ja", "nee", "ok", "dank", "hoeveel is",
        "hoeveel is plus", "hoeveel is 5 gedeeld door 0", "wat is 5 gedeeld door nul",
        "welke dag is het over 99999999 dagen", "welke dag was het 99999999 dagen geleden",
        "wanneer is 31 februari", "wanneer is 0 januari", "hoe laat is het in nergens",
        "weer in " + "a" * 500, "Wie is " + "Z" * 300, "ik hou van " + "🙂" * 50,
    ]


def willekeurige_invoer(aantal, seed):
    """Deterministisch (zelfde seed = zelfde zinnen): woordensalade en tekenbrij."""
    r = random.Random(seed)  # nosec B311 - voorspelbare test-invoer, geen beveiliging
    alfabet = string.ascii_letters + string.digits + string.punctuation + "  " + RARE_TEKENS
    uit = []
    for _ in range(aantal):
        if r.random() < 0.5:
            uit.append(" ".join(r.choice(NEDERLANDSE_WOORDEN) for _ in range(r.randint(1, 25))))
        else:
            uit.append("".join(r.choice(alfabet) for _ in range(r.randint(1, 300))))
    return uit


def kort(tekst, max_len=MAX_TOONBAAR):
    """Een invoer leesbaar in een rapport (repr, afgekapt)."""
    t = repr(tekst)
    return t if len(t) <= max_len else t[: max_len - 1] + "…"


def draai(invoeren, toon):
    """Draait alle invoer door een verse mini-Nova. Geeft (crashes, traag, tijden)."""
    import core.semantic as semantic_module

    namen = list(rb.STANDAARD_NIVEAU3_MODULES)
    voorfouten = rb.importeer_modules(namen)
    extra = [n for n in namen if n not in voorfouten]
    controles = [("core.semantic", getattr(semantic_module, "__file__", None)),
                 ("CONCEPTS_FILE", os.path.abspath(semantic_module.CONCEPTS_FILE))]
    controles += [(n, getattr(sys.modules.get(n), "__file__", None)) for n in extra]
    if not rb.controleer_in_kopie(os.getcwd(), controles):
        return None
    keten = rb.Keten(os.path.abspath(semantic_module.CONCEPTS_FILE), extra_modules=extra, voorfouten=voorfouten)

    crashes, traag, tijden = [], [], []
    for invoer in invoeren:
        begin = time.perf_counter()
        _, fout = keten.draai(invoer)
        duur = time.perf_counter() - begin
        tijden.append(duur)
        if fout and "tijdslimiet" in fout:
            traag.append((invoer, fout))
        elif fout:
            crashes.append((invoer, fout))
        elif toon:
            print(f"  ok  {kort(invoer)}")
    return crashes, traag, tijden


def main():
    ap = argparse.ArgumentParser(description="Nova rommel-invoertest")
    ap.add_argument("--aantal", type=int, default=60, help="aantal willekeurige invoeren erbij (standaard 60)")
    ap.add_argument("--seed", type=int, default=None, help="seed (standaard: de datum van vandaag)")
    ap.add_argument("--toon", action="store_true", help="print ook de invoer die goed ging")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else int(datetime.date.today().strftime("%Y%m%d"))
    invoeren = vaste_invoer() + willekeurige_invoer(max(args.aantal, 0), seed)
    rb.TIJDSLIMIET_SECONDEN = TIJDSLIMIET

    hash_voor = rb.hash_bestand(rb.ECHT_CONCEPTS_PAD)
    print("Kopie van het project maken (je echte bestanden blijven onaangeroerd)...")
    tmp_root, kopie = rb.maak_kopie()
    try:
        sys.path.insert(0, kopie)
        os.chdir(kopie)
        rb.zet_netwerk_uit()
        resultaat = draai(invoeren, args.toon)
        if resultaat is None:
            return 2
        crashes, traag, tijden = resultaat
        mediaan = statistics.median(tijden) * 1000 if tijden else 0.0
        langste = max(tijden) * 1000 if tijden else 0.0
        if crashes:
            print("\n--- CRASHES (invoer en fout)")
            for invoer, fout in crashes[:15]:
                print(f"  [{kort(invoer)}] {fout[:150]}")
        if traag:
            print("\n--- TE TRAAG (tijdslimiet)")
            for invoer, fout in traag[:15]:
                print(f"  [{kort(invoer)}] {fout[:150]}")
        print(f"ROMMELTEST: {len(invoeren)} invoeren, {len(crashes)} crashes, {len(traag)} te traag, "
              f"mediaan {mediaan:.0f} ms, langste {langste:.0f} ms (seed {seed})")
        return rb.controleer_echte_data(hash_voor) or (1 if crashes or traag else 0)
    finally:
        os.chdir(rb.PROJECT_ROOT)
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())