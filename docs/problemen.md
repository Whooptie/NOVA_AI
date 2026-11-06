pyflakes

root@fe3ba95a4e86:/app# python -m pyflakes core modules identity tools scripts main.py
core/memory.py:5:1: 'os' imported but unused
modules/chess/chess_engine.py:10:1: 'pathlib.Path' imported but unused
modules/chess/chess_engine.py:425:9: local variable 'HIGHLIGHT_BG' is assigned to but never used
modules/chess/chess_engine.py:432:13: local variable 'gemarkeerde_velden' is assigned to but never used
modules/chess/chess_engine.py:773:33: f-string is missing placeholders
modules/learning/intent_classifier.py:23:1: 'os' imported but unused
modules/learning/intent_classifier.py:561:9: redefinition of unused 'os' from line 23
modules/response_learning/variant_feedback_logger.py:72:1: 'os' imported but unused
modules/debug/debug_commands.py:319:19: f-string is missing placeholders
modules/debug/debug_commands.py:350:19: f-string is missing placeholders
modules/debug/debug_commands.py:619:9: local variable 'aantal_voor' is assigned to but never used
modules/knowledge/graph_render_3d.py:35:1: 'modules.knowledge.graph_render.KLEUREN' imported but unused
modules/math/math.py:2583:13: `nonlocal dims` is unused: name is never assigned in scope
modules/math/math.py:2608:5: redefinition of unused '_dims_to_string' from line 578
modules/weather/weather.py:7:1: 'pathlib.Path' imported but unused
modules/preferences/train_sentiment_classifier.py:230:15: f-string is missing placeholders
modules/preferences/train_sentiment_classifier.py:237:19: f-string is missing placeholders
modules/preferences/kevin_profile.py:54:1: 'pathlib.Path' imported but unused
modules/chat/response_pipeline.py:3:1: 'random' imported but unused
identity/personality/train_classifier.py:223:15: f-string is missing placeholders
identity/personality/train_classifier.py:230:19: f-string is missing placeholders
scripts/spacy_verkenning3.py:205:23: f-string is missing placeholders
scripts/migrate_trust_state.py:185:5: local variable 'nieuwe_stats' is assigned to but never used
scripts/test_atomic_save.py:42:11: f-string is missing placeholders
scripts/test_atomic_save.py:43:11: f-string is missing placeholders
scripts/test_atomic_save.py:44:11: f-string is missing placeholders
root@fe3ba95a4e86:/app# 



radon

root@fe3ba95a4e86:/app# radon cc core modules identity tools scripts main.py -s -a -n D
core/semantic.py
    M 1648:4 ReasoningEngine.find_contradictions - D (29)
    M 932:4 SenseEngine.detect_pos - D (28)
    M 2405:4 TeachEngine._normalize_plural_if_noun - D (24)
    M 661:4 SenseEngine.add_periode - D (21)
core/intent_router.py
    M 5685:4 IntentRouter._route_intern - F (67)
    M 1193:4 IntentRouter.detect_definition - F (60)
    M 311:4 IntentRouter.handle_preference - D (27)
    M 574:4 IntentRouter.handle_weerleg - D (22)
    M 426:4 IntentRouter._ontleed_voorkeur_zin - D (21)
core/rekenfuncties.py
    F 109:0 _formule - E (38)
core/context_resolver.py
    F 247:0 los_op - D (29)
modules/chess/chess_engine.py
    M 725:4 ChessModule.handle_move - D (27)
modules/learning/intent_classifier.py
    M 380:4 IntentClassifier._haal_layer0_voorbeelden_op - D (21)
modules/knowledge/graph_render_3d.py
    F 86:0 _bouw_data - D (22)
modules/knowledge/graph_data.py
    F 463:0 statistieken - D (27)
    F 286:0 volledige_graaf - D (24)
modules/knowledge/knowledge_proposals.py
    M 280:4 KnowledgeProposals.on_extract - D (26)
modules/knowledge/similarity_proposals.py
    M 470:4 SimilarityProposals.on_keuze - E (36)
    M 345:4 SimilarityProposals.on_review - D (24)
modules/knowledge/wikipedia_teacher.py
    M 273:4 WikipediaTeacher._teach_word - F (47)
    M 819:4 WikipediaTeacher.on_wiki_andere_betekenis - D (30)
modules/knowledge/datum_terugblik.py
    F 273:0 vind_terugblik - E (40)
