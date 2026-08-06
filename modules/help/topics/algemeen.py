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
  help wiskunde  (voor het volledige overzicht: algebra, calculus,
                  statistiek, fysica, complexe getallen, en meer)

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

🗑️ KENNIS WEERLEGGEN/VERWIJDEREN (verwijderpad, punt 1)
  weerleg: hond is_a meubel                    (wijst 1 relatie af, blijft zichtbaar in geschiedenis)
  weerleg betekenis: python 2                  (wijst 1 betekenis af, blijft zichtbaar)
  weerleg concept: verzonnenwoord               (wijst ALLE betekenissen van een woord af)
  verwijder definitief: hond is_a meubel        (verwijdert een AFGEWEZEN relatie echt,
                                                  moet eerst geweerlegd zijn)
  verwijder definitief betekenis: python 2      (idem, voor een betekenis)
  verwijder definitief concept: verzonnenwoord  (idem, voor een heel woord)

♟️ SCHAKEN
  help schaken  (voor alle schaakcommando's)

💛 VOORKEUREN
  onthoud: ik hou van koffie          (voorkeur vastleggen)
  onthoud: ik hou niet van kou        (afkeur vastleggen)
  vergeet: koffie                     (voorkeur/afkeur laten vergeten)
  wat kan ik drinken                  (suggestie op basis van je voorkeuren)
  wat kan ik eten                     (idem, voor eten)
  wat weet je over mij                (volledig overzicht van je profiel)
  wat vind ik leuk                    (idem)
  onthoud sense python                (kies welke betekenis je meestal bedoelt
                                        bij een meerduidig woord, bv. python
                                        als taal of als slang)

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
  help debug         (debug-/testcommando's voor development)
""".strip()