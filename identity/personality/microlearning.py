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
        self.HERTRAINING_DREMPEL = 20

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
        kilte_indicatie = len(text.strip()) <= 3

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
        elif kilte_indicatie:
            signalen.append("kilte")

        return signalen

    def _log_uncertain(self, text, model_signaal, marge, woordenlijst_signaal):
        """
        Layer 6, Fase 6 onderdeel 1: logt een twijfelgeval — een
        bericht waar het model geen duidelijke marge tussen de
        winnende en tweede klasse had. Dit is de groeiende
        trainingsdata voor toekomstige, automatische hertraining
        (zie train_classifier.py's gebruik van deze data, en
        onderdeel 6 hierna: de automatische hertraining-trigger).

        Het uiteindelijk gebruikte signaal (woordenlijst indien die
        een match had, anders het model-resultaat) wordt gelogd als
        het "signaal"-veld — dat is wat train_classifier.py later als
        label zal gebruiken bij hertraining. GEEN mensencontrole op
        dit moment — bewust zo ontworpen (zie ontwerpgesprek): het
        ijkpunt-testsetje (benchmark_data.json) is de kwaliteitsrem,
        niet elke individuele log-regel.
        """
        gebruikt_signaal = (woordenlijst_signaal[0] if woordenlijst_signaal
                             else model_signaal)

        try:
            with open(self._uncertain_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "text": text,
                    "signaal": gebruikt_signaal,
                    "model_signaal": model_signaal,
                    "marge": round(marge, 4),
                    "bron": "woordenlijst" if woordenlijst_signaal else "model_fallback",
                    "tijdstip": datetime.now().isoformat(),
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

        # Fase 6 onderdeel 6: elke nieuwe log-regel kan de drempel
        # voor automatische hertraining bereiken — check dit meteen,
        # zodat Nova (die 24/7 draait, geen herhaalde opstarts) niet
        # hoeft te wachten tot een volgende herstart.
        self._check_hertraining(bij_opstart=False)

    # ---------------------------------------------------------
    # 7. Automatische hertraining (Fase 6, onderdeel 6)
    # ---------------------------------------------------------
    def _tel_huidige_uncertain_regels(self):
        if not os.path.exists(self._uncertain_path):
            return 0
        with open(self._uncertain_path, "r", encoding="utf-8") as f:
            return sum(1 for regel in f if regel.strip())

    def _laad_hertraining_status(self):
        """
        Onthoudt hoeveel regels er in uncertain_signals.jsonl stonden
        bij de LAATSTE hertraining — nodig om te bepalen hoeveel
        NIEUWE twijfelgevallen er sindsdien zijn bijgekomen, zonder
        steeds dezelfde oude regels opnieuw te tellen.
        """
        if not os.path.exists(self._hertraining_status_pad):
            return {"aantal_bij_laatste_training": 0, "laatste_training": None}

        try:
            with open(self._hertraining_status_pad, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"aantal_bij_laatste_training": 0, "laatste_training": None}

    def _save_hertraining_status(self, aantal_regels):
        status = {
            "aantal_bij_laatste_training": aantal_regels,
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
        huidig_aantal = self._tel_huidige_uncertain_regels()
        status = self._laad_hertraining_status()
        nieuwe_sinds_laatste = huidig_aantal - status["aantal_bij_laatste_training"]

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
                f"[MICROLEARNING] {nieuwe_sinds_laatste} nieuwe twijfelgevallen "
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
    def _verwerk_signaal(self, signaal: str):
        signaal_info = self.mapping.get("signalen", {}).get(signaal)
        if not signaal_info:
            return

        effecten = signaal_info.get("effecten", {})

        for trait_naam, richting in effecten.items():
            self._update_teller(trait_naam, richting)

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