# test_memory_archivering.py
#
# Echte pytest-test voor archive_old_events() en compress_ancient_events()
# ZELF -- een aanvulling op test_memory_fase4_archief.py, die enkel
# bevestigde dat testdata in de juiste tabel terechtkwam, niet dat de
# archiverings-/compressiefunctie de rijen ook echt verplaatst (dat
# stond daar letterlijk als TODO).
#
# Isolatie: MemoryModule accepteert een save_path-parameter, waaruit
# db_path automatisch wordt afgeleid (zie __init__ in memory.py) --
# elke test bouwt zijn eigen MemoryModule op binnen pytest's tmp_path,
# NOOIT de echte data/interactions.db.
#
# BELANGRIJK: MemoryModule start in __init__() een achtergrond-
# onderhoudstimer (start_maintenance()) en registreert atexit/signal-
# hooks. De fixture hieronder roept daarom expliciet _on_shutdown() op
# na elke test (via yield + teardown) om de timer te stoppen en de
# SQLite-connectie netjes te sluiten -- anders blijft er een levende
# achtergrondthread hangen na de test.
#
# Uitvoeren: pytest tests/test_memory_archivering.py -v

import time
import json
import gzip

import pytest

from core.memory import MemoryModule


class DummyEventBus:
    """MemoryModule heeft enkel subscribe() nodig in __init__()
    (event_bus.subscribe("*", self.on_event)) -- publish() wordt in
    deze tests niet gebruikt, maar voor de volledigheid toch aanwezig."""
    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, *args, **kwargs):
        pass


@pytest.fixture
def memory(tmp_path):
    """Bouwt een volledig geïsoleerde MemoryModule op, met
    interactions.db in een tijdelijke map."""
    save_path = tmp_path / "interactions.jsonl"
    mm = MemoryModule(DummyEventBus(), save_path=str(save_path))

    yield mm

    # Teardown: stopt de achtergrond-onderhoudstimer en sluit de
    # SQLite-connectie netjes, zodat er geen thread blijft hangen na
    # deze test (zie _on_shutdown() in memory.py).
    mm._on_shutdown()


