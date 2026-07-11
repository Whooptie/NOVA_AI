LLM Codegen & Fallback-Analyse Roadmap: Claude API als externe tool
Status: Concept/idee, nog niet ingepland in bouwvolgorde Depends on: Anthropic API-key, bestaand .env-patroon (zoals OpenWeatherMap-key) Gebruikt door: losse tool/module buiten Nova's EventBus-brein, optioneel getriggerd via Nova Datum: 11 juli 2026
INHOUDSOPGAVE
Wat lost dit op?
Het kernprincipe: wie beslist wanneer
Deel A: fallback/missing-intent tracking (100% symbolisch)
Deel B: Claude API als codeer-tool ("live typen")
Deel C: Claude API voor fallback-analyse (bewust NIET autonoom)
Context-laag: waarom de API niks "onthoudt"
Fase-roadmap
Eerlijkheid: wat kan wel/niet
WAT LOST DIT OP? {#wat-lost-dit-op}
Kevin wil op termijn twee dingen kunnen doen:
Nova live zien "coderen" in VSCode (Claude schrijft code weg naar bestanden, Kevin kijkt toe)
Ontdekken welke modules Nova mist, op basis van herhaalde fallback/onbekende verzoeken
Beide kunnen de Claude API gebruiken. Geen van beide hoort ooit binnen Nova's symbolische kern of haar 24/7-daemon-redenering te draaien. Dit document legt vast waarom, en hoe het dan wél kan.
HET KERNPRINCIPE: WIE BESLIST WANNEER {#kernprincipe}
Dit is de enige vraag die telt bij elk toekomstig LLM-gebruik rond Nova:
Gebeurt de API-call omdat Kevin het expliciet vraagt (van buitenaf), of beslist Nova dat zelf, autonoom, binnen haar eigen daemon-loop?
✅ Kevin triggert ("Nova, roep Claude op om dit te coderen") → prima, altijd toegestaan. Dit is exact hetzelfde soort actie als Kevin nu al doet in een Claude-chat, alleen via Nova als tussenpersoon.
❌ Nova beslist zelf, autonoom ("ik zie een patroon, dus ik roep zelf Claude op om te redeneren over een oplossing") → dit ís een LLM die binnen Nova's brein beslissingen/voorstellen genereert. Dat is precies wat het architectuurprincipe uitsluit: "Nova's core is 100% symbolic Python — no LLM, no generative AI as the brain."
Het verschil met Stockfish (wél toegestaan als externe specialist): Stockfish lost één afgebakende, begrensde taak op (een zet berekenen) op expliciete aanroep. Een Claude-call die "kijk naar mijn logs en bedenk een nieuwe module" doet, is open-ended generatief redeneren — dat is zelf de brain-taak, geen specialist-taak binnen een vaste taak.
Vuistregel: zodra de output van de API-call is "wat moet er gebeuren" in plaats van "hier is het gevraagde resultaat", hoort het niet in Nova's autonome loop thuis.
DEEL A: FALLBACK/MISSING-INTENT TRACKING (100% SYMBOLISCH) {#deel-a}
Dit hoort wél in Nova zelf, en heeft geen LLM nodig.
Kevin's zin matcht geen enkele detect_* in intent_router.py
       ↓
publiceer event_bus.publish("fallback_triggered", {"tekst": ..., "tijd": ...})
       ↓
Layer 1/2 telt dit generiek mee (zelfde mechanisme als topic_detected)
Optionele uitbreiding — woordfrequentie i.p.v. enkel een teller: Sla per fallback-event de zelfstandige naamwoorden op (via bestaande detect_pos/tokenisatie uit Layer 1). Dan kan Nova zeggen:
"Het woord 'mail' kwam nu 5x voor in verzoeken die ik niet begreep."
Dit is nog steeds puur tellen — geen interpretatie van bedoeling. Nova weet niet wát je met "mail" wilt, enkel dát het woord vaak terugkomt in mislukte pogingen.
Grens: Nova mag nooit zelf formuleren "dit lijkt me een taak voor een e-mailmodule" — dat is een interpretatieve sprong die geen teller kan maken (zie Deel C).
DEEL B: CLAUDE API ALS CODEER-TOOL ("LIVE TYPEN") {#deel-b}
100% Kevin-getriggerd, nooit autonoom.
Kevin: "Nova, laat Claude dit coderen: [opdracht]"
       ↓
Nova (losse tool-module, buiten EventBus-brein) roept Anthropic API aan
       ↓
API retourneert code (tekst)
       ↓
Tool schrijft dit blok-voor-blok (met kleine pauzes) naar het doelbestand
       ↓
VSCode detecteert bestandswijziging → toont dit als "live typen"
Belangrijk over dat "live typen"-effect: dit is puur cosmetisch. Het is een vertraagde write naar schijf, geen extra intelligentie. Het voegt niets toe aan wat de LLM al gegenereerd heeft — het is theater voor Kevin als kijker, wat op zich prima is, maar goed om helder te houden.
VSCode Copilot / Claude-extensie zijn hier NIET bruikbaar — die zijn gebouwd om jou (de mens in de editor) te helpen, geen publieke API die een extern Python-script kan aanroepen. Alleen de rechtstreekse Anthropic API (api.anthropic.com) is hiervoor geschikt.
DEEL C: CLAUDE API VOOR FALLBACK-ANALYSE (BEWUST NIET AUTONOOM) {#deel-c}
Dit is de plek waar het eerder besproken idee ("Nova ziet een patroon en stelt zelf een module voor") wél kan, maar met een harde grens:
Kevin (expliciet, van buitenaf): "Nova, analyseer je fallback-logs van deze maand"
       ↓
Nova exporteert de ruwe fallback-teksten (geen interpretatie, enkel export)
       ↓
Losse tool-module stuurt dit naar Claude API met vraag: "zie jij een patroon?"
       ↓
Claude's antwoord wordt getoond aan Kevin — als suggestie, niet als actie
       ↓
Kevin beslist zelf of hij daar een nieuwe module voor laat bouwen
Dit gebeurt nooit vanzelf tijdens Nova's 24/7-daemon-run. Het is functioneel identiek aan wat Kevin en Claude nu al doen in een gewone chat — Nova is hier enkel de bron van de logs, niet de beslisser.
CONTEXT-LAAG: WAAROM DE API NIKS "ONTHOUDT" {#context-laag}
Cruciaal verschil met claude.ai (deze app): de kale Anthropic API heeft geen geheugen tussen aanroepen. Elke API-call begint blanco. Wat hier in de app aanvoelt als "Claude onthoudt Nova's project" is een apart systeem (memory + project knowledge) dat Anthropic specifiek voor claude.ai gebouwd heeft — niet iets dat automatisch meekomt met de API.
Gevolg voor Deel B en C: elke keer dat Nova (of de tool-module) de API aanroept, moet zij zelf een contextpakket meesturen — bv. relevante stukken uit nova_state.md, relevante bestanden uit C:\Nova_AI. Dit is een aparte, zelf te bouwen laag ("context injection"), geen gratis bijkomstigheid. Vergelijkbaar met de al geplande maar nog ongebouwde memory_vector_index.py / retrieval_router.py / embedder.py uit het modules-overzicht.
FASE-ROADMAP {#fase-roadmap}
Fase
Omschrijving
ML/LLM nodig?
Geschat werk
1
fallback_triggered-event publiceren + Layer 1/2 laten meetellen
❌ Nee
Klein
2
Woordfrequentie binnen fallback-events (i.p.v. enkel totaalteller)
❌ Nee
Klein-Middel
3
Losse codegen_tool.py: Kevin-getriggerde Anthropic API-call, output naar bestand
✅ Ja — expliciet, Kevin-getriggerd
Middel
4
"Live typen"-effect: vertraagde/blokgewijze write naar bestand
❌ Nee (puur cosmetisch)
Klein
5
Context-injectielaag: relevante nova_state.md/bestanden automatisch meesturen bij Fase 3
❌ Nee (bouw is symbolisch, gebruik voedt een LLM)
Groot
6
Losse fallback_analyzer.py: Kevin-getriggerde export + API-call voor patroonanalyse
✅ Ja — expliciet, Kevin-getriggerd
Middel
Afhankelijkheden: Fase 1-2 zijn onafhankelijk bouwbaar, nu al. Fase 3-6 vereisen een bewuste keuze van Kevin om de Claude API in te zetten — dit is geen verplicht vervolg op Fase 1-2.
EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}
✅ Nova telt hoe vaak fallback voorkomt, en welke woorden daarbij terugkeren — 100% symbolisch, geen ML
✅ Kevin roept expliciet Claude API aan via Nova om code te laten schrijven — toegestaan, want Kevin-getriggerd, net als een gewone chat
✅ Kevin roept expliciet Claude API aan om fallback-logs te laten analyseren — toegestaan, zelfde reden
✅ "Live typen"-effect in VSCode — puur cosmetisch, geen extra intelligentie
❌ Nova roept zelf, autonoom tijdens haar daemon-run, de API aan om te beslissen wat er gebouwd moet worden — dit is een LLM als brein-vervanging, expliciet uitgesloten
❌ Verwachten dat de API "vanzelf" Nova's project kent na een tijdje gebruiken — geen ingebouwd geheugen; elke call vereist zelf meegestuurde context
❌ VSCode Copilot/Claude-extensie als aanroepbare tool voor Nova — die zijn voor de mens in de editor, geen aanroepbare API voor een extern script
Status in de bouwvolgorde: idee/concept, geen prioriteit. Fase 1-2 kunnen onafhankelijk van de rest gebouwd worden. Fase 3-6 wachten op Kevin's bewuste keuze om de Claude API in te zetten.
Author: Claude + Kevin