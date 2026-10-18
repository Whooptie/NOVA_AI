# test_intent_classifier.py
#
# Echte pytest-test voor IntentClassifier (modules/learning/intent_classifier.py).
#
# BELANGRIJK (eerlijkheid over wat dit wel/niet test): dit is een
# scikit-learn ML-model (TF-IDF + LogisticRegression), geen LLM. De
# TF-IDF-vectorizer en LogisticRegression zijn deterministisch bij
# dezelfde trainingsdata (geen willekeurige initialisatie zoals bv.
# een neuraal netwerk) -- daarom test deze suite op EXACTE categorie-
# voorspellingen. Exacte confidence-scores test ik bewust NIET hard:
# die kunnen licht verschuiven bij een kleine wijziging in de
# TfidfVectorizer-instellingen of scikit-learn-versie, zonder dat de
# voorspelling zelf fout wordt. Categorie = het gedrag dat ertoe doet
# voor intent_router.py; confidence is een gevoeligere interne waarde.
#
# Isolatie: IntentClassifier accepteert data_dir als parameter -- elke
# test bouwt zijn eigen classifier op met tmp_path als data_dir, dus
# NOOIT de echte data/training_data.json, intent_classifier_model.pkl
# of intent_classifier_vectorizer.pkl.
#
# Uitvoeren: pytest tests/test_intent_classifier.py -v

import pytest

from modules.learning.intent_classifier import IntentClassifier


# Kleine, met opzet compacte trainingsset -- genoeg voorbeelden per
# categorie om LogisticRegression zinvol te laten trainen (elke
# categorie heeft minstens een paar duidelijk onderscheidende
# voorbeelden), maar klein genoeg om een test snel te houden. Dit is
# GEEN kopie van Kevin's echte, veel grotere trainingsset (198
# voorbeelden/10 categorieën) -- een eigen, kleine set binnen de test
# zelf, zodat de test niet afhankelijk is van Kevin's data die kan
# blijven groeien/wijzigen.
TRAININGSVOORBEELDEN = [
    ("wil je een potje schaken", "chess"),
    ("laten we schaken vanavond", "chess"),
    ("speel je een partij mee", "chess"),
    ("zin om te gaan schaken", "chess"),
    ("laten we nog een partij schaken", "chess"),
    ("ik wil een potje schaak spelen", "chess"),
    ("hoe is het weer vandaag", "weather"),
    ("moet ik een paraplu meenemen", "weather"),
    ("wordt het nog warm buiten", "weather"),
    ("is het lekker weer buiten", "weather"),
    ("gaat het morgen regenen", "weather"),
    ("hoe warm is het buiten", "weather"),
    ("hoe laat is het nu", "time"),
    ("heb je de tijd voor me", "time"),
    ("hoe laat zou het nu zijn", "time"),
    ("wat is de tijd op dit moment", "time"),
    ("hoe laat is het op de klok", "time"),
    ("wat zegt de klok nu", "time"),
    ("tel 15 en 27 op", "math"),
    ("wat is de wortel van 81", "math"),
    ("bereken de oppervlakte van een cirkel", "math"),
    ("hoeveel is twaalf keer drie", "math"),
    ("wat is vijf min twee", "math"),
    ("hoeveel is dertig plus acht min drie", "math"),
]


@pytest.fixture
def classifier(tmp_path):
    """Bouwt een geïsoleerde IntentClassifier op: eigen data_dir in
    tmp_path, eigen kleine trainingsset, eigen getraind model -- raakt
    nooit Kevin's echte data/training_data.json of modelbestanden."""
    clf = IntentClassifier(event_bus=None, data_dir=str(tmp_path))
    for tekst, label in TRAININGSVOORBEELDEN:
        clf.add_training_example(tekst, label, bron="test")
    getraind = clf.retrain()
    assert getraind, "retrain() gaf False terug -- te weinig categorieën/data."
    return clf


def test_predict_geeft_verwachte_structuur_terug(classifier):
    """predict() hoort een dict met label/confidence/all_scores terug
    te geven, met all_scores voor elke bekende categorie."""
    resultaat = classifier.predict("gaan we schaken vandaag")

    assert resultaat is not None
    assert "label" in resultaat
    assert "confidence" in resultaat
    assert "all_scores" in resultaat
    assert set(resultaat["all_scores"].keys()) == {"chess", "weather", "time", "math"}


