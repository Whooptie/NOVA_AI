# test_mediapipe_debug.py
#
# LOS TESTSCRIPT — niet onderdeel van Nova. Draai dit los om te zien
# welke MediaPipe-versie geinstalleerd is en welke API's beschikbaar
# zijn, zodat we de juiste fix kunnen kiezen i.p.v. te gokken.
#
# Gebruik:
#   (venv) PS C:\Nova_AI> python test_mediapipe_debug.py

import mediapipe as mp

print(f"MediaPipe versie: {mp.__version__}")
print()
print("Heeft 'solutions'?", hasattr(mp, "solutions"))
print("Heeft 'tasks'?", hasattr(mp, "tasks"))
print()
print("Alle top-level attributen van mediapipe:")
for attr in dir(mp):
    if not attr.startswith("_"):
        print(f"  - {attr}")