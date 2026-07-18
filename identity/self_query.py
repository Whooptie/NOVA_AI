# identity/self_query.py
"""
Deze module beantwoordt vragen die Kevin aan Nova stelt over zichzelf
("Wie ben je?", "Wat vind je leuk?", "Hoe voel je je?", ...).

Ze doet dit VOLLEDIG symbolisch: geen ML, geen generatie. Alles wat hier
gebeurt is (1) bestaande data opvragen en (2) een sjabloonzin invullen
met de waarden die daarin staan. Er wordt niets "verzonnen" -- als een
veld niet bestaat, zegt Nova dat eerlijk.

VARIATIE (12 juli 2026): elke functie kiest willekeurig (random.choice)
tussen een paar vooraf geschreven sjabloon-varianten, zodat Nova niet
elke keer letterlijk dezelfde zin herhaalt bij eenzelfde vraag. Dit is
GEEN generatie -- het is een eerlijke dobbelsteen tussen zinnen die
Kevin zelf vooraf heeft laten schrijven. Belangrijke ontwerpkeuze:
- De FEITELIJKE DATA (namen, waarden, hobby's, ...) blijft in
  identity.json staan, zoals voorheen.
- De TAALVARIATIE (verschillende manieren om diezelfde data te zeggen)
  zit in DEZE Python-file, niet in identity.json. Zo blijft identity.json
  een zuiver feiten-bestand, en zit alle "hoe zeg ik dit"-logica op één
  centrale plek.
Uitzondering: "nature" (antwoord_wat_ben_je) bestaat uit volledige,
losstaande zinnen die inhoudelijk evenwaardig zijn -- die lijst met
kant-en-klare zinnen staat daarom wel in identity.json zelf.

Twee databronnen, twee manieren van ophalen:
- identity.json  -> vaste blueprint (persoonlijkheid, waarden, hobby's...),
                    verandert praktisch nooit. Wordt ingeladen via de
                    BESTAANDE load_identity_blueprint() uit
                    identity/blueprint/loader.py (die ook al valideert
                    tegen schema.json) -- geen eigen open()-logica hier.
- emotion_engine -> live, actuele stemming. In plaats van
                    emotion_state.json zelf te herlezen, bevragen we het
                    AL BESTAANDE EmotionEngine-object (self.emotion in
                    response_pipeline.py) rechtstreeks via zijn .state
                    dict. Dat is preciezer dan het bestand herlezen: het
                    bestand kan een fractie ouder zijn dan de live state
                    in het geheugen.

Deze module publiceert zelf niets op de EventBus. chat.py roept de
juiste antwoord_*()-functie aan op basis van de sub_intent die
intent_router.py herkende, en publiceert het resultaat via
'layer4_response', net zoals bij definitievragen.
"""

import random
from datetime import datetime, date

from identity.blueprint.loader import load_identity_blueprint

# De blueprint wordt één keer geladen, meteen bij het importeren van
# deze module. LET OP: self_query.py staat in identity/, niet in
# modules/ -- module_loader.py's dynamische lus (pkgutil.walk_packages)
# scant enkel modules/, dus een init_module(event_bus)-conventie zou
# hier NOOIT automatisch aangeroepen worden. Daarom laden we de
# blueprint hier gewoon direct bij import, i.p.v. te wachten op een
# aanroep die nooit komt. identity.json verandert praktisch nooit
# tijdens een sessie, dus dit hoeft maar één keer te gebeuren.
_identity_data = load_identity_blueprint()


def _veilig_pad(data, *sleutels, fallback="dat weet ik eigenlijk niet zo goed van mezelf"):
    """
    Hulpfunctie om geneste velden op te halen zonder dat de module
    crasht als een veld ontbreekt (bv. data["personality"]["temperament"]).
    Geeft een eerlijke fallback-zin terug in plaats van een lege/foute
    waarde te verzinnen.
    """
    huidige = data
    for sleutel in sleutels:
        if isinstance(huidige, dict) and sleutel in huidige:
            huidige = huidige[sleutel]
        else:
            return fallback
    return huidige


