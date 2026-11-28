# tests/test_kleding.py
import copy

import pytest

from core import clock
from core.state_store import StateStore
from modules.body.kleding import Kleding, _valideer
from modules.body.kleding_tekst import KOUD

DATA = {
    "items": {
        "hoodie": {"laag": 1, "demping": 0.20, "groep": None},
        "shirt": {"laag": 2, "demping": 0.10, "groep": "bovenkant"},
        "topje": {"laag": 2, "demping": 0.08, "groep": "bovenkant"},
        "short": {"laag": 1, "demping": 0.15, "groep": None},
    },
    "toestanden": ["aan", "los", "verschoven", "uit"],
    "start": {
        "wakker": {"hoodie": "uit", "shirt": "aan", "topje": "uit", "short": "aan"},
        "slapen": {"hoodie": "uit", "shirt": "aan", "topje": "uit", "short": "uit"},
    },
    "regels": {
        "los_zet_demping_op_nul": True,
        "volgorde_breken": "weiger",
        "comfort_zone_meenemen": False,
        "bekeken_bonus": 0.10,
        "initiatief": "temperatuur",
    },
    "zones": {
        "torso": ["hoodie", "shirt"],
        "nek": ["hoodie"],
        "schouders": ["hoodie"],
        "rug": ["hoodie"],
        "buik": ["shirt"],
        "borst_links": ["shirt", "topje"],
        "tepel_links": ["shirt", "topje"],
        "vulva": ["short"],
        "billen": ["short"],
        "benen": [],
    },
}


class NepBus:
    def __init__(self):
        self.events = []
        self.subs = {}
        self.modules = {}

    def subscribe(self, naam, fn):
        self.subs[naam] = fn

    def publish(self, naam, data=None):
        self.events.append((naam, data))

    def van(self, naam):
        return [d for n, d in self.events if n == naam]


class NepBekeken:
    def __init__(self, actief=False):
        self.actief = actief
        self.verhogingen = []

    def is_actief(self):
        return self.actief

    def verhoog(self, factor=1.0):
        self.verhogingen.append(factor)


@pytest.fixture
def k(tmp_path):
    fake = clock.FakeClock(80_000.0)
    clock.set_provider(fake)
    bus = NepBus()
    store = StateStore(tmp_path / "state.json")
    yield Kleding(bus, store=store, data=copy.deepcopy(DATA)), bus, store, fake
    clock.reset()


# ---------------- start en staat ----------------
def test_starttoestand(k):
    kl, _, _, _ = k
    assert kl.staat("shirt") == "aan"
    assert kl.staat("short") == "aan"
    assert kl.staat("hoodie") == "uit"
    assert kl.is_naakt() is False


def test_onbekend_item_doet_niets(k):
    kl, bus, _, _ = k
    assert kl.on_intent({"item": "jurk", "actie": "uit"}) is None
    assert not bus.van("body_reactie")


def test_onbekende_actie_doet_niets(k):
    kl, bus, _, _ = k
    assert kl.on_intent({"item": "shirt", "actie": "opengeknoopt"}) is None
    assert not bus.van("body_reactie")


def test_aan_terwijl_al_aan_doet_niets(k):
    kl, bus, _, _ = k
    assert kl.on_intent({"item": "shirt", "actie": "aan"}) is None
    assert not bus.van("body_reactie")


# ---------------- volgorde ----------------
def test_shirt_weigert_onder_een_hoodie(k):
    kl, bus, _, _ = k
    kl.on_intent({"item": "hoodie", "actie": "aan"})
    bus.events.clear()

    kl.on_intent({"item": "shirt", "actie": "uit"})

    assert kl.staat("shirt") == "aan"
    assert "hoodie" in bus.van("body_reactie")[0]["text"]


def test_hoodie_eerst_dan_shirt(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "hoodie", "actie": "aan"})
    kl.on_intent({"item": "hoodie", "actie": "uit"})
    kl.on_intent({"item": "shirt", "actie": "uit"})
    assert kl.staat("shirt") == "uit"


