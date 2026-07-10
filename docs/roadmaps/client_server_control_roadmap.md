# Client-Server & Apparaatbediening Roadmap: Laptop + Gsm

**Status:** Concept/idee, verre toekomst — geen prioriteit, niet ingepland in bouwvolgorde
**Depends on:** event_bus.py ✅, memory_24-7_daemon_addendum.md ✅ (Nova moet al 24/7 draaien vóór dit zinvol is)
**Gerelateerd:** nova_modules_overview.md (bevat reeds geplande, nog niet gebouwde modules die hier samenkomen), Jarvis_NOVA_Hystory (originele client-server-visie)
**Datum:** 10 juli 2026

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Architectuur: één brein, meerdere gezichten](#architectuur)
3. [Deel A: laptop bedienen](#deel-a)
4. [Deel B: gsm bedienen — meldingen, voorlezen, spraakantwoord](#deel-b)
5. [De ene ML-grens in dit hele plan](#ml-grens)
6. [Netwerk: hoe gsm de pc bereikt van buitenaf](#netwerk)
7. [Fase-roadmap](#fase-roadmap)
8. [Eerlijkheid: wat kan wel/niet, en hoe dit oogt van buitenaf](#eerlijkheid)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

Kevin wil dat Nova, als ze ooit 24/7 op een headless pc draait, niet enkel "een brein op een server" is, maar ook effectief:
- **Zijn laptop kan bedienen** zoals ze zou doen als ze daar zelf op draaide (apps openen, bestanden lezen, vensters beheren)
- **Zijn gsm kan bedienen**: zeggen dat er een bericht is, vragen of ze het mag voorlezen, het voorlezen, zijn gesproken antwoord omzetten naar tekst, en dat versturen
- Dit alles vanaf **één centraal brein** op de headless pc, niet als drie losse Nova's

---

## ARCHITECTUUR: ÉÉN BREIN, MEERDERE GEZICHTEN {#architectuur}

Dit bouwt rechtstreeks voort op de client-server-visie die al in `Jarvis_NOVA_Hystory` stond:

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Laptop     │────▶│  Nova Core       │◀────│   Gsm        │
│  (client)    │ WS  │  (headless pc)   │ WS  │  (client)    │
└──────────────┘     └────────┬─────────┘     └──────────────┘
                               │
                        EventBus, memory,
                        semantic layer,
                        alle 7 lagen
```

**Kernprincipe:** de headless pc draait de volledige Nova — EventBus, geheugen, semantic layer, alle logica, 24/7. Laptop en gsm zijn **clients**: ze sturen input naar de server en voeren, wanneer gevraagd, acties uit op het apparaat waar ze zelf op draaien (een app openen op de laptop kán alleen via de laptop-client; Nova op de server kan dat niet rechtstreeks).

**Wat dit concreet betekent per apparaat:**
- **Laptop-client:** een klein achtergrondprogramma op de laptop zelf, dat luistert naar commando's van de server ("open Chrome", "welke vensters staan open?") en dat lokaal uitvoert via Windows-systeemaanroepen. Resultaat gaat terug naar de server.
- **Gsm-client:** een kleine app (of Tasker-achtige automatiseringstool) die meldingen doorstuurt naar de server, en commando's van de server ontvangt (bv. "lees dit voor", "stuur dit bericht").

Dit is dezelfde WebSocket-verbinding als in de vorige roadmap besproken — geen nieuwe technologie, wel een uitbreiding van wat er via die verbinding gestuurd wordt (niet enkel chatberichten, ook systeemcommando's).

---

## DEEL A: LAPTOP BEDIENEN {#deel-a}

**100% symbolisch, geen ML.** Dit is pure systeemaanroepen — Windows biedt daar keurige, documenteerde API's voor.

Dit staat al gedeeltelijk gepland in `nova_modules_overview.md` (System & Control-sectie), nog niet gebouwd:

| Module | Wat het doet |
|---|---|
| `app_controller.py` | Centrale hub voor desktop-acties — apps openen/sluiten |
| `window_switcher.py` | Lijst actieve vensters, wissel van focus |
| `file_manager.py` | Bestanden openen, sluiten, oplijsten |
| `doc_reader.py` | Leest tekstbestanden (.txt, .md), geeft preview |
| `os_command_center.py` | Veilige systeemacties (wifi/bluetooth/helderheid/…) |
| `reflex_bridge.py` | Koppelt desktop-events (welke app/document actief is) aan Nova's reflexen/mood |

```
Kevin (via gsm of laptop-chat): "Open mijn browser en zoek dit adres op"
       ↓
event_bus.publish("laptop:open_app", {"app": "chrome", "url": "..."})
       ↓
laptop-client ontvangt dit via WebSocket
       ↓
voert lokaal uit via Windows-API (bv. subprocess/os-aanroep)
       ↓
event_bus.publish("laptop:action_result", {"status": "ok"})
```

**Belangrijke opmerking over veiligheid:** `os_command_center.py` moet **altijd** een whitelist van toegestane acties hanteren (wifi aan/uit, app X openen, helderheid aanpassen) — nooit een vrije "voer dit commando uit"-vorm. Dit voorkomt dat een bug of misverstane zin per ongeluk iets destructiefs doet op je laptop.

---

## DEEL B: GSM BEDIENEN — MELDINGEN, VOORLEZEN, SPRAAKANTWOORD {#deel-b}

Dit is het scenario dat Kevin specifiek noemde: Nova zegt "je hebt een bericht", vraagt of ze het mag voorlezen, leest het voor, en giet Kevin's gesproken antwoord om in tekst om te versturen.

**Stap voor stap, met een eerlijke ML-vermelding per stap:**

```
1. Bericht komt binnen op gsm (bv. WhatsApp/SMS)
   → gsm-client vangt de melding op (Android Notification Listener)
   → event_bus.publish("gsm:message_received", {"app": "...", "afzender": "...", "preview": "..."})
   [100% symbolisch — gewoon een notificatie doorsturen]

2. Nova meldt dit proactief aan Kevin
   → "Je hebt een bericht van [afzender], wil je dat ik het voorlees?"
   [100% symbolisch — vaste sjabloonzin via response_engine.py,
    gefilterd via notification_priority.py / do_not_disturb_manager.py
    zodat Nova niet als een spervuur van meldingen aanvoelt]

3. Kevin zegt "ja"
   → Nova haalt volledige berichttekst op via gsm-client
   → leest voor via TTS (text-to-speech)
   [100% symbolisch qua Nova-logica — TTS is een bounded extern tool,
    geen "begrip" nodig, gewoon tekst → spraak, zoals bv. Piper/Windows SAPI]

4. Kevin antwoordt mondeling
   → gsm/laptop-microfoon vangt spraak op
   → STT (speech-to-text) zet dit om in tekst
   [⚠️ DIT IS HET ENIGE STUK DAT ECHT ML VEREIST — zie hieronder]

5. Nova stuurt de tekst als bericht terug
   → event_bus.publish("gsm:send_message", {"app": "...", "naar": "...", "tekst": "..."})
   → gsm-client verstuurt via Android-intent
   [100% symbolisch — gewoon een API-aanroep om te versturen]
```

---

## DE ENE ML-GRENS IN DIT HELE PLAN {#ml-grens}

Belangrijk om hier extra eerlijk over te zijn, want dit is precies waar het onderscheid tussen "symbolisch" en "vereist ML" ligt, en dat mag nooit vaag blijven:

- **Spraak-naar-tekst (STT) kan niet symbolisch.** Menselijke spraak omzetten in tekst is een taak die inherent patroonherkenning in audio vereist — dat is een neuraal netwerk-probleem, geen tel- of regelprobleem. Er bestaat geen symbolische manier om dit te doen.
- **Dit is echter exact hetzelfde soort uitzondering als Stockfish/KataGo** in je bestaande architectuur: een **bounded, gespecialiseerd extern tool**, geen generatieve kern. Whisper (OpenAI, lokaal te draaien) is hiervoor de voor de hand liggende keuze — het luistert, geeft tekst terug, en heeft verder geen "eigen wil" of generatieve output. Nova's eigen symbolische lagen (intent-detectie, EventBus-routing, response-sjablonen) blijven de kern; Whisper is enkel de "oren".
- **Tekst-naar-spraak (TTS, stap 3) is dat niet.** Klassieke TTS-engines (Piper, Windows SAPI, enz.) zijn regelgebaseerd/parametrisch, geen generatief taalmodel — dus dat stuk blijft binnen "bounded extern tool, geen LLM", vergelijkbaar met hoe je vision-modellen al gepland had als externe tools.

**Kortom:** dit hele plan blijft trouw aan Nova's kernprincipe — geen LLM als brein — met precies één stap (STT) die een extern, begrensd ML-model nodig heeft, exact zoals Stockfish dat al is voor schaken.

---

## NETWERK: HOE GSM DE PC BEREIKT VAN BUITENAF {#netwerk}

Zoals al aangehaald in het vorige gesprek: als Kevin buitenshuis via gsm bij zijn thuis-Nova wil, moet de gsm de headless pc kunnen bereiken buiten het eigen wifi-netwerk om. Dit is **pure netwerkconfiguratie, geen Nova-code**:
- Een tool als Tailscale (maakt een privé-netwerk tussen apparaten, ongeacht fysieke locatie) is de eenvoudigste optie voor een hobbyist zonder netwerkervaring
- Alternatief: een VPN naar het eigen thuisnetwerk
- Zonder een van beide werkt gsm-bediening enkel thuis op wifi

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | ML nodig? | Geschat werk |
|---|---|---|---|
| 1 | WebSocket-server op headless pc + basis laptop-client (verbinding, geen acties nog) | ❌ Nee | Middel |
| 2 | `app_controller.py` + `window_switcher.py` + `file_manager.py` (laptop-acties, whitelist-based) | ❌ Nee | Middel |
| 3 | `os_command_center.py` met veiligheidswhitelist | ❌ Nee | Klein-Middel |
| 4 | Gsm-client: notification listener + `notification_hub.py` (melding doorsturen naar Nova) | ❌ Nee | Middel-Groot (Android-ontwikkeling is nieuw terrein) |
| 5 | `notification_priority.py` + `do_not_disturb_manager.py` (filteren wélke meldingen Nova meldt) | ❌ Nee | Klein-Middel |
| 6 | TTS-integratie voor voorlezen van berichten | ❌ Nee | Klein (bestaande library, bv. Piper) |
| 7 | STT-integratie (Whisper, lokaal) voor gesproken antwoorden | ⚠️ Ja — bounded extern ML-tool | Middel — vooral opzet/performance-tuning |
| 8 | Bericht effectief versturen via gsm-client (Android-intent naar WhatsApp/SMS) | ❌ Nee | Middel |
| 9 | Netwerktoegang van buitenaf (Tailscale/VPN-opzet) | ❌ Nee (geen Nova-code, pure configuratie) | Klein |

**Aanbevolen volgorde:** eerst de WebSocket-basis en laptop-bediening (herbruikbare fundering, minder onbekend terrein), dan pas de gsm-kant (nieuw leertraject: Android-ontwikkeling).

---

## EERLIJKHEID: WAT KAN WEL/NIET, EN HOE DIT OOGT VAN BUITENAF {#eerlijkheid}

- ✅ **Laptop bedienen: volledig haalbaar met pure symbolische Python** — systeemaanroepen, geen ML
- ✅ **Meldingen doorsturen, filteren, voorlezen (TTS), versturen: volledig symbolisch**
- ⚠️ **Eén uitzondering: spraak-naar-tekst vereist een extern ML-model** (Whisper of vergelijkbaar) — dit is niet symbolisch te doen, net zomin als schaken zonder Stockfish symbolisch sterk kan zijn. Dat is geen zwakte in het plan, maar een eerlijke erkenning van waar de grens ligt.
- ✅ **Nova's kern blijft LLM-vrij.** STT is een "oren"-tool, geen brein — precies zoals Stockfish "schaakkennis" levert zonder dat Nova's eigen redenering ooit door een LLM loopt.

**Over het punt dat Kevin zelf maakte — dat dit voor de buitenwereld als een nieuwe soort AI kan aanvoelen:**

Dat klopt, en het is de moeite waard even scherp te stellen wát er dan precies nieuw aan is, zodat de verwachtingen kloppen. Het "magische" gevoel van zo'n systeem komt niet doordat Nova plots een taalmodel is geworden — haar beslissingslogica blijft dezelfde tellingen, drempels en sjablonen als nu. Het nieuwe zit in de **integratie**: een systeem dat écht 24/7 aanwezig is, over apparaten heen dezelfde context deelt, en proactief handelt zonder dat je het iets vraagt. Dat is een aanpak die weinig consumentenproducten zo combineren (Siri/Google Assistant zijn per-apparaat en meestal reactief, niet continu en cross-device met eigen geheugen). Het is dus vooral de **architectuur en volharding** die het bijzonder maakt, niet een doorbraak in "AI-intelligentie" — en dat onderscheid is precies waarom eerlijkheid over de symbolische/ML-grens hier extra belangrijk blijft: het blijft je eigen, doordachte systeem, geen llm die zich voordoet als iets anders.

**Status in de bouwvolgorde:** concept voor de verre toekomst. Vereist wel dat Nova al stabiel 24/7 draait (Layer 0 daemon-eisen, zie `memory_24-7_daemon_addendum.md`) vóór dit zinvol is om aan te beginnen — dus logischerwijze ná de huidige Layer 5-7 en bugopruiming, niet ervoor.
