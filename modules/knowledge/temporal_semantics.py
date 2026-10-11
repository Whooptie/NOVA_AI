# modules/knowledge/temporal_semantics.py
#
# Semantic Fase 9 -- Temporal Semantics.
#   9.1: het ontstaansjaar van een woord ("python bestaat sinds 1991").
#   9.2: periodes per woord ("python was van 1991 tot 2005 een niche"),
#        "wat was python in 2003", "tijdlijn van python",
#        "wis de periodes van python".
#
# Puur symbolisch: Kevin leert Nova jaartallen en periodes, Nova bewaart ze
# bij de sense van het woord (zie SenseEngine.set_ontstaan / add_periode) en
# zoekt ze op. Geen voorspellingen, geen schattingen.
#
# Luistert op de events die intent_router.detect_temporal() publiceert:
#   intent_temporal_leer           {"word", "jaar"}
#   intent_temporal_query          {"word", "vorm"}   (vorm = "wanneer" of "hoelang")
#   intent_temporal_periode_leer   {"word", "van", "tot" (None = tot nu), "label"}
#   intent_temporal_periode_query  {"word", "jaar"}
#   intent_temporal_tijdlijn       {"word"}
#   intent_temporal_periodes_wis   {"word"}
#   intent_temporal_omgekeerd      {"vorm", "van", "tot", "jaar"}   (9.3)
# Korte antwoorden gaan via layer4_response (tone-pipeline); de tijdlijn is een
# lijst en gaat, net als concept_overview.py, rechtstreeks via chat_response.

from datetime import datetime


def _huidig_jaar():
    return datetime.now().year


