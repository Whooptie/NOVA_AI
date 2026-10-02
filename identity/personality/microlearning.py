# identity/personality/microlearning.py
"""
Layer 6, Fase 6: Adaptive Learning

Symbolisch systeem dat traits.json LANGZAAM en BINNEN HARDE GRENZEN
laat meebewegen op basis van geobserveerde signalen in Kevin's
berichten (frustratie, waardering, interesse, verwarring, focus,
kilte) — zie signal_trait_mapping.json voor de volledige koppeling.

BELANGRIJKE ARCHITECTUUR-KEUZE: dit bestand beslist ZELF NIETS over
HOEVEEL een trait verschuift of WANNEER — dat ligt volledig vast in
adaptive_rules.json (tempo, stapgrootte, drempel, min/max). Dit
bestand is puur de "motor" die: (1) een signaal herkent, (2) de
tellers in growth_metrics.json bijwerkt, (3) bij het bereiken van een
drempel de vaste stap toepast op traits.json. Geen giswerk, geen
"voorspelde" hoeveelheid — een stap is altijd exact stap_grootte uit
adaptive_rules.json, nooit meer of minder.

VOORLOPIGE SIGNAALDETECTIE (17 juli 2026): dit gebruikt nu nog simpele
woordenlijst-matching als PLACEHOLDER voor het geplande, kleine
sentiment-classificatiemodel (Fase 6, onderdeel 1 — scikit-learn,
bounded specialist-tool, net als de al geplande intent classifier).
Zodra dat model gebouwd is, wordt ENKEL _detecteer_signaal() hieronder
vervangen — de rest van deze module (tellers bijwerken, traits
verschuiven) blijft ongewijzigd, want die is al signaal-onafhankelijk
opgezet.
"""

import json
import os
import pickle
import re
from datetime import datetime


