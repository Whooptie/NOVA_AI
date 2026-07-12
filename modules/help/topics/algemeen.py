# modules/help/topics/algemeen.py

def get_help():
    return """
📖 Algemene commando's:

🕐 TIJD & DATUM
  hoe laat is het
  wat is de datum

🌤️ WEER
  hoe is het weer

🔢 WISKUNDE
  2 + 2 / 10 * 5 / sqrt(16)
  25°C  (temperatuurconversie)

📚 KENNISBANK
  wat is een zwart gat
  wat betekent fotosynthese
  wiki zwart gat
  teach fotosynthese een proces waarbij planten licht omzetten
  example appel Ik eet elke dag een appel.
  synoniemen van blij
  antoniemen van groot
  waarvoor gebruik je een hamer
  wat veroorzaakt regen
  wat zijn eigenschappen van vuur

🧠 REDENEREN
  is een hond een dier
  hond is een dier                    (leert Nova de relatie, met bevestiging)
  is een snaar onderdeel van een gitaar
  snaar is onderdeel van een gitaar   (leert Nova de part_of-relatie, met bevestiging)
  welke soorten dier ken je
  noem soorten van dier

♟️ SCHAKEN
  help schaken  (voor alle schaakcommando's)

🧠 GEHEUGEN
  memory stats                    (hoeveel events opgeslagen, hoe groot de database)
  memory search <woord>           (zoek een woord terug in het geheugen)
  memory similar <woord>          (vind events die lijken op een woord, ook bij typfouten)

📊 PATRONEN (Layer 2, tijdelijk testcommando)
  patronen                        (algemene stats: hoeveel event_types en observaties)
  patronen <event_type>           (bv. patronen chat_message, patronen topic_detected:chess)
                                   toont ruwe patroondata, of het patroon nu actief is,
                                   wanneer het volgende voorkomen verwacht wordt, en
                                   recente anomalieën)
    Generiek (via RELEVANTE_EVENT_TYPES in pattern_matcher.py):
      patronen chat_message
      patronen chat_response

    Per onderwerp (via _emit_topic in intent_router.py):
      patronen topic_detected:greeting
      patronen topic_detected:time
      patronen topic_detected:weather
      patronen topic_detected:chess
      patronen topic_detected:help
      patronen topic_detected:memory
      patronen topic_detected:math
      patronen topic_detected:definitie
      patronen topic_detected:relatie
      patronen topic_detected:part_of
      patronen topic_detected:subtypes
    
❓ HELP
  help               (dit overzicht)
  help schaken       (schaakcommando's)
""".strip()