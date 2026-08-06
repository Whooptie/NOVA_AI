# scripts/test_atomic_save.py
#
# Test voor de atomic-write-fix in ConceptStore.save() (6 augustus 2026,
# "ConceptStore.save() atomisch maken").
#
# WAT DIT DOET:
# 1. Maakt een WERKKOPIE van je echte concepts.json (nooit het origineel
#    zelf aangeraakt).
# 2. Laadt die werkkopie in een echte ConceptStore.
# 3. Simuleert een crash MIDDEN IN het schrijfproces (een kunstmatige
#    exception, precies zoals een stroomuitval het schrijven zou
#    onderbreken).
# 4. Controleert dat de werkkopie van concepts.json na de crash nog
#    steeds:
#      a) exact hetzelfde is als voor de crash (geen corruptie)
#      b) geldige, leesbare JSON is
#      c) geen achtergebleven .tmp-bestand overlaat
#
# VEILIGHEID: dit script raakt NOOIT je echte data/concepts.json aan --
# alles gebeurt in een apart, tijdelijk testmapje. Je eigen Nova-data
# is op geen enkel moment in gevaar tijdens deze test.
#
# GEBRUIK (Nova hoeft hiervoor niet gestopt te zijn -- dit script werkt
# los van een draaiende Nova, op een eigen kopie):
#   python scripts/test_atomic_save.py

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Zorgt dat "import semantic" werkt ongeacht vanuit welke map je dit
# script start -- zoekt core/semantic.py relatief t.o.v. dit bestand.
HUIDIGE_MAP = Path(__file__).resolve().parent
PROJECT_ROOT = HUIDIGE_MAP.parent
CORE_MAP = PROJECT_ROOT / "core"

if not (CORE_MAP / "semantic.py").exists():
    print(f"FOUT: {CORE_MAP / 'semantic.py'} niet gevonden.")
    print(f"Dit script verwacht te draaien vanuit Nova_AI/scripts/ met")
    print(f"Nova_AI/core/semantic.py ernaast. Pas HUIDIGE_MAP/PROJECT_ROOT")
    print(f"in dit script aan als jouw mapstructuur afwijkt.")
    sys.exit(1)

sys.path.insert(0, str(CORE_MAP))

import semantic  # noqa: E402


