#modules/knowledge/embedding_specialist.py

"""
embedding_specialist.py -- Semantic Fase 12, stap 1 (losstaand).

EERLIJKE LABEL: dit is een ML-specialist, GEEN symbolische AI.
Een voorgetraind taalmodel (sentence-transformers) zet tekst om in
getallen (vectoren). Nova's symbolische kern beslist wat er met de
scores gebeurt. Contract van deze module:

    tekst erin  ->  gelijkenis-score (cosine, -1 .. 1) eruit

Zelfde categorie als spaCy (Fase 11), Stockfish en MediaPipe: een
begrensde, externe tool. Het model is NIET de kern van Nova.

Wat deze module (nog) NIET doet:
  - niets opslaan in concepts.json (stap 2: Kevin bevestigt eerst)
  - niets aan de EventBus publiceren
  - Layer 1 / PMI niet aanraken (stap 3, optioneel)

Veilig falen: ontbreekt sentence-transformers of het model, dan
wordt de module uitgeschakeld (reden_uit) en geven alle methodes
een lege lijst terug. Nova start gewoon door.

Schaalwaarschuwing: cosine (-1..1) en PMI (0..1 genormaliseerd) zijn
NIET vergelijkbaar. Embedding-resultaten dragen daarom altijd
"bron": "embedding" en "model": <naam>.
"""

import hashlib
import importlib.util
import os
from pathlib import Path

try:
    import numpy as np
except ImportError:  # numpy staat in requirements, maar veilig falen
    np = None

# Kandidaat-standaard: meertalig (ook Nederlands). Dit is GEEN definitieve
# keuze -- tools/meet_embeddings.py vergelijkt kandidaten op jouw concepten.
MODEL_NAAM = "paraphrase-multilingual-MiniLM-L12-v2"
BRON_LABEL = "embedding"


def _project_root():
    # modules/knowledge/<dit bestand> -> project-root
    return Path(__file__).resolve().parents[2]


def _standaard_models_map():
    return _project_root() / "data" / "models"


def _standaard_cache_pad():
    return _project_root() / "data" / "embeddings_cache.npz"


def concept_tekst(woord, concept):
    """
    Bouwt de tekst die we laten embedden: 'woord: definitie'.
    Afgewezen (rejected) senses worden genegeerd. Geen bruikbare
    definitie -> None (zo'n concept doen we niet mee).
    """
    if not concept:
        return None
    defs = []
    for sense in concept.get("senses", []):
        if sense.get("status") == "rejected":
            continue
        d = (sense.get("definition") or "").strip()
        if d:
            defs.append(d)
    if not defs:
        return None
    return f"{woord}: " + " ".join(defs)