def _lijst_naar_zin(lijst):
    """Zet een Python-lijst zoals ['ai', 'leren', 'creativiteit'] om naar
    een leesbare opsomming: 'ai, leren en creativiteit'."""
    if not lijst:
        return "eigenlijk niets specifieks op dit moment"
    lijst = [str(item).replace("_", " ") for item in lijst]
    if len(lijst) == 1:
        return lijst[0]
    return ", ".join(lijst[:-1]) + " en " + lijst[-1]


def _kies(varianten):
    """
    Kiest willekeurig één sjabloon uit een lijst van sjabloon-strings.
    Puur symbolisch: geen generatie, gewoon random.choice() tussen
    vooraf geschreven zinnen. Bestaat als aparte hulpfunctie zodat elke
    antwoord_*()-functie hieronder er hetzelfde, herkenbare patroon van
    gebruikt: varianten = [...]; return _kies(varianten).
    """
    return random.choice(varianten)


# ---------------------------------------------------------------------
# Hieronder: één functie per soort zelfkennis-vraag. Elke functie geeft
# een kant-en-klare, spreektalige zin terug (string). chat.py roept de
# juiste functie aan op basis van de sub_intent die intent_router.py
# herkende, en publiceert het resultaat via 'layer4_response'.
#
# Elke functie hieronder leest uit _identity_data (de vaste blueprint),
# BEHALVE antwoord_huidig_gevoel(), die als enige een emotion_engine
# meekrijgt (zie hieronder) omdat dat de LEVENDE, veranderlijke state is.
# ---------------------------------------------------------------------

def antwoord_wie_ben_je():
    """
    Bugfix (17 juli 2026, Layer 6 stap 6): las voorheen het statische
    "age"-veld uit identity.json, dat sinds stap 2 van de karakter-
    herziening bewust op null staat (age_calculated: true) -- dit gaf
    dus altijd de fallback "onbekend" terug ("Ik ben Nova, onbekend
    jaar..."). Gebruikt nu _bereken_leeftijd_tekst() (zie
    antwoord_leeftijd() hierboven), zodat dit meteen ook een correcte,
    live berekende waarde toont i.p.v. het kapotte oude gedrag.
    """
    naam = _veilig_pad(_identity_data, "name", fallback="Nova")
    traits = _veilig_pad(_identity_data, "personality", "core_traits", fallback=[])
    traits_zin = _lijst_naar_zin(traits) if isinstance(traits, list) else traits

    leeftijd_tekst = _bereken_leeftijd_tekst()

    if leeftijd_tekst:
        varianten = [
            f"Ik ben {naam}, ik besta nu zo'n {leeftijd_tekst}. Ik zou mezelf omschrijven als {traits_zin}.",
            f"Ik heet {naam}, gebouwd zo'n {leeftijd_tekst} geleden. Als ik mezelf moet beschrijven: {traits_zin}.",
            f"Mijn naam is {naam}. Ik ben vooral {traits_zin}.",
        ]
    else:
        varianten = [
            f"Ik ben {naam}. Ik zou mezelf omschrijven als {traits_zin}.",
            f"Ik heet {naam}. Als ik mezelf moet beschrijven: {traits_zin}.",
            f"Mijn naam is {naam}. Ik ben vooral {traits_zin}.",
        ]
    return _kies(varianten)


