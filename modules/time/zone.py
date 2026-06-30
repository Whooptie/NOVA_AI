# modules/time/zone.py

from datetime import datetime, timedelta
import time
import requests

class TimeZoneModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus

        # Standaard offset (fallback)
        self.tz_offset_minutes = self._get_os_offset()

        # DST
        self.dst_active = self._is_dst()

        # Automatische tijdzone staat standaard uit
        self.auto_mode = False

        # Registreren
        event_bus.register_module("zone", self)

        # Geen event publish hier → IntentRouter en andere modules zijn nog niet klaar

    # ----------------------------------------------------
    # 1. OS offset (fallback)
    # ----------------------------------------------------
    def _get_os_offset(self):
        try:
            now = datetime.now()
            utc = datetime.utcnow()
            delta = now - utc
            return int(delta.total_seconds() // 60)
        except Exception:
            return 0

    # ----------------------------------------------------
    # 2. DST actief?
    # ----------------------------------------------------
    def _is_dst(self):
        try:
            return time.localtime().tm_isdst == 1
        except Exception:
            return False

    # ----------------------------------------------------
    # 3. Lokale tijd
    # ----------------------------------------------------
    def now_local(self):
        utc = datetime.utcnow()
        return utc + timedelta(minutes=self.tz_offset_minutes)

    # ----------------------------------------------------
    # 4. UTC tijd
    # ----------------------------------------------------
    def now_utc(self):
        return datetime.utcnow()

    # ----------------------------------------------------
    # 5. Offset in uren
    # ----------------------------------------------------
    def get_offset(self):
        return self.tz_offset_minutes / 60

    # ----------------------------------------------------
    # 6. Tijdzone instellen via API
    # ----------------------------------------------------
    def set_timezone(self, timezone_name):
        try:
            r = requests.get(
                f"https://worldtimeapi.org/api/timezone/{timezone_name}",
                timeout=4
            )
            data = r.json()
        except Exception:
            return False

        offset_str = data.get("utc_offset")
        if not offset_str:
            return False

        sign = 1 if offset_str[0] == "+" else -1
        hours = int(offset_str[1:3])
        minutes = int(offset_str[4:6])

        self.tz_offset_minutes = sign * (hours * 60 + minutes)
        self.dst_active = self._is_dst()

        # Event uitsturen (nu veilig)
        self.event_bus.publish("time_zone_ready", {
            "offset_minutes": self.tz_offset_minutes,
            "dst_active": self.dst_active
        })

        return True

    # ----------------------------------------------------
    # 7. Automatische tijdzone via IP
    # ----------------------------------------------------
    def auto_update_timezone(self):
        """
        Probeert tijdzone via twee betrouwbare APIs.
        Als beide falen, gebruikt Nova de OS-offset (correct dankzij _get_os_offset()).
        Geen chat-meldingen meer bij falen, alleen console-debug.
        """
        timezone = None

        # -----------------------------
        # 1. Eerste poging: ipinfo.io
        # -----------------------------
        try:
            r = requests.get("https://ipinfo.io/json", timeout=4).json()
            timezone = r.get("timezone")
            if timezone:
                print("[TimeZone] ipinfo.io →", timezone)
                return self.set_timezone(timezone)
        except Exception as e:
            print("[TimeZone] ipinfo.io faalde:", e)

        # -----------------------------
        # 2. Tweede poging: ip-api.com
        # -----------------------------
        try:
            r = requests.get("http://ip-api.com/json", timeout=4).json()
            timezone = r.get("timezone")
            if timezone:
                print("[TimeZone] ip-api.com →", timezone)
                return self.set_timezone(timezone)
        except Exception as e:
            print("[TimeZone] ip-api.com faalde:", e)

        # -----------------------------
        # 3. Fallback: OS-offset
        # -----------------------------
        print("[TimeZone] Geen externe API beschikbaar → gebruik OS-offset:", self.tz_offset_minutes, "min")
        return False

    # ----------------------------------------------------
    # 8. Auto-mode activeren
    # ----------------------------------------------------
    def enable_auto_timezone(self):
        self.auto_mode = True
        return self.auto_update_timezone()


def init_module(event_bus):
    instance = TimeZoneModule(event_bus)
    # Event pas uitsturen wanneer systeem klaar is
    event_bus.publish("module_loaded", {"name": "zone"})
    return instance