class TemporalSemantics:
    def __init__(self, event_bus, sem):
        self.event_bus = event_bus
        self.sem = sem
        event_bus.subscribe("intent_temporal_leer", self.on_leer)
        event_bus.subscribe("intent_temporal_query", self.on_query)
        event_bus.subscribe("intent_temporal_periode_leer", self.on_periode_leer)
        event_bus.subscribe("intent_temporal_periode_query", self.on_periode_query)
        event_bus.subscribe("intent_temporal_tijdlijn", self.on_tijdlijn)
        event_bus.subscribe("intent_temporal_periodes_wis", self.on_periodes_wis)
        event_bus.subscribe("intent_temporal_omgekeerd", self.on_omgekeerd)
        event_bus.publish("module_loaded", {"name": "temporal_semantics"})

    # ---------- hulpjes ----------
    def _zeg(self, tekst):
        self.event_bus.publish("layer4_response", {"text": tekst})

    def _toon_lijst(self, tekst):
        self.event_bus.publish("chat_response", {"source": "temporal_semantics", "text": tekst})

    @staticmethod
    def _hoofdletter(woord):
        return woord[:1].upper() + woord[1:]

    @staticmethod
    def _periode_zin(naam, p):
        """'Python was van 1991 tot 2005 een niche' / 'Python is sinds 2010 dominant'."""
        if p.get("tot") is None:
            return f"{naam} is sinds {p['van']} {p['label']}"
        return f"{naam} was van {p['van']} tot {p['tot']} {p['label']}"

    # ---------- 9.1: ontstaansjaar ----------
    def on_leer(self, data, event_type=None):
        woord = data.get("word", "").strip()
        jaar = data.get("jaar")
        if not woord or jaar is None:
            return

        resultaat = self.sem.set_ontstaan(woord, jaar, source="user")
        if resultaat.get("blocked"):
            self._zeg(f"Dat kan ik niet opslaan: alle betekenissen van '{woord}' zijn afgewezen.")
            return

        naam = self._hoofdletter(woord)
        oud = resultaat.get("oud")
        if oud is None:
            self._zeg(f"Genoteerd: {naam} bestaat sinds {jaar}.")
        elif oud == jaar:
            self._zeg(f"Dat wist ik al: {naam} bestaat sinds {jaar}.")
        else:
            self._zeg(f"Aangepast: ik had {oud} genoteerd, nu staat {naam} op {jaar}.")

    def on_query(self, data, event_type=None):
        woord = data.get("word", "").strip()
        vorm = data.get("vorm", "wanneer")
        if not woord:
            return

        info = self.sem.get_ontstaan(woord)
        naam = self._hoofdletter(woord)
        if not info:
            self._zeg(
                f"Ik weet nog niet wanneer {woord} ontstond. "
                f"Je kunt het me leren, bijvoorbeeld: '{woord} bestaat sinds 1991'."
            )
            return

        jaar = info["jaar"]
        extra = "" if info.get("status") == "confirmed" else " (nog niet bevestigd)"

        if vorm == "hoelang":
            verschil = _huidig_jaar() - jaar
            if verschil <= 0:
                tekst = f"{naam} bestaat sinds dit jaar ({jaar})."
            elif verschil == 1:
                tekst = f"{naam} bestaat al 1 jaar (sinds {jaar})."
            else:
                tekst = f"{naam} bestaat al {verschil} jaar (sinds {jaar})."
        else:
            tekst = f"{naam} bestaat sinds {jaar}."
        self._zeg(tekst + extra)

    # ---------- 9.2: periodes ----------
    def on_periode_leer(self, data, event_type=None):
        woord = data.get("word", "").strip()
        van = data.get("van")
        tot = data.get("tot")
        label = data.get("label", "").strip()
        if not woord or van is None or not label:
            return

        naam = self._hoofdletter(woord)
        r = self.sem.add_periode(woord, van, tot, label, source="user")

        if r.get("ok"):
            self._zeg(f"Genoteerd: {self._periode_zin(naam, r['periode'])}.")
        elif r.get("bestaat"):
            self._zeg(f"Dat wist ik al: {self._periode_zin(naam, r['periode'])}.")
        elif r.get("gesloten"):
            self._zeg(f"Afgesloten: {self._periode_zin(naam, r['periode'])}.")
        elif r.get("conflict"):
            self._zeg(
                f"Dat botst met wat ik al weet: {self._periode_zin(naam, r['conflict'])}. "
                f"Wil je iets corrigeren? Zeg dan 'wis de periodes van {woord}' en leer ze opnieuw."
            )
        elif r.get("voor_ontstaan"):
            self._zeg(
                f"Dat kan niet: {woord} ontstond pas in {r['voor_ontstaan']}, "
                f"een periode vanaf {van} klopt dus niet."
            )
        else:
            self._zeg(f"Dat kan ik niet opslaan ({r.get('fout', 'onbekende reden')}).")

    def on_periode_query(self, data, event_type=None):
        woord = data.get("word", "").strip()
        jaar = data.get("jaar")
        if not woord or jaar is None:
            return

        naam = self._hoofdletter(woord)
        ontstaan = self.sem.get_ontstaan(woord)
        periode = self.sem.get_periode_in(woord, jaar)

        if periode:
            self._zeg(f"In {jaar} was {naam} {periode['label']}.")
        elif ontstaan and jaar < ontstaan["jaar"]:
            self._zeg(f"In {jaar} bestond {woord} nog niet (het ontstond in {ontstaan['jaar']}).")
        elif ontstaan:
            self._zeg(
                f"Ik weet niet wat {woord} in {jaar} was; "
                f"wel dat het bestaat sinds {ontstaan['jaar']}."
            )
        else:
            self._zeg(
                f"Ik weet niet wat {woord} in {jaar} was. Je kunt het me leren, bijvoorbeeld: "
                f"'{woord} was van 1991 tot 2005 een niche'."
            )

    def on_tijdlijn(self, data, event_type=None):
        woord = data.get("word", "").strip()
        if not woord:
            return

        naam = self._hoofdletter(woord)
        ontstaan = self.sem.get_ontstaan(woord)
        periodes = self.sem.get_periodes(woord)

        if not ontstaan and not periodes:
            self._zeg(
                f"Ik heb nog geen tijdlijn voor {woord}. Leer me bijvoorbeeld "
                f"'{woord} bestaat sinds 1991' of '{woord} was van 1991 tot 2005 een niche'."
            )
            return

        regels = []
        if ontstaan:
            regels.append((ontstaan["jaar"], 0, f"- {ontstaan['jaar']}: ontstaan"))
        for p in periodes:
            if p.get("tot") is None:
                tekst = f"- sinds {p['van']}: {p['label']}"
            else:
                tekst = f"- {p['van']}-{p['tot']}: {p['label']}"
            regels.append((p["van"], 1, tekst))
        regels.sort(key=lambda r: (r[0], r[1]))

        self._toon_lijst(f"Tijdlijn van {naam}:\n" + "\n".join(r[2] for r in regels))

    def on_periodes_wis(self, data, event_type=None):
        woord = data.get("word", "").strip()
        if not woord:
            return

        aantal = self.sem.clear_periodes(woord, source="user")
        if aantal == 0:
            self._zeg(f"Ik had geen periodes van {woord} om te wissen.")
        elif aantal == 1:
            self._zeg(f"Gewist: 1 periode van {woord}. Het ontstaansjaar blijft staan.")
        else:
            self._zeg(f"Gewist: {aantal} periodes van {woord}. Het ontstaansjaar blijft staan.")

    # ---------- 9.3: omgekeerd ----------
    MAX_REGELS = 20

    def on_omgekeerd(self, data, event_type=None):
        vorm = data.get("vorm")
        van = data.get("van")
        tot = data.get("tot")
        jaar = data.get("jaar")
        if vorm is None:
            return

        alle = self.sem.get_all_ontstaan()
        gevonden = [
            r for r in alle
            if (van is None or r["jaar"] >= van) and (tot is None or r["jaar"] <= tot)
        ]
        aantal_bekend = len(alle)

        if vorm == "bestond":
            kop = f"Dit bestond al in {jaar} (voor zover ik weet):"
            leeg = f"Ik ken geen woorden waarvan ik weet dat ze in {jaar} al bestonden"
        elif vorm == "exact":
            kop = f"Dit ontstond in {jaar} (voor zover ik weet):"
            leeg = f"Ik ken geen woord dat in {jaar} ontstond"
        elif vorm == "tussen":
            kop = f"Dit ontstond tussen {van} en {tot} (voor zover ik weet):"
            leeg = f"Ik ken geen woord dat tussen {van} en {tot} ontstond"
        elif vorm == "voor":
            kop = f"Dit ontstond voor {jaar} (voor zover ik weet):"
            leeg = f"Ik ken geen woord dat voor {jaar} ontstond"
        else:
            kop = f"Dit ontstond na {jaar} (voor zover ik weet):"
            leeg = f"Ik ken geen woord dat na {jaar} ontstond"

        if not gevonden:
            if aantal_bekend == 0:
                self._zeg(
                    f"{leeg}. Ik ken nog van geen enkel woord een jaartal; "
                    f"leer me bijvoorbeeld 'python bestaat sinds 1991'."
                )
            else:
                self._zeg(
                    f"{leeg}. Dat zegt niets over wat er echt bestond: "
                    f"ik ken maar van {aantal_bekend} woorden een jaartal."
                )
            return

        regels = [f"- {r['word']} ({r['jaar']})" for r in gevonden[:self.MAX_REGELS]]
        if len(gevonden) > self.MAX_REGELS:
            regels.append(f"- ... en nog {len(gevonden) - self.MAX_REGELS} meer")
        self._toon_lijst(kop + "\n" + "\n".join(regels))


def init_module(event_bus, sem):
    return TemporalSemantics(event_bus, sem)