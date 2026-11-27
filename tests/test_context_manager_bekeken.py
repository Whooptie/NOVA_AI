"""Bekeken-as mag de context niet slopen en moet de stijl op kort zetten."""

from modules.context.context_manager import ContextManager


class NepBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))


class NepBekeken:
    def __init__(self, actief):
        self.actief = actief

    def is_actief(self):
        return self.actief


def _manager(tmp_path, actief):
    bus = NepBus()
    bus.modules["bekeken"] = NepBekeken(actief)
    cm = ContextManager(bus)
    cm.log_path = tmp_path / "context_log.jsonl"
    cm._on_kevin_typte({})  # Kevin zit in de terminal: geen harde stopregel
    return cm


def test_bekeken_actief_geeft_korte_stijl_en_heel_context(tmp_path):
    cm = _manager(tmp_path, True)
    ctx = cm.get_current()
    assert ctx["response_style"] == "kort"
    assert isinstance(ctx["should_interrupt"], bool)
    assert "bekeken-as actief" in ctx["reden"]


def test_zonder_bekeken_gewone_stijl(tmp_path):
    cm = _manager(tmp_path, False)
    ctx = cm.get_current()
    assert ctx["response_style"] != "kort"
    assert "bekeken-as actief" not in ctx["reden"]


def test_can_interrupt_blijft_werken_met_bekeken(tmp_path):
    cm = _manager(tmp_path, True)
    assert cm.can_interrupt() in (True, False)