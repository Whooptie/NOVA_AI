# modules/preferences/kevin_profile.py
"""
User Preferences module (Fase 1-3: databestand, CRUD, expliciet +
automatisch commando).

Wat dit is
----------
Een module die EXPLICIETE feiten over Kevin bijhoudt: voorkeuren en
afkeuren. Dit is bewust iets anders dan Layer 1 (word_associations_learner.py),
die statistische verbanden tussen willekeurige woorden leert. Deze module
legt concrete, opvraagbare feiten vast: "Kevin drinkt graag koffie" is
een simpele ja/nee-lookup, geen gewicht/score.

Zie: memory_user_preferences_roadmap.md voor de volledige architectuur-
uitleg en de reden waarom dit een aparte module is naast Layer 1.

DATASTRUCTUUR (v2, sinds 25 juli 2026)
----------------------------------------
Elk woord houdt TWEE aparte bronnen bij, niet één:

    "koffie": {
      "expliciet":   {"sentiment": "positief", "datum": "...", "aantal_keer_genoemd": 1},
      "automatisch": {"sentiment": "positief", "datum": "...", "aantal_keer_genoemd": 3}
    }

Reden voor deze opzet (i.p.v. één sentiment/bron per woord, zoals in
Fase 1): een woord dat expliciet ("onthoud: ...") EN automatisch
(losse herkende zin) genoemd wordt, verliest zo geen informatie. Een
woord kan ook maar één van de twee sub-blokken hebben (bv. enkel
"automatisch" als het nooit expliciet gezegd is).

Bij een CONFLICT (expliciet zegt positief, automatisch zegt negatief,
of omgekeerd) geldt: EXPLICIET WINT ALTIJD voor het "actieve" sentiment
van dat woord (zie get_preference()/get_by_sentiment() hieronder). De
automatisch-tak blijft gewoon in het bestand staan -- er gaat dus geen
geschiedenis verloren, enkel het opvragen van "wat geldt nu" kiest de
expliciete kant bij twijfel.

Wat dit (nog) NIET is
----------------------
Nog geen integratie in chat.py (Fase 4) -- deze module is de bouwsteen
waar Fase 4 op zal steunen.

Symbolisch vs. ML
------------------
100% symbolisch. Platte JSON-lezen/schrijven module -- geen ML, geen
LLM. De patroonherkenning van tekst zelf (welk woord, welk sentiment)
gebeurt in intent_router.py (handle_preference()/detect_preference()),
niet hier -- deze module doet enkel opslag en opvraging.
"""

import json
from datetime import datetime
from pathlib import Path

from modules.paths import get_project_root

C_RESET = "\033[0m"
C_GREEN = "\033[92m"
C_CYAN = "\033[96m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"


def dbg(label, text=""):
    print(f"{C_CYAN}[KEVIN_PROFILE]{C_RESET} {label} {text}")


