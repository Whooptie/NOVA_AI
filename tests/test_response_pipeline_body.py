import pytest

from modules.chat.response_pipeline import ResponsePipeline


class NepBus:
    def __init__(self):
        self.events = []

    def subscribe(self, naam, fn):
        pass

    def publish(self, naam, data=None):
        self.events.append((naam, data))

    def register_module(self, naam, obj):
        pass

    modules = {}


@pytest.fixture
def pipeline():
    return ResponsePipeline(NepBus())


def test_body_reactie_gaat_naar_pipeline_response(pipeline):
    pipeline.on_body_reactie({"text": "Au.", "zone": "vagina", "klasse": "pijn"})
    naam, data = pipeline.event_bus.events[-1]
    assert naam == "pipeline_response"
    assert data["base_text"] == "Au."
    assert data["bron"] == "body"
    assert data["zone"] == "vagina"


def test_lege_tekst_doet_niets(pipeline):
    pipeline.on_body_reactie({"text": ""})
    assert not pipeline.event_bus.events