@pytest.mark.parametrize("tekst, verwachte_categorie", [
    ("laten we verder schaken", "chess"),
    ("zullen we een potje schaak spelen", "chess"),
    ("wordt het morgen zonnig", "weather"),
    ("neem ik best een jas mee vandaag", "weather"),
    ("hoe laat begint de film", "time"),
    ("wat is klokslag nu", "time"),
    ("wat is twintig min acht", "math"),
    ("bereken hoeveel dat is samen", "math"),
], ids=[
    "chess_variant_1", "chess_variant_2",
    "weather_variant_1", "weather_variant_2",
    "time_variant_1", "time_variant_2",
    "math_variant_1", "math_variant_2",
])
def test_predict_kiest_juiste_categorie_voor_nieuwe_zin(classifier, tekst, verwachte_categorie):
    """
    Zinnen die NIET letterlijk in de trainingsset zitten (maar wel
    duidelijk bij één categorie horen) horen naar de juiste categorie
    geclassificeerd te worden -- dit is de kern-garantie: het model
    generaliseert, het herkent geen exacte zinnen uit het geheugen.
    """
    resultaat = classifier.predict(tekst)
    assert resultaat["label"] == verwachte_categorie, (
        f"'{tekst}' werd geclassificeerd als '{resultaat['label']}' "
        f"(scores: {resultaat['all_scores']}), verwachtte '{verwachte_categorie}'."
    )


def test_confidence_ligt_tussen_0_en_1(classifier):
    """De confidence-score (en alle scores in all_scores) horen
    geldige kansen te zijn, tussen 0 en 1."""
    resultaat = classifier.predict("gaan we schaken")
    assert 0.0 <= resultaat["confidence"] <= 1.0
    for score in resultaat["all_scores"].values():
        assert 0.0 <= score <= 1.0


def test_all_scores_telt_op_tot_1(classifier):
    """predict_proba() geeft een kansverdeling terug -- alle scores
    samen horen (afgerond) op te tellen tot 1.0."""
    resultaat = classifier.predict("wat voor weer wordt het")
    totaal = sum(resultaat["all_scores"].values())
    assert totaal == pytest.approx(1.0, abs=0.01)


def test_predict_zonder_getraind_model_geeft_none(tmp_path):
    """Een classifier zonder trainingsdata/model hoort None terug te
    geven bij predict(), niet te crashen."""
    lege_classifier = IntentClassifier(event_bus=None, data_dir=str(tmp_path))
    resultaat = lege_classifier.predict("gaan we schaken")
    assert resultaat is None


def test_add_training_example_breidt_categorieen_uit(classifier):
    """Een nieuw voorbeeld met een NIEUWE categorie hoort na
    add_training_example() + retrain() ook echt gekend te worden.

    LET OP: 4 voorbeelden gebruikt (gelijk aan de andere categorieën
    in TRAININGSVOORBEELDEN) i.p.v. eerder 2 -- met slechts 2 nieuwe
    voorbeelden tegenover 4 voor elke bestaande categorie stond de
    nieuwe categorie op voorhand in het nadeel (te weinig TF-IDF-
    signaal om tegen de rest op te wegen), wat geen bug was maar een
    te krappe testopzet."""
    classifier.add_training_example("hoi hallo goedemorgen", "greeting", bron="test")
    classifier.add_training_example("hey daar, hoe gaat het", "greeting", bron="test")
    classifier.add_training_example("goedendag, alles goed", "greeting", bron="test")
    classifier.add_training_example("hallo daar, fijn dat je er bent", "greeting", bron="test")
    getraind = classifier.retrain()

    assert getraind
    stats = classifier.get_stats()
    assert "greeting" in stats["categorieën"]

    resultaat = classifier.predict("hoi, goedemorgen daar")
    assert resultaat["label"] == "greeting"


def test_get_stats_bevat_verwachte_velden(classifier):
    stats = classifier.get_stats()
    assert stats["aantal_voorbeelden"] == len(TRAININGSVOORBEELDEN)
    assert set(stats["categorieën"]) == {"chess", "weather", "time", "math"}
    assert stats["model_geladen"] is True
    assert stats["laatst_getraind"] is not None


def test_model_wordt_herladen_van_schijf_niet_opnieuw_getraind(tmp_path):
    """
    Een NIEUWE IntentClassifier-instantie met hetzelfde data_dir hoort
    het al opgeslagen model van schijf te laden (pickle-bestanden),
    niet blindelings opnieuw te trainen -- bevestigt dat persistentie
    werkt zoals _laad_of_train_model() beschrijft.
    """
    clf1 = IntentClassifier(event_bus=None, data_dir=str(tmp_path))
    for tekst, label in TRAININGSVOORBEELDEN:
        clf1.add_training_example(tekst, label, bron="test")
    clf1.retrain()

    assert (tmp_path / "intent_classifier_model.pkl").exists()
    assert (tmp_path / "intent_classifier_vectorizer.pkl").exists()

    clf2 = IntentClassifier(event_bus=None, data_dir=str(tmp_path))
    resultaat = clf2.predict("laten we schaken")
    assert resultaat["label"] == "chess", (
        "Het herladen model geeft een andere voorspelling dan verwacht "
        "-- mogelijk werd het model niet correct van schijf geladen."
    )


