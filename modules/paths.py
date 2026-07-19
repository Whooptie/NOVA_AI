# modules/paths.py
"""
Centrale hulpmodule om de project-root (C:\\Nova_AI) te vinden, ongeacht
vanuit welke submap of hoe diep genest een module dit aanroept.

Waarom dit bestaat:
--------------------
Losse modules gebruikten voorheen "Path(__file__).parent.parent.parent"
om bij de hoofdmap uit te komen. Dat werkt, maar telt blindelings een
vast aantal mapniveaus — verhuist een module ooit dieper of ondieper,
dan breekt dat stilzwijgend (geen foutmelding, gewoon een verkeerd pad).

Deze module lost dat structureel op: ze zoekt automatisch omhoog vanaf
het aanroepende bestand tot ze een map vindt met "main.py" erin. Dat
herkenningspunt is de project-root, hoe diep de module ook genest zit.
"""

from pathlib import Path

# Het bestand waaraan we de project-root herkennen. main.py staat in de
# hoofdmap van Nova (C:\Nova_AI\main.py) en verhuist normaal nooit.
HERKENNINGSBESTAND = "main.py"


def get_project_root(vanaf_bestand):
    """
    Zoekt omhoog vanaf 'vanaf_bestand' tot de map met main.py erin.

    Gebruik in een module zo:
        from modules.paths import get_project_root
        PROJECT_ROOT = get_project_root(__file__)
        data_pad = PROJECT_ROOT / "data" / "mijn_bestand.json"

    Argumenten:
        vanaf_bestand: geef hier altijd __file__ van de aanroepende module mee.

    Geeft terug:
        Path-object naar de project-root.

    Foutmelding:
        RuntimeError als main.py nergens gevonden wordt (bv. bij een
        losstaand/verplaatst bestand buiten het Nova-project). Dit is
        bewust een harde fout i.p.v. stil een verkeerd pad gebruiken —
        een fout data-pad zou anders onopgemerkt data op de verkeerde
        plek wegschrijven.
    """
    huidige_map = Path(vanaf_bestand).resolve().parent

    # Loop omhoog door de mappenstructuur, tot aan de schijf-root toe.
    for map_pad in [huidige_map, *huidige_map.parents]:
        if (map_pad / HERKENNINGSBESTAND).exists():
            return map_pad

    raise RuntimeError(
        f"Kon de Nova project-root niet vinden (op zoek naar "
        f"'{HERKENNINGSBESTAND}'), gestart vanaf: {vanaf_bestand}. "
        f"Staat dit bestand wel binnen de Nova-projectmap?"
    )