def _voeg_event_toe(memory, tabel, dagen_oud, tekst):
    """Voegt rechtstreeks 1 rij toe aan 'interactions' of
    'interactions_old', met een timestamp X dagen in het verleden --
    zelfde patroon als test_memory_fase4_archief.py, nu op de ECHTE
    MemoryModule-connectie i.p.v. een handgebouwd schema."""
    ts = time.time() - (dagen_oud * 24 * 3600)
    from datetime import datetime
    dt = datetime.fromtimestamp(ts)
    memory.conn.execute(f"""
        INSERT INTO {tabel} (timestamp, month, year, event_type, data, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ts, dt.strftime("%Y-%m"), dt.year, "test_event", json.dumps({"tekst": tekst}), time.time()))
    memory.conn.commit()


def _tel_rijen(memory, tabel):
    return memory.conn.execute(f"SELECT COUNT(*) FROM {tabel}").fetchone()[0]


# ─────────────────────────────────────────────────────────────
# archive_old_events(): interactions -> interactions_old
# ─────────────────────────────────────────────────────────────

def test_archive_verplaatst_oude_events(memory):
    """Events ouder dan archive_after_days (90) horen VERPLAATST te
    worden van 'interactions' naar 'interactions_old'."""
    _voeg_event_toe(memory, "interactions", dagen_oud=100, tekst="oud genoeg om te archiveren")
    _voeg_event_toe(memory, "interactions", dagen_oud=120, tekst="ook oud genoeg")

    memory.archive_old_events()

    assert _tel_rijen(memory, "interactions") == 0, (
        "De oude events hadden uit 'interactions' verwijderd moeten worden."
    )
    assert _tel_rijen(memory, "interactions_old") == 2, (
        "De oude events hadden in 'interactions_old' moeten belanden."
    )


def test_archive_laat_recente_events_ongemoeid(memory):
    """Events JONGER dan archive_after_days horen in 'interactions' te
    BLIJVEN staan -- archive_old_events() mag ze niet verplaatsen."""
    _voeg_event_toe(memory, "interactions", dagen_oud=10, tekst="veel te recent om te archiveren")

    memory.archive_old_events()

    assert _tel_rijen(memory, "interactions") == 1, (
        "Een recent event werd onterecht verplaatst/verwijderd."
    )
    assert _tel_rijen(memory, "interactions_old") == 0


def test_archive_behoudt_de_inhoud_correct(memory):
    """De data zelf (niet enkel het aantal rijen) moet correct
    overkomen naar interactions_old -- zelfde tekst, zelfde event_type."""
    _voeg_event_toe(memory, "interactions", dagen_oud=100, tekst="unieke test-inhoud-12345")

    memory.archive_old_events()

    rij = memory.conn.execute(
        "SELECT event_type, data FROM interactions_old"
    ).fetchone()
    assert rij[0] == "test_event"
    data = json.loads(rij[1])
    assert data["tekst"] == "unieke test-inhoud-12345"


# ─────────────────────────────────────────────────────────────
# compress_ancient_events(): interactions_old -> .jsonl.gz-bestand
# ─────────────────────────────────────────────────────────────

def test_compress_verwijdert_uit_interactions_old(memory):
    """Events ouder dan compress_after_days (365) horen uit
    'interactions_old' verwijderd te worden na compressie."""
    _voeg_event_toe(memory, "interactions_old", dagen_oud=400, tekst="oud genoeg om te comprimeren")
    _voeg_event_toe(memory, "interactions_old", dagen_oud=450, tekst="ook oud genoeg")

    memory.compress_ancient_events()

    assert _tel_rijen(memory, "interactions_old") == 0, (
        "De zeer oude events hadden uit 'interactions_old' verwijderd "
        "moeten worden na compressie."
    )


def test_compress_laat_recentere_old_events_ongemoeid(memory):
    """Events die wel in 'interactions_old' zitten, maar nog niet ouder
    zijn dan compress_after_days, horen te BLIJVEN staan."""
    _voeg_event_toe(memory, "interactions_old", dagen_oud=200, tekst="oud, maar niet oud genoeg voor compressie")

    memory.compress_ancient_events()

    assert _tel_rijen(memory, "interactions_old") == 1


def test_compress_schrijft_geldig_gzip_bestand_met_juiste_inhoud(memory):
    """
    Het gzip-bestand moet ECHT aangemaakt worden, op de juiste plek
    (naast save_path, in een 'archive'-submap), en de inhoud moet
    correct leesbare JSONL zijn met de juiste data erin -- niet enkel
    dat de rijen uit de db verdwijnen.
    """
    _voeg_event_toe(memory, "interactions_old", dagen_oud=400, tekst="unieke compressie-inhoud-67890")

    memory.compress_ancient_events()

    archive_dir = memory.save_path.parent / "archive"
    assert archive_dir.exists(), "De 'archive'-submap werd niet aangemaakt."

    gz_bestanden = list(archive_dir.glob("interactions_compressed_*.jsonl.gz"))
    assert len(gz_bestanden) == 1, (
        f"Verwachtte precies 1 gzip-archiefbestand, vond {len(gz_bestanden)}."
    )

    with gzip.open(gz_bestanden[0], "rt", encoding="utf-8") as f:
        regels = [json.loads(line) for line in f if line.strip()]

    assert len(regels) == 1
    data = json.loads(regels[0]["data"])
    assert data["tekst"] == "unieke compressie-inhoud-67890"


def test_volledige_levenscyclus_recent_naar_archief_naar_compressie(memory):
    """
    Integratietest: simuleert het VOLLEDIGE traject van een event --
    recent (blijft in interactions) -> gearchiveerd (na 90 dagen,
    verhuist naar interactions_old) -> gecomprimeerd (na 365 dagen,
    verhuist naar het gzip-bestand). Bevestigt dat de twee functies
    correct op elkaar aansluiten.
    """
    _voeg_event_toe(memory, "interactions", dagen_oud=10, tekst="recent")
    _voeg_event_toe(memory, "interactions", dagen_oud=100, tekst="moet archiveren")
    _voeg_event_toe(memory, "interactions", dagen_oud=400, tekst="moet uiteindelijk comprimeren")

    # Stap 1: archiveren -- de 100- en 400-dagen-events verhuizen naar interactions_old
    memory.archive_old_events()
    assert _tel_rijen(memory, "interactions") == 1  # enkel de 10-dagen-event blijft
    assert _tel_rijen(memory, "interactions_old") == 2

    # Stap 2: comprimeren -- enkel de 400-dagen-event (>365 dagen) verhuist verder
    memory.compress_ancient_events()
    assert _tel_rijen(memory, "interactions_old") == 1  # de 100-dagen-event blijft hier
    assert _tel_rijen(memory, "interactions") == 1  # ongewijzigd