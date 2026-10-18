# modules/help/topics/semantic.py
#
# "help semantic" -- alle commando's rond Nova's kennis (semantic.py):
# leren, opvragen, redeneren, oorzaak/gevolg, tijd, zekerheid en weerleggen.
# Aliassen in help.py: "semantic", "kennis", "kennisbank".

def get_help():
    return """
🧠 KENNIS (semantic) -- alle commando's

📚 LEREN EN OPVRAGEN
  wat is een zwart gat
  wat betekent fotosynthese
  wiki zwart gat
  zijn er nog andere betekenissen        (na een "wat is X"-vraag: andere Wikipedia-betekenissen)
  wat weet je allemaal over fysica       (kort overzicht van alles wat Nova over een woord weet;
                                          typ 'ja' of een nummer voor het volledige detail)
  teach fotosynthese een proces waarbij planten licht omzetten
  example appel Ik eet elke dag een appel.
  synoniemen van blij
  antoniemen van groot
  waarvoor gebruik je een hamer
  wat zijn eigenschappen van vuur

🔗 REDENEREN (relaties)
  is een hond een dier
  hond is een dier                      (leert Nova de relatie, met bevestiging)
  is een snaar onderdeel van een gitaar
  snaar is onderdeel van een gitaar     (leert de part_of-relatie, met bevestiging)
  welke soorten dier ken je
  noem soorten van dier
  welke onderdelen heeft fiets          (alle onderdelen, ook via een keten)
  waar bestaat lichaam uit
  wat zit er in huis
  is snaar gerelateerd aan muziek       (associatief verband, ook via een keten)
  heeft ei te maken met kip
  is een hond een meubel                (bij "nee": toont het alternatief dat Nova wél weet)
  vergelijk hond met huiskat
  wat is het verschil tussen gitaar en schaak
  welke onderdelen van keuken zijn scherp  (onderdelen + eigenschap)

⚡ OORZAAK EN GEVOLG
  regen veroorzaakt modder              (leert een oorzaak; ook "zorgt voor" en "leidt tot")
  wat veroorzaakt regen                 (de oorzaken van regen; ook: wat leidt tot regen /
                                         wat zorgt voor regen)
  wat zijn de gevolgen van regen        (ook: wat is het gevolg van regen / waartoe leidt regen)
  leidt regen tot modder                (check; ook: veroorzaakt regen modder /
                                         zorgt regen voor modder / kan regen modder veroorzaken)
                                         Direct: "Ja, ...". Een keten krijgt: "Waarschijnlijk wel:
                                         ... via: ...". Staat het er niet: Nova zegt dat ze het niet
                                         kan bewijzen en noemt wat regen wél veroorzaakt.
                                         In lijsten staat "(verder weg: ...)" voor gevolgen/oorzaken
                                         die via een keten bereikt worden (tot 4 schakels).

🕰️ TIJD EN GESCHIEDENIS
  python bestaat sinds 1991             (ook: ontstond in 1991 / is ontstaan in 1991)
  wanneer ontstond python               (ook: sinds wanneer bestaat python)
  hoe lang bestaat python al
  python was van 1991 tot 2005 een niche   (ook: tussen 1991 en 2005 / van 2010 tot nu / is sinds 2010)
  python was van 2010 tot 2024 dominant    (sluit een open periode "sinds 2010 dominant" af;
                                            een periode die overlapt met een bestaande wordt geweigerd)
  wat was python in 2003
  tijdlijn van python
  wis de periodes van python            (ook: verwijder de tijdlijn van python; het ontstaansjaar blijft staan)
  wat bestond er in 1960                (alle woorden met een jaartal)
  wat ontstond er in 1991 / tussen 1900 en 1950 / voor 1900 / na 1990

🎯 ZEKERHEID
  hoe zeker ben je dat een hond een dier is
  hoe zeker ben je dat wiel onderdeel is van auto
  hoe zeker ben je dat roken tot kanker leidt
                                        (ook in meervoud: honden dieren zijn / wielen onderdelen
                                         zijn van auto). Onbevestigde kennis noemt Nova nooit
                                         "zeker"; ze vraagt of je het wilt bevestigen: ja / nee
  waarom ben je er niet zeker van dat een hond een wolf is
  hoe zeker ben je dat een appel een vrucht is
                                        (staat het er niet direct: Nova zoekt de zekerste keten;
                                         die is zo zeker als de zwakste schakel en je kunt
                                         precies die schakel bevestigen)
  wat weet je niet zeker                (genummerde lijst, onzekerste eerst, max. 10)
  wat weet je niet zeker over hond
  bevestig 3                            (nummer uit de laatste lijst, 10 minuten geldig)
  wijs af 3                             (wijst die relatie af)

📖 KENNIS UIT WIKIPEDIA (voorstellen)
  wiki fiets                            (haalt de definitie op; daarna vraagt Nova of je ook de
                                         voorstellen wilt zien: typ 'ja')
  extraheer fiets                       (Nova zoekt feiten in de Wikipedia-inleiding en toont ze
                                         als genummerde lijst; er wordt NIETS opgeslagen)
                                        (ook: haal kennis uit wikipedia over fiets)
  extraheer regen (neerslag)            (kan een woord meerdere dingen betekenen, dan toont Nova
                                         de mogelijkheden en kies je er zelf een)
  neem 2 over                           (slaat voorstel 2 op en bevestigt het meteen)
  neem alles over
  laat 2 vallen                         (wijst voorstel 2 af; het komt niet meer terug)
                                        (voorstellen zijn "X is een Y", "X bestaat uit ...",
                                         "X is onderdeel van Y", "X veroorzaakt Y" en
                                         "X wordt gebruikt voor Y";
                                         de nummers blijven 10 minuten geldig)

🗑️ WEERLEGGEN EN VERWIJDEREN
  weerleg: hond is_a meubel                    (wijst 1 relatie af, blijft zichtbaar in geschiedenis)
  weerleg betekenis: python 2                  (wijst 1 betekenis af)
  weerleg concept: verzonnenwoord              (wijst ALLE betekenissen van een woord af)
  verwijder definitief: hond is_a meubel       (verwijdert een AFGEWEZEN relatie echt;
                                                moet eerst geweerlegd zijn)
  verwijder definitief betekenis: python 2     (idem, voor een betekenis)
  verwijder definitief concept: verzonnenwoord (idem, voor een heel woord)

❓ ANDERE HELP
  help               (algemeen overzicht)
  help schaken / help wiskunde / help debug
""".strip()