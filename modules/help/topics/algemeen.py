# modules/help/topics/algemeen.py

def get_help():
    return """
📖 Algemene commando's:

🕐 TIJD & DATUM
  hoe laat is het
  wat is het vandaag                  (dag + datum + maand + jaar + week in één zin)
  welke dag is het   wat is de datum   welke maand is het   welk jaar is het   welke week is het
  over 10 dagen   15 augustus   25/12  (datum berekenen; jaar springt automatisch door als die dit jaar al voorbij is)
  hoeveel dagen tot kerst   welke dag van de week is pasen   hoeveel dagen geleden was 1 januari

🎉 FEESTDAGEN
  wanneer is kerst   wanneer valt pasen   is het vandaag een feestdag
  wat is de volgende feestdag

🏖️ SCHOOLVAKANTIES (Vlaanderen)
  wanneer is de paasvakantie   wanneer is de krokusvakantie
  zijn we nu in vakantie   wat is de volgende vakantie   hoeveel dagen tot de vakantie

📅 OP DEZE DAG IN DE GESCHIEDENIS (Wikipedia)
  wat is er vandaag gebeurd   wat is er gebeurd op 25 december
  wie is er vandaag geboren   wie is er overleden op 9 december

🌤️ WEER
  hoe is het weer

📚 KENNIS & REDENEREN  (alles hierover: help semantic)
  wat is een zwart gat
  wiki zwart gat
  teach fotosynthese een proces waarbij planten licht omzetten
  is een hond een dier
  hoe zeker ben je dat een hond een dier is
  wat weet je niet zeker
  weerleg: hond is_a meubel
  help semantic  (leren, redeneren, oorzaak/gevolg, tijd, zekerheid, weerleggen)

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
  wat heb ik je al gevraagd over koffie   (gewone taal, idem als memory search maar zonder commando-vorm)
  waar praten we vaak over                 (idem, algemeen: geen specifiek onderwerp)

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
      patronen topic_detected:causes_check             (leidt X tot Y)
      patronen topic_detected:ontstaan                 (wanneer ontstond X)
      patronen topic_detected:tijdlijn                 (tijdlijn van X)
      patronen topic_detected:zekerheid                (hoe zeker ben je dat ...)
    
❓ HELP
  help               (dit overzicht)
  help semantic      (alles over Nova's kennis: leren, redeneren, tijd, zekerheid)
  help schaken       (schaakcommando's)
  help wiskunde      (wiskunde-overzicht)
  help debug         (debug-/testcommando's voor development)
""".strip()