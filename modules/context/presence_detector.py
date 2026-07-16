# modules/context/presence_detector.py

"""
Layer 5, Fase 4: Presence Detector

Detecteert OF ER MENSEN AANWEZIG ZIJN via de webcam — puur AANWEZIGHEID
(hoeveel gezichten zijn er in beeld?), GEEN IDENTITEIT (wiens gezicht
is dit?). Dat laatste is een bewust latere, aparte uitbreiding (zie
Kevin's presence/identiteits-roadmap, nog te schrijven).

BELANGRIJK — dit is de EERSTE Layer 5-module die een extern ML-model
gebruikt (MediaPipe Face Detection), in tegenstelling tot Fase 1-3 die
allemaal pure Python/OS-API's waren. Dit is bewust en correct volgens
Nova's architectuurprincipe: het model is een BOUNDED, EXTERNAL
SPECIALIST TOOL — het levert enkel een getal terug ("aantal gezichten
gedetecteerd"), en heeft GEEN enkele rol in Nova's eigen redenering.
Nova's symbolische kern (context_manager.py) beslist nog steeds zelf,
met gewone if/else-logica, wat ze met dat getal doet.

BELANGRIJKE TECHNISCHE NOOT (16 juli 2026): MediaPipe verwijderde de
oude, eenvoudige "Solutions"-API (mp.solutions.face_detection) volledig
vanaf versie 0.10.x — dit bestand gebruikt daarom de NIEUWE Tasks API
(mp.tasks.vision.FaceDetector), die een apart, lokaal opgeslagen
.task-modelbestand vereist (niet meer intern meegeleverd door het
pip-pakket zelf). Zie MODEL_PAD hieronder — dit bestand MOET
gedownload worden vóór presence_detector.py werkt (zie module-
docstring onderaan voor de downloadlink en instructies).

WAAROM MediaPipe (i.p.v. bv. RetinaFace) — afweging met Kevin
(16 juli 2026): voor dit scenario (1 gezicht, dichtbij, webcam, goed
licht) is MediaPipe ruim voldoende nauwkeurig, officieel onderhouden
door Google, en snel genoeg. RetinaFace's extra precisie is gericht
op drukke scenes met kleine/verre/gedeeltelijk verborgen gezichten —
een probleem dat Kevin hier niet heeft.

BELANGRIJK — wat dit NIET is:
- Geen identiteitsherkenning: dit weet NOOIT wiens gezicht het is,
  enkel HOEVEEL gezichten er zijn.
- Geen continue opname/opslag: er wordt GEEN video of foto opgeslagen
  op schijf. Elk frame wordt enkel in het geheugen geanalyseerd
  (aantal gezichten) en daarna weggegooid.
- Geen constante webcam-activiteit: detect_presence() wordt enkel
  aangeroepen wanneer iets (bv. de achtergrondthread) erom vraagt.
"""

import os
import time
from pathlib import Path

# Onderdrukt MediaPipe/absl's interne C++-logging (o.a. de
# "portable_clearcut_uploader" telemetrie-foutmeldingen, zie het
# gesprek met Kevin op 16 juli 2026 — de bijhorende netwerkverbinding
# is intussen ook geblokkeerd via een Windows Firewall-regel).
# MOET gezet worden VOOR "import mediapipe", anders heeft het geen
# effect (de C++-logger leest deze omgevingsvariabelen enkel bij het
# eigen opstarten in).
os.environ.setdefault("GLOG_minloglevel", "3")
os.environ.setdefault("GLOG_logtostderr", "0")

try:
    import cv2
    OPENCV_BESCHIKBAAR = True
except ImportError:
    OPENCV_BESCHIKBAAR = False

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    MEDIAPIPE_BESCHIKBAAR = True
except ImportError:
    MEDIAPIPE_BESCHIKBAAR = False