class MicroLearning:
    # Marge-drempel (17 juli 2026, na live-analyse van het eerste
    # getrainde model): met 6 mogelijke signalen en een kleine
    # trainingsset liggen ALLE confidence-scores relatief laag
    # (0.18-0.30), ook bij overduidelijk correcte voorspellingen —
    # een vaste absolute drempel (bv. "confidence > 0.5") zou dus
    # bijna alles als onzeker bestempelen. In plaats daarvan kijken
    # we naar de MARGE tussen de winnende en de op-één-na-beste
    # klasse: hoe groter dat verschil, hoe overtuigder het model is,
    # ongeacht de absolute hoogte van de scores zelf.
    MARGE_DREMPEL = 0.10

    # Fase B (2 oktober 2026): STRIKTE trefwoorden om twijfelgevallen
    # AUTOMATISCH te labelen ("label_auto"). Bewust apart van de grove
    # woordenlijst in _detecteer_signaal_woordenlijst(), die blijft voor
    # de directe signaalherkenning. Hier: enkel hele woorden/zinsdelen,
    # enkel ondubbelzinnige trefwoorden. Bewust NIET opgenomen: "top"
    # (zit ook in "stop"), "leuk"/"cool"/"wow" (kan sarcastisch zijn),
    # "hoe werkt" (gewone vraag, geen verwarring).
    STRIKTE_TREFWOORDEN = {
        "frustratie": ["frustrerend", "irritant", "werkt niet", "werkt gewoon niet"],
        "waardering": ["dank je", "dankjewel", "dank u", "bedankt", "merci", "dat helpt"],
        "verwarring": ["snap ik niet", "begrijp ik niet", "snap het niet",
                       "begrijp het niet", "wat bedoel je"],
        "focus": ["niet storen", "in de flow", "geconcentreerd"],
        "interesse": ["interessant", "vertel meer", "vertel eens meer"],
    }

    def __init__(self, event_bus):
        self.event_bus = event_bus

        base = os.path.dirname(__file__)
        self._rules_path = os.path.join(base, "adaptive_rules.json")
        self._metrics_path = os.path.join(base, "growth_metrics.json")
        self._mapping_path = os.path.join(base, "signal_trait_mapping.json")
        self._traits_path = os.path.join(base, "traits.json")
        self._model_path = os.path.join(base, "signal_model.pkl")
        self._uncertain_path = os.path.join(base, "uncertain_signals.jsonl")

        with open(self._rules_path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)
        with open(self._metrics_path, "r", encoding="utf-8") as f:
            self.metrics = json.load(f)
        with open(self._mapping_path, "r", encoding="utf-8") as f:
            self.mapping = json.load(f)
        with open(self._traits_path, "r", encoding="utf-8") as f:
            self.traits = json.load(f)

        self.model = self._laad_model()

        # Layer 6, Fase 6 onderdeel 6 (17 juli 2026): automatische
        # hertraining. Nova draait 24/7 als event-driven daemon (geen
        # normale "sessie" die regelmatig herstart) — dus enkel bij
        # opstart checken zou in de praktijk zelden gebeuren. Daarom
        # BEIDE: één check meteen bij opstart (dit blok hieronder), én
        # een doorlopende check na elk nieuw gelogd twijfelgeval (zie
        # _log_uncertain(), die nu _check_hertraining() aanroept).
        self._hertraining_status_pad = os.path.join(base, "hertraining_status.json")
        # Fase A (2 oktober 2026): telt nu NIEUWE, DOOR KEVIN GELABELDE
        # unieke twijfelzinnen (niet meer ruwe logregels) -- vandaar
        # een lagere drempel dan de vroegere 20.
        self.HERTRAINING_DREMPEL = 10

        self._check_hertraining(bij_opstart=True)

        event_bus.subscribe("raw_user_message", self.on_raw_message)

    def _laad_model(self):
        """
        Laadt het getrainde signaal-classificatiemodel (train_
        classifier.py). Geeft None terug als het nog niet bestaat
        (bv. Kevin heeft train_classifier.py nog niet gedraaid) —
        _detecteer_signaal() valt dan volledig terug op de
        woordenlijst-aanpak, geen crash.
        """
        if not os.path.exists(self._model_path):
            print(
                "[MICROLEARNING] Geen getraind model gevonden "
                f"({self._model_path}). Draai train_classifier.py "
                "eerst — voorlopig wordt enkel de woordenlijst-"
                "fallback gebruikt."
            )
            return None

        try:
            with open(self._model_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"[MICROLEARNING] Kon model niet laden: {e}")
            return None

    # ---------------------------------------------------------
    # 1. Signaal detecteren — model (Fase 6 onderdeel 1) + fallback
    # ---------------------------------------------------------
    def _detecteer_signaal(self, text: str):
        """
        Geeft een lijst met PRECIES ÉÉN signaal-naam terug (of een
        lege lijst als het "neutraal" is — dat heeft toch geen
        effecten in signal_trait_mapping.json).

        AANGEPAST (17 juli 2026): gebruikt nu het getrainde model
        (train_classifier.py) als primaire bron. Bij een LAGE MARGE
        tussen de winnende en de op-één-na-beste klasse (het model
        twijfelt) wordt het geval:
        (a) gelogd in uncertain_signals.jsonl, voor toekomstige
            hertraining (zie _log_uncertain()), EN
        (b) ter controle ook door de oude woordenlijst-aanpak
            gehaald — bij een duidelijke woordenlijst-match wordt
            DIE gebruikt (specifieker/betrouwbaarder bij evidente
            trefwoorden), anders blijft het model-resultaat gelden.

        Als er geen model geladen kon worden: volledige fallback op
        enkel de woordenlijst, zoals vóór deze uitbreiding.
        """
        if self.model is None:
            return self._detecteer_signaal_woordenlijst(text)

        try:
            proba = self.model.predict_proba([text])[0]
            klassen = self.model.classes_
            gesorteerd = sorted(zip(klassen, proba), key=lambda x: -x[1])
            top_klasse, top_score = gesorteerd[0]
            _, tweede_score = gesorteerd[1]
            marge = top_score - tweede_score
        except Exception:
            # Model faalde onverwacht op deze specifieke tekst — nooit
            # crashen, gewoon terugvallen op de woordenlijst.
            return self._detecteer_signaal_woordenlijst(text)

        if marge < self.MARGE_DREMPEL:
            woordenlijst_resultaat = self._detecteer_signaal_woordenlijst(text)
            self._log_uncertain(text, model_signaal=top_klasse, marge=marge,
                                 woordenlijst_signaal=woordenlijst_resultaat)
            if woordenlijst_resultaat:
                return woordenlijst_resultaat
            # Fase A (2 oktober 2026): twijfel zonder bevestiging door
            # de woordenlijst = GEEN signaal. Voorheen viel de code hier
            # door naar het model-resultaat, waardoor bv. elke schaakzet
            # (marge 0.0957) als "kilte" telde en traits liet schuiven.
            return []

        if top_klasse == "neutraal":
            return []
        return [top_klasse]

    def _detecteer_signaal_woordenlijst(self, text: str):
        """
        De oorspronkelijke, simpele woordenlijst-aanpak — blijft
        bestaan als (a) fallback wanneer er geen model geladen is,
        en (b) extra controle bij lage model-confidence hierboven.
        """
        tekst_lower = text.lower()
        signalen = []

        frustratie_woorden = ["frustrerend", "werkt niet", "ugh", "irritant", "kut", "ff*k"]
        waardering_woorden = ["dank je", "dankjewel", "goed zo", "top", "perfect", "dat helpt"]
        interesse_woorden = ["interessant", "leuk", "wow", "cool", "gaaf", "vertel meer"]
        verwarring_woorden = ["snap ik niet", "begrijp niet", "wat bedoel", "hoe werkt", "onduidelijk"]
        focus_woorden = ["focussen", "geconcentreerd", "niet storen", "in de flow", "even stil", "doorwerken"]
        # Fase A (2 oktober 2026): de oude regel "bericht van max. 3
        # tekens = kilte" is geschrapt -- die gaf vooral foute signalen
        # ("hey", "pi", "3", een getal als antwoord op een vraag).

        if any(w in tekst_lower for w in frustratie_woorden):
            signalen.append("frustratie")
        elif any(w in tekst_lower for w in waardering_woorden):
            signalen.append("waardering")
        elif any(w in tekst_lower for w in interesse_woorden):
            signalen.append("interesse")
        elif any(w in tekst_lower for w in verwarring_woorden):
            signalen.append("verwarring")
        elif any(w in tekst_lower for w in focus_woorden):
            signalen.append("focus")

        return signalen

    def _log_uncertain(self, text, model_signaal, marge, woordenlijst_signaal):
        """
        Layer 6, Fase 6 onderdeel 1: logt een twijfelgeval — een
        bericht waar het model geen duidelijke marge tussen de
        winnende en tweede klasse had. Dit is de groeiende
        trainingsdata voor toekomstige, automatische hertraining
        (zie train_classifier.py's gebruik van deze data, en
        onderdeel 6 hierna: de automatische hertraining-trigger).

        Het "signaal"-veld bevat de GOK van de woordenlijst of het
        model -- louter informatief. Fase A (2 oktober 2026): dit veld
        wordt NIET meer als trainingslabel gebruikt (dat gaf
        zelfbevestigend leren: het model leerde van zijn eigen
        onzekere gokken). Een twijfelgeval telt pas mee bij
        hertraining zodra Kevin het een eigen label gaf (veld
        "label_kevin", zie train_classifier.py).
        """
        gebruikt_signaal = (woordenlijst_signaal[0] if woordenlijst_signaal
                             else model_signaal)

        regel = {
            "text": text,
            "signaal": gebruikt_signaal,
            "model_signaal": model_signaal,
            "marge": round(marge, 4),
            "bron": "woordenlijst" if woordenlijst_signaal else "model_fallback",
            "tijdstip": datetime.now().isoformat(),
        }

        # Fase B (2 oktober 2026): bij een ondubbelzinnig strikt
        # trefwoord krijgt het twijfelgeval meteen een automatisch
        # label. Dat label komt van een bron BUITEN het model, dus geen
        # zelfbevestigend leren. Kevins eigen label ("label_kevin")
        # wint later altijd.
        auto_label = self._auto_label(text)
        if auto_label:
            regel["label_auto"] = auto_label
            regel["label_bron"] = "woordenlijst_strikt"

        try:
            with open(self._uncertain_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(regel, ensure_ascii=False) + "\n")
        except Exception:
            pass

        # Fase 6 onderdeel 6: elke nieuwe log-regel kan de drempel
        # voor automatische hertraining bereiken — check dit meteen,
        # zodat Nova (die 24/7 draait, geen herhaalde opstarts) niet
        # hoeft te wachten tot een volgende herstart.
        self._check_hertraining(bij_opstart=False)

    def _auto_label(self, text: str):
        """
        Fase B (2 oktober 2026): geeft een signaal-label terug als
        PRECIES ÉÉN categorie uit STRIKTE_TREFWOORDEN matcht, anders
        None. Zoekt op hele woorden (niet als stukje van een ander
        woord). Een ontkenning direct ervoor of erna ("niet
        interessant", "dat helpt niet") blokkeert het automatische
        label volledig -- liever geen label dan een fout label.
        Trefwoorden die zelf al "niet" bevatten ("werkt niet",
        "niet storen") worden daarbij niet als ontkend gezien.
        """
        tekst = (text or "").lower()
        gevonden = set()

        for signaal, trefwoorden in self.STRIKTE_TREFWOORDEN.items():
            for woord in trefwoorden:
                patroon = r"(?<!\w)" + re.escape(woord) + r"(?!\w)"
                for match in re.finditer(patroon, tekst):
                    if "niet" not in woord and "geen" not in woord:
                        ervoor = tekst[:match.start()]
                        erna = tekst[match.end():]
                        if (re.search(r"(?<!\w)(niet|geen)\s+$", ervoor)
                                or re.match(r"\s+(niet|geen)(?!\w)", erna)):
                            return None
                    gevonden.add(signaal)

        if len(gevonden) == 1:
            return gevonden.pop()
        return None

    # ---------------------------------------------------------
    # 7. Automatische hertraining (Fase 6, onderdeel 6)
    # ---------------------------------------------------------
    def _tel_gelabelde_twijfelzinnen(self):
        """
        Fase A (2 oktober 2026): telt het aantal UNIEKE twijfelzinnen
        waaraan Kevin een eigen label gaf ("label_kevin", niet leeg en
        niet "skip"). Ruwe, ongelabelde logregels tellen niet meer mee
        voor de hertraining-trigger -- die worden niet meer als
        trainingsdata gebruikt, dus hertrainen op basis daarvan zou
        enkel dezelfde schone data opnieuw trainen.
        """
        if not os.path.exists(self._uncertain_path):
            return 0

        unieke_teksten = set()
        with open(self._uncertain_path, "r", encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    item = json.loads(regel)
                except json.JSONDecodeError:
                    continue
                # Fase B: Kevins label wint (ook "skip"); anders telt
                # een automatisch label mee.
                label = item.get("label_kevin") or item.get("label_auto")
                tekst = item.get("text", "").strip().lower()
                if label and label != "skip" and tekst:
                    unieke_teksten.add(tekst)
        return len(unieke_teksten)

    def _laad_hertraining_status(self):
        """
        Onthoudt hoeveel regels er in uncertain_signals.jsonl stonden
        bij de LAATSTE hertraining — nodig om te bepalen hoeveel
        NIEUWE twijfelgevallen er sindsdien zijn bijgekomen, zonder
        steeds dezelfde oude regels opnieuw te tellen.
        """
        leeg = {"gelabeld_bij_laatste_training": 0, "laatste_training": None}
        if not os.path.exists(self._hertraining_status_pad):
            return leeg

        try:
            with open(self._hertraining_status_pad, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            return leeg

        # Fase A (2 oktober 2026): een oud statusbestand bevat enkel de
        # vroegere sleutel "aantal_bij_laatste_training" (ruwe
        # logregels). Die telling is niet vergelijkbaar met het nieuwe
        # aantal gelabelde zinnen -- dus bewust genegeerd, we starten
        # vanaf 0 gelabelde.
        status.setdefault("gelabeld_bij_laatste_training", 0)
        status.setdefault("laatste_training", None)
        return status

    def _save_hertraining_status(self, aantal_gelabeld):
        status = {
            "gelabeld_bij_laatste_training": aantal_gelabeld,
            "laatste_training": datetime.now().isoformat(),
        }
        with open(self._hertraining_status_pad, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)

    def _check_hertraining(self, bij_opstart: bool):
        """
        Checkt of er genoeg NIEUWE twijfelgevallen zijn sinds de
        laatste hertraining om een nieuwe trainingsronde te
        rechtvaardigen. Roept train_classifier.train_model() aan als
        dat zo is — dat script bevat zelf al de volledige
        veiligheidsrem (ijkpunt-vergelijking, nieuwe versie wordt
        enkel actief bij minstens gelijke score, zie train_
        classifier.py). Deze methode moet dus ZELF geen kwaliteits-
        oordeel vellen — enkel bepalen WANNEER er een nieuwe
        trainingspoging de moeite waard is.

        Na een succesvolle trainingspoging (ongeacht of de nieuwe
        versie uiteindelijk actief werd): als de nieuwe versie ECHT
        actief werd, moet MicroLearning zijn eigen self.model
        herladen — anders blijft deze lopende instantie het OUDE
        model gebruiken tot de volgende herstart, wat dezelfde
        "dode koppeling"-fout zou zijn als bij onderdeel 5 hierboven.
        """
        huidig_aantal = self._tel_gelabelde_twijfelzinnen()
        status = self._laad_hertraining_status()
        nieuwe_sinds_laatste = huidig_aantal - status["gelabeld_bij_laatste_training"]

        moet_hertrainen = (
            nieuwe_sinds_laatste >= self.HERTRAINING_DREMPEL
            or (bij_opstart and status["laatste_training"] is None and huidig_aantal >= 10)
        )

        if not moet_hertrainen:
            return

        try:
            # Late import: train_classifier.py importeert zelf
            # scikit-learn, wat we liever niet onnodig belasten als
            # er toch niets te hertrainen valt.
            from identity.personality import train_classifier

            print(
                f"[MICROLEARNING] {nieuwe_sinds_laatste} nieuwe door Kevin gelabelde twijfelzinnen "
                f"sinds de laatste hertraining — automatische hertraining wordt gestart."
            )
            resultaat = train_classifier.train_model()

            if resultaat.get("succes"):
                self._save_hertraining_status(huidig_aantal)

                if resultaat.get("wordt_actief"):
                    print(
                        "[MICROLEARNING] Nieuwe modelversie is beter of gelijk aan "
                        "het ijkpunt — wordt nu actief geladen."
                    )
                    self.model = self._laad_model()
                else:
                    print(
                        "[MICROLEARNING] Nieuwe modelversie scoorde lager op het "
                        "ijkpunt — huidige, actieve versie blijft in gebruik."
                    )
            else:
                print(f"[MICROLEARNING] Hertraining niet gelukt: {resultaat.get('reden')}")
        except Exception as e:
            # Hertraining is een aanvullende, niet-kritieke achtergrond-
            # taak — een fout hier mag Nova's normale werking nooit
            # verstoren.
            print(f"[MICROLEARNING] Onverwachte fout bij automatische hertraining: {e}")

    # ---------------------------------------------------------
    # 2. Event-handler
    # ---------------------------------------------------------
    def on_raw_message(self, data, event_type=None):
        text = data.get("text", "")
        if not text:
            return

        try:
            signalen = self._detecteer_signaal(text)
            for signaal in signalen:
                self._verwerk_signaal(signaal)
        except Exception:
            # Nooit de rest van Nova laten crashen door een fout hier
            # — adaptive learning is een aanvullende, niet-kritieke
            # laag, geen kernfunctionaliteit.
            pass

    # ---------------------------------------------------------
    # 3. Eén signaal verwerken: tellers bijwerken, evt. trait verschuiven
    # ---------------------------------------------------------
    # Layer 6, Fase 6 uitbreiding (koppeling met emotion_engine.py,
    # nova_state.md punt 8): MicroLearning herkent hier al een signaal
    # in Kevin's bericht, maar dat signaal bereikte tot nu toe ENKEL
    # traits.json (via _update_teller() hieronder) — emotion_engine.py's
    # apply_trigger() werd in de hele codebase maar op 1 plek aangeroepen
    # (response_pipeline.py's on_greeting(), altijd hardcoded
    # "excitement"). Deze mapping hergebruikt het AL BESTAANDE
    # classificatiemodel/signaal, in plaats van een nieuwe, aparte
    # detectie te bouwen — 1 signaal, 2 bestemmingen (traits EN emotie).
    #
    # "kilte" heeft bewust GEEN tegenhanger: emotion_rules.json kent
    # geen bijpassende trigger, en die zelf verzinnen is een aparte
    # ontwerpbeslissing die hier niet gemaakt wordt.
    _SIGNAAL_NAAR_EMOTION_TRIGGER = {
        "frustratie": "frustration",
        "interesse": "interest",
        "verwarring": "confusion",
        "focus": "focus",
        "waardering": "waardering",
        "kilte": "kilte",
    }

    def _verwerk_signaal(self, signaal: str):
        signaal_info = self.mapping.get("signalen", {}).get(signaal)
        if not signaal_info:
            return

        effecten = signaal_info.get("effecten", {})

        for trait_naam, richting in effecten.items():
            self._update_teller(trait_naam, richting)

        self._apply_emotion_trigger_indien_van_toepassing(signaal)

    def _apply_emotion_trigger_indien_van_toepassing(self, signaal: str):
        """
        Stuurt hetzelfde signaal ook naar emotion_engine.py, via de
        al bestaande PersonalityEngine-instantie (event_bus.modules
        ["personality"], geregistreerd in response_pipeline.py).

        Faalt dit ooit (personality/emotion nog niet geladen, of een
        onverwachte fout) — dan gewoon stilzwijgend niets doen, zelfde
        principe als de rest van deze module: adaptive learning/emotie
        is een aanvullende laag, mag Nova's kernwerking nooit breken.
        """
        trigger = self._SIGNAAL_NAAR_EMOTION_TRIGGER.get(signaal)
        if not trigger:
            return

        try:
            personality = self.event_bus.modules.get("personality")
            emotion = self.event_bus.modules.get("emotion")
            if personality is None or emotion is None:
                return
            emotion.apply_trigger(trigger, personality_engine=personality)
        except Exception:
            pass

    def _update_teller(self, trait_naam: str, richting: str):
        """
        richting is "positief" of "negatief" — werkt de bijbehorende
        teller in growth_metrics.json bij, en controleert meteen of
        de drempel voor deze trait bereikt is.
        """
        if trait_naam not in self.metrics.get("traits", {}):
            return

        trait_metrics = self.metrics["traits"][trait_naam]

        if richting == "positief":
            trait_metrics["positive_count"] += 1
        else:
            trait_metrics["negative_count"] += 1

        self._check_drempel(trait_naam)
        self._save_metrics()

    # ---------------------------------------------------------
    # 4. Drempel-check: bij genoeg signalen, trait verschuiven
    # ---------------------------------------------------------
    def _check_drempel(self, trait_naam: str):
        trait_regels = self.rules.get("traits", {}).get(trait_naam)
        if not trait_regels:
            # Trait niet in adaptive_rules.json (bv. uitgesloten
            # zoals boundary_respect/safety_alignment) — nooit
            # aanpassen, ongeacht wat de mapping zegt.
            return

        tempo_naam = trait_regels["tempo"]
        tempo_regels = self.rules["tempo_categorieen"][tempo_naam]
        drempel = tempo_regels["signal_threshold"]
        stap = tempo_regels["stap_grootte"]

        trait_metrics = self.metrics["traits"][trait_naam]
        netto = trait_metrics["positive_count"] - trait_metrics["negative_count"]

        if abs(netto) < drempel:
            return

        richting = 1 if netto > 0 else -1
        self._verschuif_trait(trait_naam, richting * stap, trait_regels)

        # Tellers resetten na een verschuiving — een nieuwe cyclus
        # begint, niet blijven doortellen op de oude signalen.
        trait_metrics["positive_count"] = 0
        trait_metrics["negative_count"] = 0
        trait_metrics["total_shifts"] += 1
        trait_metrics["last_shift"] = datetime.now().isoformat()
        trait_metrics["last_shift_direction"] = "positief" if richting > 0 else "negatief"

    # ---------------------------------------------------------
    # 5. Daadwerkelijke, begrensde verschuiving toepassen
    # ---------------------------------------------------------
    def _verschuif_trait(self, trait_naam: str, delta: float, trait_regels: dict):
        huidige_waarde = self.traits.get(trait_naam, 0.5)
        nieuwe_waarde = huidige_waarde + delta

        # Harde grenzen uit adaptive_rules.json — een trait kan NOOIT
        # buiten deze range komen, ongeacht hoeveel signalen er ooit
        # binnenkomen. Dit is de "persoonlijkheidskern" die intact
        # blijft.
        min_grens = trait_regels["min"]
        max_grens = trait_regels["max"]
        nieuwe_waarde = max(min_grens, min(max_grens, nieuwe_waarde))

        self.traits[trait_naam] = round(nieuwe_waarde, 4)
        self._save_traits()

        # Layer 6, Fase 6: publiceer een event zodat dit net als
        # identity_state:updated automatisch door memory.py wordt
        # opgeslagen (wildcard-subscribe, zie personality_engine.py's
        # _publish_state_update() voor hetzelfde patroon).
        if self.event_bus is not None:
            try:
                self.event_bus.publish("trait_shifted", {
                    "trait": trait_naam,
                    "delta": delta,
                    "nieuwe_waarde": self.traits[trait_naam],
                })
            except Exception:
                pass

    # ---------------------------------------------------------
    # Publieke API (voor andere modules, bv. Layer 7 emergence_engine.py)
    # ---------------------------------------------------------
    def get_growth_metrics(self) -> dict:
        """
        Geeft de per-trait groei-tellers terug (positive_count/
        negative_count/total_shifts/last_shift/last_shift_direction).

        Geeft de AL INGELEZEN, levende self.metrics["traits"]-dict
        terug — geen nieuwe schijf-lezing nodig, want deze data wordt
        toch al bij elke wijziging bijgewerkt via _save_metrics().
        Bewust een kopie (dict(...)) i.p.v. de originele referentie,
        zodat een aanroeper deze data nooit per ongeluk kan wijzigen.
        """
        return dict(self.metrics.get("traits", {}))

    # ---------------------------------------------------------
    # 6. Opslaan
    # ---------------------------------------------------------
    def _save_metrics(self):
        with open(self._metrics_path, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)

    def _save_traits(self):
        with open(self._traits_path, "w", encoding="utf-8") as f:
            json.dump(self.traits, f, indent=2, ensure_ascii=False)


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'sem' wordt hier niet gebruikt maar moet aanwezig zijn voor de
    dynamische scan in module_loader.py — LET OP: dit bestand staat
    in identity/, niet modules/, dus wordt NIET automatisch gescand
    (zelfde architecturale les als self_query.py, zie nova_state.md).
    Moet dus, net als self_query.py, apart geladen worden — zie de
    module_loader.py-aanpassing die hierna nog nodig is.
    """
    instance = MicroLearning(event_bus)
    event_bus.publish("module_loaded", {"name": "microlearning"})
    return instance