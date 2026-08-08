# test_focus_debug.py
#
# LOS TESTSCRIPT — niet onderdeel van Nova, gewoon draaien vanuit
# C:\Nova_AI om de ruwe Windows API-waarden te zien.
#
# Gebruik:
#   (venv) PS C:\Nova_AI> python test_focus_debug.py
#
# Typ dit commando, wacht dan 5-10 seconden ZONDER muis/toetsenbord
# aan te raken, en kijk wat er verandert.

import ctypes
from ctypes import wintypes
import time


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


def main():
    for i in range(5):
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)

        ok = ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
        tick_now = ctypes.windll.kernel32.GetTickCount()

        print(f"--- meting {i+1} ---")
        print(f"GetLastInputInfo() succesvol: {bool(ok)}")
        print(f"info.dwTime (laatste input, ms sinds boot): {info.dwTime}")
        print(f"GetTickCount() (nu, ms sinds boot): {tick_now}")
        print(f"Verschil (ms): {tick_now - info.dwTime}")
        print(f"Verschil (seconden): {(tick_now - info.dwTime) / 1000.0}")
        print()

        time.sleep(3)


if __name__ == "__main__":
    main()