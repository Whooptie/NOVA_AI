"""
audit_zoeken.py - zoek- en filterlogica voor het debug-commando `audit`.

Waarom dit een los hulpbestand is (en geen tweede toegangsweg naast de chat):
- Het commando wordt aangeroepen vanuit debug_commands.py, dus je typt het
  gewoon in het gesprek met Nova, zoals `geheugen stats` of `bridge`.
- Dit bestand is puur lezen. Het wijzigt NOOIT iets in concepts.json.
- Geen klasse, geen init_module(), geen EventBus. Alleen pure functies,
  zoals core/twijfel_labeler.py. De module_loader slaat modules/debug/ sowieso
  over in de dynamische scan, dus er is niets te registreren.

100% symbolisch: bestand inlezen, lijsten filteren, tekst opmaken.

Syntax (alles na het woord `audit`):
    audit                      -> korte hulptekst
    audit <woord>              -> alle audit-regels van dat woord
    audit woord <woord>        -> idem, voor een woord dat zo heet als een
                                  sleutelwoord hieronder (bv. een concept "bron")
    audit laatste [n]          -> de n nieuwste audit-regels (standaard 10)
    audit afgewezen [dagen]    -> afwijzingen van de laatste N dagen (standaard 30)
    audit bron <naam>          -> alle betekenissen en relaties met die bron
    audit event <tekst> [dagen]-> audit-regels waarvan de eventnaam <tekst> bevat
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

try:
    from modules.paths import get_project_root
except Exception:  # pragma: no cover - alleen als het bestand los draait
    get_project_root = None


# ----------------------------------------------------------------------
# Instellingen
# ----------------------------------------------------------------------

MAX_REGELS = 25             # meer regels tonen we niet, wel "en nog N meer"
STANDAARD_LAATSTE = 10      # `audit laatste` zonder getal
STANDAARD_DAGEN = 30        # `audit afgewezen` zonder getal
MAX_DETAIL_TEKENS = 90      # lange details worden afgekapt

# Ik ken de exacte veldnamen in de audit-entries niet zeker (de ene plek zegt
# "event", een andere "action"). Daarom probeer ik per soort meerdere namen,
# de eerste die bestaat wint.
TIJD_SLEUTELS = ("timestamp", "tijd", "time", "ts", "at", "datum", "date", "created_at")
EVENT_SLEUTELS = ("event_type", "event", "action", "actie", "type", "soort")
BRON_SLEUTELS = ("source", "bron")

# Deze velden tonen we niet nog eens bij de details, die staan al in de regel.
_NIET_IN_DETAIL = set(TIJD_SLEUTELS) | set(EVENT_SLEUTELS) | set(BRON_SLEUTELS)

# Alles waarin dit stukje voorkomt, tellen we als een afwijzing.
AFWIJS_STUKJES = ("reject", "afgewezen", "weerleg", "tombstone")

HULPTEKST = (
    "Audit-log doorzoeken (alleen lezen):\n"
    "  audit <woord>               alle audit-regels van een woord\n"
    "  audit woord <woord>         idem, als het woord zelf een sleutelwoord is\n"
    "  audit laatste [n]           de n nieuwste regels (standaard 10)\n"
    "  audit afgewezen [dagen]     afwijzingen van de laatste dagen (standaard 30)\n"
    "  audit bron <naam> [status]  alles met die bron, bv. audit bron wikipedia rejected\n"
    "  audit event <tekst> [dagen] regels waarvan de eventnaam <tekst> bevat"
)


# ----------------------------------------------------------------------
# Inlezen
# ----------------------------------------------------------------------

def standaard_concepts_pad():
    """Pad naar data/concepts.json, gevonden via modules/paths.py."""
    if get_project_root is None:
        raise RuntimeError("modules.paths niet beschikbaar, geef een pad mee")
    return Path(get_project_root(__file__)) / "data" / "concepts.json"


def laad_concepten(pad=None):
    """
    Leest concepts.json en geeft de dictionary {woord: concept} terug.
    Bij een ontbrekend of kapot bestand: (None, foutmelding).
    """
    try:
        pad = Path(pad) if pad else standaard_concepts_pad()
        with open(pad, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, "concepts.json niet gevonden."
    except Exception as e:
        return None, f"concepts.json kon niet gelezen worden: {e}"

    if not isinstance(data, dict):
        return None, "concepts.json heeft een onverwacht formaat."
    return data, None


# ----------------------------------------------------------------------
# Hulpfuncties
# ----------------------------------------------------------------------

def _eerste_waarde(entry, sleutels):
    """Geeft de waarde van de eerste sleutel die in entry staat (anders None)."""
    for sleutel in sleutels:
        if sleutel in entry and entry[sleutel] not in (None, ""):
            return entry[sleutel]
    return None


def _parse_tijd(waarde):
    """
    Zet een tijdstip om naar een gewone (naive) datetime, of None.
    Kan tegen ISO-tekst ("2026-10-24T14:03:11", ook met Z of +02:00)
    en tegen een getal (seconden sinds 1970).
    """
    if waarde is None:
        return None
    try:
        if isinstance(waarde, (int, float)):
            return datetime.fromtimestamp(waarde)
        tekst = str(waarde).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(tekst)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _kort(tekst, max_tekens=MAX_DETAIL_TEKENS):
    tekst = str(tekst).replace("\n", " ")
    if len(tekst) <= max_tekens:
        return tekst
    return tekst[: max_tekens - 1] + "…"


def _naar_int(tekst, standaard):
    """'30' -> 30. Alles wat geen positief getal is -> standaardwaarde."""
    try:
        waarde = int(tekst)
        return waarde if waarde > 0 else standaard
    except (TypeError, ValueError):
        return standaard


def _maak_regel(woord, plek, entry):
    """Zet een ruwe audit-entry om naar een uniform dictionary-tje."""
    tijd_ruw = _eerste_waarde(entry, TIJD_SLEUTELS)
    details = {k: v for k, v in entry.items() if k not in _NIET_IN_DETAIL}
    return {
        "woord": woord,
        "plek": plek,                       # bv. "hond" of "hond#1"
        "event": str(_eerste_waarde(entry, EVENT_SLEUTELS) or "?"),
        "tijd": _parse_tijd(tijd_ruw),
        "tijd_ruw": tijd_ruw,
        "bron": _eerste_waarde(entry, BRON_SLEUTELS),
        "details": details,
    }


def verzamel_audit_regels(concepten):
    """
    Loopt over alle concepten en geeft ALLE audit-entries terug als lijst
    uniforme dictionary's: op concept-niveau en op sense-niveau.
    Kapotte stukken worden stil overgeslagen, zodat een vreemde regel
    nooit het hele commando laat crashen.
    """
    regels = []
    for woord, concept in concepten.items():
        if not isinstance(concept, dict):
            continue

        for entry in concept.get("audit_log") or []:
            if isinstance(entry, dict):
                regels.append(_maak_regel(woord, woord, entry))

        for sense in concept.get("senses") or []:
            if not isinstance(sense, dict):
                continue
            plek = sense.get("sense_id") or woord
            for entry in sense.get("audit_log") or []:
                if isinstance(entry, dict):
                    regels.append(_maak_regel(woord, plek, entry))
    return regels


def _sorteer_nieuwste_eerst(regels):
    # Regels zonder tijdstip komen helemaal achteraan.
    return sorted(regels, key=lambda r: (r["tijd"] is not None, r["tijd"] or datetime.min), reverse=True)


def _formatteer_regel(r, met_woord=False):
    """met_woord=True: het woord staat al vooraan de regel, dus de plek
    (die bij concept-regels gewoon het woord zelf is) niet nog eens tonen."""
    tijd = r["tijd"].strftime("%Y-%m-%d %H:%M") if r["tijd"] else "(geen tijd)"
    delen = [tijd] if (met_woord and r["plek"] == r["woord"]) else [tijd, r["plek"]]
    delen.append(r["event"])
    if r["bron"]:
        delen.append(f"bron={r['bron']}")
    if r["details"]:
        details = ", ".join(f"{k}={_kort(v)}" for k, v in r["details"].items())
        delen.append(details)
    return "  " + "  ".join(delen)


def _toon_lijst(kop, regels_tekst, extra_voet=None):
    """Plakt kop + (max MAX_REGELS) regels + 'en nog N meer' aan elkaar."""
    uitvoer = [kop]
    uitvoer.extend(regels_tekst[:MAX_REGELS])
    if len(regels_tekst) > MAX_REGELS:
        uitvoer.append(f"  … en nog {len(regels_tekst) - MAX_REGELS} meer")
    if extra_voet:
        uitvoer.append(extra_voet)
    return "\n".join(uitvoer)


# ----------------------------------------------------------------------
# De losse zoekopdrachten
# ----------------------------------------------------------------------

def audit_woord(concepten, woord):
    woord = woord.strip().lower()
    if woord not in concepten:
        return f"Ik ken het woord '{woord}' niet in concepts.json."
    regels = [r for r in verzamel_audit_regels(concepten) if r["woord"] == woord]
    if not regels:
        return f"'{woord}' bestaat, maar heeft geen audit-regels."
    regels = _sorteer_nieuwste_eerst(regels)
    return _toon_lijst(
        f"Audit-log van '{woord}' ({len(regels)} regels, nieuwste eerst):",
        [_formatteer_regel(r) for r in regels],
    )


def audit_laatste(concepten, n):
    regels = _sorteer_nieuwste_eerst(verzamel_audit_regels(concepten))
    if not regels:
        return "Er zijn nog geen audit-regels."
    regels = regels[:n]
    return _toon_lijst(
        f"De {len(regels)} nieuwste audit-regels:",
        [f"{r['woord']:<12}" + _formatteer_regel(r, met_woord=True) for r in regels],
    )


def _filter_op_periode(regels, dagen, nu):
    """Houdt regels van de laatste `dagen` dagen. Geeft (gefilterd, aantal_zonder_tijd)."""
    grens = nu - timedelta(days=dagen)
    zonder_tijd = sum(1 for r in regels if r["tijd"] is None)
    return [r for r in regels if r["tijd"] is not None and r["tijd"] >= grens], zonder_tijd


def _voet_zonder_tijd(aantal):
    if not aantal:
        return None
    return f"  ({aantal} regel(s) zonder tijdstip zijn overgeslagen)"


def audit_afgewezen(concepten, dagen, nu):
    alle = [
        r for r in verzamel_audit_regels(concepten)
        if any(stuk in r["event"].lower() for stuk in AFWIJS_STUKJES)
    ]
    gefilterd, zonder_tijd = _filter_op_periode(alle, dagen, nu)
    gefilterd = _sorteer_nieuwste_eerst(gefilterd)

    if not gefilterd:
        antwoord = f"Geen afwijzingen in de laatste {dagen} dagen."
        voet = _voet_zonder_tijd(zonder_tijd)
        return antwoord + ("\n" + voet if voet else "")

    return _toon_lijst(
        f"Afwijzingen van de laatste {dagen} dagen ({len(gefilterd)}):",
        [f"{r['woord']:<12}" + _formatteer_regel(r, met_woord=True) for r in gefilterd],
        _voet_zonder_tijd(zonder_tijd),
    )


def audit_event(concepten, tekst, dagen, nu):
    tekst = tekst.lower()
    alle = [r for r in verzamel_audit_regels(concepten) if tekst in r["event"].lower()]
    if dagen is not None:
        alle, zonder_tijd = _filter_op_periode(alle, dagen, nu)
        periode = f" in de laatste {dagen} dagen"
    else:
        zonder_tijd = 0
        periode = ""
    alle = _sorteer_nieuwste_eerst(alle)

    if not alle:
        antwoord = f"Geen audit-regels met '{tekst}' in de eventnaam{periode}."
        voet = _voet_zonder_tijd(zonder_tijd)
        return antwoord + ("\n" + voet if voet else "")
    return _toon_lijst(
        f"Audit-regels met '{tekst}'{periode} ({len(alle)}):",
        [f"{r['woord']:<12}" + _formatteer_regel(r, met_woord=True) for r in alle],
        _voet_zonder_tijd(zonder_tijd),
    )


def audit_bron(concepten, bron, status=None):
    """
    Dit kijkt niet in de audit-regels maar naar de data zelf: elke betekenis
    en elke relatie die als bron `bron` heeft. Met `status` (bv. "rejected")
    blijven alleen items met die status over.
    """
    bron = bron.strip().lower()
    status = status.strip().lower() if status else None
    gevonden = []
    for woord, concept in sorted(concepten.items()):
        if not isinstance(concept, dict):
            continue
        for sense in concept.get("senses") or []:
            if not isinstance(sense, dict):
                continue
            sense_id = sense.get("sense_id") or woord
            if (str(sense.get("source", "")).lower() == bron
                    and (status is None or str(sense.get("status", "")).lower() == status)):
                gevonden.append(
                    f"  {sense_id}  betekenis  status={sense.get('status', '?')}: "
                    f"{_kort(sense.get('definition', ''), 60)}"
                )
            for rel in sense.get("relations") or []:
                if (isinstance(rel, dict)
                        and str(rel.get("source", "")).lower() == bron
                        and (status is None or str(rel.get("status", "")).lower() == status)):
                    gevonden.append(
                        f"  {sense_id}  {rel.get('type', '?')} {rel.get('target', '?')}  "
                        f"status={rel.get('status', '?')}"
                    )

    extra = f" en status '{status}'" if status else ""
    if not gevonden:
        return f"Niets gevonden met bron '{bron}'{extra}."
    return _toon_lijst(f"Alles met bron '{bron}'{extra} ({len(gevonden)}):", gevonden)


# ----------------------------------------------------------------------
# Ingang voor debug_commands.py
# ----------------------------------------------------------------------

def voer_audit_uit(argumenten, concepts_pad=None, nu=None):
    """
    `argumenten` is alles wat na het woord `audit` getypt werd (mag leeg zijn).
    Geeft altijd een tekst terug, nooit een exception.
    """
    nu = nu or datetime.now()
    delen = (argumenten or "").strip().split()

    if not delen or delen[0].lower() in ("help", "hulp", "?"):
        return HULPTEKST

    concepten, fout = laad_concepten(concepts_pad)
    if fout:
        return fout

    try:
        commando = delen[0].lower()
        rest = delen[1:]

        if commando == "laatste":
            return audit_laatste(concepten, _naar_int(rest[0] if rest else None, STANDAARD_LAATSTE))

        if commando == "afgewezen":
            return audit_afgewezen(concepten, _naar_int(rest[0] if rest else None, STANDAARD_DAGEN), nu)

        if commando == "bron":
            if not rest:
                return "Geef een bron mee, bv.: audit bron wikipedia [rejected]"
            return audit_bron(concepten, rest[0], rest[1] if len(rest) > 1 else None)

        if commando == "event":
            if not rest:
                return "Geef een stukje van de eventnaam mee, bv.: audit event reject 14"
            dagen = _naar_int(rest[1], None) if len(rest) > 1 else None
            return audit_event(concepten, rest[0], dagen, nu)

        if commando == "woord":
            if not rest:
                return "Geef een woord mee, bv.: audit woord hond"
            return audit_woord(concepten, " ".join(rest))

        # Geen sleutelwoord: dan is het een gewoon woord.
        return audit_woord(concepten, " ".join(delen))

    except Exception as e:
        return f"audit: er ging iets mis ({e})"