# modules/chat/fallback_reflectie.py
"""
Laag: patroon-gebaseerde zin-reflectie bij fallback (geen LLM, puur
symbolisch -- zelfde soort mechanisme als het historische ELIZA-
programma uit 1966: decompositie + reassemblage + voornaamwoord-
omkering, hier toegepast op Nederlandse tekst).

BELANGRIJK OM EERLIJK TE BLIJVEN: dit "begrijpt" niets. Het herkent
een zinsvorm (bv. "ik ben moe") via een vast patroon, haalt er een
stuk tekst uit, keert voornaamwoorden om, en plakt het in een al
bestaande sjabloonzin. Er wordt nergens betekenis afgeleid of nieuwe
tekst gegenereerd -- exact zoals response_engine.py en
conversation_engine.py dat ook nooit doen.

Wordt NIET zelf op "intent_fallback" geabonneerd -- zelfde reden als
conversation_engine.py: dat zou een TWEEDE, apart antwoord opleveren
naast response_pipeline.py's on_fallback(). In plaats daarvan roept
on_fallback() de publieke methode reflecteer() hier rechtstreeks aan,
NA conversation_engine.py's twee observatie-pogingen en VOOR de kale
sjabloon-fallback.

PATRONEN ZITTEN IN DATA, NIET IN CODE (data/fallback_reflectie_
patronen.json) -- nieuwe patronen/keywords toevoegen betekent dus
enkel dat JSON-bestand bewerken, geen wijziging aan dit bestand.
Zelfde filosofie als identity/blueprint/identity.json, traits.json,
enz. Ontbreekt het bestand of is het corrupt, dan valt deze module
terug op LEGE patronenlijsten (dus reflecteer() geeft dan altijd
None terug, en on_fallback() valt gewoon door naar zijn kale
sjabloon-fallback) -- nooit een crash, zelfde defensieve aanpak als
overal elders in Nova bij ontbrekende data.

TWEE LAGEN, IN VOLGORDE (robuustste opzet -- beide vangen andere
gevallen op):
  1. Decompositie: herkent een VASTE ZINSVORM (bv. "ik ben *") en
     herformuleert die vorm. Specifiek, dus geraakt niet elke zin.
  2. Keyword-reflectie: als geen enkele zinsvorm matchte, wordt de
     zin op losse bekende woorden gescand (bv. "moe", "druk") --
     breder vangnet voor zinnen die niet in een vaste vorm passen.
Matcht geen van beide, dan geeft reflecteer() None terug en valt
on_fallback() terug op zijn kale, generieke sjabloon-lijst.
"""

import json
import re
from typing import Optional

from modules.paths import get_project_root
from modules.response_learning.variant_kiezer import kies_variant


