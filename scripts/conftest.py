# scripts/conftest.py -- de bestanden hier zijn handmatige proefscripts
# (je draait ze zelf met python), geen pytest-tests. Zonder deze regel pakt
# pytest hun test_*-functies op en faalt op de parameters (lat, lon).
collect_ignore_glob = ["test_*.py"]