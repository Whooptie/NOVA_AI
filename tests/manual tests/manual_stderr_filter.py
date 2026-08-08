# test_zonder_filter.py
#
# LOS TESTSCRIPT — exact dezelfde MediaPipe-stappen als
# test_stderr_filter.py, maar ZONDER de stderr-omleiding, om te
# checken of het script op zich foutloos doorloopt.
#
# Gebruik:
#   (venv) PS C:\Nova_AI> python test_zonder_filter.py

import time
from pathlib import Path

print("Stap 1: gewone print werkt.")

import cv2
print("Stap 2: cv2 geimporteerd.")

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
print("Stap 3: mediapipe geimporteerd.")

model_pad = Path("C:/Nova_AI/data/models/blaze_face_short_range.tflite")
print(f"Stap 4: model_pad = {model_pad}, bestaat: {model_pad.exists()}")

if model_pad.exists():
    base_options = mp_python.BaseOptions(model_asset_path=str(model_pad))
    options = mp_vision.FaceDetectorOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.IMAGE,
    )
    detector = mp_vision.FaceDetector.create_from_options(options)
    print("Stap 5: FaceDetector aangemaakt.")

    camera = cv2.VideoCapture(0)
    print(f"Stap 6: camera geopend: {camera.isOpened()}")

    gelukt, frame = camera.read()
    print(f"Stap 7: frame gelezen: {gelukt}")

    if gelukt:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        resultaat = detector.detect(mp_image)
        print(f"Stap 8: Aantal gezichten gedetecteerd: {len(resultaat.detections)}")

    camera.release()
    detector.close()

print("Test klaar, script liep volledig door.")