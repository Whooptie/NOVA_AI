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
  zijn er nog andere betekenissen        (na een "wat is X"-vraag: toont eventuele
                                          andere Wikipedia-betekenissen van datzelfde woord)
  wat weet je allemaal over fysica       (kort overzicht van ALLES wat Nova al weet
                                          over een woord — alle betekenissen, relaties
                                          en voorbeelden; typ 'ja' of een nummer voor
                                          het volledige detail)
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
  welke onderdelen heeft fiets         (alle onderdelen, ook via een keten)
  waar bestaat lichaam uit
  wat zit er in huis
  is snaar gerelateerd aan muziek      (associatief verband, ook via een keten)
  heeft ei te maken met kip
  is een hond een meubel               (bij "nee": toont het alternatief dat Nova wél weet)
  vergelijk hond met huiskat           (gedeelde en verschillende kennis naast elkaar)
  wat is het verschil tussen gitaar en schaak
  welke onderdelen van keuken zijn scherp  (combineert onderdelen + eigenschap)

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
      patronen topic_detected:definitie_<woord>
      patronen topic_detected:andere_betekenis_<woord>
      patronen topic_detected:concept_overview_<woord>
      patronen topic_detected:relatie
      patronen topic_detected:part_of
      patronen topic_detected:subtypes
      patronen topic_detected:parts                  (idee #1: welke onderdelen heeft X)
      patronen topic_detected:related_to_check        (idee #2: is X gerelateerd aan Y)
      patronen topic_detected:compare_concepts         (idee #6: vergelijk X met Y)
      patronen topic_detected:parts_with_property      (idee #4: welke onderdelen van X zijn Y)
    
❓ HELP
  help               (dit overzicht)
  help schaken       (schaakcommando's)
  help debug         (debug-/testcommando's voor development)
""".strip()