class KevinProfile:
    """
    Houdt Kevins expliciete en automatisch-herkende voorkeuren/afkeuren
    bij in een plat JSON-bestand (data/kevin_profile.json).

    Bewust GEEN SQLite/WAL zoals memory.py (Layer 0): dit bestand
    schrijft zelden en groeit traag (hooguit een paar honderd items
    ooit). Een database zou hier overkill zijn.
    """

    BRONNEN = ("expliciet", "automatisch")

    def __init__(self, event_bus=None):
        self.event_bus = event_bus

        project_root = get_project_root(__file__)
        self.data_pad = project_root / "data" / "kevin_profile.json"

        self._zorg_dat_databestand_bestaat()
        self.data = self._laad()

        dbg(f"{C_GREEN}geladen ({len(self.data['voorkeuren'])} voorkeuren, "
            f"{len(self.data['afkeuren'])} afkeuren){C_RESET}")

    # -----------------------------------------------------------
    # Laden / opslaan
    # -----------------------------------------------------------
    def _zorg_dat_databestand_bestaat(self):
        """
        Maakt data/kevin_profile.json aan met een lege structuur als het
        nog niet bestaat. Maakt ook de 'data'-map zelf aan indien nodig.
        """
        self.data_pad.parent.mkdir(parents=True, exist_ok=True)

        if not self.data_pad.exists():
            leeg = {"voorkeuren": {}, "afkeuren": {}, "sense_voorkeuren": {}}
            self.data_pad.write_text(
                json.dumps(leeg, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            dbg(f"{C_GREEN}nieuw databestand aangemaakt: {self.data_pad}{C_RESET}")

    def _laad(self):
        """
        Leest het databestand in. Bij een corrupt/onleesbaar bestand
        wordt een lege structuur teruggegeven i.p.v. te crashen.

        Migratie van v1 -> v2 (25 juli 2026): oudere databestanden
        hadden een plat {"sentiment", "bron", "datum", "aantal_keer_genoemd"}
        per woord i.p.v. de nieuwe {"expliciet": {...}, "automatisch": {...}}
        sub-structuur. _migreer_woord_indien_nodig() zet elk woord dat
        nog de oude vorm heeft automatisch om, zodat een bestaand
        databestand van Kevin niet stuk gaat bij het opstarten na deze
        update.
        """
        try:
            ruw = self.data_pad.read_text(encoding="utf-8")
            data = json.loads(ruw)
        except (json.JSONDecodeError, OSError) as e:
            dbg(f"{C_RED}kon databestand niet lezen ({e}), start met leeg profiel{C_RESET}")
            return {"voorkeuren": {}, "afkeuren": {}}

        data.setdefault("voorkeuren", {})
        data.setdefault("afkeuren", {})
        # Bug #10-fix (sense-disambiguatie): apart, eenvoudig blok naast
        # voorkeuren/afkeuren. Dit is GEEN sentiment (positief/negatief)
        # zoals de rest van dit bestand, maar een keuze uit meerdere
        # betekenissen van eenzelfde woord (bv. "python" -> "python#2").
        # Daarom bewust in een eigen top-level sleutel gehouden i.p.v.
        # in de bestaande voorkeuren/afkeuren-structuur geperst.
        data.setdefault("sense_voorkeuren", {})

        gemigreerd = False
        for categorie in ("voorkeuren", "afkeuren"):
            for woord, info in data[categorie].items():
                nieuw_info = self._migreer_woord_indien_nodig(info)
                if nieuw_info is not info:
                    data[categorie][woord] = nieuw_info
                    gemigreerd = True

        if gemigreerd:
            dbg(f"{C_YELLOW}oud databestand (v1) gedetecteerd, automatisch gemigreerd naar v2-structuur{C_RESET}")

        return data

    def _migreer_woord_indien_nodig(self, info):
        """
        Herkent de oude v1-vorm (een plat dict met 'sentiment' als
        rechtstreekse sleutel) en zet dat om naar de nieuwe v2-vorm
        (een dict met 'expliciet'/'automatisch' als sub-sleutels). Geeft
        'info' ongewijzigd terug als het al de nieuwe vorm heeft.
        """
        if "sentiment" not in info:
            # Al v2 -- heeft geen top-level 'sentiment'-sleutel meer.
            return info

        bron = info.get("bron", "automatisch")
        if bron not in self.BRONNEN:
            bron = "automatisch"

        return {
            bron: {
                "sentiment": info["sentiment"],
                "datum": info.get("datum", datetime.now().strftime("%Y-%m-%d")),
                "aantal_keer_genoemd": info.get("aantal_keer_genoemd", 1),
            }
        }

    def _opslaan(self):
        """
        Schrijft het volledige profiel terug naar schijf. Simpele,
        directe write -- geen write-buffering zoals Layer 0.
        """
        self.data_pad.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # -----------------------------------------------------------
    # Interne helper: actief sentiment bepalen bij conflict
    # -----------------------------------------------------------
    def _bepaal_actief_sentiment(self, woord_info):
        """
        Geeft het "geldende" sentiment terug voor een woord dat zowel
        een 'expliciet'- als 'automatisch'-blok kan hebben.

        Regel: expliciet wint altijd als beide bestaan en het oneens
        zijn. Bestaat er maar één van de twee, dan geldt die vanzelf.

        Geeft terug: "positief", "negatief", of None als het woord geen
        van beide blokken heeft (zou niet mogen voorkomen in de praktijk,
        maar defensief afgehandeld).
        """
        expliciet = woord_info.get("expliciet")
        automatisch = woord_info.get("automatisch")

        if expliciet:
            return expliciet["sentiment"]
        if automatisch:
            return automatisch["sentiment"]
        return None

    def _vind_woord(self, woord):
        """
        Zoekt een woord op in beide categorieën (voorkeuren/afkeuren).
        Geeft terug: (categorie, woord_info) of (None, None) als het
        woord nergens gevonden werd.

        Let op: de categorie waarin een woord opgeslagen staat wordt
        bepaald door het ACTIEVE sentiment (zie _bepaal_actief_sentiment),
        dus een woord staat maar in één categorie tegelijk, ook al heeft
        het intern een expliciet- en automatisch-blok die het oneens
        zouden kunnen zijn.
        """
        for categorie in ("voorkeuren", "afkeuren"):
            if woord in self.data[categorie]:
                return categorie, self.data[categorie][woord]
        return None, None

    # -----------------------------------------------------------
    # Publieke API
    # -----------------------------------------------------------
    def add_preference(self, woord, sentiment, bron="automatisch"):
        """
        Voegt een voorkeur of afkeur toe (of werkt een bestaande bij)
        onder de gegeven bron ("expliciet" of "automatisch").

        Argumenten:
            woord: het onderwerp, bv. "koffie". Wordt intern gelowercased
                   en getrimd.
            sentiment: "positief" of "negatief" -- het sentiment ZOALS
                   GEZIEN VANUIT DEZE BRON. Dit hoeft niet het uiteindelijk
                   "actieve" sentiment te zijn als de andere bron het
                   oneens is (zie _bepaal_actief_sentiment).
            bron: "expliciet" (Kevin zei het letterlijk via 'onthoud:')
                  of "automatisch" (patroonherkenning, Fase 3).

        Gedrag: elke bron (expliciet/automatisch) houdt zijn EIGEN
        aantal_keer_genoemd en datum bij, onafhankelijk van de andere
        bron. Een automatische herkenning kan dus nooit een bestaande
        expliciete uitspraak "overschrijven" of andersom -- ze staan
        naast elkaar. Welke categorie (voorkeuren/afkeuren) het woord
        uiteindelijk in staat, wordt bepaald door het ACTIEVE sentiment
        (expliciet wint bij conflict).

        Publiceert 'preference_learned' op de EventBus met het actieve
        sentiment na deze wijziging, plus of er een conflict was.
        """
        if sentiment not in ("positief", "negatief", "neutraal_gemengd"):
            raise ValueError(
                f"sentiment moet 'positief', 'negatief' of 'neutraal_gemengd' zijn, kreeg: {sentiment!r}"
            )
        if bron not in self.BRONNEN:
            raise ValueError(
                f"bron moet 'expliciet' of 'automatisch' zijn, kreeg: {bron!r}"
            )

        woord = woord.strip().lower()
        if not woord:
            dbg(f"{C_RED}leeg woord genegeerd bij add_preference{C_RESET}")
            return

        # Bestaand woord opzoeken, ongeacht in welke categorie het nu
        # staat -- het kan immers van categorie wisselen als dit de
        # bron is die het conflict veroorzaakt/oplost.
        _, woord_info = self._vind_woord(woord)
        if woord_info is None:
            woord_info = {}

        bestaand_in_bron = woord_info.get(bron)
        aantal = bestaand_in_bron["aantal_keer_genoemd"] + 1 if bestaand_in_bron else 1

        woord_info[bron] = {
            "sentiment": sentiment,
            "datum": datetime.now().strftime("%Y-%m-%d"),
            "aantal_keer_genoemd": aantal,
        }

        actief_sentiment = self._bepaal_actief_sentiment(woord_info)

        conflict = (
            "expliciet" in woord_info and "automatisch" in woord_info
            and woord_info["expliciet"]["sentiment"] != woord_info["automatisch"]["sentiment"]
        )

        # Woord eerst overal weghalen (kan in de andere categorie staan
        # van vóór deze wijziging), dan opnieuw plaatsen onder de
        # categorie die bij het actieve sentiment hoort.
        for categorie in ("voorkeuren", "afkeuren"):
            self.data[categorie].pop(woord, None)

        # "voorkeuren" is de thuis voor zowel positief als
        # neutraal_gemengd -- enkel een uitgesproken negatief sentiment
        # komt in afkeuren terecht (ontwerpgesprek 26 juli 2026, optie B).
        doel_categorie = "afkeuren" if actief_sentiment == "negatief" else "voorkeuren"
        self.data[doel_categorie][woord] = woord_info
        self._opslaan()

        if conflict:
            dbg(f"{C_YELLOW}'{woord}': conflict tussen expliciet en automatisch "
                f"-- expliciet ({woord_info['expliciet']['sentiment']}) wint{C_RESET}")
        else:
            dbg(f"{C_GREEN}'{woord}' → {sentiment} ({bron}, x{aantal}){C_RESET}")

        if self.event_bus:
            self.event_bus.publish("preference_learned", {
                "woord": woord,
                "sentiment": sentiment,
                "bron": bron,
                "aantal_keer_genoemd": aantal,
                "actief_sentiment": actief_sentiment,
                "conflict": conflict,
            })

    def remove_preference(self, woord, bron=None):
        """
        Verwijdert een woord.

        Argumenten:
            woord: het te verwijderen woord.
            bron: indien opgegeven ("expliciet" of "automatisch"),
                  wordt ENKEL dat sub-blok verwijderd -- blijft het
                  woord over met enkel de andere bron, dan blijft het
                  gewoon bestaan onder dat sentiment. Indien None
                  (default), wordt het woord volledig verwijderd,
                  ongeacht hoeveel bronnen het heeft. Dit is de
                  bestaande 'vergeet: <woord>'-flow uit Fase 2, die
                  geen onderscheid maakt.

        Geeft True terug als er iets verwijderd werd, False als het
        woord (of die specifieke bron ervan) niet gevonden werd.
        """
        woord = woord.strip().lower()
        categorie, woord_info = self._vind_woord(woord)

        if woord_info is None:
            dbg(f"'{woord}' niet gevonden, niets te verwijderen")
            return False

        if bron is None:
            # Volledig verwijderen, ongeacht bronnen.
            del self.data[categorie][woord]
            self._opslaan()
            dbg(f"{C_GREEN}'{woord}' volledig verwijderd uit {categorie}{C_RESET}")
            if self.event_bus:
                self.event_bus.publish("preference_forgotten", {"woord": woord, "bron": None})
            return True

        if bron not in woord_info:
            dbg(f"'{woord}' heeft geen '{bron}'-blok, niets te verwijderen")
            return False

        del woord_info[bron]

        if not woord_info:
            # Geen enkele bron meer over -- woord volledig weg.
            del self.data[categorie][woord]
        else:
            # Nog een bron over: mogelijk moet het woord van categorie
            # wisselen als het overblijvende sentiment anders is.
            nieuw_sentiment = self._bepaal_actief_sentiment(woord_info)
            del self.data[categorie][woord]
            # Zelfde regel als in add_preference(): enkel een
            # uitgesproken negatief sentiment gaat naar afkeuren.
            nieuwe_categorie = "afkeuren" if nieuw_sentiment == "negatief" else "voorkeuren"
            self.data[nieuwe_categorie][woord] = woord_info

        self._opslaan()
        dbg(f"{C_GREEN}'{woord}': '{bron}'-blok verwijderd{C_RESET}")
        if self.event_bus:
            self.event_bus.publish("preference_forgotten", {"woord": woord, "bron": bron})
        return True

    def get_preference(self, woord):
        """
        Zoekt een woord op.

        Geeft terug: een dict met:
            - "sentiment": het ACTIEVE sentiment (expliciet wint bij
              conflict)
            - "categorie": "voorkeuren" of "afkeuren"
            - "conflict": True/False -- had expliciet en automatisch
              een verschillend sentiment?
            - "expliciet": het expliciete sub-blok, of None als dat niet
              bestaat
            - "automatisch": het automatische sub-blok, of None als dat
              niet bestaat
        Of None als het woord nergens gevonden werd.
        """
        woord = woord.strip().lower()
        categorie, woord_info = self._vind_woord(woord)

        if woord_info is None:
            return None

        expliciet = woord_info.get("expliciet")
        automatisch = woord_info.get("automatisch")
        conflict = (
            expliciet is not None and automatisch is not None
            and expliciet["sentiment"] != automatisch["sentiment"]
        )

        return {
            "sentiment": self._bepaal_actief_sentiment(woord_info),
            "categorie": categorie,
            "conflict": conflict,
            "expliciet": expliciet,
            "automatisch": automatisch,
        }

    def get_all_preferences(self):
        """
        Geeft het volledige, ruwe profiel terug: {"voorkeuren": {...},
        "afkeuren": {...}}, met per woord de volledige expliciet/
        automatisch-substructuur. Geeft een kopie terug, geen referentie
        naar de interne data.
        """
        return {
            "voorkeuren": dict(self.data["voorkeuren"]),
            "afkeuren": dict(self.data["afkeuren"]),
        }

    # -----------------------------------------------------------
    # Sense-voorkeuren (Bug #10-fix, 26 juli 2026)
    # -----------------------------------------------------------
    def set_sense_voorkeur(self, woord, sense_id):
        """
        Legt vast welke sense Kevin meestal bedoelt bij een meerduidig
        woord, bv. set_sense_voorkeur("python", "python#2") als Kevin
        met "python" meestal de slang bedoelt, niet de programmeertaal.

        Dit is ALTIJD een expliciete, handmatige keuze (bv. via een
        commando als "onthoud dat ik met python meestal de slang
        bedoel") -- er is bewust GEEN automatische telling/leren
        gebouwd, want dat zou een probleem oplossen dat grotendeels al
        opgelost is door semantic.py's detect_sense() (die per zin al
        de juiste sense herkent via signaalwoorden). Deze voorkeur is
        enkel het vangnet voor de zeldzame, contextloze gevallen waar
        detect_sense() zelf niets kan vinden.

        Overschrijft gewoon een eerder ingestelde voorkeur voor
        hetzelfde woord, zonder waarschuwing -- de nieuwste keuze van
        Kevin geldt altijd.
        """
        woord = woord.strip().lower()
        self.data["sense_voorkeuren"][woord] = sense_id
        self._opslaan()
        dbg(f"{C_GREEN}sense-voorkeur ingesteld: {woord} -> {sense_id}{C_RESET}")

    def get_sense_voorkeur(self, woord):
        """
        Geeft de opgeslagen sense-voorkeur voor een woord terug (bv.
        "python#2"), of None als er nog geen voorkeur is ingesteld.
        """
        woord = woord.strip().lower()
        return self.data["sense_voorkeuren"].get(woord)

    def get_by_sentiment(self, sentiment):
        """
        Geeft een lijst van woorden terug met het gevraagde ACTIEVE
        sentiment (na conflictregel).

        Argumenten:
            sentiment: "positief", "negatief", of "neutraal_gemengd".

        Geeft terug: lijst van woorden (str). Let op: "positief" en
        "neutraal_gemengd" staan beide fysiek in de "voorkeuren"-
        categorie (zie add_preference()) -- dit filtert dus WEL
        correct op het exacte sentiment-veld per woord, niet enkel op
        de categorie waarin het woord toevallig staat.
        """
        if sentiment == "negatief":
            bron_categorie = "afkeuren"
        else:
            bron_categorie = "voorkeuren"

        resultaat = []
        for woord, info in self.data[bron_categorie].items():
            if self._bepaal_actief_sentiment(info) == sentiment:
                resultaat.append(woord)
        return resultaat


def init_module(event_bus, semantic_module=None):
    """
    Standaard module_loader.py-conventie.
    """
    profile = KevinProfile(event_bus)
    event_bus.publish("module_loaded", {"name": "kevin_profile"})
    return profile