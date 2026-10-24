"""Tests voor punt 29: de tone-pipeline mag een "?" nooit in een "!" veranderen."""
import pytest

from modules.chat.expression_injector import ExpressionInjector


class NepEventBus:
    """Houdt bij wat er gepubliceerd wordt, zonder echte EventBus."""

    def __init__(self):
        self.gepubliceerd = []

    def subscribe(self, naam, handler):
        pass

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))


def injecteer(text, tone=None, personality=None, response_style="normaal"):
    bus = NepEventBus()
    inj = ExpressionInjector(bus)
    inj.on_expression_inject({
        "text": text,
        "tone": tone or {},
        "personality": personality or {},
        "emotion": {},
        "response_style": response_style,
    })
    naam, data = bus.gepubliceerd[-1]
    assert naam == "chat_response"
    return data["text"]


# ---------- de hulpfunctie zelf ----------

@pytest.mark.parametrize("invoer, verwacht", [
    ("Toevallig?", "Toevallig?"),          # vraag blijft vraag
    ("Echt?!", "Echt?!"),                  # al een uitroep
    ("Wat zeg je??", "Wat zeg je??"),
    ("Klaar!", "Klaar!"),
    ("Klaar.", "Klaar!"),                  # gewone punt wordt wel een uitroep
    ("Klaar", "Klaar!"),
    ("Klaar. ", "Klaar!"),
    ("Hmm...", "Hmm..."),                  # aarzeling blijft aarzeling
    ("Hmm…", "Hmm…"),
    ("Hoi. Hoe gaat het?", "Hoi. Hoe gaat het?"),
    ("Toevallig? ", "Toevallig? "),        # spatie erachter, nog steeds een vraag
    ("", ""),                              # lege tekst blijft leeg
])
def test_maak_uitroep(invoer, verwacht):
    assert ExpressionInjector._maak_uitroep(invoer) == verwacht


# ---------- de drie plekken waar het misging ----------

def test_hoge_expressiveness_laat_vraag_staan():
    assert injecteer("Toevallig?", tone={"expressiveness": 0.95}) == "Toevallig?"


def test_hoge_expressiveness_zet_wel_uitroep_na_punt():
    assert injecteer("Dat is leuk.", tone={"expressiveness": 0.95}) == "Dat is leuk!"


def test_interrupts_laat_vraag_staan():
    p = {"interrupts": True}
    assert injecteer("Toevallig?", tone={"expressiveness": 0.7}, personality=p) == "Toevallig?"


def test_interrupts_zet_wel_uitroep_na_punt():
    p = {"interrupts": True}
    assert injecteer("Dat is leuk.", tone={"expressiveness": 0.7}, personality=p) == "Dat is leuk!"


def test_dramatic_laat_vraag_staan():
    assert injecteer("Toevallig?", personality={"dramatic": True}) == "Toevallig?"


def test_dramatic_zet_wel_uitroep_na_punt():
    assert injecteer("Dat is leuk.", personality={"dramatic": True}) == "Dat is leuk!"


def test_dramatic_laat_aarzeling_staan():
    assert injecteer("Hmm...", personality={"dramatic": True}) == "Hmm..."


# ---------- bestaand gedrag mag niet veranderen ----------

def test_kort_haalt_uitroep_weg_maar_laat_vraag_staan():
    assert injecteer("Wow!", response_style="kort") == "Wow"
    assert injecteer("Toevallig?", response_style="kort") == "Toevallig?"


def test_dramatic_negeert_kort():
    assert injecteer("Dat is leuk.", personality={"dramatic": True}, response_style="kort") == "Dat is leuk."


def test_lage_expressiveness_haalt_uitroep_weg():
    assert injecteer("Dat is leuk!", tone={"expressiveness": 0.1}) == "Dat is leuk"


def test_emoji_komt_nog_steeds_achteraan():
    tone = {"expressiveness": 0.95, "emoji_style": ["🙂"]}
    assert injecteer("Toevallig?", tone=tone) == "Toevallig? 🙂"