# modules/help/topics/debug.py

def get_help():
    return """
🛠️ Debug-commando's (voor development/testen, niet voor dagelijks gebruik):

🌱 LAYER 7 — EMERGENCE ENGINE
  emergence                              (roept reflect() handmatig aan, toont insights)
  emergence debug                        (toont ruwe self.layers-status)
  emergence feedback                     (toont opgeslagen feedback per insight-type)
  emergence feedback <type> <ok|slecht>  (geef feedback op een insight-type)
  emergence drempel <type>               (toont originele vs. effectieve drempel + stats)

🧩 REASONING — CONTRADICTION CHECKER (punt 2)
  contradicties                          (forceert nu meteen een volledige check op
                                           tegenstrijdige is_a-relaties in concepts.json,
                                           toont ALLE conflicten inclusief al eerder
                                           gemelde — wijzigt de spam-preventie niet)

🎲 TOPIC SUGGESTIONS (punt 7, topic_events_roadmap.md Fase 5)
  topic suggesties                       (toont per gewhitelist topic: patroon actief?
                                           mag onderbreken? al voorgesteld dit uur?
                                           — puur informatief, wijzigt niets)
  topic suggesties forceer               (roept check_suggesties() ECHT aan — publiceert
                                           een echte layer4_response als er een geschikt
                                           topic is, en wijzigt de spam-preventie-state)

🧠 LAYER 0 — MEMORY
  onderhoud                     (forceert een onderhoudsronde: archiveren/comprimeren/VACUUM)
  geheugen stats                (memory-statistieken, gebruikt cache indien < 120 sec oud)
  geheugen stats vers           (zelfde, maar forceert een verse berekening)
  geheugen gezondheid           (health check: detecteert problemen in de memory-module)

🖥️ LAYER 5 — CONTEXT (activiteit / focus / presence)
  context                       (toont huidige context-samenvatting)
  context geschiedenis          (laatste 10 Layer 5-beslissingen)
  context geschiedenis <n>      (laatste n beslissingen)
  activiteit debug              (ruwe venstertitel/procesnaam + herkende activiteit)
  focus debug                   (seconden sinds laatste input + focus-niveau)
  presence debug                (forceert nu een webcam-check, toont resultaat)
  presence debug context        (webcam-check + meteen doorgeven aan context_manager)

🎭 LAYER 6 — PERSONALITY
  traits                        (live, in-memory trait-waarden van Nova's personality_engine)

⏱️ ACTIVITY-AWARE INTERACTION
  interruption test <activiteit> <ja|nee> <aantal>
                                 (simuleert feedback zonder te wachten op de tijdsdrempel,
                                  bv. "interruption test coderen ja 5")
  interruption gedrag <activiteit>
                                 (toont wat beslis_interruption_gedrag() nu zou teruggeven)

📊 LAYER 2 — PATTERN MATCHER
  patronen                       (algemene stats: hoeveel event_types en observaties)
  patronen <event_type>          (ruwe patroondata, actief?, volgend verwacht moment, anomalieën)

🔗 LAYER 1 — WORD ASSOCIATIONS
  associaties                    (algemene stats: hoeveel woorden/associaties totaal)
  associaties <woord>            (alle opgeslagen associaties + sentiment voor dat woord)
  bridge <woord1> <woord2>       (brugwoorden tussen twee woorden: waar zijn ze
                                   allebei mee geassocieerd, en hoe sterk)
  trending                       (welke woorden zijn recent actief, met extra
                                   gewicht voor nieuwe woorden; standaard 7 dagen)
  trending <dagen>                (idem, met een ander tijdvenster)
  sentiment woorden               (Layer 1's eigen positieve/negatieve woordenlijst
                                   — let op: dit is NIET de echte sentiment-bron
                                   van Nova, puur Layer 1's simpele schatting)

💛 USER PREFERENCES
  preferences debug              (profiel-aantallen, sentiment-classifier-status,
                                   kandidaat-suggesties-status in één oogopslag)

🎯 INTENT CLASSIFIER (ML-fallback, Fase 1-6)
  intent debug                   (aantal voorbeelden, categorieën, laatste training)
  intent test <zin>               (test een zin rechtstreeks tegen de classifier)
  intent retrain                  (forceert retrain_vanuit_bestanden() nu meteen)

🌐 WIKIPEDIA TEACHER
  wiki debug <woord>             (toont ruw Wikipedia-antwoord: type + extract,
                                   en bij een doorverwijspagina ook wat onze eigen
                                   extractiefunctie ermee doet)

ℹ️ Dit zijn tijdelijke test-/debugcommando's voor jou als developer,
   geen onderdeel van Nova's normale gesprek met de gebruiker.
""".strip()