# ---------------------------------------------------------------------
# Bug #50 (18 oktober 2026): Layer 0-voorbeelden bleven niet bewaard
# ---------------------------------------------------------------------
# Vroeger zat een gevonden Layer 0-voorbeeld enkel in het model van de
# hertraining waarin het gevonden werd, en viel het er bij de volgende
# hertraining zonder nieuwe gesprekken weer uit. Deze tests bewaken dat
# het voortaan permanent bewaard blijft in data/layer0_opgenomen.jsonl.
#
# Layer 0 zelf (memory.py) wordt hier NIET nagebootst: we vervangen
# _haal_layer0_voorbeelden_op() door een nepfunctie die een vaste
# reeks antwoorden teruggeeft. Dat functie logt anders naar het echte
# "data/"-pad, wat deze tests nooit mogen aanraken.

NIEUWE_LAYER0_VOORBEELDEN = [
    {"tekst": "zullen we een schaakpartij starten", "label": "chess", "bron": "layer0"},
    {"tekst": "gaat het vandaag sneeuwen", "label": "weather", "bron": "layer0"},
]


def test_layer0_voorbeelden_blijven_na_tweede_hertraining_in_het_model(classifier, monkeypatch):
    """
    DE regressietest voor bug #50. Eerste hertraining vindt 2 Layer 0-
    voorbeelden, tweede hertraining vindt er niets nieuws. Beide
    keren hoort het model op basis + dezelfde 2 voorbeelden getraind
    te worden (vroeger viel de tweede terug op enkel de basisset).
    """
    basis = len(classifier.voorbeelden)

    # Nep-Layer 0: eerste scan vindt 2 voorbeelden, tweede scan niets.
    reeks = [list(NIEUWE_LAYER0_VOORBEELDEN), []]
    monkeypatch.setattr(classifier, "_haal_layer0_voorbeelden_op", lambda: reeks.pop(0))

    # Spion op retrain(): onthoud met hoeveel voorbeelden er getraind werd.
    getraind_op = []
    originele_retrain = classifier.retrain

    def spion():
        getraind_op.append(len(classifier.voorbeelden))
        return originele_retrain()

    monkeypatch.setattr(classifier, "retrain", spion)

    assert classifier.retrain_vanuit_bestanden()
    assert classifier.retrain_vanuit_bestanden()

    assert getraind_op == [basis + 2, basis + 2], (
        f"Aantal trainingsvoorbeelden per hertraining: {getraind_op}, "
        f"verwachtte [{basis + 2}, {basis + 2}] -- een eerder gevonden "
        f"Layer 0-voorbeeld verdwijnt weer uit het model (bug #50)."
    )


def test_retrain_vanuit_bestanden_laat_training_data_json_schoon(classifier, monkeypatch, tmp_path):
    """training_data.json blijft Kevin's schone basisset: de Layer 0-
    voorbeelden horen enkel in layer0_opgenomen.jsonl te komen, nooit
    in training_data.json zelf (en ook niet blijvend in self.voorbeelden)."""
    import json

    basis = len(classifier.voorbeelden)
    monkeypatch.setattr(
        classifier, "_haal_layer0_voorbeelden_op",
        lambda: list(NIEUWE_LAYER0_VOORBEELDEN)
    )

    assert classifier.retrain_vanuit_bestanden()

    assert len(classifier.voorbeelden) == basis
    with open(tmp_path / "training_data.json", encoding="utf-8") as f:
        opgeslagen = json.load(f)
    assert len(opgeslagen["voorbeelden"]) == basis
    assert not any(v.get("bron") == "layer0" for v in opgeslagen["voorbeelden"])

    # En ze staan wél in het eigen Layer 0-bestand.
    assert (tmp_path / "layer0_opgenomen.jsonl").exists()
    assert len(classifier._laad_layer0_opgenomen()) == 2


def test_layer0_opgenomen_filtert_dubbels_onbekende_labels_en_rommel(classifier, tmp_path):
    """Bij het inlezen: dubbele zinnen (ook met andere hoofdletters)
    tellen één keer, onbekende labels, lege teksten en kapotte regels
    worden overgeslagen."""
    inhoud = "\n".join([
        '{"tekst": "zullen we schaken", "label": "chess"}',
        '{"tekst": "Zullen we schaken", "label": "chess"}',
        '{"tekst": "iets heel raars", "label": "bestaat_niet"}',
        'dit is helemaal geen json',
        '{"tekst": "   ", "label": "weather"}',
        '',
        '{"tekst": "gaat het sneeuwen", "label": "weather"}',
    ]) + "\n"
    (tmp_path / "layer0_opgenomen.jsonl").write_text(inhoud, encoding="utf-8")

    geladen = classifier._laad_layer0_opgenomen()

    assert [(v["tekst"], v["label"]) for v in geladen] == [
        ("zullen we schaken", "chess"),
        ("gaat het sneeuwen", "weather"),
    ]


def test_layer0_opgenomen_zonder_bestand_geeft_lege_lijst_en_lege_bewaring_maakt_geen_bestand(classifier, tmp_path):
    """Geen bestand = lege lijst (geen crash), en een lege lijst
    bewaren hoort geen leeg bestand aan te maken."""
    assert classifier._laad_layer0_opgenomen() == []

    classifier._bewaar_layer0_voorbeelden([])

    assert not (tmp_path / "layer0_opgenomen.jsonl").exists()