class FallbackReflectie:

    DATA_BESTAND = "data/fallback_reflectie_patronen.json"

    # ------------------------------------------------------------
    # Voornaamwoord-omkering: nodig zodat "ik ben moe" grammaticaal
    # correct "je bent moe" wordt in plaats van "ik bent moe".
    # Toegepast op los-getokeniseerde woorden (niet 1 grote regex
    # over de hele string), om te voorkomen dat een omgekeerd woord
    # per ongeluk opnieuw matcht met een latere regel.
    # ------------------------------------------------------------
    OMKERING = {
        "ik": "je",
        "mij": "jou",
        "me": "je",
        "mijn": "jouw",
        "mezelf": "jezelf",
        "ben": "bent",
        "voel": "voelt",
        "heb": "hebt",
        "wil": "wilt",
        "denk": "denkt",
        "vind": "vindt",
        "moet": "moet",
        "kan": "kan",
        "ga": "gaat",
    }

    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.project_root = get_project_root(__file__)
        self.data_pad = self.project_root / self.DATA_BESTAND

        self._decompositie_patronen = []
        self._keyword_groepen = []
        self._laad_patronen()

    # ------------------------------------------------------------
    # Laden van data/fallback_reflectie_patronen.json.
    # Defensief: ontbrekend/corrupt bestand of een verkeerd
    # regex-patroon binnenin mag deze module NOOIT laten crashen --
    # in het slechtste geval blijven de lijsten leeg en geeft
    # reflecteer() dan altijd None terug (zelfde eindresultaat als
    # "geen match"), zodat on_fallback() gewoon zijn kale
    # sjabloon-fallback gebruikt.
    # ------------------------------------------------------------
    def _laad_patronen(self):
        if not self.data_pad.exists():
            print(
                f"[FALLBACK_REFLECTIE] WAARSCHUWING: {self.data_pad} "
                "niet gevonden -- reflectie-laag blijft uitgeschakeld "
                "(geen patronen geladen)."
            )
            return

        try:
            with open(self.data_pad, "r", encoding="utf-8") as f:
                ruwe_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(
                f"[FALLBACK_REFLECTIE] WAARSCHUWING: kon "
                f"{self.data_pad} niet lezen ({e}) -- reflectie-laag "
                "blijft uitgeschakeld."
            )
            return

        for entry in ruwe_data.get("decompositie", []):
            gecompileerd = self._compileer_decompositie_entry(entry)
            if gecompileerd is not None:
                self._decompositie_patronen.append(gecompileerd)

        for entry in ruwe_data.get("keywords", []):
            gecontroleerd = self._controleer_keyword_entry(entry)
            if gecontroleerd is not None:
                self._keyword_groepen.append(gecontroleerd)

    def _compileer_decompositie_entry(self, entry):
        """
        Geeft (gecompileerde_regex, sjabloon_naam, varianten) terug,
        of None als deze ENE entry ongeldig is -- een fout in 1
        patroon mag de andere, wel geldige patronen niet blokkeren.
        """
        patroon = entry.get("patroon")
        sjabloon_naam = entry.get("sjabloon_naam")
        varianten = entry.get("varianten")

        if not patroon or not sjabloon_naam or not varianten:
            print(
                f"[FALLBACK_REFLECTIE] WAARSCHUWING: entry "
                f"overgeslagen, ontbrekend veld: {entry}"
            )
            return None

        try:
            gecompileerd = re.compile(patroon)
        except re.error as e:
            print(
                f"[FALLBACK_REFLECTIE] WAARSCHUWING: ongeldig regex-"
                f"patroon overgeslagen ({sjabloon_naam}): {e}"
            )
            return None

        return (gecompileerd, sjabloon_naam, varianten)

    def _controleer_keyword_entry(self, entry):
        """
        Geeft (set_trefwoorden, sjabloon_naam, varianten) terug, of
        None als deze ENE entry ongeldig is. Trefwoorden worden hier
        al naar kleine letters genormaliseerd, zodat _probeer_
        keyword_reflectie() dat niet telkens opnieuw hoeft te doen.
        """
        trefwoorden = entry.get("trefwoorden")
        sjabloon_naam = entry.get("sjabloon_naam")
        varianten = entry.get("varianten")

        if not trefwoorden or not sjabloon_naam or not varianten:
            print(
                f"[FALLBACK_REFLECTIE] WAARSCHUWING: keyword-entry "
                f"overgeslagen, ontbrekend veld: {entry}"
            )
            return None

        trefwoorden_set = {w.lower() for w in trefwoorden}
        return (trefwoorden_set, sjabloon_naam, varianten)

    # ------------------------------------------------------------
    def _keer_om(self, tekst: str) -> str:
        woorden = tekst.split()
        omgekeerd = []
        for woord in woorden:
            kaal = woord.strip(".,!?;:")
            vervanging = self.OMKERING.get(kaal.lower())
            if vervanging is not None:
                omgekeerd.append(vervanging)
            else:
                omgekeerd.append(woord)
        return " ".join(omgekeerd)

    # ------------------------------------------------------------
    def _probeer_decompositie(self, tekst_klein: str) -> Optional[str]:
        for gecompileerd, sjabloon_naam, varianten in self._decompositie_patronen:
            match = gecompileerd.search(tekst_klein)
            if not match:
                continue

            # Generiek voor 1 OF MEER vanggroepen -- een patroon als
            # "had ik (.+?) moeten (.+)" heeft er 2 ({1} en {2}), de
            # meeste andere patronen hebben er 1. Elke groep apart
            # opschonen/omkeren; als ÉÉN groep leeg is, telt de hele
            # match niet (voorkomt een kapotte "...had je moeten ?").
            groepen = match.groups()
            opgevangen_lijst = []
            for groep in groepen:
                schoon = (groep or "").strip().rstrip(".,!?;:")
                if not schoon:
                    opgevangen_lijst = []
                    break
                opgevangen_lijst.append(self._keer_om(schoon))

            if not opgevangen_lijst:
                continue

            variant_logger = self.event_bus.modules.get("variant_feedback_logger")
            sjabloon = kies_variant(
                varianten=varianten,
                sjabloon_naam=sjabloon_naam,
                event_bus=self.event_bus,
                variant_feedback_logger=variant_logger,
            )
            # sjabloon.format(...) vult {1}/{2}/... in als POSITIONEEL
            # argument (index in de args-tuple) -- {1} is GEEN geldige
            # keyword, dus **{"1": ...} zou een IndexError geven. Een
            # lege placeholder op index 0 zorgt dat {1} altijd op de
            # EERSTE groep wijst, {2} op de tweede, enz. -- ongeacht
            # hoeveel groepen dit specifieke patroon heeft.
            try:
                return sjabloon.format("", *opgevangen_lijst)
            except (IndexError, KeyError):
                # Een sjabloon die een {N} gebruikt die dit patroon
                # niet heeft (bv. door een tikfout in de data) mag
                # nooit de hele reflectie-laag laten crashen -- dan
                # gewoon deze match overslaan i.p.v. de rest van de
                # pipeline te breken.
                continue

        return None

    # ------------------------------------------------------------
    def _probeer_keyword_reflectie(self, tekst_klein: str) -> Optional[str]:
        woorden = {w.strip(".,!?;:") for w in tekst_klein.split()}

        for trefwoorden, sjabloon_naam, varianten in self._keyword_groepen:
            if woorden & trefwoorden:
                variant_logger = self.event_bus.modules.get("variant_feedback_logger")
                return kies_variant(
                    varianten=varianten,
                    sjabloon_naam=sjabloon_naam,
                    event_bus=self.event_bus,
                    variant_feedback_logger=variant_logger,
                )

        return None

    # ------------------------------------------------------------
    # Publieke methode -- wordt rechtstreeks aangeroepen door
    # response_pipeline.py's on_fallback(), NA conversation_engine.py's
    # twee observatie-pogingen en VOOR de kale sjabloon-fallback.
    # Geeft tekst terug, of None als geen van beide lagen iets vond
    # (inclusief als er helemaal geen patronen geladen konden worden).
    # ------------------------------------------------------------
    def reflecteer(self, tekst: str) -> Optional[str]:
        if not tekst:
            return None

        tekst_klein = tekst.lower().strip()

        resultaat = self._probeer_decompositie(tekst_klein)
        if resultaat is not None:
            return resultaat

        return self._probeer_keyword_reflectie(tekst_klein)


def init_module(event_bus, semantic_module=None):
    return FallbackReflectie(event_bus, semantic_module)