# test_forceer_anomalieen.py
#
# LOS TESTSCRIPT — NIET onderdeel van Nova zelf, niet in modules/ zetten.
# Draai dit vanuit C:\Nova_AI, TERWIJL NOVA NIET DRAAIT (eerst 'exit' typen).
#
# Doel: 3 nepanomalieën van "vandaag" toevoegen aan patterns_layer2.json,
# zodat je kan testen of context_manager.py's should_interrupt daadwerkelijk
# op False springt zodra er >= 3 anomalieën vandaag zijn.
#
# Na de test: gewoon dit script niet meer draaien. Je kan de 3 nep-
# anomalieën gerust laten staan (ze zijn onschadelijk, puur test-data),
# of ze handmatig weer verwijderen uit patterns_layer2.json indien gewenst.
#
# Gebruik:
#   (venv) PS C:\Nova_AI> python test_forceer_anomalieen.py

import json
from pathlib import Path
from datetime import datetime

PAD = Path(__file__).resolve().parent / "data" / "patterns_layer2.json"

def main():
    if not PAD.exists():
        print(f"Bestand niet gevonden: {PAD}")
        print("Heb je Nova al minstens 1x gedraaid? patterns_layer2.json wordt pas aangemaakt na de eerste opslag.")
        return

    with open(PAD, "r", encoding="utf-8") as f:
        data = json.load(f)

    anomalieen = data.get("anomalies", [])

    nu = datetime.now().timestamp()

    nep_anomalieen = [
        {
            "event_type": "chat_message",
            "type": "ongewone_timing",
            "timestamp": nu,
            "omschrijving": "TESTDATA: nepanomalie 1 (door test_forceer_anomalieen.py)"
        },
        {
            "event_type": "chat_message",
            "type": "ongewone_timing",
            "timestamp": nu,
            "omschrijving": "TESTDATA: nepanomalie 2 (door test_forceer_anomalieen.py)"
        },
        {
            "event_type": "chat_message",
            "type": "ongewone_timing",
            "timestamp": nu,
            "omschrijving": "TESTDATA: nepanomalie 3 (door test_forceer_anomalieen.py)"
        },
    ]

    # Vooraan toevoegen, want pattern_matcher.py's eigen _log_anomalie()
    # doet dat ook (meest recente eerst).
    data["anomalies"] = nep_anomalieen + anomalieen

    with open(PAD, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"3 nepanomalieën toegevoegd aan {PAD}")
    print("Start Nova nu opnieuw en typ 'context' — should_interrupt zou nu False moeten zijn.")


if __name__ == "__main__":
    main()