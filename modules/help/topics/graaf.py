# modules/help/topics/graaf.py
#
# "help graaf" -- de kennisgraaf: een 3D-pagina waarin je Nova's kennis kunt zien,
# draaien en aanklikken (modules/knowledge/graph_commands.py).
# Suggestie voor aliassen in help.py: "graaf", "kennisgraaf".

def get_help():
    return """
🕸️ KENNISGRAAF -- Nova's kennis zichtbaar maken

📊 TONEN
  toon graaf van fiets                 (maakt een 3D-pagina rond fiets: het woord en zijn buren)
  toon graaf van fiets diepte 2        (ook de buren van de buren; diepte 1 tot 3)
  laat de graaf van fiets zien         (ook: teken / geef / open, en "visualiseer fiets")
  toon de hele kennisgraaf             (alle woorden met relaties, met kleuren per groep;
                                        ook: toon de hele graaf / laat de volledige graaf zien /
                                        toon alles in de graaf)

🧭 VERBINDINGEN
  hoe zijn fiets en auto verbonden     (het kortste pad in gewone zinnen, en een pagina met het
                                        pad in het rood; ook: pad tussen fiets en auto)

📏 METEN
  graaf statistieken                   (aantal woorden, unieke verbindingen, losse woorden,
                                        zekerheid, en fouten zoals een ontbrekend relatietype)

🖱️ IN DE PAGINA
  slepen = draaien, scrollen = zoomen, rechtermuisknop = schuiven
  klik op een woord                    (alleen dat woord en zijn buren lichten op; de rest wordt gedimd;
                                        links zie je de definitie en alle relaties, ook aanklikbaar)
  klik op een leeg stuk                (laat het woord weer los)
  zoekveld, pad tussen twee woorden, relatietypes en groepen aan/uit, krachtschuifjes

ℹ️ GOED OM TE WETEN
  De pagina is een momentopname: nieuwe kennis zie je pas als je het commando opnieuw geeft.
  Is je laptop verbonden, dan opent de pagina daar meteen; anders zegt Nova waar het bestand
  staat (data/graphs/).
  Alles is tellen, zoeken en tekenen; er zit geen taalmodel of ML onder. De kleuren komen van een
  gewoon grafenalgoritme dat woorden groepeert die veel met elkaar verbonden zijn.

❓ ANDERE HELP
  help               (algemeen overzicht)
  help semantic      (alle commando's rond Nova's kennis)
""".strip()