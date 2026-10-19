# ochtend_diagnose.py  -  draaien in de container:  python ochtend_diagnose.py
# Wijzigt niets blijvends: het "vandaag gedaan"-bestandje gaat naar /tmp,
# en er wordt niets uitgesproken.
import os, sys, subprocess
from pathlib import Path
sys.path.insert(0, "/app")

print("== 1. Staat de aansluiting in main.py op schijf?")
tekst = Path("/app/main.py").read_text(encoding="utf-8", errors="replace")
for sleutel in ("OCHTEND_CHECK_INTERVAL_MINUTEN", "_layer5_laat_spreken_toe", "check_ochtend_samenvatting"):
    print(f"   {sleutel}: {'JA' if sleutel in tekst else 'NEE  <-- main.py mist dit blok'}")

print("\n== 2. Sinds wanneer draait het Nova-proces? (main.py wordt NIET door hot reload vernieuwd)")
print(subprocess.run("ps -eo pid,lstart,cmd | grep -i '[m]ain.py'", shell=True, capture_output=True, text=True).stdout or "   (geen main.py-proces gevonden)")
print("   main.py laatst gewijzigd:", __import__("time").ctime(Path("/app/main.py").stat().st_mtime))

print("\n== 3. Is vandaag al als 'gedaan' bewaard?")
for p in Path("/app").rglob("weather_ochtend.json"):
    print("  ", p, "->", p.read_text())
else:
    pass

print("\n== 4. Zou de samenvatting nu gebouwd kunnen worden? (mag_spreken=ja, bestandje naar /tmp)")
from modules.weather.weather import WeatherModule
class NepBus:
    def __init__(self): self.b = []
    def subscribe(self, *a, **k): pass
    def publish(self, n, d=None):
        if n == "layer4_response": self.b.append(d["text"])
bus = NepBus()
wm = WeatherModule(bus, os.getenv("OPENWEATHER_API_KEY"))
wm._ochtend_pad = lambda: Path("/tmp/weather_ochtend_test.json")
Path("/tmp/weather_ochtend_test.json").unlink(missing_ok=True)
print("  ", wm.check_ochtend_samenvatting(mag_spreken=lambda: True))