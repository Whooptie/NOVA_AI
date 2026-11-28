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

# Nieuwe onderdelen voor Fleur komen hier bij.
SECTIES = [CYCLUS]


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