class PresenceDetector:
    """
    Layer 5, Fase 4: detecteert of er mensen aanwezig zijn via de
    webcam, met MediaPipe Face Detection (Tasks API, aanwezigheid,
    geen identiteit).
    """

    # Welke webcam-index gebruiken? 0 is meestal de ingebouwde
    # laptop-webcam.
    WEBCAM_INDEX = 0

    # MediaPipe's eigen betrouwbaarheidsdrempel voor een detectie.
    MIN_DETECTION_CONFIDENCE = 0.5

    # Pad naar het lokaal gedownloade .task-modelbestand. Portable,
    # zelfde principe als context_manager.py's log_path: relatief
    # t.o.v. dit bestand, geen hardcoded Windows-pad.
    # modules/context/presence_detector.py -> ../../data/models/...
    #
    # DIT BESTAND MOET JE ZELF EENMALIG DOWNLOADEN — zie de instructies
    # in de module-docstring onderaan dit bestand voor de link en
    # het commando.
    MODEL_BESTANDSNAAM = "blaze_face_short_range.tflite"

    def __init__(self, event_bus):
        self.event_bus = event_bus

        self.model_pad = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "models" / self.MODEL_BESTANDSNAAM
        )

        self._beschikbaar = False
        self._face_detector = None

        if not OPENCV_BESCHIKBAAR:
            print(
                "[PRESENCE_DETECTOR] WAARSCHUWING: 'opencv-python' is "
                "niet geïnstalleerd. Presence-detectie geeft altijd "
                "'geen info' terug. Installeer met: "
                "pip install opencv-python"
            )
            return

        if not MEDIAPIPE_BESCHIKBAAR:
            print(
                "[PRESENCE_DETECTOR] WAARSCHUWING: 'mediapipe' is niet "
                "geïnstalleerd. Presence-detectie geeft altijd 'geen "
                "info' terug. Installeer met: pip install mediapipe"
            )
            return

        if not self.model_pad.exists():
            print(
                f"[PRESENCE_DETECTOR] WAARSCHUWING: modelbestand niet "
                f"gevonden op {self.model_pad}. Presence-detectie geeft "
                f"altijd 'geen info' terug. Download het model — zie "
                f"de instructies bovenaan presence_detector.py."
            )
            return

        try:
            base_options = mp_python.BaseOptions(
                model_asset_path=str(self.model_pad)
            )
            options = mp_vision.FaceDetectorOptions(
                base_options=base_options,
                min_detection_confidence=self.MIN_DETECTION_CONFIDENCE,
                running_mode=mp_vision.RunningMode.IMAGE,
            )
            self._face_detector = mp_vision.FaceDetector.create_from_options(options)
            self._beschikbaar = True
        except Exception as e:
            print(f"[PRESENCE_DETECTOR] Kon FaceDetector niet initialiseren: {e}")

    # ------------------------------------------------------------
    # Kern: aanwezigheid detecteren
    # ------------------------------------------------------------

    def detect_presence(self):
        """
        Neemt EENMALIG 1 frame van de webcam, telt hoeveel gezichten
        MediaPipe daarin herkent, en geeft een dictionary terug.

        Publiceert ook een "presence_detected"-event.

        Geeft bij elk probleem netjes "faces_detected: None" terug —
        NOOIT een crash, en NOOIT aangenomen dat "geen info" hetzelfde
        is als "niemand aanwezig".
        """
        aantal_gezichten = None

        if self._beschikbaar:
            aantal_gezichten = self._neem_frame_en_tel_gezichten()

        resultaat = {
            "faces_detected": aantal_gezichten,
            "is_alone": (aantal_gezichten == 0) if aantal_gezichten is not None else None,
            "time": time.time(),
        }

        if self.event_bus is not None:
            self.event_bus.publish("presence_detected", resultaat)

        return resultaat

    def _neem_frame_en_tel_gezichten(self):
        """
        Opent de webcam, leest PRECIES 1 frame, sluit de webcam
        onmiddellijk weer, en telt hoeveel gezichten MediaPipe erin
        vindt via de Tasks API. Geeft None terug bij eender welk
        probleem.
        """
        camera = None
        try:
            camera = cv2.VideoCapture(self.WEBCAM_INDEX)

            if not camera.isOpened():
                return None

            gelukt, frame = camera.read()
            if not gelukt or frame is None:
                return None

            # MediaPipe verwacht RGB, OpenCV geeft standaard BGR terug.
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # De Tasks API verwacht een mp.Image-object, geen kale
            # numpy-array zoals de oude Solutions-API dat wel accepteerde.
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

            resultaat = self._face_detector.detect(mp_image)

            return len(resultaat.detections)
        except Exception as e:
            print(f"[PRESENCE_DETECTOR] Fout bij webcam-detectie: {e}")
            return None
        finally:
            if camera is not None:
                camera.release()

    def shutdown(self):
        """
        Nette opruiming bij het afsluiten van Nova.
        """
        if self._face_detector is not None:
            try:
                self._face_detector.close()
            except Exception:
                pass


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    """
    instance = PresenceDetector(event_bus)
    event_bus.publish("module_loaded", {"name": "presence_detector"})
    return instance


# ----------------------------------------------------------------------
# EENMALIGE SETUP VEREIST — lees dit voor je Nova herstart
# ----------------------------------------------------------------------
#
# Download het modelbestand (BlazeFace, "short range" — bedoeld voor
# gezichten dichtbij de camera, precies zoals een laptop-webcam):
#
#   https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite
#
# En zet het op:
#
#   C:\Nova_AI\data\models\blaze_face_short_range.tflite
#
# In PowerShell kan dit met:
#
#   mkdir C:\Nova_AI\data\models -Force
#   Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite" -OutFile "C:\Nova_AI\data\models\blaze_face_short_range.tflite"
#
# Zonder dit bestand print presence_detector.py een duidelijke
# waarschuwing bij opstarten en valt netjes terug op "geen info" —
# geen crash, maar ook geen echte detectie.