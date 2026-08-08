# test_stderr_simpel.py
#
# LOS TESTSCRIPT — eenvoudige, kortstondige stderr-onderdrukking:
# stderr (OS-niveau, fd 2) wordt tijdelijk naar "nergens" (os.devnull)
# omgeleid tijdens de MediaPipe-import + modelinitialisatie, en
# meteen daarna teruggezet naar normaal. Geen aparte thread, geen
# doorlopend filter — enkel een korte "stilte".
#
# Gebruik:
#   (venv) PS C:\Nova_AI> python test_stderr_simpel.py

import os
import sys
import contextlib
from pathlib import Path


@contextlib.contextmanager
def onderdruk_stderr_tijdelijk():
    """
    Leidt OS-niveau stderr (fd 2) tijdelijk om naar os.devnull, en
    herstelt die daarna weer naar het origineel. Vangt ook C++-output
    die rechtstreeks naar fd 2 schrijft (zoals absl/glog/TFLite-logs),
    niet enkel Python's eigen sys.stderr.
    """
    stderr_fd = 2
    origineel_fd = os.dup(stderr_fd)

    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull_fd, stderr_fd)
    os.close(devnull_fd)

    try:
        yield
    finally:
        os.dup2(origineel_fd, stderr_fd)
        os.close(origineel_fd)


if __name__ == "__main__":
    print("Stap 1: voor de onderdrukking, gewone print werkt.")
    sys.stderr.write("Stap 1b: dit ZOU zichtbaar moeten zijn (voor de onderdrukking).\n")

    with onderdruk_stderr_tijdelijk():
        sys.stderr.write("Dit zou VERBORGEN moeten zijn (tijdens de onderdrukking).\n")

        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        model_pad = Path("C:/Nova_AI/data/models/blaze_face_short_range.tflite")

        detector = None
        if model_pad.exists():
            base_options = mp_python.BaseOptions(model_asset_path=str(model_pad))
            options = mp_vision.FaceDetectorOptions(
                base_options=base_options,
                running_mode=mp_vision.RunningMode.IMAGE,
            )
            detector = mp_vision.FaceDetector.create_from_options(options)

    # Buiten de "with"-blok: stderr is weer normaal.
    print("Stap 2: na de onderdrukking, gewone print werkt nog steeds.")
    sys.stderr.write("Stap 2b: dit ZOU weer zichtbaar moeten zijn (na de onderdrukking).\n")

    if detector is not None:
        camera = cv2.VideoCapture(0)
        gelukt, frame = camera.read()
        if gelukt:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            resultaat = detector.detect(mp_image)
            print(f"Stap 3: Aantal gezichten gedetecteerd: {len(resultaat.detections)}")
        camera.release()
        detector.close()

    print("Test klaar.")