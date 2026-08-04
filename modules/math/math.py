# modules/math/math.py
import ast
import operator
import math
import cmath
import re
from fractions import Fraction

# Fase 4, punt 10 — Symbolische algebra (SymPy)
# SymPy is een externe bibliotheek voor symbolisch rekenen (formules
# blijven formules, i.p.v. te worden uitgerekend tot een getal). We
# importeren hem hier met een try/except: als hij niet geïnstalleerd is
# (bv. na een schone Nova-installatie zonder "pip install sympy"),
# crasht Nova niet in zijn geheel — enkel de nieuwe symbolische functies
# (differentiate, solve_sym, ...) geven dan een duidelijke Nederlandse
# foutmelding i.p.v. de rest van math.py onbruikbaar te maken.
try:
    import sympy as sp
    SYMPY_BESCHIKBAAR = True
except ImportError:
    SYMPY_BESCHIKBAAR = False

class UnitValue:
    def __init__(self, value, dims=None, label=None):
        self.value = value
        self.dims = dims or {}  # {"m": 1, "s": -2}
        self.label = label

    def bind_math(self, math_module):
        self._math = math_module
        return self

    def to(self, target_unit: str):
        if not hasattr(self, "_math"):
            raise ValueError("UnitValue is niet gebonden aan MathModule")
        return self._math._convert(self, target_unit)

    def _combine_dims(self, other, op):
        """Combineert dimensies bij vermenigvuldiging of deling."""
        new = self.dims.copy()

        for k, v in other.dims.items():
            if op == "+":
                new[k] = new.get(k, 0) + v
            elif op == "-":
                new[k] = new.get(k, 0) - v

        # verwijder nul-exponenten
        new = {k: v for k, v in new.items() if v != 0}
        return new

    def _check_same_dims(self, other):
        """Controleert of dimensies identiek zijn."""
        return self.dims == other.dims

    # -----------------------------
    #   Operatoren
    # -----------------------------

    def __add__(self, other):
        if isinstance(other, UnitValue):
            if not self._check_same_dims(other):
                raise ValueError("Kan geen grootheden met verschillende dimensies optellen")
            return UnitValue(self.value + other.value, self.dims.copy()).bind_math(self._math)
        raise ValueError("Kan alleen UnitValue optellen")

    def __sub__(self, other):
        if isinstance(other, UnitValue):
            if not self._check_same_dims(other):
                raise ValueError("Kan geen grootheden met verschillende dimensies aftrekken")
            return UnitValue(self.value - other.value, self.dims.copy()).bind_math(self._math)
        raise ValueError("Kan alleen UnitValue aftrekken")

    def __mul__(self, other):
        if isinstance(other, UnitValue):
            new_dims = self._combine_dims(other, "+")
            return UnitValue(self.value * other.value, new_dims).bind_math(self._math)
        elif isinstance(other, (int, float)):
            return UnitValue(self.value * other, self.dims.copy(), label=self.label).bind_math(self._math)
        raise ValueError("Ongeldige vermenigvuldiging")

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, UnitValue):
            new_dims = self._combine_dims(other, "-")
            return UnitValue(self.value / other.value, new_dims).bind_math(self._math)
        elif isinstance(other, (int, float)):
            return UnitValue(self.value / other, self.dims.copy(), label=self.label).bind_math(self._math)
        raise ValueError("Ongeldige deling")

    def __rtruediv__(self, other):
        # ondersteunt: scalar / UnitValue
        if isinstance(other, (int, float)):
            # scalar / (value * dims)  →  (scalar/value) * dims⁻¹
            inv_dims = {k: -v for k, v in self.dims.items()}
            return UnitValue(other / self.value, inv_dims).bind_math(self._math)
        raise ValueError("Ongeldige deling (UnitValue staat rechts)")

    def __pow__(self, exp):
        if not isinstance(exp, (int, float)):
            raise ValueError("Exponent moet een getal zijn")
        new_dims = {k: v * exp for k, v in self.dims.items()}
        return UnitValue(self.value ** exp, new_dims).bind_math(self._math)

    # -----------------------------
    #   Representatie
    # -----------------------------
    def __repr__(self):
        if self.label:
            return f"{self.value} {self.label}"
        # normale units
        unit_str = self._math._dims_to_string(self.dims)
        return f"{self.value} {unit_str}"

class MathModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        event_bus.subscribe("intent_math", self.on_math)

        self.unit_sep = "·"   # of " "
        UnitValue.bind_math = UnitValue.bind_math

        # Fase 5, punt 16 — Afronding & precisie: instelbare precisie
        # voor de hele sessie (relevant bij fysica-berekeningen met
        # meetonzekerheid, waar je bv. altijd op 3 decimalen wil
        # afronden). None = geen speciale precisie ingesteld, gedraag je
        # zoals voorheen (geen wijziging aan bestaande weergave).
        self.sessie_precisie = None

        # veilige operatoren
        self.ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg
        }

        # veilige functies
        self.funcs = {
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,      # log(x) of log(x, base)
            "ln": math.log,       # alias voor natuurlijke log
            "exp": math.exp,
            "abs": abs,
            "round": round,
            "dot": self._dot,
            "norm": self._norm,
            "cross": self._cross,
            "unit": self._unit,
            "proj": self._proj,
            "transpose": self._transpose,
            "det": self._det,
            "inverse": self._inverse,
            "identity": self._identity,
            "rotX": self._rotX,
            "rotx": self._rotX,   # alias
            "rotY": self._rotY,
            "roty": self._rotY,  # alias voor router die lowercase maakt
            "rotZ": self._rotZ,
            "rotz": self._rotZ,   # alias voor router die lowercase maakt
            "rotAxis": self._rotAxis,
            "rotaxis": self._rotAxis,   # alias voor router die lowercase maakt
            "solve": self._solve,
            "solveGauss": self._solveGauss,
            "solvegauss": self._solveGauss,   # alias voor router die lowercase maakt

            # Fase 3 — Algebra-module (numeriek), 100% puur symbolisch
            "solveQuadratic": self._solveQuadratic,
            "solvequadratic": self._solveQuadratic,   # alias voor router die lowercase maakt
            "wortel": self._solveQuadratic,           # Nederlandse alias: "wortel(1,-5,6)"
            "newton": self._newton,
            "nulpunt": self._newton,                  # Nederlandse alias: "nulpunt(x^2-4, 1)"
            "polyeval": self._polyeval,
            "bereken": self._polyeval,                # Nederlandse alias: "bereken(x^2+2x+1, 3)"
            "extremum": self._extremum,
            "minmax": self._extremum,                 # Nederlandse alias: "minmax(-x^2+4x, 0, 5)"

            # Fase 3, punt 8 — Calculus-module (numeriek), 100% puur symbolisch
            "afgeleide": self._afgeleide,              # afgeleide(x^2, 3) -> 6.0
            "integraal": self._integraal,               # integraal(x^2, 0, 3) -> 9.0
            "limiet": self._limiet,                     # limiet(sin(x)/x, 0) -> 1.0
            "dv": self._dv,                             # dv(x-y, y0=1, van=0, tot=5) -> standaard RK4
            "dv_euler": self._dv_euler,                 # expliciet Euler
            "dv_rk4": self._dv_rk4,                     # expliciet RK4

            # Fase 3, punt 9 — Statistiek-module, 100% puur symbolisch/numeriek
            "gemiddelde": self._gemiddelde,             # gemiddelde([1,2,3,4]) -> 2.5
            "mediaan": self._mediaan,                   # mediaan([1,3,2]) -> 2
            "modus": self._modus,                       # modus([1,2,2,3]) -> [2]
            "variantie": self._variantie,               # variantie([2,4,4,4,5,5,7,9]) -> 4.571429
            "stdafwijking": self._stdafwijking,         # stdafwijking([2,4,4,4,5,5,7,9]) -> 2.13809
            "regressie": self._regressie,               # regressie([1,2,3],[2,4,6]) -> {helling, snijpunt}
            "correlatie": self._correlatie,             # correlatie([1,2,3],[2,4,6]) -> 1.0
            "faculteit": self._faculteit,               # faculteit(5) -> 120
            "combinaties": self._combinaties,           # combinaties(5,2) -> 10
            "permutaties": self._permutaties,           # permutaties(5,2) -> 20
            "binomiaal": self._binomiaal,               # binomiaal(10,3,0.5) -> kans
            "normaal": self._normaal,                   # normaal(0) -> 0.5

            # Fase 4, punt 10 — Symbolische algebra (via SymPy)
            "differentiate": self._differentiate,       # differentiate(x^3+2x) -> "3x^2 + 2"
            "integrate_sym": self._integrate_sym,       # integrate_sym(x^2) -> "x^3/3"
            "simplify_sym": self._simplify_sym,         # simplify_sym(sin(x)^2+cos(x)^2) -> "1"
            "expand_sym": self._expand_sym,             # expand_sym((x+1)^2) -> "x^2 + 2x + 1"
            "factor_sym": self._factor_sym,             # factor_sym(x^2-4) -> "(x-2)(x+2)"
            "solve_sym": self._solve_sym,               # solve_sym(x^2-5x+6=0) -> "x = 2 of x = 3"
            "solve_stelsel": self._solve_stelsel,       # solve_stelsel(x+y=10, x-y=2) -> "x = 6, y = 4

            # Fase 4, punt 11 — Fysica-engine, 100% puur symbolisch/numeriek
            "kracht": self._kracht,                                 # kracht(1000, 3) -> 3000 N
            "energie_kinetisch": self._energie_kinetisch,           # energie_kinetisch(5, 10) -> 250 J
            "energie_potentieel": self._energie_potentieel,         # energie_potentieel(2, 10) -> 196.2 J
            "arbeid": self._arbeid,                                 # arbeid(50, 3) -> 150 J
            "snelheid_na": self._snelheid_na,                       # snelheid_na(0, 9.81, 3) -> 29.43 m/s
            "afstand_na": self._afstand_na,                         # afstand_na(20, -5, 4) -> 40 m
            "projectiel": self._projectiel,                         # projectiel(20, 45) -> bereik/hoogte/vluchttijd
            "val_met_weerstand": self._val_met_weerstand,           # simulatie via numerieke integratie

            # Fase 5, punt 12 — Getaltheorie & combinatoriek
            "is_priem": self._is_priem,                 # is_priem(17) -> True
            "priemgetallen": self._priemgetallen,       # priemgetallen(30) -> [2,3,5,7,...,29]
            "ggd": self._ggd,                           # ggd(48, 18) -> 6
            "kgv": self._kgv,                           # kgv(4, 6) -> 12
            "modulo": self._modulo,                     # modulo(17, 5) -> 2

            # Fase 5, punt 14 — Extra eenheden: talstelsel-conversies
            "naar_binair": self._naar_binair,           # naar_binair(255) -> "11111111"
            "naar_octaal": self._naar_octaal,           # naar_octaal(255) -> "377"
            "naar_hex": self._naar_hex,                 # naar_hex(255) -> "ff"
            "vanuit_talstelsel": self._vanuit_talstelsel,  # vanuit_talstelsel("ff", 16) -> 255

            # Fase 5, punt 15 — Klassieke CS-algoritmes
            "binary_search": self._binary_search,       # binary_search([1,3,5,7], 5) -> 2
            "bubble_sort": self._bubble_sort,           # bubble_sort([5,2,8,1]) -> [1,2,5,8]
            "quick_sort": self._quick_sort,             # quick_sort([5,2,8,1]) -> [1,2,5,8]
            "bfs": self._bfs,                           # bfs({"A":["B"]}, "A") -> ["A","B"]
            "dfs": self._dfs,                           # dfs({"A":["B"]}, "A") -> ["A","B"]
            "dijkstra": self._dijkstra,                 # dijkstra({"A":{"B":4}}, "A") -> {"A":0,"B":4}
            "levenshtein": self._levenshtein,           # levenshtein("kitten","sitting") -> 3

            # Fase 5, punt 16 — Afronding & precisie
            "significante_cijfers": self._significante_cijfers,  # significante_cijfers(123456,3) -> 123000
            "stel_precisie_in": self._stel_precisie_in,          # stel_precisie_in(3)
            "reset_precisie": self._reset_precisie,              # reset_precisie()

            # Fase 5, punt 18 — Breuken als exact type
            "breuk": self._breuk,                       # breuk(1, 3) -> 1/3 (exact)

            # Fase 5, punt 19 — Reeksen/rijen
            "som_reeks": self._som_reeks,               # som_reeks(1, 100) -> 5050
            "sigma": self._sigma,                       # sigma(x^2, 1, 5) -> 55
            "meetkundige_reeks": self._meetkundige_reeks,  # meetkundige_reeks(1, 2, 5) -> 31

            # Fase 5, punt 20 — Eenvoudige kansrekening (discreet)
            "kans_dobbelsteen": self._kans_dobbelsteen,  # kans_dobbelsteen(2, 7) -> kans
            "kans_kaart": self._kans_kaart,              # kans_kaart(4, 52, 5) -> kans
        }
        # constante waarden
        self.consts = {
            "pi": math.pi,
            "e": math.e
        }

        # SI-basiseenheden
        base_units = {
            "m":   ({"m": 1}, 1),
            # BUGFIX (1 aug 2026): "g" (gram) ontbrak als grondeenheid.
            # "kg" stond hier met factor 1, waardoor het prefix-systeem
            # hieronder er bovenop bouwde en onzinnige combinaties als
            # "kkg"/"mkg" genereerde in plaats van het verwachte/normale
            # "g"/"mg". Nu is "g" de grondeenheid (SI-conventie: kilogram
            # is de enige basiseenheid met prefix erin), en "kg" blijft
            # apart bestaan als alias voor compatibiliteit met bestaande
            # code/tests.
            "g":   ({"kg": 1}, 0.001),
            "kg":  ({"kg": 1}, 1),
            "s":   ({"s": 1}, 1),
            "A":   ({"A": 1}, 1),
            "K":   ({}, 1),
            "mol": ({"mol": 1}, 1),
            "cd":  ({"cd": 1}, 1),

            # niet‑SI maar handig: uur
            "h":   ({"s": 1}, 3600),
        }

        # SI-afgeleide eenheden
        derived_units = {
            "Hz":  ({"s": -1}, 1),
            "N":   ({"kg": 1, "m": 1, "s": -2}, 1),
            "Pa":  ({"kg": 1, "m": -1, "s": -2}, 1),
            "J":   ({"kg": 1, "m": 2, "s": -2}, 1),
            "W":   ({"kg": 1, "m": 2, "s": -3}, 1),
            "C":   ({"A": 1, "s": 1}, 1),
            "V":   ({"kg": 1, "m": 2, "s": -3, "A": -1}, 1),
            "F":   ({"kg": -1, "m": -2, "s": 4, "A": 2}, 1),
            "Ω":   ({"kg": 1, "m": 2, "s": -3, "A": -2}, 1),
            "S":   ({"kg": -1, "m": -2, "s": 3, "A": 2}, 1),
            "Wb":  ({"kg": 1, "m": 2, "s": -2, "A": -1}, 1),
            "T":   ({"kg": 1, "m": 0, "s": -2, "A": -1}, 1),
            "H":   ({"kg": 1, "m": 2, "s": -2, "A": -2}, 1),
            "lm":  ({"cd": 1}, 1),
            "lx":  ({"cd": 1, "m": -2}, 1),
            "Bq":  ({"s": -1}, 1),
            "Gy":  ({"m": 2, "s": -2}, 1),
            "Sv":  ({"m": 2, "s": -2}, 1),
            "kat": ({"mol": 1, "s": -1}, 1),
            "bar": ({"kg": 1, "m": -1, "s": -2}, 1e5),
            "mbar": ({"kg": 1, "m": -1, "s": -2}, 100),
            "L": ({"m": 3}, 1e-3),
            "mL": ({"m": 3}, 1e-6),
            "rpm": ({"s": -1}, 2 * math.pi / 60),
            "Wh": ({"kg": 1, "m": 2, "s": -2}, 3600),   # 1 Wh = 3600 J
            "Ah": ({"A": 1, "s": 1}, 3600),             # 1 Ah = 3600 C

            # --------------------------------------------------------
            # UITBREIDING (1 aug 2026): veelgebruikte niet-SI eenheden
            # die ontbraken. Allemaal vaste, bekende omrekenfactoren —
            # puur symbolisch, geen enkele hiervan vereist ML/generatie.
            # --------------------------------------------------------

            # tijd (naast "h" dat al bestond)
            "min": ({"s": 1}, 60),
            "day": ({"s": 1}, 86400),
            # LET OP: bewust GEEN losse "d" voor dag toegevoegd — "d" is
            # al de deci-prefix (1e-1) in het bestaande prefix-systeem.
            # Gebruik "day" voluit om dubbelzinnigheid te vermijden.
            "week": ({"s": 1}, 604800),

            # lengte — imperial
            "mile": ({"m": 1}, 1609.344),
            "mi":   ({"m": 1}, 1609.344),
            "ft":   ({"m": 1}, 0.3048),
            "foot": ({"m": 1}, 0.3048),
            "inch": ({"m": 1}, 0.0254),
            "yard": ({"m": 1}, 0.9144),
            "yd":   ({"m": 1}, 0.9144),
            # LET OP: "nmi" (nautische mijl) NIET hier toevoegen — het
            # prefix-systeem verderop genereert automatisch "n"+"mi"
            # (nano-prefix × mile) en overschrijft een hier gedefinieerde
            # "nmi" met een compleet verkeerde waarde (zelfde soort
            # naamconflict als eerder bij "L"/"mL"). Zie de expliciete
            # herstelregel bij "herstel meter-eenheid" verderop.

            # massa — imperial
            "lb":  ({"kg": 1}, 0.45359237),
            "lbs": ({"kg": 1}, 0.45359237),
            "oz":  ({"kg": 1}, 0.028349523125),
            "ton": ({"kg": 1}, 1000),   # metrische ton
            # Fase 5, punt 14 — Extra eenheden: stone (Britse gewichts-
            # eenheid, vooral gebruikt voor lichaamsgewicht in UK/Ierland)
            "stone": ({"kg": 1}, 6.35029318),  # 1 stone = 14 lb

            # snelheid — kant-en-klaar (naast "km / h" handmatig delen)
            "kmh": ({"m": 1, "s": -1}, 1000 / 3600),
            "kph": ({"m": 1, "s": -1}, 1000 / 3600),
            "mph": ({"m": 1, "s": -1}, 1609.344 / 3600),

            # energie
            "cal":  ({"kg": 1, "m": 2, "s": -2}, 4.184),
            "kcal": ({"kg": 1, "m": 2, "s": -2}, 4184),
            "eV":   ({"kg": 1, "m": 2, "s": -2}, 1.602176634e-19),

            # druk
            "atm":  ({"kg": 1, "m": -1, "s": -2}, 101325),
            "psi":  ({"kg": 1, "m": -1, "s": -2}, 6894.757293168),
            "mmHg": ({"kg": 1, "m": -1, "s": -2}, 133.322387415),

            # volume — imperial (Amerikaanse maten)
            "gal": ({"m": 3}, 0.003785411784),
            "pt":  ({"m": 3}, 0.000473176473),
            "qt":  ({"m": 3}, 0.000946352946),

            # hoek — dimensieloos (rad is de SI-eenheid, dus factor 1;
            # deg is graden->radialen, relevant voor rotX/rotY/rotZ/rotAxis
            # die intern radialen verwachten)
            "rad": ({}, 1),
            "deg": ({}, math.pi / 180),

            # data (geen natuurkundige dimensie — eigen "byte"-dimensie)
            "byte": ({"byte": 1}, 1),
            "kB":   ({"byte": 1}, 1000),
            "MB":   ({"byte": 1}, 1000000),
            "GB":   ({"byte": 1}, 1000000000),
        }

        prefixes = {
            "Y": 1e24,  "Z": 1e21,  "E": 1e18,  "P": 1e15,  "T": 1e12,
            "G": 1e9,   "M": 1e6,   "k": 1e3,   "h": 1e2,   "da": 1e1,
            "d": 1e-1,  "c": 1e-2,  "m": 1e-3,  "u": 1e-6,  "µ": 1e-6,
            "n": 1e-9,  "p": 1e-12, "f": 1e-15, "a": 1e-18, "z": 1e-21, "y": 1e-24
        }

        self.units = {}

        # 1. basiseenheden (met lowercase alias)
        for name, (dims, factor) in base_units.items():
            self.units[name] = (dims, factor)
            self.units[name.lower()] = (dims, factor)

        # 2. afgeleide eenheden (GEEN lowercase alias → voorkomt 'pa' en 'h'-conflict)
        for name, (dims, factor) in derived_units.items():
            self.units[name] = (dims, factor)

        # 3. prefix-eenheden genereren
        for prefix, pfactor in prefixes.items():

            # base units (met lowercase alias)
            for unit, (dims, factor) in base_units.items():
                if prefix == "m" and unit == "m":
                    continue
                pname = prefix + unit
                # blokkeer temperatuur-eenheden
                if pname in ("degC", "degF"):
                    continue
                self.units[pname] = (dims, factor * pfactor)
                self.units[pname.lower()] = (dims, factor * pfactor)

            # derived units (GEEN lowercase alias → voorkomt 'Pa' vs 'pA')
            for unit, (dims, factor) in derived_units.items():
                pname = prefix + unit
                # blokkeer temperatuur-eenheden
                if pname in ("degC", "degF"):
                    continue
                self.units[pname] = (dims, factor * pfactor)

                # BUGFIX (1 aug 2026): "L" (liter) is de enige derived
                # unit waarvoor de veelgebruikte kleine-letter-schrijfwijze
                # (ml, cl, dl) geen risico op verwarring geeft — anders
                # dan bv. Pa/pA. Zonder deze uitzondering bestond enkel
                # de correcte SI-notatie "mL"/"cL", niet de in de praktijk
                # vaker getypte "ml"/"cl".
                if unit == "L":
                    self.units[pname.lower()] = (dims, factor * pfactor)

        # herstel meter-eenheid
        self.units["m"] = ({"m": 1}, 1)
        self.units["meter"] = ({"m": 1}, 1)

        self.units["m3"] = ({"m": 3}, 1)
        self.units["m^3"] = ({"m": 3}, 1)
        self.units["m**3"] = ({"m": 3}, 1)
        self.units["m2"] = ({"m": 2}, 1)
        self.units["m^2"] = ({"m": 2}, 1)

        # Fase 5, punt 14 — Extra eenheden: "nmi" (nautische mijl) moet
        # HIER, na het prefix-systeem, expliciet ingesteld worden — zie
        # de toelichting bij "lengte — imperial" hierboven over waarom
        # het niet in derived_units kan staan (wordt anders overschreven
        # door "n" (nano-prefix) + "mi" (mile), met een compleet
        # verkeerde waarde als gevolg).
        self.units["nmi"] = ({"m": 1}, 1852)

    import re

    def preprocess(self, expr):
        # Fase 5, punt 13 — Complexe getallen: de imaginaire eenheid "i"
        # (wiskundige standaardnotatie, bv. "3+4i") wordt hier vertaald
        # naar een TIJDELIJKE, veilige placeholder ("__IMAG__"), niet
        # meteen naar Python's "j"-notatie. Reden: als we hier al "j"
        # zouden schrijven, zou de latere eenheden-regex verderop in deze
        # functie (die "getal+letter" als eenheid interpreteert, bv.
        # "5m" → "(5*m)") een kale "4j" ten onrechte ook als "4 van
        # eenheid j" behandelen en er "(4*j)" van maken — exact hetzelfde
        # soort conflict als de eerdere "3x^2"-bug. "__IMAG__" bevat een
        # underscore, die niet in de eenheden-regex' letter-klasse zit,
        # en blijft daardoor ongemoeid tot de allerlaatste regel van deze
        # functie, waar we het pas definitief naar "j" omzetten.
        # Twee gevallen: "4i" (getal direct voor de i) en een losse "i"
        # (zonder getal ervoor, bv. in "3+i" of "i" alleen) — die laatste
        # betekent impliciet "1i".
        expr = re.sub(r'(\d+(\.\d+)?)\s*i\b', r'\1__IMAG__', expr)
        expr = re.sub(r'(?<![\w.])i\b', '1__IMAG__', expr)

        # Fase 5, punt 17 — Percentages als eersteklas notatie: "20%"
        # betekent "20/100" (0.20). Puur syntactische suiker rond
        # bestaande deling — geen nieuwe rekenlogica. Moet vroeg in de
        # pipeline gebeuren, vóór eventuele andere regels een kans
        # krijgen om het "%"-teken verkeerd te interpreteren.
        expr = re.sub(r'(\d+(\.\d+)?)\s*%', r'(\1/100)', expr)

        # temperatuur: °C en °F → tokens zonder speciale tekens
        expr = expr.replace("°C", "degC")
        expr = expr.replace("°F", "degF")
        expr = expr.replace("°c", "degC")
        expr = expr.replace("°f", "degF")

        # superscripts → normale exponenten
        superscripts = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
        expr = expr.translate(superscripts)
        # 1b. getal-exponent zonder ^ → voeg ^ toe
        #    voorbeelden: 10-4 → 10^-4
        # BUGFIX (Fase 3, Algebra-module): zonder de (?<!\^) negative
        # lookbehind greep deze regel ook in bij expressies als "x^2-4"
        # (bedoeld als x²-4, dus x-kwadraat MIN vier) — die had al een
        # eigen "^" vlak ervoor staan, maar de regel voegde er stiekem
        # nóg een "^" bovenop toe en maakte er "x^2^-4" (x tot de macht
        # (2 tot de macht -4)) van, wiskundig compleet iets anders. Met
        # de lookbehind slaat de regel niet meer toe zodra er al een "^"
        # vlak vóór het eerste getal staat.
        expr = re.sub(r'(?<!\^)(\d+)-(\d+)', r'\1^-\2', expr)

        # 1. unit + exponent → unit^exponent
        #    voorbeelden: m3 → m^3, m2 → m^2, s-1 → s^-1
        # BUGFIX (Fase 3, Calculus-module): zonder de (?!\w*\() negative
        # lookahead greep deze regel ook in bij functienamen die op een
        # cijfer eindigen, bv. "dv_rk4(...)" → "dv_rk^4(...)" (fout, want
        # "^" wordt later "**" en "dv_rk" bestaat niet als functienaam).
        # Met de lookahead slaat de regel niet meer toe als er verderop
        # (evt. na nog meer letters/cijfers) een "(" volgt — dat betekent
        # namelijk een functie-aanroep, geen eenheid-met-macht.
        expr = re.sub(r'([A-Za-z]+)(\d+)(?!\w*\()', r'\1^\2', expr)
        expr = re.sub(r'([A-Za-z]+)-(\d+)(?!\w*\()', r'\1^-\2', expr)

        # 2. µ → u
        expr = expr.replace("µ", "u")

        # 3. '3x5' → '3*5'
        expr = re.sub(r'(\d)\s*[xX]\s*(\d)', r'\1*\2', expr)

         # 4. alias-operatoren
        expr = expr.replace(" x ", " * ")
        expr = expr.replace("×", "*")
        # BUGFIX (Fase 5, punt 15 — CS-algoritmes): zonder de negative
        # lookbehind/lookahead greep deze regel ook in bij dict-syntax
        # (bv. bfs()/dfs()/dijkstra()'s graaf-argument, {"A": ["B","C"]}),
        # en veranderde de dubbele punt na een dict-key ten onrechte in
        # een deelteken — {"A": [...]} werd zo onleesbare, kapotte syntax.
        # Nu slaat de regel niet meer toe als de ":" direct voorafgegaan
        # wordt door een aanhalingsteken (dict-key) of gevolgd wordt door
        # een aanhalingsteken/haakje/accolade (dict-value die met zo'n
        # teken begint) — enkel een kale "getal : getal"-breuknotatie
        # (bv. "10:4") wordt nog vervangen.
        expr = re.sub(r'(?<!["\'])\s*:\s*(?!\s*["\'\[{])', '/', expr)
        expr = expr.replace("^", "**")

        # 5. detecteer getal + unit (alleen letters, maar NIET splitsen)
        #    dit matcht 5m, 10km, 3mw, 12uf, 1pa, 50km/h
        # 1) getal + unit zonder spatie (1m, 50km/h, 250mL)
        #    BUGFIX (1 aug 2026): haakjes toegevoegd — zonder haakjes groepeerde
        #    "3m / 2s" als ((3*m)/2)*s door gelijke */-voorrang, wat een
        #    verkeerde eenheid opleverde (m·s i.p.v. m/s of m·s^-1)
        # BUGFIX (Fase 4, punt 10): zonder de (?=\*\*)-uitzondering hierna
        # werd bv. "3x^2" (bedoeld als 3·x², de coëfficiënt 3 maal x in het
        # kwadraat) fout gegroepeerd tot "(3*x)**2" = 9x² — want "^" was op
        # dat moment al "**" geworden (stap 4 hierboven), en deze regel zag
        # enkel het losse stuk "3x" zonder te beseffen dat de macht ERNA
        # bij "x" alleen hoort, niet bij "3x" samen. We splitsen dit nu in
        # twee gevallen: staat er een "**" direct achter de match, dan komt
        # er enkel een "*" tussen getal en letter (geen haakjes om het
        # geheel) — anders (het echte eenheden-geval, bv. "5m") blijft het
        # bestaande haakjes-gedrag ongewijzigd.
        expr = re.sub(r'(\d+(\.\d+)?)([A-Za-zµ][A-Za-zµ/]*)(?=\*\*)', r'\1*\3', expr)
        expr = re.sub(r'(\d+(\.\d+)?)([A-Za-zµ][A-Za-zµ/]*)(?!\*\*)', r'(\1*\3)', expr)

        # 2) getal + spatie + unit (1 bar, 250 mL, 60 rpm, 1 Wh, 2.5 Ah)
        # BUGFIX (Fase 4, punt 10): zelfde reden als hierboven, nu voor de
        # variant MET spatie (bv. "3 x^2").
        expr = re.sub(r'(\d+(\.\d+)?)[ ]+([A-Za-zµ][A-Za-zµ/]*)(?=\*\*)', r'\1*\3', expr)
        expr = re.sub(r'(\d+(\.\d+)?)[ ]+([A-Za-zµ][A-Za-zµ/]*)(?!\*\*)', r'(\1*\3)', expr)

        # Fase 5, punt 13 — Complexe getallen: nu pas, als allerlaatste
        # stap, zetten we de "__IMAG__"-placeholder (zie bovenaan deze
        # functie) definitief om naar Python's "j"-notatie. Alle eerdere
        # preprocess-stappen (eenheden, machten, enz.) hebben de
        # placeholder niet meer kunnen aanraken, dus "4__IMAG__" wordt nu
        # veilig "4j" — een geldige Python complex-literal.
        expr = expr.replace("__IMAG__", "j")

        return expr
        
    def _dims_to_string(self, dims):
        if not dims:
            return ""
        parts = []
        for unit, exp in dims.items():
            if exp == 1:
                parts.append(unit)
            else:
                parts.append(f"{unit}^{exp}")
        return "·".join(parts)
        
    def _dot(self, a, b):
        if not (isinstance(a, list) and isinstance(b, list)):
            raise ValueError("dot verwacht twee vectoren")
        if len(a) != len(b):
            raise ValueError("dot: vectoren moeten even lang zijn")
        return sum(x * y for x, y in zip(a, b))

    def _norm(self, v):
        if not isinstance(v, list):
            raise ValueError("norm verwacht een vector")
        return math.sqrt(sum(x * x for x in v))

    def _cross(self, a, b):
        if not (isinstance(a, list) and isinstance(b, list)):
            raise ValueError("cross verwacht twee vectoren")

        if len(a) != 3 or len(b) != 3:
            raise ValueError("cross: vectoren moeten lengte 3 hebben")

        ax, ay, az = a
        bx, by, bz = b

        return [
            ay * bz - az * by,
            az * bx - ax * bz,
            ax * by - ay * bx
        ]

    def _unit(self, v):
        if not isinstance(v, list):
            raise ValueError("unit verwacht een vector")

        n = self._norm(v)
        if n == 0:
            raise ValueError("unit: nulvector heeft geen richting")

        return [x / n for x in v]

    def _proj(self, a, b):
        if not (isinstance(a, list) and isinstance(b, list)):
            raise ValueError("proj verwacht twee vectoren")

        if len(a) != len(b):
            raise ValueError("proj: vectoren moeten even lang zijn")

        dot = self._dot(a, b)
        norm_sq = self._dot(b, b)

        if norm_sq == 0:
            raise ValueError("proj: de tweede vector is een nulvector")

        scale = dot / norm_sq
        return [scale * x for x in b]

    def _transpose(self, M):
        if not isinstance(M, list) or not all(isinstance(row, list) for row in M):
            raise ValueError("transpose verwacht een matrix")

        # lege matrix
        if len(M) == 0:
            return []

        # controle: alle rijen even lang
        row_len = len(M[0])
        if any(len(row) != row_len for row in M):
            raise ValueError("transpose: onregelmatige matrix")

        # transponeren
        return [[M[i][j] for i in range(len(M))] for j in range(row_len)]

    def eval_expr(self, expr):
        # UITZONDERING (Fase 4, punt 10 — solve_sym): een vergelijking als
        # "solve_sym(x**2-5*x+6 = 0)" bevat een "="-teken, en dat is geen
        # geldige Python-eval-expressie — ast.parse(mode="eval") zou hier
        # meteen op stuklopen, VOOR we ook maar bij _eval()'s bestaande
        # functie-routering geraken. Daarom vangen we dit specifieke
        # geval hier al af, met een simpele regex die enkel de inhoud
        # tussen de buitenste haakjes van solve_sym(...) plukt en die
        # rechtstreeks (als ruwe string, nog steeds via Nova's eigen
        # beveiligde AST-parser in _sympy_parse — zie _solve_sym) aan de
        # symbolische oplosser doorgeeft.
        solve_sym_match = re.match(r"^solve_sym\s*\((.*)\)\s*$", expr.strip())
        if solve_sym_match:
            return self._solve_sym(solve_sym_match.group(1))

        # UITZONDERING (solve_stelsel, 2 aug 2026): zelfde reden als
        # hierboven bij solve_sym, maar dan met TWEE "="-tekens (één per
        # vergelijking in het stelsel), bv.
        # "solve_stelsel(x+y=10, x-y=2)".
        solve_stelsel_match = re.match(r"^solve_stelsel\s*\((.*)\)\s*$", expr.strip())
        if solve_stelsel_match:
            return self._solve_stelsel(solve_stelsel_match.group(1))

        node = ast.parse(expr, mode="eval").body
        return self._eval(node)

    def _det(self, M):
        # validatie
        if not isinstance(M, list) or not all(isinstance(row, list) for row in M):
            raise ValueError("det verwacht een matrix")

        n = len(M)
        if n == 0:
            raise ValueError("det: lege matrix heeft geen determinant")

        # controle: vierkante matrix
        if any(len(row) != n for row in M):
            raise ValueError("det: matrix moet vierkant zijn")

        # 1×1 matrix
        if n == 1:
            return M[0][0]

        # 2×2 matrix
        if n == 2:
            return M[0][0]*M[1][1] - M[0][1]*M[1][0]

        # algemene n×n matrix (Laplace-expansie)
        det_sum = 0
        for col in range(n):
            # submatrix maken zonder rij 0 en kolom col
            sub = [
                [M[r][c] for c in range(n) if c != col]
                for r in range(1, n)
            ]
            sign = -1 if col % 2 else 1
            det_sum += sign * M[0][col] * self._det(sub)

        return det_sum

    def _inverse(self, M):
        # validatie
        if not isinstance(M, list) or not all(isinstance(row, list) for row in M):
            raise ValueError("inverse verwacht een matrix")

        n = len(M)
        if n == 0:
            raise ValueError("inverse: lege matrix heeft geen inverse")

        # controle: vierkante matrix
        if any(len(row) != n for row in M):
            raise ValueError("inverse: matrix moet vierkant zijn")

        # determinant
        detM = self._det(M)
        if detM == 0:
            raise ValueError("inverse: matrix is singulier (det = 0)")

        # 1×1 matrix
        if n == 1:
            return [[1 / detM]]

        # cofactor-matrix
        cof = []
        for r in range(n):
            row = []
            for c in range(n):
                # submatrix zonder rij r en kolom c
                sub = [
                    [M[i][j] for j in range(n) if j != c]
                    for i in range(n) if i != r
                ]
                sign = -1 if (r + c) % 2 else 1
                row.append(sign * self._det(sub))
            cof.append(row)

        # adjoint = transpose(cofactor-matrix)
        adj = self._transpose(cof)

        # inverse = (1/det) * adjoint
        return [[adj[i][j] / detM for j in range(n)] for i in range(n)]

    def _rotX(self, theta):
        # hoek in radialen
        if not isinstance(theta, (int, float)):
            raise ValueError("rotX verwacht een hoek in radialen")

        c = math.cos(theta)
        s = math.sin(theta)

        return [
            [1, 0, 0],
            [0, c, -s],
            [0, s,  c]
        ]

    def _rotY(self, theta):
        if not isinstance(theta, (int, float)):
            raise ValueError("rotY verwacht een hoek in radialen")

        c = math.cos(theta)
        s = math.sin(theta)

        return [
            [ c, 0, s],
            [ 0, 1, 0],
            [-s, 0, c]
        ]

    def _rotZ(self, theta):
        if not isinstance(theta, (int, float)):
            raise ValueError("rotZ verwacht een hoek in radialen")

        c = math.cos(theta)
        s = math.sin(theta)

        return [
            [ c, -s, 0],
            [ s,  c, 0],
            [ 0,  0, 1]
        ]

    def _rotAxis(self, axis, theta):
        # validatie
        if not (isinstance(axis, list) and len(axis) == 3):
            raise ValueError("rotAxis verwacht een vector van lengte 3")

        if not isinstance(theta, (int, float)):
            raise ValueError("rotAxis verwacht een hoek in radialen")

        # normaliseer de as
        x, y, z = axis
        n = math.sqrt(x*x + y*y + z*z)
        if n == 0:
            raise ValueError("rotAxis: rotatie-as mag geen nulvector zijn")

        x /= n
        y /= n
        z /= n

        c = math.cos(theta)
        s = math.sin(theta)
        t = 1 - c

        # Rodrigues' rotatiematrix
        return [
            [t*x*x + c,     t*x*y - s*z,   t*x*z + s*y],
            [t*x*y + s*z,   t*y*y + c,     t*y*z - s*x],
            [t*x*z - s*y,   t*y*z + s*x,   t*z*z + c]
        ]

    def _solve(self, A, b):
        # validatie
        if not isinstance(A, list) or not all(isinstance(row, list) for row in A):
            raise ValueError("solve verwacht een matrix A")

        if not isinstance(b, list):
            raise ValueError("solve verwacht een vector b")

        n = len(A)
        if any(len(row) != n for row in A):
            raise ValueError("solve: matrix A moet vierkant zijn")

        if len(b) != n:
            raise ValueError("solve: dimensies van A en b komen niet overeen")

        # x = inverse(A) * b
        invA = self._inverse(A)
        return [sum(invA[i][j] * b[j] for j in range(n)) for i in range(n)]

    def _solveGauss(self, A, b):
        # validatie
        if not isinstance(A, list) or not all(isinstance(row, list) for row in A):
            raise ValueError("solveGauss verwacht een matrix A")

        if not isinstance(b, list):
            raise ValueError("solveGauss verwacht een vector b")

        n = len(A)
        if any(len(row) != n for row in A):
            raise ValueError("solveGauss: matrix A moet vierkant zijn")

        if len(b) != n:
            raise ValueError("solveGauss: dimensies van A en b komen niet overeen")

        # Maak kopieën zodat we A en b niet wijzigen
        M = [row[:] for row in A]
        v = b[:]

        # --- Voorwaartse eliminatie ---
        for i in range(n):
            # pivot zoeken (als M[i][i] = 0 is)
            if M[i][i] == 0:
                for r in range(i+1, n):
                    if M[r][i] != 0:
                        M[i], M[r] = M[r], M[i]
                        v[i], v[r] = v[r], v[i]
                        break
                else:
                    raise ValueError("solveGauss: matrix is singulier (geen unieke oplossing)")

            # elimineer onder de pivot
            for r in range(i+1, n):
                factor = M[r][i] / M[i][i]
                for c in range(i, n):
                    M[r][c] -= factor * M[i][c]
                v[r] -= factor * v[i]

        # --- Achterwaartse substitutie ---
        x = [0] * n
        for i in reversed(range(n)):
            if M[i][i] == 0:
                raise ValueError("solveGauss: matrix is singulier (geen unieke oplossing)")

            s = sum(M[i][j] * x[j] for j in range(i+1, n))
            x[i] = (v[i] - s) / M[i][i]

        return x

    def _identity(self, n):
        if not isinstance(n, int) or n <= 0:
            raise ValueError("identity verwacht een positief geheel getal")

        return [[1 if i == j else 0 for j in range(n)] for i in range(n)]

    # -----------------------------------------------------------
    # Fase 3 — Algebra-module (numeriek), 100% puur symbolisch
    # -----------------------------------------------------------

    def _solveQuadratic(self, a, b, c):
        # ax^2 + bx + c = 0
        if not all(isinstance(v, (int, float)) for v in (a, b, c)):
            raise ValueError("solveQuadratic verwacht drie getallen: a, b, c")

        if a == 0:
            # eigenlijk geen kwadratische maar een lineaire vergelijking
            if b == 0:
                raise ValueError("solveQuadratic: a en b zijn beide 0, geen oplosbare vergelijking")
            return [-c / b]

        discriminant = b ** 2 - 4 * a * c

        if discriminant < 0:
            # UPDATE (Fase 5, punt 13 — Complexe getallen, nu gebouwd):
            # eerder gaf Nova hier een foutmelding, want complexe
            # getallen bestonden nog niet. Nu tonen we het correcte
            # complexe antwoord, via cmath.sqrt() (Python's ingebouwde
            # complexe-wiskunde-module, i.p.v. math.sqrt() dat hier zou
            # falen op een negatief getal).
            sqrt_d = cmath.sqrt(discriminant)
            x1 = (-b + sqrt_d) / (2 * a)
            x2 = (-b - sqrt_d) / (2 * a)
            return sorted([x1, x2], key=lambda z: (z.real, z.imag))

        if discriminant == 0:
            return [-b / (2 * a)]

        sqrt_d = math.sqrt(discriminant)
        x1 = (-b + sqrt_d) / (2 * a)
        x2 = (-b - sqrt_d) / (2 * a)
        return sorted([x1, x2])

    def _newton(self, f, x0, tol=1e-10, max_iter=100):
        # Newton-Raphson: zoekt een wortel (f(x)=0) van een vrije expressie
        # met x, bv. newton(x^2 - 4, 1) → zoekt vanaf startwaarde x0=1
        if not callable(f):
            raise ValueError("newton verwacht als eerste argument een expressie met x, bv. \"x^2 - 4\"")
        if not isinstance(x0, (int, float)):
            raise ValueError("newton verwacht een numerieke startwaarde x0")

        h = 1e-6  # kleine stap voor numerieke afgeleide
        x = x0

        for _ in range(max_iter):
            fx = f(x)
            # numerieke afgeleide via centraal verschil
            dfx = (f(x + h) - f(x - h)) / (2 * h)

            if dfx == 0:
                raise ValueError("newton: afgeleide is 0, geen verdere toenadering mogelijk (probeer een andere startwaarde)")

            x_nieuw = x - fx / dfx

            if abs(x_nieuw - x) < tol:
                return x_nieuw

            x = x_nieuw

        raise ValueError(f"newton: geen convergentie na {max_iter} iteraties (probeer een andere startwaarde)")

    def _polyeval(self, f, x):
        # Evalueert een vrije expressie met x op een specifiek punt,
        # bv. polyeval(x^3 + 2x - 5, 3) → vult x=3 in
        if not callable(f):
            raise ValueError("polyeval verwacht als eerste argument een expressie met x, bv. \"x^3 + 2x - 5\"")
        if not isinstance(x, (int, float)):
            raise ValueError("polyeval verwacht een numerieke waarde voor x")

        return f(x)

    def _extremum(self, f, start, eind, stappen=1000):
        # Zoekt numeriek het minimum en maximum van een vrije expressie
        # met x binnen een bereik [start, eind], bv.
        # extremum(-x^2 + 4x, 0, 5) → zoekt minima/maxima tussen x=0 en x=5
        if not callable(f):
            raise ValueError("extremum verwacht als eerste argument een expressie met x, bv. \"-x^2 + 4x\"")
        if not all(isinstance(v, (int, float)) for v in (start, eind)):
            raise ValueError("extremum verwacht numerieke grenzen start en eind")
        if start >= eind:
            raise ValueError("extremum: start moet kleiner zijn dan eind")
        if not isinstance(stappen, int) or stappen < 2:
            raise ValueError("extremum: stappen moet een geheel getal ≥ 2 zijn")

        beste_min = (start, f(start))
        beste_max = (start, f(start))

        # BUGFIX: x via de iteratie-index berekenen i.p.v. herhaaldelijk
        # "x += stap" op te tellen — dat laatste stapelt kleine floating-
        # point-afrondingsfouten op, waardoor het randpunt "eind" (bv. 5)
        # er als 4.999999999999916 uitkwam i.p.v. netjes 5.
        for i in range(stappen + 1):
            x = start + (eind - start) * i / stappen
            waarde = f(x)
            if waarde < beste_min[1]:
                beste_min = (x, waarde)
            if waarde > beste_max[1]:
                beste_max = (x, waarde)

        # Afronden op 6 decimalen: haalt de laatste restjes floating-
        # point-ruis weg (bv. 1.9999999999999793 → 2.0) zonder dat het
        # numerieke resultaat merkbaar minder nauwkeurig wordt.
        return {
            "min": {"x": round(beste_min[0], 6), "waarde": round(beste_min[1], 6)},
            "max": {"x": round(beste_max[0], 6), "waarde": round(beste_max[1], 6)},
        }

    # -----------------------------------------------------------
    # Fase 3, punt 8 — Calculus-module (numeriek), 100% puur symbolisch
    # -----------------------------------------------------------

    def _afgeleide(self, f, x):
        # Numerieke afgeleide via centraal verschil: f'(x) ≈ (f(x+h)-f(x-h)) / 2h
        # bv. afgeleide(x^2, 3) → 6.0 (helling van x² in het punt x=3)
        if not callable(f):
            raise ValueError("afgeleide verwacht als eerste argument een expressie met x, bv. \"x^2\"")
        if not isinstance(x, (int, float)):
            raise ValueError("afgeleide verwacht een numerieke waarde voor x")

        h = 1e-6
        resultaat = (f(x + h) - f(x - h)) / (2 * h)
        return round(resultaat, 6)

    def _integraal(self, f, a, b, stappen=1000):
        # Numerieke integraal via de regel van Simpson (nauwkeuriger dan
        # trapezium-regel bij hetzelfde aantal stappen), bv.
        # integraal(x^2, 0, 3) → 9.0 (oppervlakte onder x² tussen 0 en 3)
        if not callable(f):
            raise ValueError("integraal verwacht als eerste argument een expressie met x, bv. \"x^2\"")
        if not all(isinstance(v, (int, float)) for v in (a, b)):
            raise ValueError("integraal verwacht numerieke grenzen a en b")
        if a >= b:
            raise ValueError("integraal: ondergrens a moet kleiner zijn dan bovengrens b")
        if not isinstance(stappen, int) or stappen < 2:
            raise ValueError("integraal: stappen moet een geheel getal ≥ 2 zijn")
        # Simpson's regel vraagt een even aantal deelintervallen
        if stappen % 2 != 0:
            stappen += 1

        h = (b - a) / stappen
        totaal = f(a) + f(b)

        for i in range(1, stappen):
            x = a + i * h
            factor = 4 if i % 2 != 0 else 2
            totaal += factor * f(x)

        resultaat = (h / 3) * totaal
        return round(resultaat, 6)

    def _limiet(self, f, x_naar, h=1e-6):
        # Benadert de limiet van een expressie met x, als x steeds dichter
        # naar x_naar nadert — van links én van rechts, bv.
        # limiet(sin(x)/x, 0) → 1.0
        if not callable(f):
            raise ValueError("limiet verwacht als eerste argument een expressie met x, bv. \"sin(x)/x\"")
        if not isinstance(x_naar, (int, float)):
            raise ValueError("limiet verwacht een numerieke waarde om naartoe te naderen")

        try:
            van_links = f(x_naar - h)
            van_rechts = f(x_naar + h)
        except (ZeroDivisionError, ValueError) as e:
            raise ValueError(f"limiet: kan de functie niet evalueren dicht bij x={x_naar} ({e})")

        # Als links en rechts duidelijk uiteenlopen, bestaat de limiet niet
        # in de gewone zin — dat melden we eerlijk i.p.v. een willekeurig
        # gemiddelde te presenteren als "het" antwoord.
        if abs(van_links - van_rechts) > 1e-3:
            raise ValueError(
                f"limiet: lijkt niet te bestaan rond x={x_naar} "
                f"(van links ≈ {round(van_links, 6)}, van rechts ≈ {round(van_rechts, 6)} — te veel verschil)"
            )

        return round((van_links + van_rechts) / 2, 6)

    def _dv_stap_euler(self, f, x0, y0, tot, stappen=1000):
        # Eén Euler-stap-methode, hergebruikt door zowel _dv_euler als
        # ter vergelijking beschikbaar; f is f(x, y) uit dy/dx = f(x, y)
        h = (tot - x0) / stappen
        x, y = x0, y0
        for _ in range(stappen):
            y = y + h * f(x, y)
            x = x + h
        return x, y

    def _dv_euler(self, f, y0, van, tot, stappen=1000):
        # Lost dy/dx = f(x, y) numeriek op met de Euler-methode (eenvoudig,
        # minder nauwkeurig — vooral nuttig om het principe te begrijpen).
        # bv. dv_euler(x - y, y0=1, van=0, tot=5)
        if not callable(f):
            raise ValueError("dv_euler verwacht als eerste argument een expressie met x én y, bv. \"x - y\"")
        if not all(isinstance(v, (int, float)) for v in (y0, van, tot)):
            raise ValueError("dv_euler verwacht numerieke waarden voor y0, van en tot")
        if van >= tot:
            raise ValueError("dv_euler: 'van' moet kleiner zijn dan 'tot'")
        if not isinstance(stappen, int) or stappen < 1:
            raise ValueError("dv_euler: stappen moet een geheel getal ≥ 1 zijn")

        _, y_eind = self._dv_stap_euler(f, van, y0, tot, stappen)
        return round(y_eind, 6)

    def _dv_rk4(self, f, y0, van, tot, stappen=1000):
        # Lost dy/dx = f(x, y) numeriek op met de Runge-Kutta 4 methode
        # (veel nauwkeuriger dan Euler bij hetzelfde aantal stappen — dit
        # is de standaardmethode in de praktijk).
        # bv. dv_rk4(x - y, y0=1, van=0, tot=5)
        if not callable(f):
            raise ValueError("dv_rk4 verwacht als eerste argument een expressie met x én y, bv. \"x - y\"")
        if not all(isinstance(v, (int, float)) for v in (y0, van, tot)):
            raise ValueError("dv_rk4 verwacht numerieke waarden voor y0, van en tot")
        if van >= tot:
            raise ValueError("dv_rk4: 'van' moet kleiner zijn dan 'tot'")
        if not isinstance(stappen, int) or stappen < 1:
            raise ValueError("dv_rk4: stappen moet een geheel getal ≥ 1 zijn")

        h = (tot - van) / stappen
        x, y = van, y0

        for _ in range(stappen):
            k1 = f(x, y)
            k2 = f(x + h / 2, y + h / 2 * k1)
            k3 = f(x + h / 2, y + h / 2 * k2)
            k4 = f(x + h, y + h * k3)
            y = y + (h / 6) * (k1 + 2 * k2 + 2 * k3 + k4)
            x = x + h

        return round(y, 6)

    def _dv(self, f, y0, van, tot, stappen=1000):
        # Gebruiksvriendelijke ingang voor differentiaalvergelijkingen:
        # gebruikt standaard RK4 (nauwkeuriger, de gangbare keuze in de
        # praktijk). Voor het eenvoudigere Euler-principe: dv_euler().
        # bv. dv(x - y, y0=1, van=0, tot=5)
        return self._dv_rk4(f, y0, van, tot, stappen)

    # -----------------------------------------------------------
    # Fase 3, punt 9 — Statistiek-module, 100% puur symbolisch/numeriek
    # -----------------------------------------------------------

    def _check_getallenlijst(self, data, naam):
        # Gedeelde validatie: hergebruikt door bijna alle statistiek-
        # functies hieronder, zodat foutmeldingen consistent zijn.
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"{naam}: verwacht een niet-lege lijst met getallen, bv. {naam}([1,2,3,4])")
        if not all(isinstance(v, (int, float)) for v in data):
            raise ValueError(f"{naam}: alle elementen in de lijst moeten getallen zijn")

    def _gemiddelde(self, data):
        # Rekenkundig gemiddelde: som van alle waarden gedeeld door het aantal
        # bv. gemiddelde([1,2,3,4]) → 2.5
        self._check_getallenlijst(data, "gemiddelde")
        return round(sum(data) / len(data), 6)

    def _mediaan(self, data):
        # De middelste waarde als je alles sorteert (of het gemiddelde van
        # de twee middelste bij een even aantal), bv. mediaan([1,3,2]) → 2
        self._check_getallenlijst(data, "mediaan")
        gesorteerd = sorted(data)
        n = len(gesorteerd)
        midden = n // 2
        if n % 2 == 1:
            return gesorteerd[midden]
        return round((gesorteerd[midden - 1] + gesorteerd[midden]) / 2, 6)

    def _modus(self, data):
        # De meest voorkomende waarde(n). Bij een gelijkspel worden alle
        # meest-voorkomende waarden teruggegeven (als lijst), zodat we niet
        # stiekem willekeurig één ervan kiezen. bv. modus([1,2,2,3]) → [2]
        self._check_getallenlijst(data, "modus")
        tellingen = {}
        for v in data:
            tellingen[v] = tellingen.get(v, 0) + 1
        max_telling = max(tellingen.values())
        return sorted([v for v, c in tellingen.items() if c == max_telling])

    def _variantie(self, data, steekproef=True):
        # Variantie: gemiddelde van de kwadratische afwijkingen t.o.v. het
        # gemiddelde. Standaard steekproefvariantie (deelt door n-1, de
        # gangbare keuze wanneer data een steekproef is uit een grotere
        # populatie — dit is de meest gebruikte variant in de praktijk).
        # Zet steekproef=False voor populatievariantie (deelt door n).
        # bv. variantie([2,4,4,4,5,5,7,9]) → 4.571429
        self._check_getallenlijst(data, "variantie")
        n = len(data)
        if steekproef and n < 2:
            raise ValueError("variantie: een steekproefvariantie vraagt minstens 2 waarden")
        gem = sum(data) / n
        kwadratensom = sum((v - gem) ** 2 for v in data)
        deler = (n - 1) if steekproef else n
        return round(kwadratensom / deler, 6)

    def _stdafwijking(self, data, steekproef=True):
        # Standaardafwijking = wortel van de variantie, bv.
        # stdafwijking([2,4,4,4,5,5,7,9]) → 2.138090
        return round(math.sqrt(self._variantie(data, steekproef)), 6)

    def _regressie(self, x_data, y_data):
        # Lineaire regressie via de kleinste-kwadratenmethode: zoekt de
        # rechte y = a*x + b die het beste bij de punten past.
        # bv. regressie([1,2,3,4], [2,4,6,8]) → {"helling": 2.0, "snijpunt": 0.0}
        self._check_getallenlijst(x_data, "regressie (x)")
        self._check_getallenlijst(y_data, "regressie (y)")
        if len(x_data) != len(y_data):
            raise ValueError("regressie: x_data en y_data moeten even lang zijn (elk punt heeft een x én een y)")
        if len(x_data) < 2:
            raise ValueError("regressie: minstens 2 punten nodig om een rechte te bepalen")

        n = len(x_data)
        gem_x = sum(x_data) / n
        gem_y = sum(y_data) / n

        teller = sum((x_data[i] - gem_x) * (y_data[i] - gem_y) for i in range(n))
        noemer = sum((x_data[i] - gem_x) ** 2 for i in range(n))

        if noemer == 0:
            raise ValueError("regressie: alle x-waarden zijn gelijk, geen eenduidige rechte mogelijk")

        helling = teller / noemer
        snijpunt = gem_y - helling * gem_x

        return {"helling": round(helling, 6), "snijpunt": round(snijpunt, 6)}

    def _correlatie(self, x_data, y_data):
        # Pearson-correlatiecoëfficiënt: getal tussen -1 en 1 dat aangeeft
        # hoe sterk twee datasets lineair samenhangen.
        # bv. correlatie([1,2,3,4], [2,4,6,8]) → 1.0 (perfect lineair verband)
        self._check_getallenlijst(x_data, "correlatie (x)")
        self._check_getallenlijst(y_data, "correlatie (y)")
        if len(x_data) != len(y_data):
            raise ValueError("correlatie: x_data en y_data moeten even lang zijn (elk punt heeft een x én een y)")
        if len(x_data) < 2:
            raise ValueError("correlatie: minstens 2 punten nodig")

        n = len(x_data)
        gem_x = sum(x_data) / n
        gem_y = sum(y_data) / n

        teller = sum((x_data[i] - gem_x) * (y_data[i] - gem_y) for i in range(n))
        som_kw_x = sum((v - gem_x) ** 2 for v in x_data)
        som_kw_y = sum((v - gem_y) ** 2 for v in y_data)

        if som_kw_x == 0 or som_kw_y == 0:
            raise ValueError("correlatie: alle waarden in x of y zijn gelijk, correlatie is niet gedefinieerd")

        r = teller / math.sqrt(som_kw_x * som_kw_y)
        return round(r, 6)

    def _faculteit(self, n):
        # Hulpfunctie voor combinaties/permutaties: n! = n×(n-1)×...×1
        if not isinstance(n, int) or n < 0:
            raise ValueError("faculteit verwacht een geheel getal ≥ 0")
        resultaat = 1
        for i in range(2, n + 1):
            resultaat *= i
        return resultaat

    def _combinaties(self, n, k):
        # Aantal manieren om k elementen te kiezen uit n, volgorde maakt
        # niet uit: C(n,k) = n! / (k! × (n-k)!)
        # bv. combinaties(5, 2) → 10
        if not all(isinstance(v, int) for v in (n, k)):
            raise ValueError("combinaties verwacht twee gehele getallen: n en k")
        if n < 0 or k < 0:
            raise ValueError("combinaties: n en k moeten ≥ 0 zijn")
        if k > n:
            raise ValueError("combinaties: k mag niet groter zijn dan n")
        return self._faculteit(n) // (self._faculteit(k) * self._faculteit(n - k))

    def _permutaties(self, n, k):
        # Aantal manieren om k elementen te kiezen uit n, volgorde maakt
        # WEL uit: P(n,k) = n! / (n-k)!
        # bv. permutaties(5, 2) → 20
        if not all(isinstance(v, int) for v in (n, k)):
            raise ValueError("permutaties verwacht twee gehele getallen: n en k")
        if n < 0 or k < 0:
            raise ValueError("permutaties: n en k moeten ≥ 0 zijn")
        if k > n:
            raise ValueError("permutaties: k mag niet groter zijn dan n")
        return self._faculteit(n) // self._faculteit(n - k)

    def _binomiaal(self, n, k, p):
        # Kans op precies k successen bij n onafhankelijke pogingen met
        # succeskans p per poging (bv. k keer kop bij n muntworpen).
        # bv. binomiaal(10, 3, 0.5) → kans op precies 3 keer kop bij 10 worpen
        if not all(isinstance(v, int) for v in (n, k)):
            raise ValueError("binomiaal verwacht gehele getallen voor n en k")
        if not isinstance(p, (int, float)):
            raise ValueError("binomiaal verwacht een numerieke kans p")
        if not (0 <= p <= 1):
            raise ValueError("binomiaal: p moet een kans zijn tussen 0 en 1")
        if n < 0 or k < 0 or k > n:
            raise ValueError("binomiaal: k moet tussen 0 en n liggen")

        kans = self._combinaties(n, k) * (p ** k) * ((1 - p) ** (n - k))
        return round(kans, 6)

    def _normaal(self, x, gem=0, std=1):
        # Cumulatieve kans van de normale verdeling: de kans dat een
        # willekeurige waarde uit een normaalverdeling (met gegeven
        # gemiddelde en standaardafwijking) kleiner of gelijk is aan x.
        # Gebruikt de foutfunctie (erf) uit Python's ingebouwde math-
        # module — een standaard, exacte numerieke benadering, geen ML.
        # bv. normaal(0) → 0.5 (kans dat een standaard-normale waarde ≤ 0 is)
        if not all(isinstance(v, (int, float)) for v in (x, gem, std)):
            raise ValueError("normaal verwacht numerieke waarden voor x, gemiddelde en standaardafwijking")
        if std <= 0:
            raise ValueError("normaal: standaardafwijking moet groter zijn dan 0")

        z = (x - gem) / (std * math.sqrt(2))
        kans = 0.5 * (1 + math.erf(z))
        return round(kans, 6)

    # -----------------------------------------------------------
    # Fase 4, punt 10 — Symbolische algebra (via SymPy)
    # -----------------------------------------------------------
    # LET OP — dit is de enige plek in math.py die geen 100% eigen,
    # zelfgeschreven code is: SymPy is een externe bibliotheek voor
    # symbolisch rekenen. Alle andere functies in dit bestand blijven
    # 100% eigen Python-code. Zie math_roadmap.md voor de volledige
    # afweging waarom hier bewust voor SymPy gekozen is (symbolisch,
    # geen ML/LLM — SymPy "gokt" niet, het past vaste algebraïsche
    # regels toe, net als de rest van math.py).
    #
    # VEILIGHEID: we geven NOOIT de ruwe tekst van de gebruiker
    # rechtstreeks door aan sympy.sympify() of parse_expr() — die voeren
    # intern Python's eigen eval() uit op de string, waardoor bv.
    # "__import__('os').system(...)" gewoon zou worden uitgevoerd. In
    # plaats daarvan hergebruiken we Nova's eigen, al beveiligde AST-
    # parser (ast.parse, dezelfde die _eval() ook gebruikt) en vertalen
    # we die boom zelf, knoop voor knoop, naar SymPy — met een whitelist
    # van toegestane functienamen, precies zoals _eval()'s Call-tak dat
    # al doet voor self.funcs.

    _SYMPY_TOEGESTANE_FUNCTIES = None  # wordt lazy gevuld, zie _sympy_functies()

    def _sympy_functies(self):
        # Lazy: enkel opbouwen als SymPy ook echt beschikbaar is,
        # anders zou dit al bij het opstarten van MathModule crashen
        # op een systeem zonder SymPy.
        if self._SYMPY_TOEGESTANE_FUNCTIES is None:
            self._SYMPY_TOEGESTANE_FUNCTIES = {
                "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
                "sqrt": sp.sqrt, "exp": sp.exp,
                "ln": sp.log, "log": sp.log,
                "abs": sp.Abs,
            }
        return self._SYMPY_TOEGESTANE_FUNCTIES

    def _check_sympy(self, fname):
        if not SYMPY_BESCHIKBAAR:
            raise ValueError(
                f"{fname}: SymPy is niet geïnstalleerd. Installeer het met "
                f"'pip install sympy' in Nova's virtuele omgeving en herstart Nova."
            )

    def _ast_naar_sympy(self, node, variabelen):
        # Eigen, beveiligde vertaler: AST-knoop → SymPy-object.
        # Enkel getallen, bekende variabelen, +-*/^, unair min, en een
        # whitelist van functienamen worden geaccepteerd — alles
        # daarbuiten (attribute access, imports, willekeurige
        # functie-aanroepen) wordt geweigerd met een ValueError, exact
        # zoals _eval()'s bestaande Call-tak dat al doet.
        # UPDATE (solve_stelsel, 2 aug 2026): 'variabelen' is een dict
        # (bv. {"x": x_symbool} of {"x": x_symbool, "y": y_symbool}) i.p.v.
        # een hardcoded losse 'x' — zodat dezelfde parser ook stelsels met
        # meerdere onbekenden (x én y) kan verwerken, niet enkel x alleen.
        if isinstance(node, ast.Constant):
            return sp.Number(node.value)
        if isinstance(node, ast.Num):  # oudere Python-versies
            return sp.Number(node.n)
        if isinstance(node, ast.Name):
            if node.id in variabelen:
                return variabelen[node.id]
            bekende_namen = ", ".join(f"'{v}'" for v in variabelen)
            raise ValueError(f"Onbekende naam: {node.id} (enkel {bekende_namen} is ondersteund als variabele)")
        if isinstance(node, ast.BinOp):
            links = self._ast_naar_sympy(node.left, variabelen)
            rechts = self._ast_naar_sympy(node.right, variabelen)
            if isinstance(node.op, ast.Add):
                return links + rechts
            if isinstance(node.op, ast.Sub):
                return links - rechts
            if isinstance(node.op, ast.Mult):
                return links * rechts
            if isinstance(node.op, ast.Div):
                return links / rechts
            if isinstance(node.op, ast.Pow):
                return links ** rechts
            raise ValueError("Onbekende operator in symbolische expressie")
        if isinstance(node, ast.UnaryOp):
            waarde = self._ast_naar_sympy(node.operand, variabelen)
            if isinstance(node.op, ast.USub):
                return -waarde
            if isinstance(node.op, ast.UAdd):
                return waarde
            raise ValueError("Onbekende unaire operator in symbolische expressie")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Ongeldige functie-aanroep in symbolische expressie")
            fname = node.func.id
            toegestaan = self._sympy_functies()
            if fname not in toegestaan:
                raise ValueError(f"Onbekende functie in symbolische expressie: {fname}")
            args = [self._ast_naar_sympy(a, variabelen) for a in node.args]
            return toegestaan[fname](*args)
        # Alles wat hier niet expliciet is toegestaan (Attribute, Call op
        # iets anders dan een Name, Subscript, enz.) wordt geweigerd.
        raise ValueError("Ongeldige of niet-ondersteunde symbolische expressie")

    def _sympy_parse(self, expr_str, variabelen):
        # Parseert een expressie-string (al voorbewerkt door preprocess(),
        # dus "^" is al "**") via Nova's eigen AST, NOOIT via sympify()
        # rechtstreeks op de string — zie veiligheidsuitleg hierboven.
        try:
            tree = ast.parse(expr_str, mode="eval")
        except SyntaxError:
            raise ValueError(f"Kan de expressie niet lezen: \"{expr_str}\"")
        return self._ast_naar_sympy(tree.body, variabelen)

    def _sympy_str(self, sympy_obj):
        # Vertaalt een SymPy-resultaat terug naar Nova's eigen notatie
        # (met "^" i.p.v. "**"), zodat het er hetzelfde uitziet als wat
        # de gebruiker zelf typt.
        # Fase 5, punt 13 — Complexe getallen: SymPy toont de imaginaire
        # eenheid als hoofdletter "I" (bv. "2*I" of "-I") — we vertalen
        # dat hier naar de kleine "i" die de gebruiker zelf ook intypt.
        # Veilig binnen onze functie-whitelist (sin/cos/tan/sqrt/exp/
        # log/Abs): geen van die namen bevat zelf een hoofdletter "I",
        # dus deze vervanging kan nooit per ongeluk iets anders raken.
        tekst = str(sympy_obj).replace("**", "^").replace("*", "")
        tekst = re.sub(r'\bI\b', 'i', tekst)
        return tekst

    def _differentiate(self, expr_str):
        # Symbolisch differentiëren: geeft een FORMULE terug, geen getal.
        # bv. differentiate(x^3 + 2x) → "3x^2 + 2"
        # Voor de numerieke variant (helling op één specifiek punt): afgeleide()
        self._check_sympy("differentiate")
        x = sp.symbols("x")
        expr = self._sympy_parse(expr_str, x)
        resultaat = sp.diff(expr, x)
        resultaat = sp.simplify(resultaat)
        return self._sympy_str(resultaat)

    def _integrate_sym(self, expr_str):
        # Symbolische (onbepaalde) integraal: geeft een FORMULE terug.
        # bv. integrate_sym(x^2) → "x^3/3"
        # Voor de numerieke variant (oppervlakte tussen twee punten): integraal()
        self._check_sympy("integrate_sym")
        x = sp.symbols("x")
        expr = self._sympy_parse(expr_str, {"x": x})
        resultaat = sp.integrate(expr, x)
        resultaat = sp.simplify(resultaat)
        return self._sympy_str(resultaat)

    def _simplify_sym(self, expr_str):
        # Vereenvoudigt een expressie zo veel mogelijk.
        # bv. simplify_sym(sin(x)^2 + cos(x)^2) → "1"
        self._check_sympy("simplify_sym")
        x = sp.symbols("x")
        expr = self._sympy_parse(expr_str, {"x": x})
        resultaat = sp.simplify(expr)
        return self._sympy_str(resultaat)

    def _expand_sym(self, expr_str):
        # Werkt haakjes uit.
        # bv. expand_sym((x+1)^2) → "x^2 + 2x + 1"
        self._check_sympy("expand_sym")
        x = sp.symbols("x")
        expr = self._sympy_parse(expr_str, {"x": x})
        resultaat = sp.expand(expr)
        return self._sympy_str(resultaat)

    def _factor_sym(self, expr_str):
        # Ontbindt een expressie in factoren.
        # bv. factor_sym(x^2 - 4) → "(x-2)(x+2)"
        self._check_sympy("factor_sym")
        x = sp.symbols("x")
        expr = self._sympy_parse(expr_str, {"x": x})
        resultaat = sp.factor(expr)
        return self._sympy_str(resultaat)

    def _solve_sym(self, expr_str):
        # Lost een vergelijking symbolisch/exact op — ondersteunt, dankzij
        # SymPy, ook hogere-graads vergelijkingen (niet enkel lineair/
        # kwadratisch). bv. solve_sym(x^2-5x+6=0) → "x = 2 of x = 3"
        # Voor een numerieke wortelbenadering vanaf een startwaarde: nulpunt()/newton()
        self._check_sympy("solve_sym")
        x = sp.symbols("x")

        if "=" in expr_str:
            links_str, rechts_str = expr_str.split("=", 1)
            links = self._sympy_parse(links_str.strip(), {"x": x})
            rechts = self._sympy_parse(rechts_str.strip(), {"x": x})
        else:
            links = self._sympy_parse(expr_str.strip(), {"x": x})
            rechts = sp.Number(0)

        vergelijking = sp.Eq(links, rechts)

        try:
            oplossingen = sp.solve(vergelijking, x)
        except NotImplementedError:
            raise ValueError(
                "solve_sym: kan deze vergelijking niet symbolisch/exact oplossen "
                "(bv. te complex, of geen gesloten-vorm-oplossing). "
                "Probeer nulpunt() voor een numerieke benadering."
            )

        if not oplossingen:
            raise ValueError("solve_sym: geen oplossingen gevonden voor deze vergelijking")

        # UPDATE (Fase 5, punt 13 — Complexe getallen, nu gebouwd): eerder
        # werden complexe oplossingen hier weggefilterd met een
        # foutmelding. Nu tonen we ze gewoon mee — _sympy_str() vertaalt
        # SymPy's "I" al naar onze "i"-notatie.
        opgeschreven = [self._sympy_str(o) for o in oplossingen]
        return "x = " + " of x = ".join(opgeschreven)

    def _split_top_level(self, tekst, scheidingsteken=","):
        # Splitst enkel op het scheidingsteken BUITEN haakjes, zodat een
        # eventuele functie-aanroep met komma's binnenin (bv. "sin(x,y)",
        # al komt dat in de praktijk zelden voor bij deze whitelist) niet
        # per ongeluk kapotgesplitst wordt.
        delen = []
        diepte = 0
        huidig = ""
        for ch in tekst:
            if ch == "(":
                diepte += 1
                huidig += ch
            elif ch == ")":
                diepte -= 1
                huidig += ch
            elif ch == scheidingsteken and diepte == 0:
                delen.append(huidig.strip())
                huidig = ""
            else:
                huidig += ch
        if huidig.strip():
            delen.append(huidig.strip())
        return delen

    def _solve_stelsel(self, vergelijkingen_str):
        # Lost een STELSEL van twee vergelijkingen met x ÉN y tegelijk op
        # (in tegenstelling tot solve_sym, dat maar 1 variabele aankan).
        # Nodig omdat 1 vergelijking met 2 onbekenden (bv. x+y=10) altijd
        # oneindig veel oplossingen heeft — pas met een TWEEDE, onaf-
        # hankelijke vergelijking erbij (bv. x-y=2) is er een unieke
        # oplossing. bv. solve_stelsel(x+y=10, x-y=2) → "x = 6, y = 4"
        self._check_sympy("solve_stelsel")
        x, y = sp.symbols("x y")
        variabelen = {"x": x, "y": y}

        delen = self._split_top_level(vergelijkingen_str)
        if len(delen) != 2:
            raise ValueError(
                "solve_stelsel: verwacht precies TWEE vergelijkingen, gescheiden door een "
                "komma, bv. solve_stelsel(x+y=10, x-y=2)"
            )

        vergelijkingen = []
        for deel in delen:
            if "=" not in deel:
                raise ValueError(
                    f"solve_stelsel: \"{deel}\" bevat geen \"=\"-teken — elke vergelijking "
                    f"in het stelsel moet een gelijkheid zijn"
                )
            links_str, rechts_str = deel.split("=", 1)
            links = self._sympy_parse(links_str.strip(), variabelen)
            rechts = self._sympy_parse(rechts_str.strip(), variabelen)
            vergelijkingen.append(sp.Eq(links, rechts))

        try:
            oplossing = sp.solve(vergelijkingen, [x, y])
        except NotImplementedError:
            raise ValueError(
                "solve_stelsel: kan dit stelsel niet symbolisch/exact oplossen "
                "(bv. te complex, of geen gesloten-vorm-oplossing)"
            )

        if not oplossing:
            raise ValueError(
                "solve_stelsel: geen oplossing gevonden — de twee vergelijkingen "
                "zijn mogelijk strijdig, of hebben oneindig veel gemeenschappelijke oplossingen"
            )

        # sp.solve() geeft bij een lineair stelsel met 2 onbekenden een
        # dict terug (bv. {x: 6, y: 4}); bij sommige niet-lineaire
        # stelsels een lijst van dict/tuple-oplossingen — we normaliseren
        # dat hier naar altijd een lijst van dicts, zodat de weergave
        # verderop (on_math()) consistent 1 formaat krijgt.
        if isinstance(oplossing, dict):
            oplossingen_lijst = [oplossing]
        elif isinstance(oplossing, list) and oplossing and isinstance(oplossing[0], dict):
            oplossingen_lijst = oplossing
        elif isinstance(oplossing, list):
            # Lijst van tuples (x_waarde, y_waarde), SymPy's fallback-vorm
            # bij sommige niet-lineaire stelsels.
            oplossingen_lijst = [{x: o[0], y: o[1]} for o in oplossing]
        else:
            raise ValueError("solve_stelsel: onverwacht resultaatformaat van SymPy")

        zinnen = []
        for opl in oplossingen_lijst:
            x_str = self._sympy_str(opl[x])
            y_str = self._sympy_str(opl[y])
            zinnen.append(f"x = {x_str}, y = {y_str}")
        return " of ".join(zinnen)

    # -----------------------------------------------------------
    # Fase 4, punt 11 — Fysica-engine, 100% puur symbolisch/numeriek
    # -----------------------------------------------------------
    # Klassieke (Newtoniaanse) mechanica voor één object: krachten,
    # energie, beweging in 1D/2D, en simulaties. Bewuste afbakening (zie
    # math_roadmap.md): geen botsingen tussen meerdere objecten, geen
    # rotatie/traagheidsmomenten, geen andere vakgebieden (elektromagne-
    # tisme, thermodynamica) — dat zou een apart project zijn.
    #
    # Alle argumenten zijn gewone getallen in SI-basiseenheden (kg, m, s,
    # m/s, m/s², N, J, rad). Resultaten komen terug als UnitValue, zodat
    # ze via .to(...) naar andere eenheden omgezet kunnen worden — het
    # bestaande eenhedensysteem (met automatische dimensie-tracking)
    # wordt hier hergebruikt, niet opnieuw uitgevonden.

    _ZWAARTEKRACHT = 9.81  # m/s², standaard valversnelling op aarde

    def _check_getal(self, waarde, naam, functienaam):
        if not isinstance(waarde, (int, float)):
            raise ValueError(f"{functienaam}: {naam} moet een getal zijn")

    def _kracht(self, massa, versnelling):
        # Newton's tweede wet: F = m·a
        # bv. kracht(1000, 3) → kracht op een auto van 1000kg die met 3m/s² versnelt
        self._check_getal(massa, "massa", "kracht")
        self._check_getal(versnelling, "versnelling", "kracht")
        if massa <= 0:
            raise ValueError("kracht: massa moet groter zijn dan 0")

        resultaat = massa * versnelling
        return self._make_unitvalue(resultaat, "N")

    def _energie_kinetisch(self, massa, snelheid):
        # Kinetische energie: E = ½·m·v²
        # bv. energie_kinetisch(5, 10) → kinetische energie van 5kg aan 10m/s
        self._check_getal(massa, "massa", "energie_kinetisch")
        self._check_getal(snelheid, "snelheid", "energie_kinetisch")
        if massa <= 0:
            raise ValueError("energie_kinetisch: massa moet groter zijn dan 0")

        resultaat = 0.5 * massa * snelheid ** 2
        return self._make_unitvalue(resultaat, "J")

    def _energie_potentieel(self, massa, hoogte, g=None):
        # Zwaarte-energie: E = m·g·h
        # bv. energie_potentieel(2, 10) → potentiële energie van 2kg op 10m hoogte
        self._check_getal(massa, "massa", "energie_potentieel")
        self._check_getal(hoogte, "hoogte", "energie_potentieel")
        if massa <= 0:
            raise ValueError("energie_potentieel: massa moet groter zijn dan 0")
        if g is None:
            g = self._ZWAARTEKRACHT

        resultaat = round(massa * g * hoogte, 6)
        return self._make_unitvalue(resultaat, "J")

    def _arbeid(self, kracht, afstand):
        # Arbeid: W = F·d (kracht in de bewegingsrichting maal afgelegde afstand)
        # bv. arbeid(50, 3) → arbeid geleverd door 50N over 3m
        self._check_getal(kracht, "kracht", "arbeid")
        self._check_getal(afstand, "afstand", "arbeid")

        resultaat = kracht * afstand
        return self._make_unitvalue(resultaat, "J")

    def _snelheid_na(self, v0, versnelling, tijd):
        # Eenparig versnelde beweging: v = v0 + a·t
        # bv. snelheid_na(0, 9.81, 3) → snelheid na 3s vrije val vanuit stilstand
        self._check_getal(v0, "v0", "snelheid_na")
        self._check_getal(versnelling, "versnelling", "snelheid_na")
        self._check_getal(tijd, "tijd", "snelheid_na")
        if tijd < 0:
            raise ValueError("snelheid_na: tijd kan niet negatief zijn")

        resultaat = round(v0 + versnelling * tijd, 6)
        # BUGFIX: "m/s" bestaat niet als losse sleutel in self.units (dat
        # systeem kent enkel grondeenheden zoals "m" en "s" apart, en
        # samengestelde eenheden ontstaan normaal via een berekening zoals
        # "m/s" i.p.v. rechtstreeks opgevraagd te worden). Hier bouwen we
        # daarom zelf een UnitValue met de juiste dimensies, i.p.v.
        # _make_unitvalue() te gebruiken.
        return UnitValue(resultaat, {"m": 1, "s": -1}, label="m/s").bind_math(self)

    def _afstand_na(self, v0, versnelling, tijd):
        # Eenparig versnelde beweging: x = v0·t + ½·a·t²
        # bv. afstand_na(20, -5, 4) → afgelegde afstand na 4s remmen vanaf 20m/s met -5m/s²
        self._check_getal(v0, "v0", "afstand_na")
        self._check_getal(versnelling, "versnelling", "afstand_na")
        self._check_getal(tijd, "tijd", "afstand_na")
        if tijd < 0:
            raise ValueError("afstand_na: tijd kan niet negatief zijn")

        resultaat = v0 * tijd + 0.5 * versnelling * tijd ** 2
        return self._make_unitvalue(resultaat, "m")

    def _projectiel(self, snelheid, hoek_graden, g=None):
        # Projectielbeweging (worp onder een hoek, zonder luchtweerstand):
        # geeft bereik, maximale hoogte en vluchttijd terug.
        # bv. projectiel(20, 45) → een bal die met 20m/s onder 45° wordt weggeschoten
        self._check_getal(snelheid, "snelheid", "projectiel")
        self._check_getal(hoek_graden, "hoek", "projectiel")
        if snelheid < 0:
            raise ValueError("projectiel: snelheid kan niet negatief zijn")
        if not (0 <= hoek_graden <= 90):
            raise ValueError("projectiel: hoek moet tussen 0 en 90 graden liggen")
        if g is None:
            g = self._ZWAARTEKRACHT

        hoek_rad = math.radians(hoek_graden)
        vx = snelheid * math.cos(hoek_rad)
        vy = snelheid * math.sin(hoek_rad)

        vluchttijd = (2 * vy) / g if g > 0 else 0
        bereik = vx * vluchttijd
        max_hoogte = (vy ** 2) / (2 * g) if g > 0 else 0

        return {
            "bereik": self._make_unitvalue(round(bereik, 6), "m"),
            "max_hoogte": self._make_unitvalue(round(max_hoogte, 6), "m"),
            "vluchttijd": self._make_unitvalue(round(vluchttijd, 6), "s"),
        }

    def _val_met_weerstand(self, massa, hoogte, weerstandscoefficient, stappen=1000):
        # Simulatie (Fase 4, punt 11 — "simulaties"): een vrije val MET
        # luchtweerstand heeft geen nette gesloten-vorm-formule meer (de
        # weerstandskracht hangt zelf weer af van de snelheid, die op zijn
        # beurt verandert door diezelfde kracht) — daarom lossen we dit
        # numeriek op, met exact dezelfde Runge-Kutta 4-machinerie als
        # dv_rk4() al gebruikt voor differentiaalvergelijkingen.
        # Model: dv/dt = g - (weerstandscoefficient/massa)·v²
        # bv. val_met_weerstand(80, 1000, 0.2) → valtijd van een parachutist
        self._check_getal(massa, "massa", "val_met_weerstand")
        self._check_getal(hoogte, "hoogte", "val_met_weerstand")
        self._check_getal(weerstandscoefficient, "weerstandscoëfficiënt", "val_met_weerstand")
        if massa <= 0:
            raise ValueError("val_met_weerstand: massa moet groter zijn dan 0")
        if hoogte <= 0:
            raise ValueError("val_met_weerstand: hoogte moet groter zijn dan 0")
        if weerstandscoefficient < 0:
            raise ValueError("val_met_weerstand: weerstandscoëfficiënt kan niet negatief zijn")

        g = self._ZWAARTEKRACHT
        k = weerstandscoefficient

        # We simuleren stap voor stap (RK4-achtig, met twee gekoppelde
        # grootheden: hoogte en snelheid) tot de hoogte 0 bereikt, in
        # plaats van dv_rk4() rechtstreeks te hergebruiken — die is
        # gebouwd voor één vrije expressie f(x,y), hier hebben we een
        # gekoppeld stelsel (positie én snelheid) nodig.
        dt = 0.01
        max_stappen = 100000
        t, hgt, v = 0.0, hoogte, 0.0

        for _ in range(max_stappen):
            versnelling = g - (k / massa) * v ** 2
            v_nieuw = v + versnelling * dt
            hgt_nieuw = hgt - v * dt

            if hgt_nieuw <= 0:
                # lineair interpoleren voor een nauwkeurigere landingstijd
                fractie = hgt / (hgt - hgt_nieuw) if (hgt - hgt_nieuw) != 0 else 0
                t += dt * fractie
                v = v + versnelling * dt * fractie
                hgt = 0
                break

            t += dt
            hgt, v = hgt_nieuw, v_nieuw
        else:
            raise ValueError("val_met_weerstand: geen landing binnen een redelijke simulatietijd — controleer de waarden")

        return {
            "valtijd": self._make_unitvalue(round(t, 6), "s"),
            "eindsnelheid": UnitValue(round(v, 6), {"m": 1, "s": -1}, label="m/s").bind_math(self),
        }

    # -----------------------------------------------------------
    # Fase 5, punt 12 — Getaltheorie & combinatoriek, 100% puur symbolisch
    # -----------------------------------------------------------
    # LET OP: faculteit(), combinaties() en permutaties() zijn al
    # gebouwd in Fase 3, punt 9 (Statistiek-module), waar ze nodig waren
    # voor binomiaal(). Hier komen enkel de nog ontbrekende onderdelen
    # van punt 12 bij: priemgetallen, ggd/kgv, modulo-rekenen.

    def _is_priem(self, n):
        # Test of een getal een priemgetal is (enkel deelbaar door 1 en
        # zichzelf, en groter dan 1). bv. is_priem(17) → True
        if not isinstance(n, int):
            raise ValueError("is_priem verwacht een geheel getal")
        if n < 2:
            return False
        if n in (2, 3):
            return True
        if n % 2 == 0:
            return False
        # enkel oneven delers proberen t/m de wortel van n (alles erboven
        # zou al gevonden zijn als kleinere partner van een deler eronder)
        for deler in range(3, int(math.isqrt(n)) + 1, 2):
            if n % deler == 0:
                return False
        return True

    def _priemgetallen(self, tot):
        # Genereert alle priemgetallen tot en met 'tot', via de Zeef van
        # Eratosthenes (efficiënt: één keer alle veelvouden doorstrepen
        # i.p.v. elk getal apart met is_priem() te testen).
        # bv. priemgetallen(30) → [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
        if not isinstance(tot, int):
            raise ValueError("priemgetallen verwacht een geheel getal")
        if tot < 2:
            return []
        if tot > 10_000_000:
            raise ValueError("priemgetallen: bovengrens is te groot (max. 10.000.000), zou te lang duren")

        zeef = [True] * (tot + 1)
        zeef[0] = zeef[1] = False
        for i in range(2, int(math.isqrt(tot)) + 1):
            if zeef[i]:
                for veelvoud in range(i * i, tot + 1, i):
                    zeef[veelvoud] = False
        return [i for i, is_priem in enumerate(zeef) if is_priem]

    def _ggd(self, a, b):
        # Grootste gemene deler, via het Euclidisch algoritme.
        # bv. ggd(48, 18) → 6
        if not all(isinstance(v, int) for v in (a, b)):
            raise ValueError("ggd verwacht twee gehele getallen")
        return math.gcd(a, b)

    def _kgv(self, a, b):
        # Kleinste gemene veelvoud: kgv(a,b) = |a*b| / ggd(a,b)
        # bv. kgv(4, 6) → 12
        if not all(isinstance(v, int) for v in (a, b)):
            raise ValueError("kgv verwacht twee gehele getallen")
        if a == 0 or b == 0:
            raise ValueError("kgv: is niet gedefinieerd als a of b gelijk is aan 0")
        return abs(a * b) // math.gcd(a, b)

    def _modulo(self, a, b):
        # De rest bij deling: modulo(a, b) = a % b
        # bv. modulo(17, 5) → 2
        # Als aparte, benoemde functie i.p.v. enkel het kale "%"-teken,
        # zodat er geen verwarring ontstaat met de percentage-notatie
        # (zie math_roadmap.md, Fase 5-aanvulling punt 17).
        if not all(isinstance(v, int) for v in (a, b)):
            raise ValueError("modulo verwacht twee gehele getallen")
        if b == 0:
            raise ValueError("modulo: delen door 0 kan niet")
        return a % b

    # -----------------------------------------------------------
    # Fase 5, punt 14 — Extra eenheden: talstelsel-conversies
    # -----------------------------------------------------------
    # Gebruikt Python's ingebouwde bin()/oct()/hex()/int(x, base) — 100%
    # deterministisch, geen ML nodig. naar_binair/naar_octaal/naar_hex
    # gaan er impliciet van uit dat het invoergetal decimaal is (het
    # gangbare geval: "wat is 255 in binair"). Voor de omgekeerde
    # richting: vanuit_talstelsel(tekst, grondtal) — je hoeft dan enkel
    # het grondtal van de BRON te kennen (bv. 2 voor binair), niet twee
    # grondtallen tegelijk.

    def _strip_prefix(self, python_str, prefix_len):
        # Haalt Python's ingebouwde prefix (0b/0o/0x) netjes weg, met
        # correcte afhandeling van een eventueel minteken ervoor (bv.
        # "-0b101" → "-101", niet per ongeluk "0b101" → "b101").
        if python_str.startswith("-"):
            return "-" + python_str[1 + prefix_len:]
        return python_str[prefix_len:]

    def _naar_binair(self, getal):
        # bv. naar_binair(255) → "11111111"
        if not isinstance(getal, int):
            raise ValueError("naar_binair verwacht een geheel getal")
        return self._strip_prefix(bin(getal), 2)

    def _naar_octaal(self, getal):
        # bv. naar_octaal(255) → "377"
        if not isinstance(getal, int):
            raise ValueError("naar_octaal verwacht een geheel getal")
        return self._strip_prefix(oct(getal), 2)

    def _naar_hex(self, getal):
        # bv. naar_hex(255) → "ff"
        if not isinstance(getal, int):
            raise ValueError("naar_hex verwacht een geheel getal")
        return self._strip_prefix(hex(getal), 2)

    def _vanuit_talstelsel(self, tekst, grondtal):
        # Zet een getal-als-tekst in een willekeurig grondtal (2 t/m 36)
        # om naar het gewone decimale getal.
        # bv. vanuit_talstelsel("11111111", 2) → 255
        # bv. vanuit_talstelsel("ff", 16) → 255
        if not isinstance(tekst, str):
            raise ValueError("vanuit_talstelsel verwacht het getal als tekst, bv. \"ff\"")
        if not isinstance(grondtal, int):
            raise ValueError("vanuit_talstelsel verwacht een geheel getal als grondtal")
        if not (2 <= grondtal <= 36):
            raise ValueError("vanuit_talstelsel: grondtal moet tussen 2 en 36 liggen")

        try:
            return int(tekst, grondtal)
        except ValueError:
            raise ValueError(
                f"vanuit_talstelsel: \"{tekst}\" is geen geldig getal in grondtal {grondtal}"
            )

    # -----------------------------------------------------------
    # Fase 5, punt 15 — Klassieke CS-algoritmes (losstaande module)
    # -----------------------------------------------------------
    # 100% eigen Python-code, geen ML/LLM. Bewust géén graafalgoritmes
    # specifiek voor Nova's concepts.json (kortste pad tussen concepten,
    # cykel-detectie, topologische sortering) — die horen inhoudelijk bij
    # de semantic-roadmap, niet hier. Hier enkel algemene, losstaande
    # algoritmes die op willekeurige data werken.

    def _binary_search(self, lijst, waarde):
        # Zoekt een waarde in een GESORTEERDE lijst, veel sneller dan
        # element-voor-element doorlopen bij grote lijsten.
        # bv. binary_search([1,3,5,7,9,11], 7) → 3 (index van 7)
        if not isinstance(lijst, list):
            raise ValueError("binary_search verwacht een lijst")
        if lijst != sorted(lijst):
            raise ValueError("binary_search: de lijst moet gesorteerd zijn")

        links, rechts = 0, len(lijst) - 1
        while links <= rechts:
            midden = (links + rechts) // 2
            if lijst[midden] == waarde:
                return midden
            if lijst[midden] < waarde:
                links = midden + 1
            else:
                rechts = midden - 1

        raise ValueError(f"binary_search: {waarde} niet gevonden in de lijst")

    def _bubble_sort(self, lijst):
        # Simpel, klassiek sorteeralgoritme: herhaaldelijk naburige
        # elementen omwisselen als ze in de verkeerde volgorde staan.
        # Niet het snelste algoritme (O(n²)), maar wel het meest
        # herkenbare/eenvoudigste om te begrijpen.
        # bv. bubble_sort([5,2,8,1]) → [1,2,5,8]
        if not isinstance(lijst, list):
            raise ValueError("bubble_sort verwacht een lijst")
        if not all(isinstance(v, (int, float)) for v in lijst):
            raise ValueError("bubble_sort verwacht een lijst met enkel getallen")

        resultaat = lijst.copy()
        n = len(resultaat)
        for i in range(n):
            for j in range(0, n - i - 1):
                if resultaat[j] > resultaat[j + 1]:
                    resultaat[j], resultaat[j + 1] = resultaat[j + 1], resultaat[j]
        return resultaat

    def _quick_sort(self, lijst):
        # Sneller sorteeralgoritme (gemiddeld O(n log n)): kiest een
        # spilelement (pivot) en verdeelt de rest in kleiner/gelijk/groter,
        # en herhaalt dat recursief op elk deel.
        # bv. quick_sort([5,2,8,1]) → [1,2,5,8]
        if not isinstance(lijst, list):
            raise ValueError("quick_sort verwacht een lijst")
        if not all(isinstance(v, (int, float)) for v in lijst):
            raise ValueError("quick_sort verwacht een lijst met enkel getallen")

        if len(lijst) <= 1:
            return lijst.copy()

        spil = lijst[len(lijst) // 2]
        kleiner = [x for x in lijst if x < spil]
        gelijk = [x for x in lijst if x == spil]
        groter = [x for x in lijst if x > spil]
        return self._quick_sort(kleiner) + gelijk + self._quick_sort(groter)

    def _check_graaf(self, graaf, functienaam):
        if not isinstance(graaf, dict):
            raise ValueError(
                f"{functienaam} verwacht een graaf als dictionary, "
                f'bv. {{"A": ["B","C"], "B": ["D"]}}'
            )

    def _bfs(self, graaf, start):
        # Breadth-First Search: doorloopt een graaf laag voor laag vanaf
        # het startpunt, geeft de volgorde terug waarin knopen bereikt
        # worden. bv. bfs({"A":["B","C"],"B":["D"],"C":["D"]}, "A")
        # → ["A", "B", "C", "D"]
        self._check_graaf(graaf, "bfs")
        if start not in graaf:
            raise ValueError(f"bfs: startpunt \"{start}\" komt niet voor in de graaf")

        bezocht = [start]
        wachtrij = [start]
        while wachtrij:
            huidige = wachtrij.pop(0)
            for buur in graaf.get(huidige, []):
                if buur not in bezocht:
                    bezocht.append(buur)
                    wachtrij.append(buur)
        return bezocht

    def _dfs(self, graaf, start):
        # Depth-First Search: doorloopt een graaf zo diep mogelijk in één
        # richting vóór terug te keren, geeft de bezoekvolgorde terug.
        # bv. dfs({"A":["B","C"],"B":["D"],"C":["D"]}, "A")
        # → ["A", "B", "D", "C"]
        self._check_graaf(graaf, "dfs")
        if start not in graaf:
            raise ValueError(f"dfs: startpunt \"{start}\" komt niet voor in de graaf")

        bezocht = []

        def verken(knoop):
            if knoop in bezocht:
                return
            bezocht.append(knoop)
            for buur in graaf.get(knoop, []):
                verken(buur)

        verken(start)
        return bezocht

    def _dijkstra(self, graaf, start):
        # Kortste-pad-algoritme voor een graaf MET gewichten (bv.
        # afstanden of kosten tussen knopen). Geeft voor elke bereikbare
        # knoop de kortste totale afstand vanaf het startpunt terug.
        # bv. dijkstra({"A":{"B":4,"C":2},"B":{"D":1},"C":{"B":1,"D":5}}, "A")
        # → {"A":0, "B":3, "C":2, "D":4}
        self._check_graaf(graaf, "dijkstra")
        if start not in graaf:
            raise ValueError(f"dijkstra: startpunt \"{start}\" komt niet voor in de graaf")
        for knoop, buren in graaf.items():
            if not isinstance(buren, dict):
                raise ValueError(
                    'dijkstra verwacht gewichten per verbinding, bv. '
                    '{"A": {"B": 4, "C": 2}} — gebruik bfs()/dfs() voor een graaf zonder gewichten'
                )

        afstanden = {knoop: math.inf for knoop in graaf}
        afstanden[start] = 0
        onbezocht = set(graaf.keys())

        while onbezocht:
            huidige = min(onbezocht, key=lambda k: afstanden[k])
            if afstanden[huidige] == math.inf:
                break
            onbezocht.remove(huidige)

            for buur, gewicht in graaf.get(huidige, {}).items():
                if buur not in afstanden:
                    afstanden[buur] = math.inf
                    onbezocht.add(buur)
                nieuwe_afstand = afstanden[huidige] + gewicht
                if nieuwe_afstand < afstanden[buur]:
                    afstanden[buur] = nieuwe_afstand

        return {k: v for k, v in afstanden.items() if v != math.inf}

    def _levenshtein(self, woord1, woord2):
        # Levenshtein-afstand (edit distance): minimum aantal invoeg-,
        # verwijder- en vervangbewerkingen om van woord1 naar woord2 te
        # gaan. Nova gebruikt dit concept al IMPLICIET via Python's
        # difflib (bv. voor het herkennen van gelijkaardige woorden) —
        # dit maakt het ook expliciet oproepbaar als eigen functie.
        # bv. levenshtein("kitten", "sitting") → 3
        if not all(isinstance(w, str) for w in (woord1, woord2)):
            raise ValueError("levenshtein verwacht twee woorden als tekst")

        n, m = len(woord1), len(woord2)
        # tabel[i][j] = afstand tussen de eerste i letters van woord1 en
        # de eerste j letters van woord2
        tabel = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(n + 1):
            tabel[i][0] = i
        for j in range(m + 1):
            tabel[0][j] = j

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                if woord1[i - 1] == woord2[j - 1]:
                    tabel[i][j] = tabel[i - 1][j - 1]
                else:
                    tabel[i][j] = 1 + min(
                        tabel[i - 1][j],      # verwijderen
                        tabel[i][j - 1],      # invoegen
                        tabel[i - 1][j - 1],  # vervangen
                    )

        return tabel[n][m]

    # -----------------------------------------------------------
    # Fase 5, punt 16 — Afronding & precisie, 100% puur symbolisch
    # -----------------------------------------------------------

    def _significante_cijfers(self, getal, aantal):
        # Rondt af op een gegeven aantal SIGNIFICANTE cijfers — anders
        # dan het bestaande round() (dat afrondt op decimalen), telt dit
        # vanaf het eerste niet-nul-cijfer. bv. significante_cijfers(
        # 123456, 3) → 123000 (drie significante cijfers: 1,2,3)
        # bv. significante_cijfers(0.0012345, 3) → 0.00123
        if not isinstance(getal, (int, float)):
            raise ValueError("significante_cijfers verwacht een getal")
        if not isinstance(aantal, int) or aantal < 1:
            raise ValueError("significante_cijfers: aantal moet een geheel getal ≥ 1 zijn")
        if getal == 0:
            return 0.0

        macht = aantal - math.ceil(math.log10(abs(getal)))
        factor = 10 ** macht
        return round(getal * factor) / factor

    def _stel_precisie_in(self, aantal_decimalen):
        # Stelt een vaste precisie in voor de rest van de sessie: alle
        # nieuwe berekeningsresultaten worden vanaf nu op dit aantal
        # decimalen afgerond bij weergave (relevant bij fysica-
        # berekeningen met meetonzekerheid, waar je consequent op
        # bv. 3 decimalen wil blijven). bv. stel_precisie_in(3)
        if not isinstance(aantal_decimalen, int) or aantal_decimalen < 0:
            raise ValueError("stel_precisie_in verwacht een geheel getal ≥ 0")
        self.sessie_precisie = aantal_decimalen
        return f"Precisie ingesteld op {aantal_decimalen} decimalen voor de rest van deze sessie"

    def _reset_precisie(self):
        # Zet de sessie-precisie terug naar het standaardgedrag (geen
        # vaste afronding, alle bestaande weergave-logica ongewijzigd).
        self.sessie_precisie = None
        return "Precisie teruggezet naar standaard"

    # -----------------------------------------------------------
    # Fase 5, punt 18 — Breuken als exact type
    # -----------------------------------------------------------

    def _breuk(self, teller, noemer):
        # Gebruikt Python's ingebouwde Fraction i.p.v. gewone deling,
        # zodat het resultaat EXACT blijft (bv. breuk(1,3) + breuk(1,3)
        # → 2/3, niet 0.6666666666666666). Bewust een aparte, expliciete
        # functie — GEEN wijziging aan bestaande "/"-deling, om niets
        # bestaands te breken. Fraction ondersteunt zelf al +,-,*,/ met
        # andere Fractions of gewone getallen, dus breuk(1,3)+breuk(1,6)
        # werkt automatisch correct via de bestaande operator-afhandeling.
        # bv. breuk(1, 3) → "1/3"
        if not all(isinstance(v, int) for v in (teller, noemer)):
            raise ValueError("breuk verwacht twee gehele getallen: teller, noemer")
        if noemer == 0:
            raise ValueError("breuk: noemer kan niet 0 zijn")
        return Fraction(teller, noemer)

    # -----------------------------------------------------------
    # Fase 5, punt 19 — Reeksen/rijen
    # -----------------------------------------------------------

    def _som_reeks(self, van, tot):
        # Som van alle gehele getallen van 'van' tot en met 'tot'
        # (rekenkundige reeks 1+2+...+n). bv. som_reeks(1, 100) → 5050
        if not all(isinstance(v, int) for v in (van, tot)):
            raise ValueError("som_reeks verwacht twee gehele getallen")
        if van > tot:
            raise ValueError("som_reeks: 'van' moet kleiner of gelijk zijn aan 'tot'")
        # Gauss-formule i.p.v. een expliciete lus: even snel bij n=10 als
        # bij n=10.000.000, geen prestatieverlies bij grote reeksen.
        n = tot - van + 1
        return n * (van + tot) // 2

    def _sigma(self, f, van, tot):
        # Evalueert een sigma-sommatie Σ f(i) voor i van 'van' tot en met
        # 'tot' — f is een vrije expressie met x (hergebruikt hetzelfde
        # mechanisme als newton()/afgeleide()/enz., zie EXPR_FUNCS in de
        # Call-afhandeling van _eval()).
        # bv. sigma(x^2, 1, 5) → 1+4+9+16+25 = 55
        if not callable(f):
            raise ValueError("sigma verwacht als eerste argument een expressie met x, bv. \"x^2\"")
        if not all(isinstance(v, int) for v in (van, tot)):
            raise ValueError("sigma verwacht gehele getallen voor 'van' en 'tot'")
        if van > tot:
            raise ValueError("sigma: 'van' moet kleiner of gelijk zijn aan 'tot'")

        return sum(f(i) for i in range(van, tot + 1))

    def _meetkundige_reeks(self, eerste_term, reden, aantal_termen):
        # Som van een meetkundige reeks: eerste_term + eerste_term*reden
        # + eerste_term*reden^2 + ... (aantal_termen termen totaal).
        # bv. meetkundige_reeks(1, 2, 5) → 1+2+4+8+16 = 31
        if not all(isinstance(v, (int, float)) for v in (eerste_term, reden)):
            raise ValueError("meetkundige_reeks verwacht getallen voor eerste_term en reden")
        if not isinstance(aantal_termen, int) or aantal_termen < 1:
            raise ValueError("meetkundige_reeks: aantal_termen moet een geheel getal ≥ 1 zijn")

        if reden == 1:
            return eerste_term * aantal_termen
        resultaat = eerste_term * (1 - reden ** aantal_termen) / (1 - reden)
        return round(resultaat, 6) if isinstance(resultaat, float) else resultaat

    # -----------------------------------------------------------
    # Fase 5, punt 20 — Eenvoudige kansrekening (discreet)
    # -----------------------------------------------------------
    # LET OP: nadrukkelijk iets anders dan Fase 3's Statistiek-module
    # (die gaat over data/regressie/correlatie) — hier gaat het om basis
    # kansberekening met combinatoriek, dobbelsteen/kaartspel-achtige
    # modellen. Hergebruikt combinaties()/faculteit() uit Fase 3, punt 9.

    def _kans_dobbelsteen(self, aantal_dobbelstenen, som):
        # Kans op een bepaalde som bij het gooien van N dobbelstenen
        # (elk met 6 zijden), via volledige enumeratie van alle
        # mogelijke worpen — eenvoudig en exact voor een klein aantal
        # dobbelstenen (praktisch haalbaar t/m een stuk of 6-8 stuks).
        # bv. kans_dobbelsteen(2, 7) → kans op som=7 met 2 dobbelstenen
        if not isinstance(aantal_dobbelstenen, int) or aantal_dobbelstenen < 1:
            raise ValueError("kans_dobbelsteen: aantal_dobbelstenen moet een geheel getal ≥ 1 zijn")
        if aantal_dobbelstenen > 8:
            raise ValueError("kans_dobbelsteen: te veel dobbelstenen (max. 8), zou te lang duren om te enumereren")
        if not isinstance(som, int):
            raise ValueError("kans_dobbelsteen verwacht een geheel getal als som")

        totaal_mogelijkheden = 6 ** aantal_dobbelstenen
        gunstige = 0

        def tel_worpen(resterend, huidige_som):
            nonlocal gunstige
            if resterend == 0:
                if huidige_som == som:
                    gunstige += 1
                return
            for worp in range(1, 7):
                tel_worpen(resterend - 1, huidige_som + worp)

        tel_worpen(aantal_dobbelstenen, 0)
        return round(gunstige / totaal_mogelijkheden, 6)

    def _kans_kaart(self, kaarten_gewenst, totaal_kaarten, trek_aantal):
        # Kans om minstens 1 gewenste kaart te trekken uit een stapel,
        # via de combinatie-formule (hypergeometrische verdeling): kans
        # dat GEEN van de getrokken kaarten een gewenste kaart is,
        # afgetrokken van 1.
        # bv. kans_kaart(4, 52, 5) → kans op minstens 1 aas bij 5 kaarten
        # trekken uit een kaartspel van 52 (met 4 azen)
        if not all(isinstance(v, int) for v in (kaarten_gewenst, totaal_kaarten, trek_aantal)):
            raise ValueError("kans_kaart verwacht drie gehele getallen")
        if not (0 <= kaarten_gewenst <= totaal_kaarten):
            raise ValueError("kans_kaart: kaarten_gewenst moet tussen 0 en totaal_kaarten liggen")
        if not (1 <= trek_aantal <= totaal_kaarten):
            raise ValueError("kans_kaart: trek_aantal moet tussen 1 en totaal_kaarten liggen")

        ongewenst = totaal_kaarten - kaarten_gewenst
        if trek_aantal > ongewenst:
            # Het is onmogelijk om enkel ongewenste kaarten te trekken,
            # dus de kans op minstens 1 gewenste kaart is gegarandeerd 1.
            return 1.0

        kans_geen_gewenste = self._combinaties(ongewenst, trek_aantal) / self._combinaties(totaal_kaarten, trek_aantal)
        return round(1 - kans_geen_gewenste, 6)

    def _make_unitvalue(self, number, unit_name):
        # temperatuur-markers
        if isinstance(unit_name, tuple) and unit_name[0] == "TEMP":
            unit_name = unit_name[1]
            
        if unit_name == "degC":
            return UnitValue(number + 273.15, {}, label="K").bind_math(self)

        if unit_name == "degF":
            return UnitValue((number - 32) * 5/9 + 273.15, {}, label="K").bind_math(self)

        if unit_name not in self.units:
            raise ValueError(f"Onbekende eenheid: {unit_name}")

        dims, factor = self.units[unit_name]
        return UnitValue(number * factor, dims.copy(), label=unit_name).bind_math(self)

    def _eval(self, node, variables=None):
        # NIEUW (Fase 3, Algebra-module): optioneel 'variables'-dict
        # (bv. {"x": 2.5}) waarmee newton()/polyeval()/extremum() een
        # losse variabele als x kunnen laten meelopen tijdens het
        # evalueren van een vrije expressie zoals "x^2 - 4". Bestaat
        # deze parameter niet, dan gedraagt _eval() zich exact zoals
        # voorheen (100% backward compatible, geen enkele bestaande
        # aanroep hoeft aangepast te worden).

        # getallen
        if isinstance(node, ast.Num):          # <3.8
            return node.n
        if isinstance(node, ast.Constant):     # 3.8+
            return node.value
    
        # vectoren (lijsten)
        if isinstance(node, ast.List):
            return [self._eval(e, variables) for e in node.elts]

        # tuples (functie-argumenten)
        if isinstance(node, ast.Tuple):
            return [self._eval(e, variables) for e in node.elts]

        # NIEUW (Fase 5, punt 15 — CS-algoritmes): dictionaries, nodig om
        # een graaf als functie-argument te kunnen intypen bij bfs()/
        # dfs()/dijkstra(), bv. {"A": ["B","C"], "B": ["D"]}.
        if isinstance(node, ast.Dict):
            return {
                self._eval(k, variables): self._eval(v, variables)
                for k, v in zip(node.keys, node.values)
            }

        # namen (constanten + eenheden)
        if isinstance(node, ast.Name):
            name = node.id

            # NIEUW: los variabele-symbool (bv. "x") tijdens newton/
            # polyeval/extremum — heeft voorrang op eenheden/constanten,
            # want binnen zo'n expressie ís x de bedoelde variabele.
            if variables is not None and name in variables:
                return variables[name]

            # temperatuur-eenheden altijd via _make_unitvalue verwerken
            if name in ("degC", "degF"):
                return ("TEMP", name)

            # BUGFIX (1 aug 2026): kale "C" is dubbelzinnig — kan coulomb
            # (SI-ladingseenheid, staat in self.units) of Celsius betekenen.
            # Zonder deze check werd "0C" stilzwijgend als coulomb gelezen
            # (0 A·s). We raden hier bewust NIET welke bedoeld is — dat zou
            # in de helft van de gevallen alsnog fout gokken. In plaats
            # daarvan een duidelijke fout die om het gradenteken vraagt.
            if name == "C":
                raise ValueError(
                    "Dubbelzinnige eenheid 'C': bedoel je graden Celsius (°C) "
                    "of coulomb (elektrische lading)? Typ het gradenteken erbij "
                    "voor Celsius, bv. 0°C."
                )

            # constante?
            if name in self.consts:
                return self.consts[name]

            # eenheid?
            if name in self.units:
                dims, factor = self.units[name]
                return UnitValue(factor, dims.copy()).bind_math(self)

            raise ValueError(f"Onbekende naam of eenheid: {name}")

        # binaire operatoren
        # binaire operatoren
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left, variables)
            right = self._eval(node.right, variables)
            op = self.ops[type(node.op)]

            # temperatuur-markers: forceer _make_unitvalue
            if isinstance(right, tuple) and right[0] == "TEMP":
                return self._make_unitvalue(left, right[1])

            if isinstance(left, tuple) and left[0] == "TEMP":
                return self._make_unitvalue(right, left[1])

            # -----------------------------------------
            # 1. matrix * vector  (MOET EERST!)
            # -----------------------------------------
            if isinstance(left, list) and isinstance(right, list):
                # check matrix × vector
                if all(isinstance(row, list) for row in left) and all(isinstance(x, (int, float)) for x in right):
                    if any(len(row) != len(right) for row in left):
                        raise ValueError("matrix × vector: dimensies komen niet overeen")
                    return [sum(a*b for a, b in zip(row, right)) for row in left]

            # -----------------------------------------
            # matrix + matrix  /  matrix - matrix
            # -----------------------------------------
            if isinstance(left, list) and isinstance(right, list) and op in (operator.add, operator.sub):
                if all(isinstance(row, list) for row in left) and all(isinstance(row, list) for row in right):
                    if len(left) != len(right) or any(len(a) != len(b) for a, b in zip(left, right)):
                        raise ValueError("matrix + matrix: dimensies komen niet overeen")
                    return [[op(a, b) for a, b in zip(rowA, rowB)] for rowA, rowB in zip(left, right)]

            # -----------------------------------------
            # 2. matrix * matrix
            # -----------------------------------------
            if isinstance(left, list) and isinstance(right, list):
                # check of beide matrices zijn
                if all(isinstance(row, list) for row in left) and all(isinstance(row, list) for row in right):
                    # dimensies
                    rows_A = len(left)
                    cols_A = len(left[0])
                    rows_B = len(right)
                    cols_B = len(right[0])

                    if cols_A != rows_B:
                        raise ValueError("matrix × matrix: dimensies komen niet overeen")

                    # matrixvermenigvuldiging
                    result = []
                    for i in range(rows_A):
                        row = []
                        for j in range(cols_B):
                            val = sum(left[i][k] * right[k][j] for k in range(cols_A))
                            row.append(val)
                        result.append(row)
                    return result

            # -----------------------------------------
            # scalar * matrix  of  matrix * scalar
            # -----------------------------------------
            if isinstance(left, (int, float)) and isinstance(right, list):
                if all(isinstance(row, list) for row in right):
                    return [[left * x for x in row] for row in right]

            if isinstance(right, (int, float)) and isinstance(left, list):
                if all(isinstance(row, list) for row in left):
                    return [[x * right for x in row] for row in left]

            # -----------------------------------------
            # 3. vector + vector / vector - vector
            # -----------------------------------------
            if isinstance(left, list) and isinstance(right, list):
                if len(left) != len(right):
                    raise ValueError("Vectoren moeten even lang zijn")
                return [op(a, b) for a, b in zip(left, right)]

            # -----------------------------------------
            # 4. scalar * vector of vector * scalar
            # -----------------------------------------
            if isinstance(left, list) and isinstance(right, (int, float)):
                return [op(a, right) for a in left]
            if isinstance(right, list) and isinstance(left, (int, float)):
                return [op(left, b) for b in right]

            # 5. UnitValue-ondersteuning
            if isinstance(left, UnitValue) or isinstance(right, UnitValue):
                return op(left, right)

            # 6. gewone scalars
            return op(left, right)

        # unair (bv. -5)
        if isinstance(node, ast.UnaryOp):
            op = self.ops[type(node.op)]
            return op(self._eval(node.operand, variables))

        # ⭐ 1. attribute access
        if isinstance(node, ast.Attribute):
            obj = self._eval(node.value, variables)
            attr = node.attr
            if hasattr(obj, attr):
                return getattr(obj, attr)
            raise ValueError(f"Onbekende methode: {attr}")

        # functie‑aanroepen
        if isinstance(node, ast.Call):

            # method call: x.to(...)
            if isinstance(node.func, ast.Attribute):
                obj = self._eval(node.func.value)
                method = node.func.attr

                # BUGFIX (1 aug 2026): bij .to(cm) werd "cm" eerst via
                # _eval() omgezet naar een UnitValue (0.01 m), omdat een
                # los symbool normaal als eenheid-waarde wordt opgelost.
                # _convert() verwacht de eenheid echter als STRING ("cm"),
                # niet als UnitValue — dat gaf een verwarrende foutmelding
                # ("Onbekende eenheid: 0.01 m" i.p.v. "cm"). Voor .to()
                # specifiek gebruiken we daarom de kale naam als string
                # wanneer het argument een simpele naam is (bv. cm, degF).
                if method == "to" and len(node.args) == 1 and isinstance(node.args[0], ast.Name):
                    args = [node.args[0].id]
                else:
                    args = [self._eval(a) for a in node.args]

                if hasattr(obj, method):
                    return getattr(obj, method)(*args)
                raise ValueError(f"Onbekende methode: {method}")
                
            if not isinstance(node.func, ast.Name):
                raise ValueError("Ongeldige functie‑aanroep")

            fname = node.func.id
            if fname not in self.funcs:
                raise ValueError(f"Onbekende functie: {fname}")

            # NIEUW (Fase 3, Algebra-module + Calculus-module): sommige
            # functies werken met een VRIJE EXPRESSIE als eerste argument
            # (bv. "x^2 - 4"), i.p.v. een kant-en-klare waarde. Normaal
            # evalueert _eval() elk functie-argument meteen tot een
            # getal — dat kan hier niet, want "x" (en bij de DV-functies
            # ook "y") heeft nog geen waarde. In plaats daarvan geven we
            # deze functies een klein Python-functie-object mee (f) dat,
            # ZODRA zij zelf waarden kiezen, die expressie alsnog
            # symbolisch evalueert via _eval(node, {...}). Alle overige
            # functies (sqrt, sin, det, ...) blijven ongewijzigd werken
            # zoals voorheen.

            # Groep 1: expressie met enkel x, bv. "x^2 - 4"
            EXPR_FUNCS = {
                "newton", "nulpunt", "polyeval", "bereken", "extremum", "minmax",
                "afgeleide", "integraal", "limiet",
                "sigma",  # Fase 5, punt 19 — Reeksen/rijen: sigma(x^2, 1, 5)
            }
            if fname in EXPR_FUNCS:
                if len(node.args) < 1:
                    raise ValueError(f"{fname}: eerste argument moet een expressie met x zijn, bv. \"x^2 - 4\"")

                expr_node = node.args[0]

                def f(x_waarde, _expr_node=expr_node):
                    return self._eval(_expr_node, {"x": x_waarde})

                overige_args = [self._eval(a, variables) for a in node.args[1:]]
                return self.funcs[fname](f, *overige_args)

            # Groep 2: expressie met x ÉN y samen, bv. "x - y" voor
            # differentiaalvergelijkingen dy/dx = f(x, y)
            EXPR_FUNCS_XY = {"dv_euler", "dv_rk4", "dv"}
            if fname in EXPR_FUNCS_XY:
                if len(node.args) < 1:
                    raise ValueError(f"{fname}: eerste argument moet een expressie met x en y zijn, bv. \"x - y\"")

                expr_node = node.args[0]

                def f_xy(x_waarde, y_waarde, _expr_node=expr_node):
                    return self._eval(_expr_node, {"x": x_waarde, "y": y_waarde})

                overige_args = [self._eval(a, variables) for a in node.args[1:]]
                return self.funcs[fname](f_xy, *overige_args)

            # Groep 3 (Fase 4, punt 10 — Symbolische algebra): deze
            # functies geven zelf een FORMULE terug (geen getal), en
            # verwachten daarom hun argument als STRING, niet als
            # geëvalueerde waarde of als Python-functie-object zoals
            # groep 1/2 hierboven. We gebruiken ast.unparse() om de
            # AST-node terug te vertalen naar de tekst zoals ze er
            # (na preprocess()) al stond, en geven die string door —
            # de functies zelf parsen die daarna opnieuw, veilig, via
            # _sympy_parse() (zie de uitleg daar).
            EXPR_FUNCS_SYMBOLISCH = {
                "differentiate", "integrate_sym", "simplify_sym",
                "expand_sym", "factor_sym",
            }
            if fname in EXPR_FUNCS_SYMBOLISCH:
                if len(node.args) < 1:
                    raise ValueError(f"{fname}: eerste argument moet een expressie met x zijn, bv. \"x^2 - 4\"")

                expr_str = ast.unparse(node.args[0])
                return self.funcs[fname](expr_str)

            args = [self._eval(a, variables) for a in node.args]
            return self.funcs[fname](*args)

        raise ValueError("Ongeldige expressie")

    def _parse_unit_string(self, unit_str):
        # simpele parser: check of unit exact bestaat
        if unit_str in self.units:
            dims, factor = self.units[unit_str]
            return dims.copy(), factor

        # samengestelde units zoals m/s^2
        parts = re.split(r'/', unit_str)
        num = parts[0]
        den = parts[1] if len(parts) > 1 else None

        dims = {}
        factor = 1

        def apply(part, sign):
            nonlocal dims, factor
            tokens = part.split('*')
            for t in tokens:
                # t kan zijn: m, m^2, km, s^-1
                m = re.match(r"([A-Za-z]+)(\^(-?\d+))?", t)
                if not m:
                    raise ValueError(f"Onbekende eenheid: {t}")
                base = m.group(1)
                exp = int(m.group(3)) if m.group(3) else 1

                if base not in self.units:
                    raise ValueError(f"Onbekende eenheid: {base}")

                bdims, bfactor = self.units[base]
                factor *= bfactor ** (exp * sign)

                for k, v in bdims.items():
                    dims[k] = dims.get(k, 0) + v * exp * sign

        apply(num, +1)
        if den:
            apply(den, -1)

        return dims, factor

    def _dims_to_string(self, dims):
        if not dims:
            return ""
        parts = []
        for unit, exp in dims.items():
            if exp == 1:
                parts.append(unit)
            else:
                parts.append(f"{unit}^{exp}")
        return "·".join(parts)

    def _convert(self, uv: UnitValue, target_unit: str):
        # Normaliseer temperatuur-eenheden
        if target_unit in ("°C", "degC", "celsius", "C"):
            target_unit = "degC"
        if target_unit in ("°F", "degF", "fahrenheit", "F"):
            target_unit = "degF"
        if target_unit in ("K", "kelvin"):
            target_unit = "K"

        # --- 1. Temperatuurconversies ---
        # Intern staat temperatuur altijd in Kelvin (label="K")
        if uv.label == "K" or (uv.dims == {} and uv.label in (None, "K")):
            K = uv.value

            if target_unit == "degC":
                C = K - 273.15
                return UnitValue(C, {}, label="°C").bind_math(self)

            if target_unit == "degF":
                F = (K - 273.15) * 9/5 + 32
                return UnitValue(F, {}, label="°F").bind_math(self)

            if target_unit == "K":
                return UnitValue(K, {}, label="K").bind_math(self)

        # --- 2. Als target een temperatuur-eenheid is maar uv geen temperatuur is ---
        if target_unit in ("degC", "degF", "K") and not (uv.dims == {}):
            raise ValueError("Kan alleen temperatuur converteren vanuit Kelvin")

        # --- 3. Normale unit-conversies ---
        if target_unit not in self.units:
            raise ValueError(f"Onbekende eenheid: {target_unit}")

        dims, factor = self.units[target_unit]

        if uv.dims != dims:
            raise ValueError("Dimensies komen niet overeen voor conversie")

        new_value = uv.value / factor
        return UnitValue(new_value, dims.copy(), label=target_unit).bind_math(self)

    def _format_complex(self, c):
        # Fase 5, punt 13 — Complexe getallen: vertaalt Python's eigen
        # weergave (bv. "(3+4j)") naar de wiskundige notatie die de
        # gebruiker gewend is (bv. "3 + 4i"). Coëfficiënt 1/-1 op het
        # imaginaire deel wordt kort geschreven als "i"/"-i", niet "1i".
        reeel, imag = c.real, c.imag

        if imag == 0:
            return str(int(reeel)) if reeel.is_integer() else str(reeel)

        def imag_deel(waarde):
            if waarde == 1:
                return "i"
            if waarde == -1:
                return "-i"
            getal_str = str(int(waarde)) if float(waarde).is_integer() else str(waarde)
            return f"{getal_str}i"

        if reeel == 0:
            return imag_deel(imag)

        reeel_str = str(int(reeel)) if reeel.is_integer() else str(reeel)
        if imag > 0:
            return f"{reeel_str} + {imag_deel(imag)}"
        return f"{reeel_str} - {imag_deel(abs(imag))}"

    def _format_value(self, v):
        # Fase 5, punt 13: complexe getallen krijgen hun eigen, nettere
        # notatie (zie _format_complex) i.p.v. Python's "(3+4j)".
        if isinstance(v, complex):
            return self._format_complex(v)

        # Fase 5, punt 16 — Afronding & precisie: als de gebruiker een
        # vaste sessie-precisie heeft ingesteld (via stel_precisie_in()),
        # ronden we elk float-resultaat daarop af vóór verdere opmaak.
        # Gebeurt hier, niet dieper in elke losse functie, zodat het één
        # centrale plek blijft en geen 50+ functies hoeft aan te passen.
        if isinstance(v, float) and self.sessie_precisie is not None:
            v = round(v, self.sessie_precisie)

        # 1. integer detectie
        if isinstance(v, float) and v.is_integer():
            return str(int(v))

        s = f"{v}"

        # 2. scientific notation detectie
        if "e" in s or "E" in s:
            base, exp = s.lower().split("e")
            exp = int(exp)
            supers = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
            exp_str = str(exp).translate(supers)
            return f"{base}×10{exp_str}"

        return s

    def on_math(self, data, event_type=None):
        origineel = data.get("expr", "")
        expr = self.preprocess(origineel)

        try:
            result = self.eval_expr(expr)
            # BUGFIX (1 aug 2026): het bericht toonde voorheen de intern
            # voorbewerkte expressie (met toegevoegde haakjes en *, bv.
            # "(1*kg).to(g)"), wat er technisch/programmeur-achtig uitzag.
            # We tonen nu de originele, door de gebruiker getypte tekst
            # ("1kg.to(g)") — de berekening zelf blijft de voorbewerkte
            # versie gebruiken, alleen de weergave verandert.

            # NIEUW (Fase 3): extremum() geeft een dict {"min": {...},
            # "max": {...}} terug — die rauw tonen ("{'min': {'x': ...") is
            # niet leesbaar. Hier bouwen we er een nette Nederlandse zin
            # van, gebruikmakend van de bestaande _format_value() voor
            # nette getalnotatie.
            if isinstance(result, dict) and "min" in result and "max" in result:
                mn, mx = result["min"], result["max"]
                msg = (
                    f"{origineel} → "
                    f"minimum {self._format_value(mn['waarde'])} bij x={self._format_value(mn['x'])}, "
                    f"maximum {self._format_value(mx['waarde'])} bij x={self._format_value(mx['x'])}"
                )
            # NIEUW (Fase 3, punt 9): regressie() geeft een dict
            # {"helling": ..., "snijpunt": ...} terug — ook hier bouwen
            # we een leesbare Nederlandse zin i.p.v. de rauwe dict te tonen.
            elif isinstance(result, dict) and "helling" in result and "snijpunt" in result:
                msg = (
                    f"{origineel} → "
                    f"y = {self._format_value(result['helling'])}x "
                    f"{'+' if result['snijpunt'] >= 0 else '-'} {self._format_value(abs(result['snijpunt']))} "
                    f"(helling={self._format_value(result['helling'])}, snijpunt={self._format_value(result['snijpunt'])})"
                )
            # NIEUW (Fase 4, punt 11): projectiel() geeft een dict met
            # bereik/max_hoogte/vluchttijd terug — nette Nederlandse zin
            # i.p.v. de rauwe dict.
            elif isinstance(result, dict) and "bereik" in result and "max_hoogte" in result:
                msg = (
                    f"{origineel} → "
                    f"bereik {result['bereik']}, "
                    f"max. hoogte {result['max_hoogte']}, "
                    f"vluchttijd {result['vluchttijd']}"
                )
            # NIEUW (Fase 4, punt 11): val_met_weerstand() geeft een dict
            # met valtijd/eindsnelheid terug.
            elif isinstance(result, dict) and "valtijd" in result and "eindsnelheid" in result:
                msg = (
                    f"{origineel} → "
                    f"valtijd {result['valtijd']}, "
                    f"eindsnelheid {result['eindsnelheid']}"
                )
            elif isinstance(result, UnitValue):
                msg = f"{origineel} = {result}"
            # NIEUW: is_priem() geeft standaard True/False terug, wat kaal
            # aanvoelt in een gesprek. We bouwen er een natuurlijke
            # Nederlandse zin van, met het getal zelf uit de expressie
            # gehaald (bv. "is_priem(17)" -> "17 is een priemgetal").
            elif isinstance(result, bool) and re.match(r"^is_priem\s*\(", origineel.strip()):
                getal_match = re.search(r"is_priem\s*\(\s*(-?\d+)", origineel)
                getal_str = getal_match.group(1) if getal_match else "dat getal"
                if result:
                    msg = f"Ja, {getal_str} is een priemgetal!"
                else:
                    msg = f"Nee, {getal_str} is geen priemgetal."
            # NIEUW (Fase 4, punt 10): de symbolische algebra-functies
            # geven zelf al een volledige, leesbare string terug (bv.
            # "x = 2 of x = 3" voor solve_sym, of "3x^2 + 2" voor
            # differentiate). Die tonen we met een pijl i.p.v. "=", zodat
            # solve_sym niet als "... = x = 2 of x = 3" verschijnt.
            elif isinstance(result, str) and re.match(
                r"^(differentiate|integrate_sym|simplify_sym|expand_sym|factor_sym|solve_sym|solve_stelsel)\s*\(",
                origineel.strip(),
            ):
                msg = f"{origineel} → {result}"
            # NIEUW (Fase 5, punt 13): complexe getallen krijgen hun
            # eigen, nettere notatie (bv. "3 + 4i" i.p.v. Python's
            # "(3+4j)") via _format_value()/_format_complex().
            elif isinstance(result, complex):
                msg = f"{origineel} = {self._format_value(result)}"
            # NIEUW (Fase 5, punt 13): ook een LIJST met (mogelijk)
            # complexe getallen — bv. solveQuadratic() bij een negatieve
            # discriminant — moet elk element netjes formatteren i.p.v.
            # Python's rauwe "[-1j, 1j]" te tonen.
            elif isinstance(result, list) and any(isinstance(v, complex) for v in result):
                opgemaakt = ", ".join(self._format_value(v) for v in result)
                msg = f"{origineel} = [{opgemaakt}]"
            # NIEUW: kansberekening-functies (binomiaal, normaal,
            # kans_dobbelsteen, kans_kaart) geven intern nog steeds een
            # decimaal getal terug (bv. 0.166667) — dat blijft zo voor
            # eventuele verdere rekenkundige bewerkingen — maar we tonen
            # het resultaat als PERCENTAGE, wat leesbaarder is dan een
            # decimaal getal (bv. "16.6667%" i.p.v. "0.166667").
            elif isinstance(result, float) and re.match(
                r"^(binomiaal|normaal|kans_dobbelsteen|kans_kaart)\s*\(",
                origineel.strip(),
            ):
                percentage = round(result * 100, 4)
                msg = f"{origineel} = {self._format_value(percentage)}%"
            # NIEUW (Fase 5, punt 16 — Afronding & precisie): een kaal
            # float-resultaat (het meest voorkomende basisgeval, bv.
            # "1/3") moet via _format_value() lopen, niet via Python's
            # rauwe str() — anders wordt een ingestelde sessie_precisie
            # (stel_precisie_in()) genegeerd voor alle gewone berekeningen.
            elif isinstance(result, float):
                msg = f"{origineel} = {self._format_value(result)}"
            else:
                msg = f"{origineel} = {result}"

        except Exception as e:
            err = str(e)

            # --- 1. dimensie-fouten ---
            if "verschillende dimensies" in err:
                msg = "Je probeert grootheden met verschillende dimensies te combineren — dat kan niet."

            # --- 2. onbekende eenheid ---
            elif "Onbekende naam of eenheid" in err:
                unit = err.split(":")[-1].strip()
                msg = f"Ik ken de eenheid ‘{unit}’ niet. Controleer op typfouten."

            # --- 3. matrix/vector mismatch ---
            elif "Vectoren moeten even lang zijn" in err:
                msg = "Je probeert twee vectoren te combineren met verschillende lengtes."

            elif "dimensies komen niet overeen" in err:
                msg = "De dimensies van de matrix of vector passen niet bij elkaar."

            elif "division by zero" in err:
                msg = "Je deelt door nul — dat kan niet."

            elif "was never closed" in err:
                msg = "Je expressie bevat een fout: een haakje werd niet gesloten."

            # --- 4. syntaxfout ---
            elif "invalid syntax" in err:
                msg = "Ik begrijp deze expressie niet. Controleer je haakjes en operatoren."

            # --- 5. wiskundige domeinfout ---
            elif "math domain error" in err:
                msg = "Je probeert een ongeldige wiskundige operatie uit te voeren (bv. wortel van een negatief getal)."

            # --- 6. Fase 3 algebra-functies: eigen foutmeldingen zijn
            #        al volledig leesbaar Nederlands, dus die tonen we
            #        rechtstreeks zonder het technische "Er ging iets
            #        mis:"-voorvoegsel.
            elif err.startswith((
                "solveQuadratic:", "newton:", "polyeval:", "extremum:",
                "afgeleide:", "integraal:", "limiet:", "dv_euler:", "dv_rk4:",
                "gemiddelde:", "mediaan:", "modus:", "variantie:", "stdafwijking:",
                "regressie:", "correlatie:", "faculteit:", "combinaties:",
                "permutaties:", "binomiaal:", "normaal:",
                "differentiate:", "integrate_sym:", "simplify_sym:",
                "expand_sym:", "factor_sym:", "solve_sym:", "solve_stelsel:",
                "kracht:", "energie_kinetisch:", "energie_potentieel:",
                "arbeid:", "snelheid_na:", "afstand_na:", "projectiel:",
                "val_met_weerstand:",
                "is_priem:", "priemgetallen:", "ggd:", "kgv:", "modulo:",
                "naar_binair:", "naar_octaal:", "naar_hex:", "vanuit_talstelsel:",
                "binary_search:", "bubble_sort:", "quick_sort:",
                "bfs:", "dfs:", "dijkstra:", "levenshtein:",
                "significante_cijfers:", "stel_precisie_in:",
                "breuk:", "som_reeks:", "sigma:", "meetkundige_reeks:",
                "kans_dobbelsteen:", "kans_kaart:",
            )):
                msg = err

            # --- 7. fallback ---
            else:
                msg = f"Er ging iets mis: {err}"

        self.event_bus.publish("layer4_response", {"text": msg})

def init_module(event_bus, semantic_module=None):
    mod = MathModule(event_bus)
    event_bus.publish("module_loaded", {"name": "math"})
    return mod