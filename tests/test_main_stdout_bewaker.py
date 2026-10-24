"""Tests voor punt 31: prints uit andere threads breken Nova's typewriter-zin niet meer."""
import io
import re
import sys
import threading

import pytest

import main as nova_main


def zonder_kleur(tekst):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", tekst)


def in_andere_thread(functie):
    """Voert functie uit in een andere thread en wacht tot die klaar is."""
    thread = threading.Thread(target=functie)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive(), "de andere thread bleef hangen (wordt ten onrechte geblokkeerd)"


@pytest.fixture
def echte_stdout():
    return io.StringIO()


@pytest.fixture
def bewaker(echte_stdout):
    return nova_main._StdoutBewaker(echte_stdout)


def zet_typewriter_omgeving(monkeypatch, echte_stdout):
    """
    Zet een bewaker als sys.stdout en maakt de typewriter zonder tijdstempel.
    Bewust een gewone functie die BINNEN de test aangeroepen wordt, geen fixture:
    pytest zet sys.stdout bij elke testfase opnieuw naar zijn eigen opvang, dus
    een patch uit de fixture-fase zou vlak voor de test alweer weg zijn.
    """
    bewaker = nova_main._StdoutBewaker(echte_stdout)
    monkeypatch.setattr(sys, "stdout", bewaker)
    monkeypatch.setattr(nova_main, "_stdout_bewaker", bewaker)
    monkeypatch.setattr(nova_main, "TOON_TIJDSTEMPELS", False)
    return bewaker


# ---------- de bewaker zelf ----------

def test_zonder_blok_gaat_alles_gewoon_door(bewaker, echte_stdout):
    bewaker.write("hallo")
    assert echte_stdout.getvalue() == "hallo"


def test_andere_thread_wordt_vastgehouden_tijdens_blok(bewaker, echte_stdout):
    bewaker.start_blok()
    bewaker.write("Nova: ")
    in_andere_thread(lambda: bewaker.write("[CLIENT_BRIDGE] verbonden\n"))
    bewaker.write("hoi\n")
    assert echte_stdout.getvalue() == "Nova: hoi\n"          # nog niets van de andere thread
    bewaker.einde_blok()
    assert echte_stdout.getvalue() == "Nova: hoi\n[CLIENT_BRIDGE] verbonden\n"


def test_typende_thread_zelf_wordt_niet_vastgehouden(bewaker, echte_stdout):
    bewaker.start_blok()
    bewaker.write("a")
    bewaker.write("b")
    assert echte_stdout.getvalue() == "ab"
    bewaker.einde_blok()


def test_na_het_blok_gaat_alles_weer_direct_door(bewaker, echte_stdout):
    bewaker.start_blok()
    bewaker.einde_blok()
    in_andere_thread(lambda: bewaker.write("later\n"))
    assert echte_stdout.getvalue() == "later\n"


def test_volgorde_van_vastgehouden_tekst_blijft_behouden(bewaker, echte_stdout):
    bewaker.start_blok()
    in_andere_thread(lambda: (bewaker.write("een\n"), bewaker.write("twee\n")))
    bewaker.einde_blok()
    assert echte_stdout.getvalue() == "een\ntwee\n"


def test_onbekende_eigenschappen_gaan_naar_de_echte_stdout(bewaker, echte_stdout):
    # input() heeft fileno()/isatty() van sys.stdout nodig; die moeten doorgegeven worden.
    assert bewaker.isatty() is False
    bewaker.write("x")
    assert bewaker.getvalue() == "x"      # eigenschap van StringIO, via __getattr__


# ---------- installeren ----------

def test_installeren_vervangt_stdout_eenmalig(monkeypatch, echte_stdout):
    monkeypatch.setattr(sys, "stdout", echte_stdout)
    monkeypatch.setattr(nova_main, "_stdout_bewaker", None)

    eerste = nova_main.installeer_stdout_bewaker()
    tweede = nova_main.installeer_stdout_bewaker()

    assert sys.stdout is eerste
    assert tweede is eerste                       # niet twee keer ingepakt
    assert eerste._echt is echte_stdout


# ---------- de echte typewriter ----------

def test_typewriter_zin_blijft_heel_met_print_uit_andere_thread(echte_stdout, monkeypatch):
    zet_typewriter_omgeving(monkeypatch, echte_stdout)
    aantal = {"n": 0}

    def nep_sleep(seconden):
        aantal["n"] += 1
        if aantal["n"] == 3:      # na 3 letters komt er een print uit een andere thread
            in_andere_thread(lambda: print("[CLIENT_BRIDGE] Laptop-client verbonden"))

    monkeypatch.setattr(nova_main.time, "sleep", nep_sleep)

    nova_main.print_nova_typewriter("Hallo wereld")

    uitvoer = zonder_kleur(echte_stdout.getvalue())
    assert uitvoer == "Nova: Hallo wereld\n[CLIENT_BRIDGE] Laptop-client verbonden\n"


def test_typewriter_laat_andere_threads_weer_door_na_een_fout(echte_stdout, monkeypatch):
    zet_typewriter_omgeving(monkeypatch, echte_stdout)

    def kapotte_sleep(seconden):
        raise RuntimeError("boem")

    monkeypatch.setattr(nova_main.time, "sleep", kapotte_sleep)

    with pytest.raises(RuntimeError):
        nova_main.print_nova_typewriter("abc")

    in_andere_thread(lambda: print("na de fout"))
    assert "na de fout" in echte_stdout.getvalue()


def test_typewriter_werkt_ook_zonder_bewaker(monkeypatch, echte_stdout):
    monkeypatch.setattr(sys, "stdout", echte_stdout)
    monkeypatch.setattr(nova_main, "_stdout_bewaker", None)
    monkeypatch.setattr(nova_main, "TOON_TIJDSTEMPELS", False)
    monkeypatch.setattr(nova_main, "TYPEWRITER_SNELHEID", 0)

    nova_main.print_nova_typewriter("Hoi")

    assert zonder_kleur(echte_stdout.getvalue()) == "Nova: Hoi\n"