def test_verschoven_blokkeert_ook(k):
    kl, bus, _, _ = k
    kl.on_intent({"item": "hoodie", "actie": "aan"})
    kl.on_intent({"item": "hoodie", "actie": "verschoven"})
    bus.events.clear()

    kl.on_intent({"item": "shirt", "actie": "uit"})

    assert kl.staat("shirt") == "aan"
    assert bus.van("body_reactie")


def test_hoodie_zelf_wordt_niet_geblokkeerd(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "hoodie", "actie": "aan"})
    kl.on_intent({"item": "hoodie", "actie": "uit"})
    assert kl.staat("hoodie") == "uit"


# ---------------- groep ----------------
def test_topje_aan_zet_shirt_uit(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "topje", "actie": "aan"})
    assert kl.staat("topje") == "aan"
    assert kl.staat("shirt") == "uit"


def test_shirt_aan_zet_topje_uit(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "topje", "actie": "aan"})
    kl.on_intent({"item": "shirt", "actie": "aan"})
    assert kl.staat("shirt") == "aan"
    assert kl.staat("topje") == "uit"


# ---------------- demping ----------------
def test_demping_aan(k):
    kl, _, _, _ = k
    assert kl.demping("torso") == pytest.approx(0.10)


def test_demping_neemt_het_dikste_stuk(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "hoodie", "actie": "aan"})
    assert kl.demping("torso") == pytest.approx(0.20)


def test_demping_verschoven_halveert(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "hoodie", "actie": "aan"})
    kl.on_intent({"item": "hoodie", "actie": "verschoven"})
    assert kl.demping("torso") == pytest.approx(0.10)


def test_demping_uit_is_nul(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "short", "actie": "uit"})
    assert kl.demping("vulva") == 0.0


def test_los_zet_demping_op_nul(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "short", "actie": "los"})
    assert kl.staat("short") == "los"
    assert kl.demping("vulva") == 0.0


def test_los_op_shirt_wordt_verschoven(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "shirt", "actie": "los"})
    assert kl.staat("shirt") == "verschoven"


def test_zone_zonder_kleding_heeft_geen_bonus(k):
    kl, _, _, _ = k
    assert kl.demping("benen") == 0.0
    assert kl.drempel_bonus("benen") == 0.0


def test_bonus_bij_bedekte_zone(k):
    kl, _, _, _ = k
    assert kl.drempel_bonus("vulva") > 0


# ---------------- koud ----------------
def test_koud_alleen_als_het_koud_is(k):
    kl, bus, store, _ = k
    store.registreer("gesteldheid", {"temperatuur": 10.0})
    kl._state["koud"] = 0.5

    kl.on_intent({"item": "short", "actie": "uit"})

    assert kl.koud() > 0.5
    assert len(bus.van("body_reactie")[0]["text"]) > len("…uit dan.")


def test_geen_koud_in_de_warmte(k):
    kl, _, store, _ = k
    store.registreer("gesteldheid", {"temperatuur": 24.0})
    kl.on_intent({"item": "short", "actie": "uit"})
    assert kl.koud() == 0.0


def test_zonder_gesteldheid_geen_koud(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "short", "actie": "uit"})
    assert kl.koud() == 0.0


def test_koud_zakt_met_de_tijd(k):
    kl, _, _, fake = k
    kl._state["koud"] = 0.9
    fake.advance(600)
    assert kl.koud() == pytest.approx(0.6)


def test_koud_publiceert_maar_een_keer(k):
    kl, bus, store, _ = k
    store.registreer("gesteldheid", {"temperatuur": 5.0})
    kl._state["koud"] = 0.55
    bus.events.clear()

    kl.on_intent({"item": "short", "actie": "uit"})
    kl._state["koud"] = 0.58
    kl.on_intent({"item": "shirt", "actie": "verschoven"})

    teksten = [d["text"] for d in bus.van("body_reactie")]
    assert sum(any(koud in t for koud in KOUD) for t in teksten) == 1


