"""Drempel met hysterese.

Een drempel mag één keer vuren per overschrijding, niet bij elke beurt
opnieuw. Herwapenen gebeurt pas onder de onderdrempel, zodat een waarde
die rond de grens blijft hangen niet blijft publiceren.
"""


class Drempel:
    def __init__(self, hoog: float, laag: float = None) -> None:
        self.hoog = float(hoog)
        self.laag = self.hoog if laag is None else float(laag)
        if self.laag > self.hoog:
            raise ValueError("laag mag niet boven hoog liggen")
        self._actief = False

    @property
    def actief(self) -> bool:
        return self._actief

    def set(self, waarde: float) -> None:
        """Initialiseer zonder te vuren, bv. bij het laden van bestaande state."""
        self._actief = waarde > self.hoog

    def kruist(self, waarde: float) -> bool:
        if not self._actief and waarde > self.hoog:
            self._actief = True
            return True
        if self._actief and waarde < self.laag:
            self._actief = False
        return False