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

ℹ️ Dit zijn tijdelijke test-/debugcommando's voor jou als developer,
   geen onderdeel van Nova's normale gesprek met de gebruiker.
""".strip()