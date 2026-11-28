# modules/help/topics/fleur.py
#
# "help fleur" -- alles wat Nova voor Fleur bijhoudt of doet, op één plek.
# Voorlopig: maandstonden en cyclus (modules/time/cyclus.py).
#
# HOE VOEG JE LATER IETS NIEUWS TOE?
# Maak onderaan een nieuwe sectie (zelfde vorm als CYCLUS) en zet die in de
# lijst SECTIES. Meer hoef je niet te doen: "help fleur" toont ze automatisch,
# en tests/test_help_fleur.py controleert dat elk voorbeeldcommando in een
# sectie met een "module" ook echt door die module herkend wordt.
# Suggestie voor aliassen in help.py: "fleur", "cyclus", "maandstonden".

BREEDTE = 42   # kolom waarin de uitleg tussen haakjes begint

# Een sectie is een dict:
#   "kop":        de titel met emoji
#   "commando's": lijst van (commando, uitleg); uitleg mag leeg zijn
#   "goed om te weten": lijst van losse zinnen
#   "module":     de naam waaronder Nova de module kent (voor de test), of None
CYCLUS = {
    "kop": "🌸 MAANDSTONDEN EN CYCLUS",
    "module": "cyclus",
    "commando's": [
        ("fleur is vandaag ongesteld geworden", "noteert de eerste dag; ook: gisteren / eergisteren"),
        ("ze is 3 dagen geleden ongesteld geworden", ""),
        ("de maandstonden van fleur zijn begonnen op 12 november", "ook: 12/11 of 12-11-2026"),
        ("fleur is niet meer ongesteld", "noteert de laatste dag, zo leert Nova hoe lang het duurt"),
        ("ze is nog niet ongesteld", "na een melding: Nova vraagt het morgen opnieuw"),
        ("wanneer is fleur weer ongesteld", "verwachte datum en hoeveel dagen nog"),
        ("in welke fase zit fleur", "fase, vruchtbaarheid en geschatte eisprong"),
        ("is ze vruchtbaar", "zelfde antwoord als de fase"),
        ("cyclus overzicht", "alle cycli, gemiddelden en hoe goed Nova's voorspelling was"),
        ("fleur maandstonden laatste ongedaan", "verwijdert de laatste startdatum, bij een typfout"),
        ("fleur melding 3 dagen vooraf", "hoeveel dagen vooraf de melding komt, van 1 tot 14"),
        ("fleur vruchtbaarheidsmeldingen aan", "melding bij het begin van het vruchtbare venster"),
        ("fleur vruchtbaarheidsmeldingen uit", "zet die weer uit, dat is de standaard"),
    ],
    "goed om te weten": [
        "Komt ze vroeger of later dan verwacht? Zeg gewoon dezelfde zin met de echte datum.",
        "Nova past haar gemiddelde aan. Oudere data mag je ook achteraf invullen, in elke volgorde.",
        "Meldingen komen op je gsm, tussen 08:00 en 21:00: vooraf, op de dag zelf, en elke dag dat",
        "ze over tijd is (tot 14 dagen). Alles blijft lokaal in data/cyclus.json, niet op GitHub.",
        "Het is een kalenderschatting op basis van haar eerdere cycli: geen meting en geen",
        "anticonceptie. Met minder dan 3 cycli is het een grove schatting. Alles is rekenwerk,",
        "er zit geen ML of taalmodel onder.",
    ],
}

KALENDER = {
    "kop": "📅 FLEUR-KALENDER (jullie logboek, met haar toestemming)",
    "module": "fleur_kalender",
    "commando's": [
        ("fleur knuffelen ik begon", "datum en uur van nu worden zelf ingevuld"),
        ("fleur rug zij begon", "ook: samen / niets erbij"),
        ("fleur seks samen", ""),
        ("fleur poepie", "soorten: knuffelen, poepie, rug, tetjes, seks (en wat je zelf toevoegt)"),
        ("fleur seks ik probeerde maar ze wilde niet", "wordt 'niet doorgegaan'; ook: zij probeerde maar ik wilde niet"),
        ("fleur tetjes gisteren om 21:30", "datum en/of uur zelf opgeven (12 november, 12/11, 3 dagen geleden)"),
        ("fleur kalender", "deze maand, per dag; ook: fleur kalender oktober / vorige maand"),
        ("fleur overzicht", "tellers en verhoudingen; ook: fleur overzicht seks / deze maand / dit jaar"),
        ("fleur inzichten", "wat Nova er zelf uit leert (weekdag, dagdeel, wie begint, cyclusfase)"),
        ("fleur laatste", "de laatste 5 noteringen; ook: fleur laatste 10"),
        ("fleur soorten", "alle soorten die Nova kent"),
        ("fleur soort toevoegen massage", "zelf een soort toevoegen"),
        ("fleur soort verwijderen massage", "oude noteringen blijven bewaard"),
        ("fleur kalender laatste ongedaan", "haalt de laatste notering weg"),
    ],
    "goed om te weten": [
        "Kent Nova een woord niet ('fleur massage ik begon'), dan vraagt ze het eerst: zeg 'ja'",
        "(nieuwe soort), 'nee' (niets bewaard) of de naam van een bestaande soort (dan wordt het",
        "een andere naam daarvoor). Je krijgt daarna een teller per soort en per maand.",
        "Nova leert door te tellen en te vergelijken, nooit door te gokken: inzichten komen",
        "alleen als je ze vraagt en pas vanaf genoeg gegevens. Het zijn tellingen, geen verklaringen.",
        "Alles staat in data/fleur_kalender.json (niet op GitHub) en gaat nooit naar je gsm.",
    ],
}

# Nieuwe onderdelen voor Fleur komen hier bij.
SECTIES = [CYCLUS, KALENDER]


def alle_commandos(module=None):
    """Alle voorbeeldcommando's (eventueel enkel van de sectie met deze module). Voor de tests."""
    uit = []
    for sectie in SECTIES:
        if module is not None and sectie.get("module") != module:
            continue
        uit.extend(commando for commando, _ in sectie["commando's"])
    return uit


def _regel(commando, uitleg):
    if not uitleg:
        return f"  {commando}"
    return f"  {commando.ljust(BREEDTE)} ({uitleg})"


def _sectie_tekst(sectie):
    regels = [sectie["kop"], ""]
    regels.extend(_regel(c, u) for c, u in sectie["commando's"])
    noten = sectie.get("goed om te weten") or []
    if noten:
        regels.extend(["", "ℹ️ GOED OM TE WETEN"])
        regels.extend(f"  {n}" for n in noten)
    return "\n".join(regels)


def get_help():
    delen = [_sectie_tekst(s) for s in SECTIES]
    delen.append("❓ ANDERE HELP\n  help               (algemeen overzicht)")
    return "\n\n".join(delen).strip()