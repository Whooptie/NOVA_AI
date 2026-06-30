# modules/math/math.py
import ast
import operator
import math
import re

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
            "solvegauss": self._solveGauss   # alias voor router die lowercase maakt

        }

        # constante waarden
        self.consts = {
            "pi": math.pi,
            "e": math.e
        }

        # SI-basiseenheden
        base_units = {
            "m":   ({"m": 1}, 1),
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

        # herstel meter-eenheid
        self.units["m"] = ({"m": 1}, 1)
        self.units["meter"] = ({"m": 1}, 1)

        self.units["m3"] = ({"m": 3}, 1)
        self.units["m^3"] = ({"m": 3}, 1)
        self.units["m**3"] = ({"m": 3}, 1)
        self.units["m2"] = ({"m": 2}, 1)
        self.units["m^2"] = ({"m": 2}, 1)
        self.units["m**2"] = ({"m": 2}, 1)

    import re

    def preprocess(self, expr):
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
        expr = re.sub(r'(\d+)-(\d+)', r'\1^-\2', expr)

        # 1. unit + exponent → unit^exponent
        #    voorbeelden: m3 → m^3, m2 → m^2, s-1 → s^-1
        expr = re.sub(r'([A-Za-z]+)(\d+)', r'\1^\2', expr)
        expr = re.sub(r'([A-Za-z]+)-(\d+)', r'\1^-\2', expr)

        # 2. µ → u
        expr = expr.replace("µ", "u")

        # 3. '3x5' → '3*5'
        expr = re.sub(r'(\d)\s*[xX]\s*(\d)', r'\1*\2', expr)

        # 4. alias-operatoren
        expr = expr.replace(" x ", " * ")
        expr = expr.replace("×", "*")
        expr = expr.replace(":", "/")
        expr = expr.replace("^", "**")

        # 5. detecteer getal + unit (alleen letters, maar NIET splitsen)
        #    dit matcht 5m, 10km, 3mw, 12uf, 1pa, 50km/h
        # 1) getal + unit zonder spatie (1m, 50km/h, 250mL)
        expr = re.sub(r'(\d+(\.\d+)?)([A-Za-zµ][A-Za-zµ/]*)', r'\1*\3', expr)

        # 2) getal + spatie + unit (1 bar, 250 mL, 60 rpm, 1 Wh, 2.5 Ah)
        expr = re.sub(r'(\d+(\.\d+)?)[ ]+([A-Za-zµ][A-Za-zµ/]*)', r'\1*\3', expr)

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

    def _eval(self, node):
        # getallen
        if isinstance(node, ast.Num):          # <3.8
            return node.n
        if isinstance(node, ast.Constant):     # 3.8+
            return node.value
    
        # vectoren (lijsten)
        if isinstance(node, ast.List):
            return [self._eval(e) for e in node.elts]

        # tuples (functie-argumenten)
        if isinstance(node, ast.Tuple):
            return [self._eval(e) for e in node.elts]
            
        # namen (constanten + eenheden)
        if isinstance(node, ast.Name):
            name = node.id

            # temperatuur-eenheden altijd via _make_unitvalue verwerken
            if name in ("degC", "degF"):
                return ("TEMP", name)

            # constante?
            if name in self.consts:
                return self.consts[name]

            # eenheid?
            if name in self.units:
                dims, factor = self.units[name]
                return UnitValue(factor, dims.copy()).bind_math(self)

            raise ValueError(f"Onbekende naam of eenheid: {name}")

        # binaire operatoren
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
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
            if isinstance(left, list) and isinstance(right, list):
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
            return op(self._eval(node.operand))

        # ⭐ 1. attribute access
        if isinstance(node, ast.Attribute):
            obj = self._eval(node.value)
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
                args = [self._eval(a) for a in node.args]
                if hasattr(obj, method):
                    return getattr(obj, method)(*args)
                raise ValueError(f"Onbekende methode: {method}")
                
            if not isinstance(node.func, ast.Name):
                raise ValueError("Ongeldige functie‑aanroep")

            fname = node.func.id
            if fname not in self.funcs:
                raise ValueError(f"Onbekende functie: {fname}")

            args = [self._eval(a) for a in node.args]
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

    def _format_value(self, v):
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
        expr = self.preprocess(data.get("expr", ""))

        try:
            result = self.eval_expr(expr)
            if isinstance(result, UnitValue):
                msg = f"{expr} = {result}"
            else:
                msg = f"{expr} = {result}"

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

            # --- 6. fallback ---
            else:
                msg = f"Er ging iets mis: {err}"

        self.event_bus.publish("math_response", {"msg": msg})

def init_module(event_bus, semantic_module=None):
    mod = MathModule(event_bus)
    event_bus.publish("module_loaded", {"name": "math"})
    return mod