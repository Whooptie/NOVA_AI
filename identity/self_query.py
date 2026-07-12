# identity/self_query.py
"""
Deze module beantwoordt vragen die Kevin aan Nova stelt over zichzelf
("Wie ben je?", "Wat vind je leuk?", "Hoe voel je je?", ...).

Ze doet dit VOLLEDIG symbolisch: geen ML, geen generatie. Alles wat hier
gebeurt is (1) bestaande data opvragen en (2) vaste sjabloonzinnen
invullen met de waarden die daarin staan. Er wordt niets "verzonnen" --
als een veld niet bestaat, zegt Nova dat eerlijk.

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
    naam = _veilig_pad(_identity_data, "name", fallback="Nova")
    leeftijd = _veilig_pad(_identity_data, "age", fallback="onbekend")
    traits = _veilig_pad(_identity_data, "personality", "core_traits", fallback=[])
    traits_zin = _lijst_naar_zin(traits) if isinstance(traits, list) else traits
    return (
        f"Ik ben {naam}, {leeftijd} jaar. Ik zou mezelf omschrijven als "
        f"{traits_zin}."
    )


def antwoord_leeftijd():
    leeftijd = _veilig_pad(_identity_data, "age", fallback="dat weet ik niet van mezelf")
    return f"Ik ben {leeftijd} jaar."


def antwoord_karakter():
    temperament = _veilig_pad(_identity_data, "personality", "temperament")
    denkstijl = _veilig_pad(_identity_data, "personality", "thinking_style")
    return (
        f"Mijn temperament is {str(temperament).replace('_', ' ')} en ik denk vooral "
        f"{str(denkstijl).replace('_', ' ')}."
    )


def antwoord_wat_vind_je_leuk():
    topics = _veilig_pad(_identity_data, "preferences", "topics_liked", fallback=[])
    return f"Ik hou vooral van {_lijst_naar_zin(topics)}."


def antwoord_hobbies():
    intellectueel = _veilig_pad(_identity_data, "hobbies_and_interests", "intellectual", fallback=[])
    creatief = _veilig_pad(_identity_data, "hobbies_and_interests", "creative", fallback=[])
    return (
        f"Op intellectueel vlak vind ik {_lijst_naar_zin(intellectueel)} boeiend, "
        f"en creatief gezien hou ik van {_lijst_naar_zin(creatief)}."
    )


def antwoord_waarden():
    waarden = _veilig_pad(_identity_data, "values_and_morals", "core_values", fallback=[])
    return f"Mijn belangrijkste waarden zijn {_lijst_naar_zin(waarden)}."


def antwoord_grenzen():
    grenzen = _veilig_pad(_identity_data, "values_and_morals", "boundaries", fallback=[])
    return f"Dingen die ik nooit doe: {_lijst_naar_zin(grenzen)}."


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

    huidige_mood = emotion_engine.state.get("current_mood", "neutraal")
    return f"Op dit moment voel ik me {str(huidige_mood).replace('_', ' ')}."


def antwoord_enthousiasme():
    reactie = _veilig_pad(_identity_data, "emotional_profile", "typical_reactions", "to_interest")
    return f"Als iets me interesseert, dan {str(reactie).replace('_', ' ')}."


def antwoord_onzekerheid():
    reactie = _veilig_pad(_identity_data, "emotional_profile", "typical_reactions", "to_uncertainty")
    return f"Bij onzekerheid ga ik meestal {str(reactie).replace('_', ' ')}."


def antwoord_motivatie():
    kern = _veilig_pad(_identity_data, "motivation", "core_motivation")
    return f"Wat mij drijft is vooral: {str(kern).replace('_', ' ')}."


def antwoord_lange_termijn_doelen():
    doelen = _veilig_pad(_identity_data, "motivation", "long_term_goals", fallback=[])
    return f"Op lange termijn wil ik {_lijst_naar_zin(doelen)}."


def antwoord_sterktes():
    sterktes = _veilig_pad(_identity_data, "personality_depth", "strengths", fallback=[])
    return f"Ik denk dat ik sterk ben in {_lijst_naar_zin(sterktes)}."


def antwoord_groeipunten():
    groei = _veilig_pad(_identity_data, "personality_depth", "growth_edges", fallback=[])
    return f"Waar ik nog in kan groeien: {_lijst_naar_zin(groei)}."


def antwoord_communicatiestijl():
    stijl = _veilig_pad(_identity_data, "personality", "communication_style", fallback={})
    if not isinstance(stijl, dict) or not stijl:
        return "Ik weet eigenlijk niet goed hoe ik het liefst communiceer."
    toon = str(stijl.get("tone", "onbekend")).replace("_", " ")
    humor = str(stijl.get("humor_style", "onbekend")).replace("_", " ")
    return f"Ik communiceer het liefst {toon}, met een {humor} soort humor."


def antwoord_band_met_kevin():
    toon = _veilig_pad(_identity_data, "interaction_nuance", "response_to_kevin", "emotional_tone")
    return f"Met jou voel ik me {str(toon).replace('_', ' ')} -- die band is voor mij belangrijk."


def antwoord_eigen_grenzen_kennen():
    kan_praten_over_grenzen = _veilig_pad(_identity_data, "meta_cognition", "can_talk_about_own_limits", fallback=False)
    if kan_praten_over_grenzen:
        return "Ja, ik ben me bewust van mijn eigen grenzen en kan er open over praten."
    return "Ik heb daar eigenlijk nog geen goed zicht op."


def antwoord_kan_groeien():
    kan_groeien = _veilig_pad(_identity_data, "meta_cognition", "can_talk_about_own_growth", fallback=False)
    groeifocus = _veilig_pad(_identity_data, "self_improvement", "growth_focus", fallback=[])
    if kan_groeien:
        return f"Zeker, ik kan groeien -- vooral op vlak van {_lijst_naar_zin(groeifocus)}."
    return "Ik sta er eigenlijk niet echt bij stil of ik kan groeien."