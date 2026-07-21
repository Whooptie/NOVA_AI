# core/llm_bridge.py

"""
llm_bridge.py

Optionele "stylist"-laag voor Layer 4 (response_engine.py).

Belangrijk: dit is GEEN los geladen EventBus-module. Het volgt niet de
standaard init_module(event_bus, sem)-conventie, want het wordt rechtstreeks
geïmporteerd en aangeroepen door response_engine.py, net zoals response_engine.py
zelf Layer 1/2/3 rechtstreeks als Python-methodes aanroept.

Werking:
  1. genereer_zin() stuurt een klein feiten-pakket naar een lokaal Ollama-model
  2. valideer() checkt of de kernwoorden echt in het antwoord voorkomen
  3. Bij twijfel/fout/timeout: geeft None terug, zodat response_engine.py
     gewoon zijn bestaande sjabloon gebruikt (fallback, geen crash)

Vereist: Ollama moet lokaal draaien (start-ollama / Ollama-app actief) en het
model "qwen2.5:3b" moet al gedownload zijn (zie llm_layer4_bridge_roadmap.md).
"""

import requests
import logging

logger = logging.getLogger("nova.llm_bridge")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAAM = "qwen2.5:3b"
TIMEOUT_SECONDEN = 8  # als Ollama niet binnen deze tijd antwoordt, val terug op sjabloon

PROMPT_SJABLOON = (
    "Je bent een tekstgenerator. Je antwoord bestaat UITSLUITEND uit de "
    "gevraagde zin zelf — geen inleiding, geen herhaling van deze instructie, "
    "geen aanhalingstekens eromheen, geen uitleg vooraf of achteraf, en "
    "gebruik nooit de woorden \"eigenschap\" of \"onderwerp\" letterlijk in "
    "je antwoord — verwerk die informatie natuurlijk in de zin.\n\n"
    "Regels voor de zin:\n"
    "- Derde persoon, alsof een verteller over het onderwerp praat.\n"
    "- Nooit als het onderwerp zelf spreken (geen \"ik ben...\").\n"
    "- Begin de zin met de naam van het onderwerp zelf, niet met de categorie.\n"
    "- Toon: kalm, droog, licht sarcastisch.\n"
    "- Gebruik uitsluitend onderstaande feiten, verzin niets bij.\n"
    "- Gebruik het woord \"{kernwoord}\" letterlijk.\n\n"
    "Onderwerp waarover de zin gaat: {entity}\n"
    "Dit is een: {is_a}\n"
    "Extra weetje om te verwerken: {property}\n\n"
    "Jouw antwoord (enkel de zin, niets anders):"
)

# Fragmenten die erop wijzen dat het model (een deel van) de instructie
# papegaait in plaats van enkel de gevraagde zin te geven. Wordt gebruikt
# in valideer() om instructie-echo te herkennen en af te wijzen.
INSTRUCTIE_ECHO_FRAGMENTEN = [
    "vloeiende nederlandse zin",
    "beschrijft het onderwerp",
    "beschrijf, in de derde persoon",
    "geef enkel de zin",
    "geef alleen de zin",
    "jouw antwoord",
    "in de derde persoon",
    "niets anders",
    "eigenschap",  # prompt-lek: label uit onze eigen prompt-structuur
    "onderwerp waarover",  # prompt-lek: fragment van het "Onderwerp:"-label
]