# ---------------- bekeken ----------------
def test_bekeken_bonus_bij_los(k):
    kl, bus, _, _ = k
    nep = NepBekeken(actief=True)
    bus.modules["bekeken"] = nep

    kl.on_intent({"item": "short", "actie": "los"})

    assert nep.verhogingen


def test_geen_bonus_als_bekeken_niet_actief_is(k):
    kl, bus, _, _ = k
    nep = NepBekeken(actief=False)
    bus.modules["bekeken"] = nep

    kl.on_intent({"item": "short", "actie": "los"})

    assert not nep.verhogingen


def test_geen_bonus_bij_verschoven(k):
    kl, bus, _, _ = k
    nep = NepBekeken(actief=True)
    bus.modules["bekeken"] = nep

    kl.on_intent({"item": "shirt", "actie": "verschoven"})

    assert not nep.verhogingen


# ---------------- slapen ----------------
def test_slapen_trekt_hoodie_topje_en_short_uit(k):
    kl, _, _, _ = k
    kl.on_intent({"item": "hoodie", "actie": "aan"})
    kl.naar_bed()
    assert kl.staat("hoodie") == "uit"
    assert kl.staat("topje") == "uit"
    assert kl.staat("short") == "uit"
    assert kl.staat("shirt") == "aan"


def test_wakker_worden_zet_alles_terug(k):
    kl, _, _, _ = k
    kl.naar_bed()
    kl.wakker_worden()
    assert kl.staat("short") == "aan"
    assert kl.staat("hoodie") == "uit"


# ---------------- uitgang en herstart ----------------
def test_tekst_wordt_gepubliceerd_met_bron_en_zone(k):
    kl, bus, _, _ = k
    kl.on_intent({"item": "short", "actie": "uit"})
    data = bus.van("body_reactie")[0]
    assert data["bron"] == "kleding"
    assert data["zone"] == "vulva"
    assert data["text"]


def test_kleding_changed_wordt_gepubliceerd(k):
    kl, bus, _, _ = k
    kl.on_intent({"item": "short", "actie": "uit"})
    assert bus.van("kleding_changed")[-1]["items"]["short"] == "uit"


def test_snapshot_is_een_kopie(k):
    kl, _, _, _ = k
    snap = kl.snapshot()
    snap["items"]["short"] = "uit"
    assert kl.staat("short") == "aan"


def test_staat_overleeft_herstart(k, tmp_path):
    kl, _, store, _ = k
    kl.on_intent({"item": "hoodie", "actie": "aan"})
    store.flush(True)

    kl2 = Kleding(NepBus(), store=StateStore(tmp_path / "state.json"), data=copy.deepcopy(DATA))

    assert kl2.staat("hoodie") == "aan"


def test_standaardstanden_overschrijven_niets(k, tmp_path):
    kl, _, store, _ = k
    kl.naar_bed()
    store.flush(True)

    kl2 = Kleding(NepBus(), store=StateStore(tmp_path / "state.json"), data=copy.deepcopy(DATA))

    assert kl2.staat("short") == "uit"


# ---------------- validatie ----------------
def test_onbekend_item_in_zone_faalt():
    data = copy.deepcopy(DATA)
    data["zones"]["benen"] = ["broek"]
    with pytest.raises(ValueError):
        _valideer(data)


def test_ongeldige_startstaat_faalt():
    data = copy.deepcopy(DATA)
    data["start"]["wakker"]["shirt"] = "half"
    with pytest.raises(ValueError):
        _valideer(data)


def test_item_zonder_laag_faalt():
    data = copy.deepcopy(DATA)
    del data["items"]["short"]["laag"]
    with pytest.raises(ValueError):
        _valideer(data)


def test_echt_databestand_dekt_elke_zone():
    import json

    from modules.body.kleding import DATA_DIR, _laad_data

    data = _laad_data()
    assert len(data["items"]) == 4

    with open(DATA_DIR / "body_map.json", encoding="utf-8") as bestand:
        kaart = json.load(bestand)
    nodes = set(kaart["nodes"] if "nodes" in kaart else kaart)
    assert set(data["zones"]) == nodes