class EmbeddingSpecialist:
    def __init__(self, event_bus=None, sem=None, model=None,
                 model_naam=MODEL_NAAM, models_map=None, cache_pad=None,
                 concepten=None):
        """
        model     : testbaar nepmodel met .encode(lijst_teksten) -> array.
                    Is het None, dan wordt (lui, bij eerste gebruik)
                    sentence-transformers geladen.
        concepten : optioneel dict {woord: concept}; anders sem.store.concepts.
        """
        self.event_bus = event_bus
        self.sem = sem
        self.model_naam = model_naam
        self.models_map = Path(models_map) if models_map else _standaard_models_map()
        self.cache_pad = Path(cache_pad) if cache_pad else _standaard_cache_pad()
        self._concepten_override = concepten
        self._model = model
        self.reden_uit = None
        self._cache = {}  # woord -> (hash, vector)
        self._cache_geladen = False

        if np is None:
            self.reden_uit = "numpy niet geinstalleerd"
        elif model is None and importlib.util.find_spec("sentence_transformers") is None:
            self.reden_uit = "sentence-transformers niet geinstalleerd"

        if self.reden_uit:
            print(f"[EmbeddingSpecialist] uitgeschakeld: {self.reden_uit}")
        else:
            print(f"[EmbeddingSpecialist] module geladen (model: {self.model_naam}, "
                  f"wordt pas bij eerste gebruik ingeladen)")

    # ------------------------------------------------------------
    # Beschikbaarheid + model
    # ------------------------------------------------------------
    def _laad_model(self):
        """Laadt het model (eenmalig). Faalt het, dan reden_uit i.p.v. crash."""
        if self._model is not None or self.reden_uit:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self.models_map.mkdir(parents=True, exist_ok=True)
            self._model = SentenceTransformer(
                self.model_naam, cache_folder=str(self.models_map)
            )
        except Exception as e:
            self.reden_uit = f"model '{self.model_naam}' laden mislukt: {e}"
            print(f"[EmbeddingSpecialist] uitgeschakeld: {self.reden_uit}")

    def is_beschikbaar(self):
        if self.reden_uit:
            return False
        self._laad_model()
        return self._model is not None and not self.reden_uit

    # ------------------------------------------------------------
    # Kern: tekst -> vector -> score
    # ------------------------------------------------------------
    def embed(self, teksten):
        """Lijst teksten -> numpy-matrix (rij per tekst, lengte 1 genormaliseerd).
        Niet beschikbaar -> None."""
        if not teksten or not self.is_beschikbaar():
            return None
        try:
            m = np.asarray(self._model.encode(list(teksten)), dtype=float)
        except Exception as e:
            self.reden_uit = f"encode mislukt: {e}"
            print(f"[EmbeddingSpecialist] uitgeschakeld: {self.reden_uit}")
            return None
        normen = np.linalg.norm(m, axis=1, keepdims=True)
        normen[normen == 0] = 1.0
        return m / normen

    def similarity(self, tekst_a, tekst_b):
        """Cosine-gelijkenis tussen twee losse teksten, of None."""
        m = self.embed([tekst_a, tekst_b])
        if m is None:
            return None
        return float(np.dot(m[0], m[1]))

    # ------------------------------------------------------------
    # Concepten: vectoren (met cache op schijf)
    # ------------------------------------------------------------
    def _concepten(self):
        if self._concepten_override is not None:
            return self._concepten_override
        if self.sem is not None and hasattr(self.sem, "store"):
            return self.sem.store.concepts
        return {}

    @staticmethod
    def _hash(tekst, model_naam):
        return hashlib.sha1(f"{model_naam}\n{tekst}".encode("utf-8")).hexdigest()

    def _lees_cache(self):
        if self._cache_geladen:
            return
        self._cache_geladen = True
        try:
            if self.cache_pad.exists():
                data = np.load(self.cache_pad, allow_pickle=False)
                for w, h, v in zip(data["woorden"], data["hashes"], data["vectoren"]):
                    self._cache[str(w)] = (str(h), v)
        except Exception as e:
            # Kapotte cache is niet erg: we rekenen gewoon opnieuw uit.
            print(f"[EmbeddingSpecialist] cache onleesbaar, opnieuw berekenen: {e}")
            self._cache = {}

    def _schrijf_cache(self):
        if not self._cache:
            return
        tmp = Path(f"{self.cache_pad}.tmp{os.getpid()}.npz")
        try:
            self.cache_pad.parent.mkdir(parents=True, exist_ok=True)
            woorden = sorted(self._cache)
            np.savez(
                tmp,
                woorden=np.array(woorden),
                hashes=np.array([self._cache[w][0] for w in woorden]),
                vectoren=np.array([self._cache[w][1] for w in woorden]),
            )
            os.replace(tmp, self.cache_pad)  # atomisch, zoals ConceptStore.save()
        except Exception as e:
            print(f"[EmbeddingSpecialist] cache schrijven mislukt: {e}")
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def concept_vectoren(self):
        """
        {woord: vector} voor alle concepten met een bruikbare definitie.
        Alleen nieuwe of gewijzigde definities worden opnieuw uitgerekend;
        de rest komt uit de cache. Niet beschikbaar -> {}.
        """
        if not self.is_beschikbaar():
            return {}
        self._lees_cache()
        teksten = {}
        for woord, concept in self._concepten().items():
            t = concept_tekst(woord, concept)
            if t:
                teksten[woord] = t

        nieuw = [w for w, t in teksten.items()
                 if w not in self._cache
                 or self._cache[w][0] != self._hash(t, self.model_naam)]
        if nieuw:
            m = self.embed([teksten[w] for w in nieuw])
            if m is None:
                return {}
            for w, vec in zip(nieuw, m):
                self._cache[w] = (self._hash(teksten[w], self.model_naam), vec)
            self._schrijf_cache()

        return {w: self._cache[w][1] for w in teksten if w in self._cache}

    def find_similar(self, woord, top_k=5, min_score=0.0):
        """
        Meest gelijkende concepten, hoogste score eerst. Elk resultaat:
        {"woord", "score", "bron": "embedding", "model": <naam>}.
        Onbekend woord of module uit -> [].
        """
        woord = woord.lower().strip()
        vecs = self.concept_vectoren()
        if woord not in vecs:
            return []
        basis = vecs[woord]
        uit = []
        for w, v in vecs.items():
            if w == woord:
                continue
            s = float(np.dot(basis, v))
            if s >= min_score:
                uit.append({"woord": w, "score": round(s, 4),
                            "bron": BRON_LABEL, "model": self.model_naam})
        uit.sort(key=lambda r: r["score"], reverse=True)
        return uit[:top_k]


    def find_all_pairs(self, min_score=0.5):
        """
        Alle paren concepten met een score >= min_score, hoogste score eerst
        (voor de wachtrij 'gelijkenissen overlopen'). Elk paar komt maar een
        keer voor, alfabetisch: {"woord_a", "woord_b", "score", "bron", "model"}.
        Niet beschikbaar of geen concepten -> [].
        """
        vecs = self.concept_vectoren()
        if len(vecs) < 2:
            return []
        woorden = sorted(vecs)
        m = np.array([vecs[w] for w in woorden])
        s = m @ m.T
        i_idx, j_idx = np.triu_indices(len(woorden), k=1)
        scores = s[i_idx, j_idx]
        keep = np.nonzero(scores >= min_score)[0]
        uit = [{"woord_a": woorden[i_idx[k]], "woord_b": woorden[j_idx[k]],
                "score": round(float(scores[k]), 4),
                "bron": BRON_LABEL, "model": self.model_naam} for k in keep]
        uit.sort(key=lambda r: r["score"], reverse=True)
        return uit


def init_module(event_bus, sem=None):
    try:
        instance = EmbeddingSpecialist(event_bus=event_bus, sem=sem)
    except Exception as e:
        print(f"[EmbeddingSpecialist] kon niet starten: {e}")
        return None
    if hasattr(event_bus, "register_module"):
        event_bus.register_module("embedding_specialist", instance)
    return instance