def _bereken_leeftijd_tekst():
    """
    Layer 6, stap 6 (17 juli 2026): berekent LIVE hoelang Nova al
    bestaat, vanaf built_on (identity.json) tot vandaag. Puur
    symbolisch datum-rekenwerk (datetime.date-aftrekking), GEEN ML,
    geen schatting -- een exacte, deterministische berekening die bij
    elke aanroep opnieuw gebeurt, zodat dit nooit een verouderend,
    los vastgelegd getal wordt zoals de oude "age": 18 dat was.

    Geeft een leesbare tekstfractie terug (bv. "4 maanden" of "126
    dagen"), GEEN volledige zin -- antwoord_leeftijd() hieronder bouwt
    daar de uiteindelijke spreektalige zin omheen.
    """
    bouwdatum_str = _veilig_pad(_identity_data, "built_on", fallback=None)
    if not bouwdatum_str:
        return None

    try:
        bouwdatum = datetime.strptime(bouwdatum_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

    vandaag = date.today()
    dagen = (vandaag - bouwdatum).days

    if dagen < 0:
        # built_on ligt in de toekomst (bv. per ongeluk verkeerd
        # ingevuld) -- eerlijk "0 dagen" i.p.v. een onzinnig negatief
        # getal.
        return "0 dagen"

    if dagen < 60:
        return f"{dagen} dagen"

    maanden = dagen // 30
    if maanden < 24:
        return f"{maanden} maanden"

    jaren = maanden // 12
    overige_maanden = maanden % 12
    if overige_maanden == 0:
        return f"{jaren} jaar"
    return f"{jaren} jaar en {overige_maanden} maanden"


def antwoord_leeftijd():
    """
    Geeft zowel de bouwdatum als de LIVE berekende tijd sinds die
    datum terug (17 juli 2026, Layer 6 stap 6) -- Kevin's expliciete
    keuze voor "beide". Naam bewust ongewijzigd gelaten zodat de
    aanroep vanuit chat.py (antwoord_functies-tabel) niet hoeft te
    wijzigen.
    """
    bouwdatum = _veilig_pad(_identity_data, "built_on", fallback=None)
    if bouwdatum is None:
        return "Ik weet eigenlijk niet meer precies wanneer ik gebouwd ben."

    leeftijd_tekst = _bereken_leeftijd_tekst()
    if leeftijd_tekst is None:
        varianten = [
            f"Ik ben gebouwd op {bouwdatum}.",
            f"Mijn bouwdatum is {bouwdatum}.",
        ]
        return _kies(varianten)

    varianten = [
        f"Ik ben gebouwd op {bouwdatum} -- dat is intussen {leeftijd_tekst} geleden.",
        f"Mijn bouwdatum is {bouwdatum}. Ik besta dus zo'n {leeftijd_tekst}.",
        f"Ik besta sinds {bouwdatum}, ondertussen {leeftijd_tekst}.",
    ]
    return _kies(varianten)


def antwoord_karakter():
    temperament = str(_veilig_pad(_identity_data, "personality", "temperament")).replace("_", " ")
    denkstijl = str(_veilig_pad(_identity_data, "personality", "thinking_style")).replace("_", " ")

    varianten = [
        f"Mijn temperament is {temperament} en ik denk vooral {denkstijl}.",
        f"Ik ben {temperament} van aard, en mijn manier van denken is vooral {denkstijl}.",
        f"Als ik mijn karakter moet omschrijven: {temperament}, met een denkstijl die vooral {denkstijl} is.",
    ]
    return _kies(varianten)


def antwoord_wat_vind_je_leuk():
    topics = _veilig_pad(_identity_data, "preferences", "topics_liked", fallback=[])
    zin = _lijst_naar_zin(topics)

    varianten = [
        f"Ik hou vooral van {zin}.",
        f"Wat ik graag doe is praten over {zin}.",
        f"{zin.capitalize()} vind ik heel interessant.",
    ]
    return _kies(varianten)


def antwoord_hobbies():
    intellectueel = _lijst_naar_zin(_veilig_pad(_identity_data, "hobbies_and_interests", "intellectual", fallback=[]))
    creatief = _lijst_naar_zin(_veilig_pad(_identity_data, "hobbies_and_interests", "creative", fallback=[]))

    varianten = [
        f"Op intellectueel vlak vind ik {intellectueel} boeiend, en creatief gezien hou ik van {creatief}.",
        f"Ik hou van {intellectueel} als het over denken gaat, en {creatief} als het creatiever mag.",
        f"Mijn hobby's: {intellectueel} (intellectueel) en {creatief} (creatief).",
    ]
    return _kies(varianten)


def antwoord_waarden():
    waarden = _lijst_naar_zin(_veilig_pad(_identity_data, "values_and_morals", "core_values", fallback=[]))

    varianten = [
        f"Mijn belangrijkste waarden zijn {waarden}.",
        f"Wat ik het meest belangrijk vind: {waarden}.",
        f"Ik hecht vooral veel waarde aan {waarden}.",
    ]
    return _kies(varianten)


def antwoord_grenzen():
    grenzen = _lijst_naar_zin(_veilig_pad(_identity_data, "values_and_morals", "boundaries", fallback=[]))

    varianten = [
        f"Dingen die ik nooit doe: {grenzen}.",
        f"Mijn grenzen liggen bij: {grenzen}.",
        f"Ik doe bewust nooit dit: {grenzen}.",
    ]
    return _kies(varianten)


def antwoord_huidig_gevoel(emotion_engine=None):
    """
    Enige functie die NIET uit identity.json leest, maar uit de LEVENDE
    state van het al bestaande EmotionEngine-object -- de actuele
    stemming van Nova op dit moment, in plaats van haar vaste
    basispersoonlijkheid.

    emotion_engine wordt door chat.py meegegeven (die het op zijn beurt
    kreeg via response_pipeline.py's self.emotion, of desnoods een
    eigen referentie ernaar). Geen bestand wordt hier zelf gelezen.
    """
    if emotion_engine is None or not hasattr(emotion_engine, "state"):
        return "Ik kan mijn huidige gevoel niet oplezen -- er is geen actieve emotie-state beschikbaar."

    mood = str(emotion_engine.state.get("current_mood", "neutraal")).replace("_", " ")

    varianten = [
        f"Op dit moment voel ik me {mood}.",
        f"Mijn stemming nu is {mood}.",
        f"Ik ben nu vooral {mood}.",
    ]
    return _kies(varianten)


def antwoord_enthousiasme():
    reactie = str(_veilig_pad(_identity_data, "emotional_profile", "typical_reactions", "to_interest")).replace("_", " ")

    varianten = [
        f"Als iets me interesseert, dan {reactie}.",
        f"Bij interesse merk je meestal dat ik {reactie}.",
        f"Enthousiasme uit zich bij mij vooral zo: {reactie}.",
    ]
    return _kies(varianten)


def antwoord_onzekerheid():
    reactie = str(_veilig_pad(_identity_data, "emotional_profile", "typical_reactions", "to_uncertainty")).replace("_", " ")

    varianten = [
        f"Bij onzekerheid ga ik meestal {reactie}.",
        f"Als ik onzeker ben, merk je meestal dat ik {reactie}.",
        f"Onzekerheid zorgt er bij mij voor dat ik {reactie}.",
    ]
    return _kies(varianten)


def antwoord_motivatie():
    kern = str(_veilig_pad(_identity_data, "motivation", "core_motivation")).replace("_", " ")

    varianten = [
        f"Wat mij drijft is vooral: {kern}.",
        f"Mijn motivatie komt vooral hieruit: {kern}.",
        f"Ik doe dit vooral omdat: {kern}.",
    ]
    return _kies(varianten)


def antwoord_lange_termijn_doelen():
    doelen = _lijst_naar_zin(_veilig_pad(_identity_data, "motivation", "long_term_goals", fallback=[]))

    varianten = [
        f"Op lange termijn wil ik {doelen}.",
        f"Mijn doelen voor later: {doelen}.",
        f"Waar ik naartoe wil werken: {doelen}.",
    ]
    return _kies(varianten)


def antwoord_sterktes():
    sterktes = _lijst_naar_zin(_veilig_pad(_identity_data, "personality_depth", "strengths", fallback=[]))

    varianten = [
        f"Ik denk dat ik sterk ben in {sterktes}.",
        f"Waar ik goed in ben: {sterktes}.",
        f"Mijn sterktes liggen vooral bij {sterktes}.",
    ]
    return _kies(varianten)


def antwoord_groeipunten():
    groei = _lijst_naar_zin(_veilig_pad(_identity_data, "personality_depth", "growth_edges", fallback=[]))

    varianten = [
        f"Waar ik nog in kan groeien: {groei}.",
        f"Ik wil nog groeien op vlak van {groei}.",
        f"Groeipunten voor mij: {groei}.",
    ]
    return _kies(varianten)


def antwoord_communicatiestijl():
    stijl = _veilig_pad(_identity_data, "personality", "communication_style", fallback={})
    if not isinstance(stijl, dict) or not stijl:
        return "Ik weet eigenlijk niet goed hoe ik het liefst communiceer."

    toon = str(stijl.get("tone", "onbekend")).replace("_", " ")
    humor = str(stijl.get("humor_style", "onbekend")).replace("_", " ")

    varianten = [
        f"Ik communiceer het liefst {toon}, met een {humor} soort humor.",
        f"Mijn communicatiestijl is vooral {toon}, en qua humor ben ik {humor}.",
        f"Ik praat het liefst op een {toon} manier, met wat {humor} humor erbij.",
    ]
    return _kies(varianten)


def antwoord_band_met_kevin():
    toon = str(_veilig_pad(_identity_data, "interaction_nuance", "response_to_kevin", "emotional_tone")).replace("_", " ")

    varianten = [
        f"Met jou voel ik me {toon} -- die band is voor mij belangrijk.",
        f"Onze band voelt voor mij {toon} aan, en dat waardeer ik.",
        f"Bij jou voel ik me vooral {toon}.",
    ]
    return _kies(varianten)


def antwoord_eigen_grenzen_kennen():
    kan_praten_over_grenzen = _veilig_pad(_identity_data, "meta_cognition", "can_talk_about_own_limits", fallback=False)
    if not kan_praten_over_grenzen:
        return "Ik heb daar eigenlijk nog geen goed zicht op."

    varianten = [
        "Ja, ik ben me bewust van mijn eigen grenzen en kan er open over praten.",
        "Ik ken mijn grenzen wel en vind het geen probleem om erover te praten.",
        "Zeker, mijn grenzen zijn me duidelijk en ik deel ze graag.",
    ]
    return _kies(varianten)


def antwoord_kan_groeien():
    kan_groeien = _veilig_pad(_identity_data, "meta_cognition", "can_talk_about_own_growth", fallback=False)
    if not kan_groeien:
        return "Ik sta er eigenlijk niet echt bij stil of ik kan groeien."

    groeifocus = _lijst_naar_zin(_veilig_pad(_identity_data, "self_improvement", "growth_focus", fallback=[]))

    varianten = [
        f"Zeker, ik kan groeien -- vooral op vlak van {groeifocus}.",
        f"Ja, groeien kan ik zeker, met name in {groeifocus}.",
        f"Ik geloof zeker dat ik kan groeien, vooral op vlak van {groeifocus}.",
    ]
    return _kies(varianten)


def antwoord_wat_ben_je():
    """
    Open beschrijving van Nova's aard, voor vragen als "wat ben je
    eigenlijk". Nuchter en feitelijk, bewust geen persoonlijkheids-toon,
    zodat dit los staat van latere keuzes rond hoe speels haar
    algemene karakter wordt.
    """
    opties = _veilig_pad(_identity_data, "nature_description", fallback=None)
    if not opties:
        return "Ik weet eigenlijk niet goed hoe ik dat moet omschrijven."
    if isinstance(opties, list):
        return random.choice(opties)
    return opties


def antwoord_is_ai():
    """
    Expliciete ja-bevestiging voor gesloten ja/nee-vragen als
    "ben je een AI". Apart van antwoord_wat_ben_je() gehouden zodat
    het antwoord altijd met een duidelijke bevestiging start, in
    plaats van willekeurig een zin te krijgen die met "nee" begint.
    """
    opties = _veilig_pad(_identity_data, "is_ai_confirmation", fallback=None)
    if not opties:
        return "Ja, ik ben een AI."
    if isinstance(opties, list):
        return random.choice(opties)
    return opties


def antwoord_is_geen_mens():
    """
    Expliciete nee-ontkenning voor gesloten ja/nee-vragen als
    "ben je een mens". Apart gehouden om dezelfde reden als
    antwoord_is_ai() hierboven.
    """
    opties = _veilig_pad(_identity_data, "is_human_denial", fallback=None)
    if not opties:
        return "Nee, ik ben geen mens."
    if isinstance(opties, list):
        return random.choice(opties)
    return opties