modules/knowledge/knowledge_extractor.py
    M 560:4 KnowledgeExtractor._zoek_used_for - F (64)
    M 446:4 KnowledgeExtractor._zoek_causes - E (37)
    M 398:4 KnowledgeExtractor._zoek_part_of - E (35)
    M 276:4 KnowledgeExtractor._zoek_is_a - D (30)
    M 361:4 KnowledgeExtractor._zoek_ondersoort - D (27)
    M 634:4 KnowledgeExtractor._zoek_has_part - D (24)
modules/math/math.py
    M 2286:4 MathModule._eval - F (101)
    M 2716:4 MathModule.on_math - E (39)
modules/body/body_state.py
    M 119:4 BodyState.on_body - E (38)
modules/activity/session_watcher.py
    M 571:4 SessionWatcher.check_activity_interruption - D (22)
tools/run_benchmark.py
    F 556:0 main - F (51)
    F 448:0 beoordeel - F (45)
    F 830:0 rapporteer - D (29)
scripts/spacy_verkenning3.py
    F 119:0 zoek_is_a - D (26)
    F 154:0 zoek_has_part - D (23)
scripts/koppelingen_audit.py
    F 103:0 analyseer_bron - F (56)
    F 267:0 bevindingen - E (40)
    F 329:0 maak_rapport - D (22)
main.py
    F 520:0 achtergrond_loop - E (38)
    F 722:0 main - E (34)

42 blocks (classes, functions, methods) analyzed.
Average complexity: E (35.023809523809526)