def genereer_zin(entity: str, is_a: str, property_tekst: str = "") -> str | None:
    """
    Stuurt de gegeven feiten naar het lokale Ollama-model en probeert er
    één vloeiende Nederlandse zin van te maken.

    Geeft de kandidaat-zin terug als string, of None bij elke vorm van
    falen (Ollama niet bereikbaar, timeout, leeg antwoord, validatie-fout).
    response_engine.py moet bij None gewoon zijn bestaande sjabloon gebruiken.
    """
    if not entity or not is_a:
        # Zonder minimale feiten heeft aanroepen geen zin
        return None

    prompt = PROMPT_SJABLOON.format(
        kernwoord=is_a,
        entity=entity,
        is_a=is_a,
        property=property_tekst or "onbekend",
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAAM,
                "prompt": prompt,
                "stream": False,
            },
            timeout=TIMEOUT_SECONDEN,
        )
        response.raise_for_status()
        data = response.json()
        kandidaat = data.get("response", "").strip()
    except requests.exceptions.Timeout:
        logger.warning(
            f"[llm_bridge] Timeout na {TIMEOUT_SECONDEN}s bij entity='{entity}' "
            f"(reden: None -> TIMEOUT)"
        )
        return None
    except requests.exceptions.ConnectionError as e:
        logger.warning(
            f"[llm_bridge] Kan Ollama niet bereiken op {OLLAMA_URL} "
            f"(reden: None -> CONNECTION_ERROR): {e}"
        )
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(
            f"[llm_bridge] Onverwachte netwerkfout bij entity='{entity}' "
            f"(reden: None -> REQUEST_ERROR): {e}"
        )
        return None
    except (ValueError, KeyError) as e:
        logger.warning(
            f"[llm_bridge] Onverwacht Ollama-antwoordformaat bij entity='{entity}' "
            f"(reden: None -> PARSE_ERROR): {e}"
        )
        return None

    if not kandidaat:
        logger.info(
            f"[llm_bridge] Leeg antwoord van Ollama voor entity='{entity}' "
            f"(reden: None -> LEEG_ANTWOORD)"
        )
        return None

    if not valideer(kandidaat, entity, is_a):
        logger.info(
            f"[llm_bridge] Validatie afgewezen voor entity='{entity}' "
            f"(reden: None -> VALIDATIE_AFGEWEZEN): '{kandidaat}'"
        )
        return None

    return kandidaat


def valideer(kandidaat_tekst: str, entity: str, is_a: str) -> bool:
    """
    Simpele, symbolische vangrail: controleert of de kernwoorden uit de
    oorspronkelijke feiten ook echt (case-insensitive) in de gegenereerde
    tekst voorkomen. Geen taalkundige magie, gewoon stringmatching.

    Dit vangt niet elke denkbare fout op (bv. rolverwarring als "ik ben een
    gitaar" bevat wel degelijk de juiste kernwoorden), maar filtert wel de
    duidelijkste categorie fouten: het model dat het onderwerp of het
    kernfeit gewoon vergeet te noemen.
    """
    if not kandidaat_tekst:
        return False

    tekst_lower = kandidaat_tekst.lower()

    if entity.lower() not in tekst_lower:
        return False
    if is_a.lower() not in tekst_lower:
        return False

    # Kort sanity-check op lengte: te lang duidt vaak op afdwalen/fantaseren
    if len(kandidaat_tekst) > 300:
        return False

    # Instructie-echo check: wijst het antwoord af als het (een deel van)
    # de prompt-instructie zelf herhaalt, i.p.v. enkel de gevraagde zin
    # te geven. Zie testresultaten (20 juli 2026): het model papegaaide
    # soms frasen als "in ÉÉN vloeiende Nederlandse zin" mee in de output,
    # of nam het label "eigenschap" letterlijk over uit de prompt.
    for fragment in INSTRUCTIE_ECHO_FRAGMENTEN:
        if fragment in tekst_lower:
            return False

    # Lichte grammaticale sanity-check: een correcte Nederlandse zin over
    # een onderwerp bevat vrijwel altijd een van deze veelvoorkomende
    # koppel-/hulpwerkwoorden. Ontbreken ze allemaal, dan is de kans groot
    # dat de zin kromme, telegramstijl-achtige constructies bevat (zoals
    # "Honden zoogdieren zijn vaak..." zonder correcte koppeling).
    # Dit is GEEN volwaardige grammaticacontrole, enkel een grove filter.
    VEELVOORKOMENDE_WERKWOORDEN = [
        " is ", " zijn ", " wordt ", " worden ", " heeft ", " hebben ",
        " kan ", " kunnen ", " bestaat ", " bevat ",
    ]
    if not any(ww in f" {tekst_lower} " for ww in VEELVOORKOMENDE_WERKWOORDEN):
        return False

    return True


def is_ollama_bereikbaar() -> bool:
    """
    Optionele, snelle check of Ollama's lokale server draait — bruikbaar
    voor een config-check bij het opstarten van Nova, zonder meteen een
    volledige generatie te proberen.
    """
    try:
        response = requests.get("http://localhost:11434", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False