def main():
    echte_concepts = PROJECT_ROOT / "data" / "concepts.json"
    if not echte_concepts.exists():
        print(f"FOUT: {echte_concepts} niet gevonden. Pas het pad in dit "
              f"script aan als je Nova ergens anders geïnstalleerd hebt.")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="nova_atomic_save_test_") as tmp_dir:
        tmp_dir = Path(tmp_dir)
        werkkopie_pad = tmp_dir / "concepts.json"
        werk_log_pad = tmp_dir / "concepts.jsonl"

        shutil.copy(echte_concepts, werkkopie_pad)
        print(f"Werkkopie gemaakt in tijdelijke map: {tmp_dir}")
        print("(je echte data/concepts.json wordt niet aangeraakt)\n")

        store = semantic.ConceptStore(
            concepts_file=str(werkkopie_pad),
            log_file=str(werk_log_pad),
        )
        aantal_voor = len(store.concepts)
        print(f"Concepten in werkkopie: {aantal_voor}")

        with open(werkkopie_pad, "r", encoding="utf-8") as f:
            staat_voor_crash = f.read()

        # --- Test 1: normale save werkt correct ---
        print("\n--- Test 1: normale save ---")
        store.concepts["_testconcept_normale_save"] = {
            "senses": [{
                "sense_id": "_testconcept_normale_save#1",
                "definition": "test",
                "pos": "noun",
                "examples": [],
                "relations": [],
                "source": "user",
                "confidence": 1.0,
                "status": "confirmed",
                "audit_log": [],
            }],
            "metadata": {"sources": ["user"]},
            "audit_log": [],
        }
        store.save()

        tmp_bestanden = [f for f in os.listdir(tmp_dir) if ".tmp" in f]
        with open(werkkopie_pad, "r", encoding="utf-8") as f:
            data_na_normale_save = json.load(f)

        test1_ok = (
            len(tmp_bestanden) == 0
            and "_testconcept_normale_save" in data_na_normale_save
            and len(data_na_normale_save) == aantal_voor + 1
        )
        print(f"  Geen achtergebleven .tmp-bestanden: {len(tmp_bestanden) == 0}")
        print(f"  Nieuw concept correct opgeslagen: "
              f"{'_testconcept_normale_save' in data_na_normale_save}")
        print(f"  Aantal concepten klopt ({aantal_voor} + 1): "
              f"{len(data_na_normale_save) == aantal_voor + 1}")
        print(f"  TEST 1: {'GESLAAGD' if test1_ok else 'GEFAALD'}")

        # Terug naar de staat van voor test 1, voor een schone test 2
        with open(werkkopie_pad, "w", encoding="utf-8") as f:
            f.write(staat_voor_crash)
        store.concepts = store._load()

        # --- Test 2: gecontroleerde crash tijdens het schrijven ---
        print("\n--- Test 2: gesimuleerde crash tijdens save() ---")

        origineel_dump = json.dump

        def crashende_dump(obj, fp, *args, **kwargs):
            # Schrijft eerst een stuk ONGELDIGE data (zoals een
            # halverwege afgebroken write bij een echte stroomuitval),
            # en gooit daarna een exception -- simuleert het moment
            # waarop de stroom letterlijk wegvalt terwijl er al wat
            # bytes onderweg waren.
            fp.write('{"kapot_door_gesimuleerde_stroomuitval')
            raise OSError("Gesimuleerde crash tijdens json.dump()")

        json.dump = crashende_dump
        crash_opgevangen = False
        try:
            store.concepts["_dit_mag_nooit_opgeslagen_worden"] = {"senses": []}
            store.save()
        except OSError:
            crash_opgevangen = True
        finally:
            json.dump = origineel_dump

        tmp_bestanden_na_crash = [f for f in os.listdir(tmp_dir) if ".tmp" in f]
        with open(werkkopie_pad, "r", encoding="utf-8") as f:
            staat_na_crash = f.read()

        bestand_ongewijzigd = (staat_na_crash == staat_voor_crash)

        json_nog_geldig = True
        aantal_na_crash = None
        try:
            with open(werkkopie_pad, "r", encoding="utf-8") as f:
                data_na_crash = json.load(f)
            aantal_na_crash = len(data_na_crash)
        except json.JSONDecodeError:
            json_nog_geldig = False

        test2_ok = (
            crash_opgevangen
            and len(tmp_bestanden_na_crash) == 0
            and bestand_ongewijzigd
            and json_nog_geldig
        )

        print(f"  Crash correct opgevangen (geen silent failure): {crash_opgevangen}")
        print(f"  Geen achtergebleven .tmp-bestanden: {len(tmp_bestanden_na_crash) == 0}")
        print(f"  concepts.json exact ongewijzigd t.o.v. voor de crash: {bestand_ongewijzigd}")
        print(f"  concepts.json nog steeds geldige JSON: {json_nog_geldig}")
        if aantal_na_crash is not None:
            print(f"  Aantal concepten na crash (moet {aantal_voor} zijn, "
                  f"NIET {aantal_voor + 1}): {aantal_na_crash}")
        print(f"  TEST 2: {'GESLAAGD' if test2_ok else 'GEFAALD'}")

        print("\n" + "=" * 50)
        if test1_ok and test2_ok:
            print("ALLE TESTEN GESLAAGD")
            print("De atomic-write-fix beschermt concepts.json correct")
            print("tegen een onderbroken schrijfactie.")
        else:
            print("ER IS IETS MIS -- controleer de output hierboven.")
            print("Je echte data/concepts.json is NIET aangeraakt door")
            print("deze test, dus er is geen actie nodig aan je eigen data.")
        print("=" * 50)


if __name__ == "__main__":
    main()