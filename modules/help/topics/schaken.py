# modules/help/topics/schaken.py

def get_help(chess_module=None):
    niveau = "?"
    denktijd = "?"

    if chess_module:
        niveau = chess_module.skill_level
        denktijd = chess_module.think_time

    return f"""
♟️ Schaakcommando's:

🎮 PARTIJ
  nieuwe partij          (start een nieuw potje)
  bord                   (toon het huidige bord)
  statistieken           (jouw win/verlies overzicht)

♟️ ZETTEN
  pion naar e4           (natuurlijke taal)
  paard naar f3          (natuurlijke taal)
  e2e4                   (UCI-notatie)
  e4                     (alleen doelveld, pion wordt aangenomen)
  pion naar e8 dame      (promotie, stuk kiezen: dame/toren/loper/paard)
  pion naar e8           (promotie zonder stuk = automatisch dame)
  rokeer kort             (korte rokade)
  rokeer lang              (lange rokade)

⚙️ INSTELLINGEN
  niveau 0-20            (moeilijkheidsgraad, nu: {niveau}/20)
  denktijd 1-10          (seconden per zet, nu: {denktijd}s)

ℹ️ Jij speelt altijd wit, Nova speelt magenta.
""".strip()