root@fe3ba95a4e86:/app# radon mi core modules identity tools scripts main.py -s
core/reboot_manager.py - A (62.69)
core/concept_hint.py - A (57.03)
core/semantic.py - C (0.00)
core/__init__.py - A (100.00)
core/twijfel_labeler.py - A (59.52)
core/event_bus.py - A (67.08)
core/response_engine.py - A (48.63)
core/nl_stopwoorden.py - A (100.00)
core/interruption_tracker.py - A (58.47)
core/intent_router.py - C (0.00)
core/module_loader.py - A (50.08)
core/patterns.py - A (59.70)
core/memory.py - A (32.21)
core/language_normalizer.py - A (45.50)
core/rekenwoorden.py - A (28.03)
core/rekenfuncties.py - B (18.53)
core/context_resolver.py - A (54.81)
core/logger.py - A (78.96)
core/last_context.py - A (60.92)
core/pending_question.py - A (50.72)
core/llm_bridge.py - A (71.30)
modules/__init__.py - A (100.00)
modules/paths.py - A (63.12)
modules/chess/chess_engine.py - A (28.95)
modules/chess/__init__.py - A (100.00)
modules/learning/__init__.py - A (100.00)
modules/learning/pattern_matcher.py - A (43.28)
modules/learning/word_associations_learner.py - A (31.08)
modules/learning/intent_classifier.py - A (45.16)
modules/response_learning/variant_kiezer.py - A (64.05)
modules/response_learning/variant_feedback_logger.py - A (50.52)
modules/response_learning/__init__.py - A (100.00)
modules/network/client_bridge.py - A (41.46)
modules/network/ntfy_meldingen.py - A (46.21)
modules/network/__init__.py - A (100.00)
modules/help/__init__.py - A (100.00)
modules/help/help.py - A (82.31)
modules/help/topics/schaken.py - A (100.00)
modules/help/topics/semantic.py - A (100.00)
modules/help/topics/__init__.py - A (100.00)
modules/help/topics/math.py - A (100.00)
modules/help/topics/algemeen.py - A (100.00)
modules/help/topics/graaf.py - A (100.00)
modules/help/topics/debug.py - A (100.00)
modules/experimental/emergence_engine.py - B (12.79)
modules/experimental/__init__.py - A (100.00)
modules/debug/debug_commands.py - B (14.45)
modules/debug/__init__.py - A (100.00)
modules/debug/audit_zoeken.py - A (39.20)
modules/knowledge/case_herinnering.py - A (20.42)
modules/knowledge/temporal_semantics.py - A (41.34)
modules/knowledge/kennisgaten_log.py - A (73.50)
modules/knowledge/embedding_specialist.py - A (48.66)
modules/knowledge/graph_render.py - A (56.20)
modules/knowledge/graph_render_3d.py - A (52.68)
modules/knowledge/graph_data.py - A (28.06)
modules/knowledge/graph_commands.py - A (60.16)
modules/knowledge/naam_onderhoud.py - A (50.01)
modules/knowledge/topic_suggestions.py - A (59.97)
modules/knowledge/__init__.py - A (100.00)
modules/knowledge/knowledge_proposals.py - A (30.12)
modules/knowledge/uncertainty.py - A (21.99)
modules/knowledge/similarity_proposals.py - A (20.74)
modules/knowledge/wikipedia_teacher.py - B (15.69)
modules/knowledge/contradiction_checker.py - A (58.83)
modules/knowledge/concept_overview.py - A (60.15)
modules/knowledge/datum_terugblik.py - B (18.72)
modules/knowledge/knowledge_extractor.py - C (0.00)
modules/knowledge/hypothese.py - A (45.86)
modules/math/__init__.py - A (100.00)
modules/math/math.py - C (0.00)
modules/math/math_uitleg.py - A (57.70)
modules/context/context_manager.py - A (37.88)
modules/context/handler_fouten.py - A (51.87)
modules/context/afwezigheid.py - A (52.13)
modules/context/__init__.py - A (100.00)
modules/weather/__init__.py - A (100.00)
modules/weather/rain.py - C (6.51)
modules/weather/forecast.py - A (45.77)
modules/weather/weather.py - A (21.71)
modules/body/body_state.py - A (40.68)
modules/body/__init__.py - A (100.00)
modules/preferences/kandidaat_suggesties.py - A (61.80)
modules/preferences/sentiment_classifier.py - A (56.13)
modules/preferences/__init__.py - A (100.00)
modules/preferences/train_sentiment_classifier.py - A (63.38)
modules/preferences/kevin_profile.py - A (40.73)
modules/chat/chat.py - B (16.26)
modules/chat/expression_injector.py - A (65.52)
modules/chat/chat_response_engine.py - A (100.00)
modules/chat/response_pipeline.py - A (58.66)
modules/chat/conversation_engine.py - A (59.95)
modules/chat/fallback_reflectie.py - A (62.85)
modules/chat/__init__.py - A (100.00)
modules/activity/session_watcher.py - A (34.35)
modules/activity/__init__.py - A (100.00)
modules/time/calendar.py - A (47.07)
modules/time/__init__.py - A (100.00)
modules/time/vakanties.py - A (52.90)
modules/time/holidays.py - A (53.45)
modules/time/zone.py - A (70.19)
modules/time/on_this_day.py - A (42.72)
modules/time/time.py - A (100.00)
identity/self_architecture.py - A (93.39)
identity/self_uiterlijk.py - A (64.50)
identity/__init__.py - A (100.00)
identity/self_query.py - A (57.93)
identity/blueprint/__init__.py - A (100.00)
identity/blueprint/loader.py - A (89.48)
identity/emotion/__init__.py - A (100.00)
identity/emotion/emotion_engine.py - A (58.99)
identity/personality/microlearning.py - A (42.24)
identity/personality/personality_engine.py - A (65.68)
identity/personality/behavior_modifiers.py - A (90.87)
identity/personality/train_classifier.py - A (63.46)
identity/personality/__init__.py - A (100.00)
identity/expression/__init__.py - A (100.00)
identity/expression/tone_engine.py - A (65.76)
tools/maak_blind_cases.py - A (57.47)
tools/blind_naar_vast.py - A (74.52)
tools/meet_embeddings.py - A (63.50)
tools/kennisgaten_overzicht.py - A (70.01)
tools/run_benchmark.py - C (6.11)
tools/__init__.py - A (100.00)
scripts/spacy_verkenning3.py - A (30.68)
scripts/spacy_verkenning2.py - A (45.30)
scripts/spacy_verkenning.py - A (76.24)
scripts/voeg_rain_toe.py - A (67.86)
scripts/live_controle.py - A (76.40)
scripts/conftest.py - A (100.00)
scripts/__init__.py - A (100.00)
scripts/migrate_trust_state.py - A (54.72)
scripts/test_atomic_save.py - A (61.20)
scripts/extractor_proef.py - A (64.47)
scripts/maak_graaf.py - A (100.00)
scripts/vergelijk_lemmatizer.py - A (66.69)
scripts/cleanup_test_events.py - A (98.87)
scripts/koppelingen_audit.py - A (22.15)
scripts/test_regen_bronnen.py - A (56.04)
scripts/terugblik_status.py - A (83.92)
scripts/ochtend_diagnose.py - A (74.26)
main.py - A (30.15)