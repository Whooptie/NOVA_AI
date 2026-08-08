# conftest.py
#
# Dit bestand hoort in de PROJECT-ROOT te staan (C:\Nova_AI, naast main.py),
# NIET in de tests/-map.
#
# Waarom dit bestand nodig is:
# Als je "python test_fase1.py" los draait, zet Python automatisch de map
# van dat bestand vooraan in zijn zoekpad (sys.path) -- daardoor werkt
# "from modules.xxx import ..." gewoon.
#
# pytest werkt anders: het bepaalt zijn zoekpad op basis van package-
# structuur (aanwezigheid van __init__.py-bestanden), niet op basis van
# waar je het commando typt. Zonder dit bestand weet pytest niet dat
# C:\Nova_AI zelf aan sys.path toegevoegd moet worden, waardoor
# "import modules.xxx" en "import core.xxx" falen met
# "ModuleNotFoundError: No module named 'modules'".
#
# De aanwezigheid van EEN conftest.py in de project-root is voor pytest
# genoeg om die map als vertrekpunt (rootdir) te herkennen en toe te
# voegen aan sys.path. Dit bestand hoeft verder niets te bevatten --
# leeg is voldoende. Latere gedeelde fixtures (bv. een fixture die
# meerdere testbestanden herbruiken) kunnen hier later ook in.