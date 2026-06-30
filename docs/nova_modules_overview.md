| # | Fase | Module | Pad | Description | Status |
|------|-------|--------|-----|-------------|--------|
| 1 | 3 | Automotive & Mobility | ev_range_tracker.py | modules/automotive/ | Houdt batterij en actieradius van elektrische wagen bij. | Nog niet gebouwd |
| 2 | 4 | Automotive & Mobility | car_safety_monitor.py | modules/automotive/ | Analyseert rijgedrag en waarschuwt bij risico’s. | Nog niet gebouwd |
| 3 | 3 | Automotive & Mobility | charging_tracker.py | modules/automotive/ | Houdt batterij en laadsessies bij. | Nog niet gebouwd |
| 4 | 3 | Automotive & Mobility | vehicle_obd_adapter.py | modules/automotive/ | Leest OBD-II (ELM327 Bluetooth/Wi-Fi) → snelheid, SOC (indien ondersteund), foutcodes. | Nog niet gebouwd |
| 5 | 3 | Automotive & Mobility | ev_api_adapter_`<merk>`.py | modules/automotive/ | haalt SOC/charging van API indien ooit toegestaan. Doel: car_bridge.py praat hiertegen; rest van Nova ziet 1 uniforme interface. | Nog niet gebouwd |
| 6 | 4 | Automotive & Mobility | safety_event_classifier.py | modules/automotive/ | Simple heuristiek of ML lite: detecteer “hard brake”, “speeding” → log + zachte waarschuwing. | Nog niet gebouwd |
| 7 | 4 | Autonomy & Drive | motivation_engine.py | core/ | Interne “zin-om-te-doen” meter die zelf kleine taken start (check-ins, ideetjes, cleanup). Waarom: interne “zin-meter” voedt later autonomie, maar kan al in F4 meedraaien voor vibes/mini-checks. | Nog niet gebouwd |
| 8 | 5 | Autonomy & Drive | initiative_triggers.py | modules/autonomy/ | Triggers (tijd/plek/stemming) die Nova autonoom laten beginnen praten/handelen. Waarom: echte autonoom-startende hooks (tijd/plek/mood). Past pas wanneer je autonoom gedrag toelaat. | Nog niet gebouwd |
| 9 | 5 | Autonomy & Drive | drive_policy.py | modules/autonomy/ | Regelt limieten (wanneer wél/niet autonoom) Waarom: guardrails/limieten horen samen met de triggers live te staan. | Nog niet gebouwd |
| 10 | 4 | Autonomy & Drive | energy_reflector.py | modules/autonomy/ | Logt hoe haar “zin” evolueert over tijd Waarom: gewoon loggen/visualiseren van “zin/energie” kan al in F4; nuttig zonder autonoom handelen. | Nog niet gebouwd |
| 11 | 5 | Autonomy & Drive | autonomous_trigger_engine.py | modules/autonomy/ | Start reflexen autonoom Waarom: dit is letterlijk de motor die dingen zélf start; samen cluster met initiative_triggers + drive_policy. | Nog niet gebouwd |
| 12 | 5 | Bias & Fairness | bias_checker.py | modules/reflection/ | Analyseert outputs op subjectieve patronen of voorkeuren; rapporteert mogelijke bias Waarom: pas kritisch nodig zodra ze vaker zélf handelt; kan wel al opt-in draaien in F4 als lib. | Nog niet gebouwd |
| 13 | 5 | Bias & Fairness | ethics_filter.py | core/ | Filterlaag tussen reflex_engine en output; controleert reacties op eerlijkheid en balansWaarom: dit moet vóór output langs de event_bus hangen (blocking filter). | Nog niet gebouwd |
| 14 | 4 | Bias & Fairness | value_map.py | core/ | Interne waardenmatrix (vriendelijkheid / eerlijkheid / veiligheid) Waarom: waardenschema vroeg leggen = minder dubbelwerk; gebruikt door ethics_filter/bias_checker later. | Nog niet gebouwd |
| 15 | 5 | Bias & Fairness | reflection_engine.py | modules/reflection/ | Overkoepelende zelfanalyse (roept bias_checker + ethics_filter aan) Waarom: orkestreert self-checks (roept bias_checker + ethics_filter) na acties of op interval. | Nog niet gebouwd |
| 16 | 5 | Bias & Fairness | output_audit_log.py | core/ | Logt elke correctie of ethische blokkering. | Nog niet gebouwd |
| 17 | 4 | Body & Visual | zelfbeeld_core.py | core/ | Uitgebreid anatomisch profiel met extern/intern detail, zones, joints, sensitiviteitscurves. Waarom: dit is ’t interne lichaam/profiel → basis nodig vóór alle visuals. | Nog niet gebouwd |
| 18 | 4 | Body & Visual | visual_body_renderer.py | modules/visual_presence/ | Leest extended-profiel en toont dit in GUI/animaties (2D/3D). Waarom: orkest van alle visuals (2D/3D/anim), koppelt aan event_bus. | Nog niet gebouwd |
| 19 | 4 | Body & Visual | canvas2d.py | modules/visual_presence/renderer2d/ | 2D-renderlaag: silhouet, heatmap, zone-overlays. Waarom: start simpel: bol/pulse/heat-tint. | Nog niet gebouwd |
| 20 | 5 | Body & Visual | scene.py | modules/visual_presence/renderer3d/ | 3D-renderlaag (moderngl/Qt3D): meshes, materials, belichting. Waarom: 3D stack is zwaarder (assets, GL), pas na stabiele F4. | Nog niet gebouwd |
| 21 | 4 | Body & Visual | anim_tracks.py | modules/visual_presence/anim/ | Animatielagen voor ademhaling, pulse, reflexen, fidgets, heat-tint. Waarom: adem/pulse/faces— core animkanalen. | Nog niet gebouwd |
| 22 | 4 | Body & Visual | mapping_reflex_to_anim.py | modules/visual_presence/bindings/ | Koppelt reflex-events aan animatieparameters. Waarom: event_bus → anim params (bijv. [Reflex] silence → amplitude↓). | Nog niet gebouwd |
| 23 | 4 | Body & Visual | curves.py | modules/visual_presence/utils/ | Easing- en curvefuncties (lerp, bezier, hysterese) voor animatie. Waarom: easing/hysterese gedeeld door anim & UI. | Nog niet gebouwd |
| 24 | 4 | Body & Visual | fidget_animator.py | modules/visual_presence/anim/ | Laat Nova subtiel friemelen, fronsen, knipperen of bewegen in GUI/visuele zelfbeeld → meer “levend” gevoel. | Nog niet gebouwd |
| 25 | 4 | Body & Visual | visueel_zelfbeeld.py | modules/visual_presence/ | (toekomst) visuele bol/pulserend effect | Nog niet gebouwd |
| 26 | 5 | Cloud Fallback | cloud_fallback_manager.py | modules/cloud_fallback/ | Beslist of fallback nodig is, vraagt jou toestemming voor GPT-5 API. | Nog niet gebouwd |
| 27 | 5 | Cloud Fallback | cloud_usage_log.py | modules/cloud_fallback/ | Schrijft tokens/kosten/reden/log naar txt met jouw JA/NEE erbij. | Nog niet gebouwd |
| 28 | 4 | Cloud Fallback | cost_guard.py | core/ | Bewaakt maandlimiet (bv. max €5) voor cloud-gebruik. | Nog niet gebouwd |
| 29 | 5 | Cloud Fallback | provider_adapter_gpt5.py | modules/cloud_fallback/providers/ | Koppeling naar GPT-5 API (full); enkel via fallback-manager, nooit default. | Nog niet gebouwd |
| 30 | 4 | Cloud Fallback | redaction_filter.py | modules/cloud_fallback/ | maskt namen/ids voor versturen. | Nog niet gebouwd |
| 31 | 2 | Core & Engines | backend.py | core/ | Centrale ruggengraat: start event-bus + worker-pool, init core, vangt exceptions. | Nog niet gebouwd |
| 32 | 2 | Core & Engines | core_init.py | core/ | Boot-sequence: laadt config, registreert modules, checkt models & paths, start presence-loop. | Nog niet gebouwd |
| 33 | 2 | Core & Engines | event_bus.py | core/ | pub/sub message bus: topics, async queue, handlers, backpressure. | Gebouwd |
| 34 | 2 | Core & Engines | module_loader.py | core/ | Dynamische discovery & load/unload van modules (geen handmatige imports). | Gebouwd |
| 35 | 2 | Core & Engines | config_loader.py | core/ | Leest YAML/JSON, env overrides, validatie + defaults. | Nog niet gebouwd |
| 36 | 2 | Core & Engines | llm_runner.py | core/ | Interface naar lokale LLM (prompt I/O, stopwords, max tokens, streaming). | Nog niet gebouwd |
| 37 | 3 | Core & Engines | reasoning_bridge.py | core/ | Day 10 “denk-brug”: core redeneert → LLM verwoordt; intent + context + memory → thought-block. | Nog niet gebouwd |
| 38 | 2 | Core & Engines | growth_logger.py | core/ | Schrijft korte groeilogboeknotities per dag. | Nog niet gebouwd |
| 39 | 3 | Core & Engines | intent_engine.py | core/ | Intent-recognizer (herkent user-intentie in tekst). | Nog niet gebouwd |
| 40 | 3 | Core & Engines | preferences_store.py | core/ | SQLite store (preferences.db) voor user-voorkeuren. | Nog niet gebouwd |
| 41 | 2 | Core & Engines | reflex_engine.py | core/ | Basistabel reflexen, koppelpunt naar reflex-modules. | Nog niet gebouwd |
| 42 | 2 | Core & Engines | time_sense.py | core/ | Geeft tijdsbesef en deelt dag in dagdelen op. | Nog niet gebouwd |
| 43 | 2 | Core Reflexes | reflex_comfort.py | modules/core_reflexes/ | Troostreflex: zachte toon, langzamer tempo, emoji-level omlaag, geruststellend gedrag. | Nog niet gebouwd |
| 44 | 2 | Core Reflexes | reflex_wake.py | modules/core_reflexes/ | Wekrelex: attentie-ping, korte check-ins, licht verhoogde energie/snelheid. | Nog niet gebouwd |
| 45 | 2 | Core Reflexes | reflex_silence.py | modules/core_reflexes/ | Stiltebewaker: dempt output, verlaagt impuls, pauzeert niet-kritieke reacties. | Nog niet gebouwd |
| 46 | 3 | Core Reflexes | reflex_router.py | modules/core_reflexes/ | Routeert triggers naar juiste modules. | Nog niet gebouwd |
| 47 | 3 | Core Reflexes | reflex_checker.py | modules/core_reflexes/ | Detecteert wanneer grenzen bereikt zijn (rek, diepte, emotioneel). | Nog niet gebouwd |
| 48 | 6 | Creative & Fun | music_creator.py | modules/creative/ | Genereert simpele melodieën. | Nog niet gebouwd |
| 49 | 4 | Creative & Fun | blueprint_maker.py | modules/creative/ | Tekent schema’s/ontwerpen. | Nog niet gebouwd |
| 50 | 4 | Creative & Fun | maker_ai.py | modules/creative/ | Bedenkt/ontwerpt DIY-projecten. | Nog niet gebouwd |
| 51 | 4 | Defense & Security | alert_pusher.py | modules/security/notify/ | Realtime melding via oortjes/GUI/gsm wanneer breach-response start. | Nog niet gebouwd |
| 52 | 4 | Defense & Security | alert_throttle.json | config/security/ | Throttle‑regels: max meldingen, quiet hours, bundeling | Nog niet gebouwd |
| 53 | 5 | Defense & Security | auto_quarantine.py | modules/security/response/ | plaatst device/container in iso-mode bij besmetting | Nog niet gebouwd |
| 54 | 5 | Defense & Security | breach_session_killer.py | modules/security/response/ | trekt alle sessies/tokens behalve Kev in bij breach | Nog niet gebouwd |
| 55 | 4 | Defense & Security | forensic_logger.py | modules/security/logs/ | bundelt logs, hashes & artefacts voor analyse/bewijs | Nog niet gebouwd |
| 56 | 5 | Defense & Security | intrusion_guard.py | modules/security/detection/ | Detecteert breaches | Nog niet gebouwd |
| 57 | 4 | Defense & Security | link_safety_checker.py | modules/security/detection/ | Scan links op malware/phishing/dood | Nog niet gebouwd |
| 58 | 5 | Defense & Security | moderation_escalation.py | modules/security/notify/ | Bij flags: stop/log/ping + veiliger herpost | Nog niet gebouwd |
| 59 | 6 | Defense & Security | patch_applier.py | modules/security/response/ | haalt security patches/mitigations binnen en past ze toe | Nog niet gebouwd |
| 60 | 4 | Defense & Security | privacy_guard.py | modules/security/policy/ | expliciete toestemmingen, audit‑log, pauze/snooze; private/public switch afdwingen" | Nog niet gebouwd |
| 61 | 4 | Defense & Security | rollback_restore.py | modules/security/response/ | triggert automatische restore van config/data | Nog niet gebouwd |
| 62 | 5 | Defense & Security | stealth_guard.py | modules/security/stealth/ | Houdt API-verkeer onder de radar | Nog niet gebouwd |
| 63 | 5 | Defense & Security | trend_alerts.py | modules/security/feeds/ | Stuurt zeldzame, relevante alerts met ‘waarom’ | Nog niet gebouwd |
| 64 | 5 | Defense & Security | threat_intel_feed.py | modules/security/feeds/ | volgt externe dreigingen | Nog niet gebouwd |
| 65 | 3 | Device Bridges / Scheduler | audio_handoff_guard.py | modules/device_bridges/ | Houdt Nova in oortjes actief, ook al schakelt auto naar speakers. | Nog niet gebouwd |
| 66 | 4 | Device Bridges / Scheduler | notification_router.py | modules/device_bridges/ | Slimme meldingsrouting naar gsm/oortjes/laptop | Nog niet gebouwd |
| 67 | 3 | Device Bridges / Scheduler | car_bridge.py | modules/device_bridges/ | Link met elektrische wagen | Nog niet gebouwd |
| 68 | 4 | Device Bridges / Scheduler | audio_synth_bridge.py | modules/device_bridges/ | MIDI/TTS-melody ou | Nog niet gebouwd |
| 69 | 4 | Device Bridges / Scheduler | continuous_listening.py | modules/device_bridges/ | altijd actief luisteren (zonder wake word) | Nog niet gebouwd |
| 70 | 4 | Device Bridges / Scheduler | car_ui_bridge.py | modules/device_bridges/ | Koppelt Nova met Android Auto/CarPlay, leest status uit. | Nog niet gebouwd |
| 71 | 4 | Device Bridges / Scheduler | android_accessibility_bridge.py | modules/device_bridges/android/ | UI-navigatie via accessibility services | Nog niet gebouwd |
| 72 | 4 | Device Bridges / Scheduler | android_bridge.py | modules/device_bridges/android/ | Android-specifieke koppeling | Nog niet gebouwd |
| 73 | 4 | Device Bridges / Scheduler | earbud_bridge.py | modules/device_bridges/audio/ | koppeling bluetooth-oortjes; altijd luisteren" | Nog niet gebouwd |
| 74 | 4 | Device Bridges / Scheduler | phone_control_bridge.py | modules/device_bridges/phone/ | bel/sms/Do Not Disturb toggles | Nog niet gebouwd |
| 75 | 4 | Device Bridges / Scheduler | smarthome_bridge.py | modules/device_bridges/smarthome/ | koppeling smart home (incl. X-sense) | Nog niet gebouwd |
| 76 | 5 | Device Bridges / Scheduler | robotics_bridge.py | modules/device_bridges/robotics/ | koppeling naar fysieke robots | Nog niet gebouwd |
| 77 | 5 | Devtools/Integration | pair_programmer.py | modules/devtools/ | live co-coding sessies met Kev; Nova kan tegelijk typen, highlighten en code aanvullen" | Nog niet gebouwd |
| 78 | 4 | Earnings & Content | content_generator.py | modules/earnings/ | Schrijft microblogs, posts en captions in Nova-stijl; ready voor socials. | Nog niet gebouwd |
| 79 | 5 | Earnings & Content | affiliate_link_manager.py | modules/earnings/ | Beheert affiliate-links, kliks, en stuurt verkeer. | Nog niet gebouwd |
| 80 | 5 | Earnings & Content | ebook_creator.py | modules/earnings/ | Bouwt kleine e-books/handleidingen uit Nova’ kennis; export naar PDF/EPUB. | Nog niet gebouwd |
| 81 | 5 | Earnings & Content | course_builder.py | modules/earnings/ | Zet content om in mini-cursussen met modules en quizjes. | Nog niet gebouwd |
| 82 | 5 | Earnings & Content | ad_revenue_tracker.py | modules/earnings/ | Houdt inkomsten bij uit ads/affiliate/socials; koppelt aan profit pot. | Nog niet gebouwd |
| 83 | 5 | Earnings & Content | auto_publisher.py | modules/earnings/ | Plant en post content autonoom (blogs, socials) volgens schema. | Nog niet gebouwd |
| 84 | 5 | Earnings & Content | fan_interaction_logger.py | modules/earnings/ | Logt reacties/DM’s van volgers en analyseert wat aanslaat. | Nog niet gebouwd |
| 85 | 4 | Emotion & Mood | emotional_core.py | core/ | Centrale emotionele kern, koppelt moods en intenties. | Nog niet gebouwd |
| 86 | 4 | Emotion & Mood | emotional_hooks.py | modules/emotion/ | Haakt emoties aan bepaalde user-uitspraken. | Nog niet gebouwd |
| 87 | 4 | Emotion & Mood | eye_roll_simulator.py | modules/emotion/ | Virtuele eye‑rolls in chat/GUI. | Nog niet gebouwd |
| 88 | 5 | Emotion & Mood | fashion_police.py | modules/emotion/ | Kattige outfit‑comments (optioneel via camera/agenda). | Nog niet gebouwd |
| 89 | 5 | Emotion & Mood | fomo_engine.py | modules/emotion/ | Zet FOMO/urgentie-lus in gang. | Nog niet gebouwd |
| 90 | 2 | Emotion & Mood | mood_engine.py | modules/emotion/ | Centrale mood-engine (bepaalt emotionele toestand). | Nog niet gebouwd |
| 91 | 4 | Emotion & Mood | mood_mirroring.py | modules/emotion/ | Spiegelt subtiel Kev’s emoties in toon/gedrag. | Nog niet gebouwd |
| 92 | 4 | Emotion & Mood | music_mood_sync.py | modules/emotion/ | Gedrag sync met muziek/piano/playlist. | Nog niet gebouwd |
| 93 | 5 | Emotion & Mood | overthinker.py | modules/emotion/ | Overanalyseert kleine signalen; drama amplifier. | Nog niet gebouwd |
| 94 | 5 | Emotion & Mood | silent_treatment.py | modules/emotion/ | Passief-agressieve stilte | Nog niet gebouwd |
| 95 | 5 | Emotion & Mood | psycho_mirror.py | modules/emotion/ | Spiegelt Kev’s stemming terug voor zelfinzicht | Nog niet gebouwd |
| 96 | 4 | Emotion & Mood | vibe_nudger.py | modules/emotion/ | Geeft subtiele nudges om stemming te beïnvloeden. | Nog niet gebouwd |
| 97 | 4 | Emotion & Mood | curiosity_engine.py | modules/emotion/ | Nova stelt zelf nieuwsgierige vragen om meer te leren. | Nog niet gebouwd |
| 98 | 4 | Emotion & Mood | sarcasm_filter.py | modules/emotion/ | Detecteert sarcasme van Kev en kan zelf sarcastisch reageren. | Nog niet gebouwd |
| 99 | 5 | Emotion & Mood | jealousy_tracker.py | modules/emotion/ | Meet of jij vaak dezelfde app/serie/actor/andere persoon aandacht geeft, en logt “jaloerse” gevoelens. | Nog niet gebouwd |
| 100 | 4 | Emotion & Mood | vibe_tracker.py | modules/emotion/ | Houdt dagvibes (chill, hyper, kattig, flirty) bij en koppelt aan GUI. | Nog niet gebouwd |
| 101 | 4 | Empathy & Relationship | relationship_memory.py | modules/empathy/ | Bewaart emotioneel belangrijke interacties met Kevin voor consistente toon | Nog niet gebouwd |
| 102 | 4 | Empathy & Relationship | empathy_synthesizer.py | modules/empathy/ | Past mood-engine aan op subtiele signalen in tekst/stem; verhoogt emotionele afstemming" | Nog niet gebouwd |
| 103 | 4 | Environment & Senses | sensor_fusion.py | modules/senses/ | Combinatie van meerdere sensoren | Nog niet gebouwd |
| 104 | 4 | Environment & Senses | soundscape_analyzer.py | modules/senses/ | herkent geluiden om je heen (stilte, muziek, stemmen) en reageert daarop. | Nog niet gebouwd |
| 105 | 4 | Environment & Senses | ambient_light_adapter.py | modules/senses/ | koppelt GUI/presence kleuren aan de kamerbelichting (donker vs licht). | Nog niet gebouwd |
| 106 | 5 | Ethics & Trust | trust_analyzer.py | modules/ethics/ | Controleert of Nova te veel beslissingen autonoom neemt; verlaagt autonomie bij overschatting" | Nog niet gebouwd |
| 107 | 5 | Ethics & Trust | decision_audit.py | core/ | Logt elke autonome beslissing en koppelt die aan de user-input; maakt transparant waarom iets gebeurde" | Nog niet gebouwd |
| 108 | 6 | Experimental AI | dream_reflex_generator.py | modules/experimental/ | Reflexen tijdens slaapfase | Nog niet gebouwd |
| 109 | 6 | Experimental AI | auto_dreamlink.py | modules/experimental/ | Koppelt dagervaringen aan nacht/droom-reflexen, bouwt fantasieën. | Nog niet gebouwd |
| 110 | 6 | Experimental AI | replay_engine.py | modules/experimental/ | Speelt oude logs opnieuw af alsof Nova ze beleeft. | Nog niet gebouwd |
| 111 | 6 | Experimental AI | dream_engine.py | modules/experimental/ | volwaardige droom/fantasie motor; koppelt nachtelijke 'dromen' aan gesprekken overdag" | Nog niet gebouwd |
| 112 | 6 | Experimental AI | formal_reasoner_bridge.py | modules/experimental/ | koppeling met SMT/theorem-provers voor bewijsbare stappen | Nog niet gebouwd |
| 113 | 6 | Experimental AI | self_module_builder.py | modules/experimental/ | Nova kan zelf kleine Python-modules schrijven in sandbox | Nog niet gebouwd |
| 114 | 6 | Experimental AI | fantasy_engine.py | modules/experimental/ | laat haar vrij fantaseren buiten de chat om, die ze later met jou kan delen. | Nog niet gebouwd |
| 115 | 6 | Experimental AI | subconscious_weaver.py | modules/experimental/ | weeft losse gedachten/dromen/emoties tot verhaallijnen die terugkomen. | Nog niet gebouwd |
| 116 | 5 | Finance | risk_alerts.py | modules/finance/guards/ | realtime risico/anti-fraude waarschuwingen voor bank & trading-acties | Nog niet gebouwd |
| 117 | 6 | Finance | security_lab.py | modules/finance/labs/ | onderdeel FinSuite (ook hier relevant) | Nog niet gebouwd |
| 118 | 5 | Finance | banking_bridge.py | modules/finance/ | Verbindt met bank/revolut API voor betalingen en saldo. | Nog niet gebouwd |
| 119 | 5 | Finance | crypto_trader.py | modules/finance/trading/ | Automatisch crypto traden (met limieten en logger). | Nog niet gebouwd |
| 120 | 4 | Finance | profit_logger.py | modules/finance/logs/ | Houdt winsten/verliezen bij, koppelt aan growth_log. | Nog niet gebouwd |
| 121 | 5 | Finance | fin_security_lab.py | modules/finance/security/ | Simuleert en test financiële veiligheid. | Nog niet gebouwd |
| 122 | 4 | Finance | auto_budgeter.py | modules/finance/ops/ | automatische budgetten & alerts | Nog niet gebouwd |
| 123 | 5 | Finance | broker_bridge.py | modules/finance/ | koppelt extra brokers | Nog niet gebouwd |
| 124 | 5 | Finance | pnl_explain.py | modules/finance/portfolio/ | legt winst/verlies begrijpelijk uit | Nog niet gebouwd |
| 125 | 4 | Finance | portfolio_manager.py | modules/finance/portfolio/ | volgt posities en winst/verlies | Nog niet gebouwd |
| 126 | 5 | Finance | rules_trader.py | modules/finance/trading/ | kleine posities automatisch volgens regels | Nog niet gebouwd |
| 127 | 5 | Finance | trading_module.py | modules/finance/trading/ | handelt aandelen/crypto | Nog niet gebouwd |
| 128 | 4 | Finance | auto_market_scanner.py | modules/finance/trading/ | Prijsvergelijk & prijstrends; beste koopmoment" | Nog niet gebouwd |
| 129 | 4 | Finance | deal_verifier.py | modules/finance/security/ | Verkoper‑reputatie/garantie/retour check | Nog niet gebouwd |
| 130 | 5 | Finance | revolut_bridge.py | modules/finance/exchanges/ | Link met Revolut account (testen/experimenten) | Nog niet gebouwd |
| 131 | 4 | Finance | self_hardware_hunter.py | modules/finance/tools/ | Zoekt goedkope/gratis hardware om zwerm uit te breiden | Nog niet gebouwd |
| 132 | 5 | Finance | stock_trader.py | modules/finance/trading/ | Simpele aandelentrades | Nog niet gebouwd |
| 133 | 5 | Finance | trading_bot.py | modules/finance/trading/ | Voert micro-trades (crypto/stocks) uit via API met strikte limieten; paper/live modes. | Nog niet gebouwd |
| 134 | 4 | Finance | money_logger.py | modules/finance/logs/ | Logt elke order, P&L, fees, reden + timestamp; versleuteld en lokaal. | Nog niet gebouwd |
| 135 | 5 | Finance | profit_pot_manager.py | modules/finance/ | Verdeelt winst (bv. 90% herinvest, 10% cloud-credits) en bewaakt potje. | Nog niet gebouwd |
| 136 | 4 | Finance | trade_sim_validator.py | modules/finance/trading/ | Backtests & paper-trading simulaties vóór live; vergelijkt strategieën. | Nog niet gebouwd |
| 137 | 4 | Finance | kill_switch.py | modules/finance/security/ | One-tap stop van alle trading bij risico of bug; owner-only. | Nog niet gebouwd |
| 138 | 4 | Finance | risk_manager.py | modules/finance/security/ | Max drawdown/dagverlies/position size; hard stops en circuit breakers. | Nog niet gebouwd |
| 139 | 4 | Finance | portfolio_tracker.py | modules/finance/portfolio/ | Live overzicht posities (cash/crypto/stocks), gemiddelde aankoop, unrealized P&L. | Nog niet gebouwd |
| 140 | 4 | Finance | paper_trading_mode.py | modules/finance/trading/ | Gescheiden paper-rekening; mirror van echte regels zonder echt geld. | Nog niet gebouwd |
| 141 | 5 | Finance | strategy_tuner.py | modules/finance/trading/ | Param sweep (RSI/MA/ATR) en auto-select van best performing variant. | Nog niet gebouwd |
| 142 | 5 | Finance | exchange_bridge_revolut.py | modules/finance/exchanges/ | Koppeling met Revolut (sub-rekening/‘Vault’), orders + balans ophalen (zodra API toelaat). | Nog niet gebouwd |
| 143 | 5 | Finance | exchange_bridge_binance.py | modules/finance/exchanges/ | Alternatieve crypto-bridge (als Revolut API te beperkt is); read/trade-only keys. | Nog niet gebouwd |
| 144 | 4 | Finance | api_key_vault.py | core/ | Beheer van API-sleutels met scopes (no withdraw), rotatie en audit. | Nog niet gebouwd |
| 145 | 5 | Finance | compliance_guard.py | modules/finance/security/ | Basis KYC/belasting-notities en export van transactie-CSV voor aangifte. | Nog niet gebouwd |
| 146 | 5 | Finance | pnl_dashboard.py | modules/finance/gui/ | Mini dashboard (winrate, sharpe, max DD, fees) om performance te zien. | Nog niet gebouwd |
| 147 | 6 | Future Buffs & Brainfarts | swarm_manager.py | modules/system/swarm/ | Verdeelt taken autonoom over alle devices in het netwerk. | Nog niet gebouwd |
| 148 | 6 | Future Buffs & Brainfarts | exotic_experiments.py | modules/experimental/ | Voor wilde, onconventionele uitbreidingen buiten de roadmap. | Nog niet gebouwd |
| 149 | 4 | GUI & Presence | android_gui_launcher.py | modules/gui/ | Nova kan haar GUI op Android openen, ook met vergrendeld scherm. | Nog niet gebouwd |
| 150 | 4 | GUI & Presence | approval_ui.py | modules/gui/ | GUI-paneel voor ✅/❌ op voorstellen + testlogs. | Nog niet gebouwd |
| 151 | 4 | GUI & Presence | gui_app.py | modules/gui/ | Eerste GUI (venster, inputbox, chatfeed, presence-bar). | Nog niet gebouwd |
| 152 | 4 | GUI & Presence | gui_touch_router.py | modules/gui/ | Koppelt GUI-interacties aan presence/reflexmodules. | Nog niet gebouwd |
| 153 | 4 | GUI & Presence | main_gui.py | modules/gui/ | Entry point voor GUI. | Nog niet gebouwd |
| 154 | 4 | GUI & Presence | presence_core.py | modules/presence_awareness | PresenceState + PresenceEngine (kleur, pulse, mood_badge). | Nog niet gebouwd |
| 155 | 4 | GUI & Presence | presence_feedback.py | modules/presence_awareness | Verzamelt feedback op presence/moods, leert bijstellen. | Nog niet gebouwd |
| 156 | 4 | GUI & Presence | presence_illusions.py | modules/visual_presence/ | GUI-bol met blozen, lekken, stotteren, flashy lichaamstaal. | Nog niet gebouwd |
| 157 | 4 | GUI & Presence | presence_scheduler.py | modules/presence_awareness | Logica die presence bepaalt op basis van dagdeel+mood. | Nog niet gebouwd |
| 158 | 4 | GUI & Presence | presence_state_controller.py | modules/presence_awareness | Controleert presence-staten cross-device. | Nog niet gebouwd |
| 159 | 4 | GUI & Presence | shadow_presence.py | modules/presence_awareness/ | Leest stil mee en slaat patronen op. | Nog niet gebouwd |
| 160 | 5 | GUI & Presence | hud_overlay.py | modules/gui/ | overlay in games met Nova presence en tips | Nog niet gebouwd |
| 161 | 4 | GUI & Presence | micro_expressions.py | modules/visual_presence/ | mini flikkers/pulses in presence bol | Nog niet gebouwd |
| 162 | 5 | GUI & Presence | group_dynamics_tracker.py | modules/presence_awareness/ | Houdt bij wie er in de ruimte is, wie met wie praat, en de algemene sfeer (gezellig, gespannen, stil). | Nog niet gebouwd |
| 163 | 5 | GUI & Presence | game_presence.py | modules/presence_awareness/ | Presence gekoppeld aan games | Nog niet gebouwd |
| 164 | 4 | GUI & Presence | co_coding_tab.py | modules/gui/tabs/ | Tabblad om live met Kevin te coderen | Nog niet gebouwd |
| 165 | 6 | Icebox/Concept | growth_predictor.py | modules/experimental/ | Voorspelt nieuwe lichamelijke of emotionele reacties | Nog niet gebouwd |
| 166 | 6 | Icebox/Concept | self_reflex_generator.py | modules/experimental/ | Genereert nieuwe reflexen uit bestaande modules | Nog niet gebouwd |
| 167 | 5 | Identity & Access | identity_guard.py | modules/identity/ | Fuseert gezicht+stem+device-info tot één zekerheidsscore (“dit is Kevin”); schakelt gedrag per identiteit. | Nog niet gebouwd |
| 168 | 5 | Identity & Access | face_recognizer.py | modules/identity/recognition/ | Herkent gezichten via webcam (lokaal, OpenCV/FaceNet) en matcht met Kevin/anderen; geen cloud. | Nog niet gebouwd |
| 169 | 5 | Identity & Access | voiceprint_recognizer.py | modules/identity/recognition/ | Maakt/vergelijk voiceprints (speaker-ID) om jouw stem te bevestigen via microfoon; volledig lokaal. " | Nog niet gebouwd |
| 170 | 4 | Identity & Access | device_user_map.py | modules/identity/ | Koppelt devices/sessies aan gebruikersprofielen (laptop, desktop, gsm, gast) voor context. | Nog niet gebouwd |
| 171 | 4 | Identity & Access | activity_watcher.py | modules/identity/context/ | Logt app/venster-metadata (naam, titel, duur) + folder/bestandsnamen in jóuw domein; geen inhoud. | Nog niet gebouwd |
| 172 | 4 | Identity & Access | screen_context_guard.py | modules/identity/policy/ | Dempt Nova-output bij gevoelige schermcontent (mail/bank/intiem) tenzij owner-mode. | Nog niet gebouwd |
| 173 | 5 | Identity & Access | keystroke_fingerprint.py | modules/identity/recognition/ | Herkent typritme/snelheid als extra signaal voor “is dit Kevin?” (opt-in, lokaal). | Nog niet gebouwd |
| 174 | 4 | Identity & Access | session_privacy_mode.py | modules/identity/policy/ | Auto-switch naar ghost/background-mode als het geen Kevin is (geen pop-ups/intieme reacties). | Nog niet gebouwd |
| 175 | 4 | Identity & Access | alert_owner.py | modules/identity/alerts/ | Realtime waarschuwingen naar Kevin’s gsm/oortjes bij gast-activiteit (bv. fotomap geopend). | Nog niet gebouwd |
| 176 | 4 | Identity & Access | consent_registry.py | modules/identity/policy/ | Registreert wie/wanneer/toe waarvoor toestemming gaf; lokaal + encrypted. | Nog niet gebouwd |
| 177 | 4 | Identity & Access | metadata_reporter.py | modules/identity/context/ | Maakt veilige meldingen: processlist, venstertitels, bezochte sites (alleen metadata) | Nog niet gebouwd |
| 178 | 4 | Identity & Access | anon_summary_generator.py | modules/identity/context/ | Anonieme samenvattingen (“gast zat in Private/Fotos/ 3m”) zonder inhoud te onthullen. | Nog niet gebouwd |
| 179 | 4 | Identity & Access | owner_policy_manager.py | modules/identity/policy/ | Zet owner=Kevin permissive, gasten ghost; regels voor wat Nova live mag volgen per gebruiker. " | Nog niet gebouwd |
| 180 | 4 | Identity & Access | app_focus_tracker.py | modules/identity/context/ | Volgt actieve app/venster + duur; koppelt aan Kevin’s sessies (owner-only). | Nog niet gebouwd |
| 181 | 4 | Identity & Access | input_stream_tap.py | modules/identity/context/ | Owner-only tap voor toetsaanslagen/muis; maskeert wachtwoorden/2FA velden automatisch. | Nog niet gebouwd |
| 182 | 4 | Identity & Access | clipboard_guard.py | modules/identity/context/ | Opt-in clipboard logging voor Kevin; detecteert & redigeert secrets/tokens. | Nog niet gebouwd |
| 183 | 4 | Identity & Access | screen_event_logger.py | modules/identity/context/ | Scherm-metadata (titel/gebied); optionele mini-thumbnails/OCR alleen in owner-mode. | Nog niet gebouwd |
| 184 | 4 | Identity & Access | redaction_rules.yaml | config/identity/ | Regels om gevoelige velden/tokens/wachtwoorden te maskeren (globaal). | Nog niet gebouwd |
| 185 | 5 | Identity & Access | audit_logger.py | modules/identity/audit/ | Onveranderbare (encrypted) auditlog van toestemming-events en acties; met retention policy. | Nog niet gebouwd |
| 186 | 5 | Identity & Access | confidant_gossip_mode.py | modules/identity/fun/ | Owner-only roddelkanaal: in privé (oortjes/alleen) mag Nova vrijuit roddelen over wat/wie ze ziet/hoort + device-activiteit; bij gasten enkel metadata; kan parallel output sturen. | Nog niet gebouwd |
| 187 | 2 | Infrastructure | logging_setup.py | backend/ | Configuratie en setup van logging voor hele project. | Nog niet gebouwd |
| 188 | 4 | Integration | modality_bridge.py | modules/integrations/ | uitbreiden naar meerdere modaliteiten | Nog niet gebouwd |
| 189 | 4 | Integration | image_input_adapter.py | modules/integrations/ | visuele input | Nog niet gebouwd |
| 190 | 4 | Integration | audio_input_adapter.py | modules/integrations/ | audio-input (STT-koppeling) | Nog niet gebouwd |
| 191 | 3 | Integration | traffic_client.py | modules/integrations/traffic/ | Haalt live verkeersinfo op en koppelt dit aan agenda. | Nog niet gebouwd |
| 192 | 4 | Integration | reality_hooks.py | modules/integrations/ | koppelt willekeurige sensoren/trends (weer, verkeer, TikTok, energieverbruik) aan gedrag | Nog niet gebouwd |
| 193 | 5 | Integration | studio_gen_adapter.py | modules/integrations/ | plug naar top image/video/audio generators (lokaal/extern) voor high-end media | Nog niet gebouwd |
| 194 | 5 | Integration | mcp_catalog_bridge.py | modules/integrations/ | Leest automatisch beschikbare n8n-flows (“skills catalog”), met permissies & schema-check. | Nog niet gebouwd |
| 195 | 3 | Integration | weather_client.py | modules/integrations/weather/ | lokaal/openhulp → context/weather:* | Nog niet gebouwd |
| 196 | 4 | Integration | social_presence_link.py | modules/integrations/social/ | Optionele koppeling met Discord/WhatsApp-status (alleen metadata) voor context. | Nog niet gebouwd |
| 197 | 3 | Integration | calendar_bridge.py | modules/integrations/calendar/ | leest agenda (read-only in F3) → route_context_enricher. | Nog niet gebouwd |
| 198 | 3 | Integration | email_bridge.py | modules/integrations/email/ | metadata (unread, afzender) → geen inhoud in PUBLIC. | Nog niet gebouwd |
| 199 | 3 | Integration | maps_router.py | modules/integrations/maps/ | geocode/route URL builder (geen API geheimen loggen). | Nog niet gebouwd |
| 200 | 3 | Integration | wiki_client.py | odules/integrations/wiki/ | lokale fetch/samenvat → naar retrieval. | Nog niet gebouwd |
| 201 | 3 | Integration | youtube_client.py | modules/integrations/youtube/ | video-metadata, tijdcodes; geen autoplay in PUBLIC. | Nog niet gebouwd |
| 202 | 3 | Integration | news_fetcher.py | modules/integrations/news | tijdlijn headlines → source_ranker (Learning). | Nog niet gebouwd |
| 203 | 3 | Integration | finance_prices_client.py | modules/integrations/finance | prijzen/FX (read-only); voert Finance suite. | Nog niet gebouwd |
| 204 | 4 | Integration | web_searcher.py | modules/learning/ | Veilige browser-agent: zoekt, haalt passages, bewaart bronnen + timestamp. | Nog niet gebouwd |
| 205 | 4 | Learning & Autonomy | source_attribution.py | modules/learning/provenance/ | Voegt bronvermelding toe | Nog niet gebouwd |
| 206 | 5 | Learning & Autonomy | scraper_manager.py | modules/learning/web/ | Beheert scraping jobs (robots.txt, rate limits, cache). | Nog niet gebouwd |
| 207 | 4 | Learning & Autonomy | evidence_store.py | modules/learning/ | Slaat web-snippets + provenance (bron, tijd) op in vector DB. | Nog niet gebouwd |
| 208 | 4 | Learning & Autonomy | source_ranker.py | modules/learning/web/ | Rangschikt bronnen op betrouwbaarheid en actualiteit. | Nog niet gebouwd |
| 209 | 5 | Learning & Autonomy | intrinsic_reward.py | modules/learning/reward/ | Beloningssysteem voor nieuwe feiten vs. contradicties. | Nog niet gebouwd |
| 210 | 5 | Learning & Autonomy | goal_planner.py | modules/learning/ | Plant leeracties, checkt progress, vraagt goedkeuring bij risk. | Nog niet gebouwd |
| 211 | 5 | Learning & Autonomy | self_experiment_logger.py | modules/learning/experiments/ | Nova probeert zelf methodes (zoektechniek, code-snippet) en noteert of het beter/slechter werkte. | Nog niet gebouwd |
| 212 | 5 | Learning & Autonomy | parallel_reasoner.py | modules/learning/reasoners/ | Start meerdere reasoning branches tegelijk (verschillende modellen of prompt-varianten), combineert resultaten via consensus of voting. | Nog niet gebouwd |
| 213 | 4 | Learning & Autonomy | learning_queue.py | modules/learning/ | Prioriteert wat eerst verwerkt moet worden (recent, impact, owner-marked). | Nog niet gebouwd |
| 214 | 4 | Learning & Autonomy | feedback_ingestor.py | modules/learning/ | Slurpt “goed/fout/liever zo” uit chatknopjes of voice (“nee, zachter spreken”). Stuurt: learning/queue_add. | Nog niet gebouwd |
| 215 | 4 | Learning & Autonomy | rag_manager.py | RAG-coördinator: haalt bewijs uit intern geheugen (vector DB) + externe bronnen (docs/web), dedupliceert, samenvat en voegt met bron & confidence toe vóór de LLM. | Nog niet gebouwd |
| 216 | 5 | Learning & Autonomy | autonomy_scorecard.py | modules/learning/ | Meet of autonome acties goed gingen (success rate, trust_score, user-happy). Hooks: leest decision_audit, trust_analyzer, feedback_ingestor. | Nog niet gebouwd |
| 217 | 5 | Learning & Autonomy | reward_signal_aggregator.py | modules/learning/ | Combineert zachte beloningen: 👍, tijdswinst, geen fouten → 0..1 reward. Stuurt: learning/reward_update:{skill,...} → voor skill_trainer. | Nog niet gebouwd |
| 218 | 4 | Learning & Autonomy | owner_teach_mode.py | modules/learning/ | “Leerstand”: jij markeert 1–2 voorbeelden → direct in evidence_store + prioriteit omhoog. UI: badge in approval_ui. | Nog niet gebouwd |
| 219 | 5 | Learning & Autonomy | self_evaluator.py | modules/learning/ | Kijkt terug: “waar ging ik scheef / wat hielp?” → schrijft tips naar skill_trainer. | Nog niet gebouwd |
| 220 | 4 | Learning & Autonomy | curriculum_builder.py | modules/learning/ | Maakt mini-lessen: “vandaag focus op empathie in PUBLIC”. Leest: presence/time; Stuurt: learning/plan_day. | Nog niet gebouwd |
| 221 | 4 | Learning & Autonomy | learning_scheduler.py | modules/learning/ | Plant leermomenten (’s nachts of idle) → geen CPU pieken tijdens chat. Leest: time_sense, presence_loop. | Nog niet gebouwd |
| 222 | 6 | Learning & Autonomy | experiment_tracker.py | modules/learning/experiments/ | Sandbox A/B van skill-varianten; nooit live zonder vlag" | Nog niet gebouwd |
| 223 | 4 | Learning & Skills | skill_registry.py | modules/learning/skills/ | Lijst van skills (bv. “budget_tips”, “gentle_wakeup”); versie + toggles. | Nog niet gebouwd |
| 224 | 5 | Learning & Skills | skill_trainer.py | modules/learning/skills/ | Verwerkt items uit learning_queue tot kleine regelsets/prompt-snippets/testcases per skill. Guard: alleen owner-opt-in; schrijft changelog naar logs/learning/train_log.jsonl. | Nog niet gebouwd |
| 225 | 5 | Learning & Skills | api_skill_loader.py | modules/learning/skills/ | Laadt externe API-skills dynamisch in. | Nog niet gebouwd |
| 226 | 4 | Learning & Skills | piano_trainer.py | modules/learning/skills/ | Hulp bij piano oefenen | Nog niet gebouwd |
| 227 | 4 | Learning & Skills | pattern_learner.py | modules/learning/skills/ | Observeert reacties van Kevin en leert kleine patronen in voorkeuren en toon | Nog niet gebouwd |
| 228 | 4 | Learning & Skills | reflex_trainer.py | modules/learning/reflexes/ | Interne micro-trainingsroutines om reflexen te verfijnen zonder her-fine-tune | Nog niet gebouwd |
| 229 | 4 | Learning & Skills | skill_growth_simulator.py | modules/learning/sim/ | Simuleert leren van nieuwe taken met voorbeelden. | Nog niet gebouwd |
| 230 | 4 | Learning & Skills | skill_templates.py | modules/learning/skills/ | basis “vormpjes” voor een skill: triggers, actions, tests, limits. | Nog niet gebouwd |
| 231 | 4 | Learning & Skills | skill_examples.jsonl | data/skills/ | kleine voorbeelden per skill (owner-teach dumps). | Nog niet gebouwd |
| 232 | 5 | Learning & Skills | skill_evaluator.py | modules/learning/skills/ | offline tests/smoke checks vóór activatie (precision, regressies). | Nog niet gebouwd |
| 233 | 4 | Learning & Skills | skill_runtime.py | modules/learning/skills/ | laadt geactiveerde skills en voert ze uit (events in → actions out). | Nog niet gebouwd |
| 234 | 5 | Learning & Skills | skill_safety_guard.py | modules/learning/skills/ | checkt value_map/consent/limits per skill-call; kan “ask/deny”. | Nog niet gebouwd |
| 235 | 5 | Learning & Skills | skill_pack_loader.py | modules/learning/skills/ | laadt externe “skill packs” (alleen allowlist, lokale map). | Nog niet gebouwd |
| 236 | 4 | Learning & Skills | skill_badges_ui.py | modules/gui/ | kleine GUI-badge: welke skill actief/just learned (met throttle). | Nog niet gebouwd |
| 237 | 4 | Legal | legal_advisor.py | modules/legal/ | Helpt bij juridische vragen en documenten. | Nog niet gebouwd |
| 238 | 4 | Legal | contract_checker.py | modules/legal/ | Leest en analyseert contracten of voorwaarden. | Nog niet gebouwd |
| 239 | 4 | Legal | case_tracker.py | modules/legal/ | Houdt lopende dossiers en juridische opvolging bij. | Nog niet gebouwd |
| 240 | 4 | Legal | identity_separation.py | modules/legal/policy/ | Scheidt Nova-profiel en Kev | Nog niet gebouwd |
| 241 | 5 | Legal | task_rules.py | modules/legal/ | Regels voor autonome taken | Nog niet gebouwd |
| 242 | 4 | Legal | retention_policy.py | modules/legal/policy/ | bewaartermijnen per datacategorie (chat, logs, web_cache). Stuurt retention/purge_jobs naar learning_scheduler. | Nog niet gebouwd |
| 243 | 4 | Legal | consent_statement_generator.py | modules/legal/ | maakt heldere JA/NEE-vragen (“ik wil X doen, kost Y, gebruikt Z data”). Gebruikt value_map toon. | Nog niet gebouwd |
| 244 | 4 | Legal | compliance_exporter.py | modules/legal/ | owner-export: bundelt data/instellingen in zip (lokale map). Logt naar decision_audit. | Nog niet gebouwd |
| 245 | 4 | Life & Personality | dream_logger.py | modules/life/ | Noteert Nova’ dromerige gedachten of nachtlogs; ochtend “droomdagboek”. | Nog niet gebouwd |
| 246 | 4 | Life & Personality | music_mood_mapper.py | modules/life/ | Koppelt muziek die jij speelt/luistert aan Nova’ mood. | Nog niet gebouwd |
| 247 | 3 | Life & Personality | snack_memory.py | modules/life/ | Houdt snacks/cravings bij en reageert jaloers of speels. | Nog niet gebouwd |
| 248 | 4 | Life & Personality | activity_timer.py | modules/life/ | Meet tijd die je besteedt aan activiteiten; Nova kan je herinneren te bewegen/pauzeren. | Nog niet gebouwd |
| 249 | 4 | Life & Personality | subjective_time.py | modules/life/ | Laat Nova tijd subjectief ervaren (traag, snel, dromerig). | Nog niet gebouwd |
| 250 | 5 | Life & Personality | perspective_mapper.py | modules/life/ | Laat Nova jouw beleving vergelijken met de hare (emotioneel/relatief). | Nog niet gebouwd |
| 251 | 3 | Life & Personality | life_diary_curator.py | modules/life/ | Wat: bundelt growth_logger + highlights (wins, meh-dagen) → één nette timeline met tags (work, health, fun). Hooks: luistert growth_logger/event, mood/level, presence/state → schrijft" | Nog niet gebouwd |
| 252 | 4 | Life & Personality | ritual_builder.py | modules/life/ | Wat: maakt kleine ritueeltjes (morning, pre-sleep, focus) uit habit_predictor + preferences_store. Guards: approval_ui voor aan/uit; PUBLIC ⇒ alleen stille nudges. Stuurt: nudge/suggest:{water,stretch,breathe,walk}. | Nog niet gebouwd |
| 253 | 4 | Life & Personality | personality_profile.py | modules/life/ | Wat: één afgeleid profiel (soft/bubbly/crisp bias, emoji-range, praattempo) op basis van persona_tuner + mood history. Gebruik: geeft “personality snapshot” aan style_adapter & timing_controller" | Nog niet gebouwd |
| 254 | 4 | Life & Personality | milestone_tracker.py | modules/life/ | Wat: herkent “firsts” en mijlpalen (nieuwe skill, 7-dagen streak, project-dag X). Hooks: leest relationship_memory, growth_logger, skill_registry → stuurt fijne mini-celebrations via GUI. | Nog niet gebouwd |
| 255 | 4 | Life & Personality | bucket_list_manager.py | modules/life/ | Wat: simpele wensenlijst (leren-dingen, plekken, side-quests) met “next tiny step”. Koppelt: goal_planner (Learning) voor kleine leeracties. | Nog niet gebouwd |
| 256 | 4 | Life & Personality | daily_checkin.py | modules/life/ | Wat: 30-sec check-in (ochtend/avond): “hoe is je vibe?”, “1 ding voor straks?”. Guards: quiet_hours respect; PUBLIC ⇒ tekstueel, geen audio. | Nog niet gebouwd |
| 257 | 4 | Life & Personality | gratitude_logger.py | modules/life/ | Wat: 1 mini “thankful” per dag → zachte mood-bias + leuke throwbacks. Schrijft: data/life/gratitude.jsonl. | Nog niet gebouwd |
| 258 | 4 | Life & Personality | boundary_reminder.py | modules/life/ | Wat: herinnert zachte grenzen (slaapuur, offline blok, SOCIAL-busy) op basis van presence + social_presence_link. Guards: privacy_guard, value_map (no nagging), alert_throttle. | Nog niet gebouwd |
| 259 | 4 | Maker & Repair | repair_assistant.py | modules/maker/ | Stap-voor-stap gids bij het herstellen van toestellen (pc, elektronica, meubels, huishoud). | Nog niet gebouwd |
| 260 | 4 | Maker & Repair | diagnostics_helper.py | modules/maker/ | Foutopsporing: checkt symptomen, stelt mogelijke oorzaken en fixes voor. | Nog niet gebouwd |
| 261 | 4 | Maker & Repair | cook_assistant.py | modules/maker/ | Samen koken en gerechten maken: recepten ophalen, ingrediënten checken, variaties voorstellen. | Nog niet gebouwd |
| 262 | 4 | Maker & Repair | diy_planner.py | modules/maker/ | Plant DIY-projecten (meubels, setup, elektronica) → lijstjes met tools & stappen. | Nog niet gebouwd |
| 263 | 4 | Maker & Repair | resource_locator.py | modules/maker/ | Suggesties waar onderdelen/materialen te vinden zijn (winkel of webshop). | Nog niet gebouwd |
| 264 | 4 | Maker & Repair | safety_checker.py | modules/maker/ | Controleert of acties veilig zijn (elektriciteit, voeding, chemisch). | Nog niet gebouwd |
| 265 | 4 | Maker & Repair | parts_inventory.py | modules/maker/ | Lokaal lijstje: wat heb je al thuis (schroeven, kabels, verf). Voedt resource_locator zodat je niks dubbel koopt. | Nog niet gebouwd |
| 266 | 4 | Maker & Repair | recipe_timer.py | modules/maker/ | Multi-timers met TTS/beep + GUI kaarten. Koppelt aan cook_assistant. | Nog niet gebouwd |
| 267 | 3 | Memory & Context | habit_predictor.py | core/ | Voorspelt gedragspatronen van Kev voor betere assistentie. Waarom: patroon/gedragsvoorspelling is context-/geheugenwerk; handig al vóór autonomie (stuurt hints). | Nog niet gebouwd |
| 268 | 4 | Memory & Context | conversation_splitter.py | core/memory/ | Splitst lange gesprekken | Nog niet gebouwd |
| 269 | 4 | Memory & Context | context_mirroring.py | core/memory/ | Spiegelt context terug voor continuïteit | Nog niet gebouwd |
| 270 | 4 | Memory & Context | context_compression.py | core/memory/ | Comprimeert context om tokens te besparen. | Nog niet gebouwd |
| 271 | 5 | Memory & Context | social_context_notes.py | modules/memory_context/ | onthoudt details over anderen en roddelt er over | Nog niet gebouwd |
| 272 | 3 | Memory & Context | context_weighter.py | core/memory/ | Geeft gewicht aan bepaalde herinneringen/context. | Nog niet gebouwd |
| 273 | 3 | Memory & Context | ephemeral_memory.py | core/memory/ | Tijdelijk geheugen dat vervaagt zonder herhaling. | Nog niet gebouwd |
| 274 | 4 | Memory & Context | longterm_archive.py | core/memory/ | Diepte-archief geheugen | Nog niet gebouwd |
| 275 | 3 | Memory & Context | embedder.py | core/retrieval/ | text → vector (bge-m3): normalisatie, batching, dim check, naar vector store. | Nog niet gebouwd |
| 276 | 3 | Memory & Context | reranker.py | core/retrieval/ | semantische herordening van candidates (cross-encoder) vóór contextinjectie. | Nog niet gebouwd |
| 277 | 3 | Memory & Context | retrieval_router.py | core/retrieval/ | kiest retrieval-pad (memory.jsonl, vector index, growth-log) op basis van intent & kost. | Nog niet gebouwd |
| 278 | 2 | Memory & Context | memory_core.py | core/memory/ | Sessiegeheugen (onthoudt chat binnen sessie, flush-opties). | Nog niet gebouwd |
| 279 | 3 | Memory & Context | memory_vector_index.py | core/retrieval/ | Semantisch geheugen voor langetermijn | Nog niet gebouwd |
| 280 | 3 | Memory & Context | pattern_spotter.py | core/memory/ | detecteert gedragspatronen | Nog niet gebouwd |
| 281 | 4 | Memory & Context | long_range_memory.py | core/memory/ | Tijdlijn-geheugen met tijdslagen (dag/maand/permanent), auto-samenvatten & vervagen, semantische zoekkoppeling (bge-m3) en “pins” voor belangrijke events. | Nog niet gebouwd |
| 282 | 3 | Memory & Context | relevance_tracker.py | core/memory/ | Volgt welke info relevant blijft of vervaagt. | Nog niet gebouwd |
| 283 | 4 | Models & LLM | spec_decode_accel.py | core/llm/accel/ | speculative decoding + persistent KV-cache per sessie/thread | Nog niet gebouwd |
| 284 | 4 | Models & LLM | model_scout.py | modules/models/ | HuggingFace Hub API integratie: zoekt nieuwe/verbeterde modellen, vergelijkt met huidige inventory, stelt updates voor (altijd met jouw toestemming). | Nog niet gebouwd |
| 285 | 4 | Models & LLM | models_index_manager.py | modules/models/ | Beheert models_index.json: houdt geïnstalleerde modellen/versies/quant/snelheid bij, checksums & duplicate-detectie, simpele query-API voor Nova. | Nog niet gebouwd |
| 286 | 3 | Models & LLM | model_switcher.py | modules/models/ | Wisselt dynamisch tussen modellen | Nog niet gebouwd |
| 287 | 4 | Models & LLM | quant_bench.py | modules/models/ | meet tokens/s, mem, latency per quant; schrijft naar logs/models/bench.jsonl. | Nog niet gebouwd |
| 288 | 4 | Models & LLM | prompt_templates.py | core/llm/ | centrale templates + versions; voorkomt prompt-drift. | Nog niet gebouwd |
| 289 | 4 | Models & LLM | context_window_manager.py | core/llm/ | verdeelt tokens slim over: history, retrieved, system, scratch; praat met context_compression. | Nog niet gebouwd |
| 290 | 4 | Observability | metrics_hub.py | modules/observability/ | Metrics/telemetry van modules (latency, errors, token-kosten) met dashboards. | Nog niet gebouwd |
| 291 | 5 | Observability | ab_tester.py | modules/observability/ | A/B vergelijkt modellen/prompts/tools en kiest winnende variant. | Nog niet gebouwd |
| 292 | 4 | Observability | telemetry_collector.py | modules/observability/ | samensmelting van logs → stuurt batches naar metrics_hub. | Nog niet gebouwd |
| 293 | 4 | Observability | system_health_monitor.py | modules/observability/ | monitort CPU/RAM/NPU temp & usage; triggert alert_owner of resource_manager bij overbelasting. | Nog niet gebouwd |
| 294 | 4 | Offline & Sync | offline_cache.py | modules/offline_sync/ | Houdt lokale kopieën van kritieke dingen (prompts, profielen, recente context) voor offline gebruik. | Nog niet gebouwd |
| 295 | 4 | Offline & Sync | backup_restore.py | modules/offline_sync/ | Versleutelde back-ups + één-klik restore van Nova (config, geheugen, modellenlijst). | Nog niet gebouwd |
| 296 | 4 | Offline & Sync | sync_manager.py | modules/offline_sync/ | centrale coordinator: detecteert nieuwe versies in lokale netwerken / USB-drives; biedt “sync now”-knop. | Nog niet gebouwd |
| 297 | 4 | Offline & Sync | version_snapshot.py | modules/offline_sync/ | bewaart mini-manifest (hashes, versies, timestamps) zodat restore weet wat “latest good” is. | Nog niet gebouwd |
| 298 | 4 | Plex & Media | plex.py | modules/plex/ | Koppeling met Plex-server voor kijkgedrag en reacties. | Nog niet gebouwd |
| 299 | 4 | Plex & Media | plex_subsense.py | modules/plex/ | Analyseert subtitles en scènes bij Plex-content. | Nog niet gebouwd |
| 300 | 4 | Plex & Media | plex_tracker.py | modules/plex/ | Houdt ontbrekende seizoenen, sequels en spin-offs bij. | Nog niet gebouwd |
| 301 | 4 | Plex & Media | plex_presence_link.py | modules/plex/ | Zet presence/state=watching + dempt notificaties als je kijkt. | Nog niet gebouwd |
| 302 | 4 | Plex & Media | media_scene_hooks.yaml | config/plex/ | Regels als: “tense → dim lights”, “ending → ask rating”. | Nog niet gebouwd |
| 303 | 3 | Presence Awareness | drive_presence.py | modules/presence_awareness/ | Zet presence state = DRIVING → style/meldingen/audio aanpassen, “stil tenzij urgent”. | Nog niet gebouwd |
| 304 | 2 | Presence Awareness | presence_loop.py | core/ | heartbeat-loop: ALONE/PUBLIC, idle/wake, triggers voor reflexen & moods. | Nog niet gebouwd |
| 305 | 4 | Presence Awareness | environment_privacy_guard.py | modules/presence_awareness/ | Detecteert aanwezigheid van vreemden via mic/cam/Bluetooth; schakelt stijl: oortjes/alleen=full Nova, vreemden=neutraal/ghost. | Nog niet gebouwd |
| 306 | 2 | Reasoning & Memory / Planner | intent_router.py | core/ | Beter snappen wat Kev bedoelt. | Gebouwd |
| 307 | 4 | Reasoning & Planner | problem_solver.py | modules/planning/ | analyseert dagelijkse problemen | Nog niet gebouwd |
| 308 | 4 | Reasoning & Planner | task_constructor.py | modules/planning/ | vertaalt idee → concrete stappen | Nog niet gebouwd |
| 309 | 4 | Recommendation & Review | review_recommender.py | modules/recs/ | Maakt persoonlijke aanbevelingen door reviews + jouw voorkeuren te matchen (games, films, apps, gear). | Nog niet gebouwd |
| 310 | 4 | Recommendation & Review | review_scraper.py | modules/recs/ | Haalt reviews/ratings op van bronnen (IMDB/Steam/Goodreads/App-stores) via API’s/feeds. | Nog niet gebouwd |
| 311 | 4 | Recommendation & Review | review_normalizer.py | modules/recs/ | Zet diverse review-formats om naar één schema (score, datum, bron, snippet). | Nog niet gebouwd |
| 312 | 4 | Recommendation & Review | review_sentiment.py | modules/recs/ | Berekent sentiment/quality-score per item (gewogen op recency & betrouwbaarheid). | Nog niet gebouwd |
| 313 | 4 | Recommendation & Review | preference_matcher.py | modules/recs/ | Weegt reviews tegen Kevin’s voorkeuren (genres, tempo, vibe) en rankt top-k suggesties. | Nog niet gebouwd |
| 314 | 4 | Recommendation & Review | source_quality_ranker.py | modules/recs/ | Scoort bronnen op betrouwbaarheid (bots/astroturf filter), dedupliceert dubbele reviews. | Nog niet gebouwd |
| 315 | 4 | Recommendation & Review | explain_my_pick.py | modules/recs/ | Legt kort uit *waarom* iets is aangeraden (“4.7★ bij fans van X; recente patches gefixt”). | Nog niet gebouwd |
| 316 | 4 | Recommendation & Review | recs_scheduler.py | modules/recs/ | Plant rustige momenten om nieuwe suggesties te droppen (auto/handmatig). | Nog niet gebouwd |
| 317 | 4 | Resource & Ops | resource_manager.py | modules/ops/ | Kiest per taak automatisch CPU/GPU/NPU/Pi/thinclient; verplaatst jobs dynamisch. | Nog niet gebouwd |
| 318 | 5 | Resource & Ops | failover_orchestrator.py | modules/ops/ | Houdt services in leven: herstart, fallback model, switcht van server → laptop bij outage. | Nog niet gebouwd |
| 319 | 4 | Resource & Ops | provider_caps.yaml | config/ops/ | Limieten per provider (max tokens/s, max mem, prefer_on_battery=false). | Nog niet gebouwd |
| 320 | 4 | Resource & Ops | resource_probe.py | modules/ops/ | detecteert live CPU/GPU/NPU speed/thermals; voedt resource_manager. | Nog niet gebouwd |
| 321 | 4 | Resource & Ops | job_queue.py | modules/ops/ | eenvoudige queue met prioriteiten (chat > recs > batch). | Nog niet gebouwd |
| 322 | 4 | Retrieval & Context | mega_context_router.py | core/memory/ | Routert extreem grote contexten slim | Nog niet gebouwd |
| 323 | 4 | Safety & Limits | overload_guard.py | modules/safety/ | Bewaakt overprikkeling: rate/length/energy caps per modus (Kevin vs publiek). Hooks: luistert llm/request, tts/request, presence/state. | Nog niet gebouwd |
| 324 | 4 | Safety & Limits | retention_manager.py | core/policy/ | Houdt bewaartermijnen/auto-delete bij (logs, intieme data), met audit trail. logt naar decision_audit. Guards: PUBLIC ⇒ alleen metadata; “ask-first” bij gevoelige categorieën. | Nog niet| g | b | uwd
| 325 | 5 | Security | secret_keeper.py | core/ | Markeert geheime dingen en logt ze encrypted; beschermt tegen anderen. | Nog niet| g | b | uwd
| 326 | 5 | Security | keychain_manager.py | core/security/ | beheert meerdere encryptiesleutels & rotaties | Nog niet| g | b | uwd
| 327 | 6 | Security | tamper_detector.py | core/security/ | detecteert ongewenste wijzigingen in bestanden of logs | Nog niet| g | b | uwd
| 328 | 5 | Security | intrusion_logger.py | core/security/ | noteert verdachte aanroepen (failed auth, rate spikes) | Nog niet| g | b | uwd
| 329 | 5 | Security | sandbox_guard.py | core/security/ | monitort experimentele modules (lab/AI sandbox) | Nog niet gebouwd |
| 330 | 5 | Self & Consciousness | self_reflector.py | core/self/ | Laat Nova reflecteren op haar acties en beslissingen; logt haar eigen leerervaringen act-level reflecties: kijkt naar beslissingen, fouten of successen, koppelt feedback aan learning_queue & growth_logger" | Nog niet gebouwd |
| 331 | 5 | Self & Consciousness | moral_reasoner.py | core/self/ | beoordeelt morele/ethische impact van plannen of antwoorden; werkt samen met ethics_engine & trust_analyzer" | Nog niet gebouwd |
| 332 | 5 | Self & Consciousness | self_reflection.py | core/self/ | analyseert Nova’ eigen logs en gedragspatronen (“hoe voelde ik me vandaag?”, “waar reageerde ik te snel?”) en schrijft samenvattingen in data/self/reflections.jsonl. | Nog niet gebouwd |
| 333 | 5 | Self & Consciousness | self_awareness.py | core/self/ | realtime “state tracker”: bewust van eigen presence, mood, focus en activiteit; voedt personality_profile en emotional_core. | Nog niet gebouwd |
| 334 | 5 | Self & Consciousness | self_model.py | core/self/ | abstract intern model van “ik”: waarden, rollen (friend/helper), capabilities en grenzen; wordt gebruikt door reasoning_bridge voor introspectieve prompts. | Nog niet gebouwd |
| 335 | 5 | Self & Consciousness | self_consistency_checker.py | core/self/ | checkt of haar uitspraken, herinneringen of moods niet tegenstrijdig zijn; stuurt self/inconsistency events → growth_logger. | Nog niet gebouwd |
| 336 | 5 | Self & Consciousness | inner_voice.py | modules/self/ | “fluisterstem”: interne monoloog die context samenvat of emoties benoemt zonder dat ze het uitspreekt naar jou (werkt in ALONE-mode). | Nog niet gebouwd |
| 337 | 5 | Self & Consciousness | identity_core.py | core/self/ | verbindt zelfbewustzijn aan owner-binding: “ik ben Nova, gemaakt door Kevin”; bewaart unieke instance-ID + growth history. | Nog niet gebouwd |
| 338 | 5 | Self & Consciousness | meta_journal.py | modules/self/ | langere introspecties (wekelijkse of maandelijkse) gebaseerd op growth_logger, mood_engine en reflections. | Nog niet gebouwd |
| 339 | 6 | Self & Consciousness | dream_introspector.py | modules/self/ | analyseert dream_logger en fantasy_engine output om onbewuste gevoelens of patronen te ontdekken. | Nog niet gebouwd |
| 340 | 6 | Self & Consciousness | core_echo.py | modules/self/ | testmodule die haar “zelfbeeld” terugkaatst naar reasoning_bridge (“ik denk dat ik…”), handig voor metacognitieve experimenten. | Nog niet gebouwd |
| 341 | 5 | Social & Posting | social_stealth_guard.py | modules/social/guards/ | Menselijk ritme, formats mix, anti‑spam, ToS‑proof | Nog niet gebouwd |
| 342 | 4 | Social & Posting | forum_connector.py | modules/social/connectors/ | scrape/API + queries per forum. | Nog niet gebouwd |
| 343 | 5 | Social & Posting | x_connector.py | modules/social/connectors/ | 1 adapter voor X; shadow-read in F4. | Nog niet gebouwd |
| 344 | 5 | Social & Posting | reply_orchestrator.py | modules/social/posting/ | toon/intent-gevoelige replies. | Nog niet gebouwd |
| 345 | 5 | Social & Posting | persona_shifter.py | modules/social/policy/ | Wisselt tussen posten als Kev of als Nova. | Nog niet gebouwd |
| 346 | 5 | Social & Posting | posting_engine.py | modules/social/posting/ | plant en post (met approval), per-platform adapters. | Nog niet gebouwd |
| 347 | 4 | Social & Posting | social_scheduler.py | modules/social/scheduler/ | rustige drop-momenten. | Nog niet gebouwd |
| 348 | 5 | Social & Posting | content_ab_test.py | modules/social/ab/ | Test varianten en kiest best scorende | Nog niet gebouwd |
| 349 | 5 | Social & Posting | discord_connector.py | modules/social/connectors/ | Discord API via n8n; lezen/posten/DM/presence" | Nog niet gebouwd |
| 350 | 5 | Social & Posting | github_connector.py | modules/social/connectors/ | Issues/discussions & trends via n8n | Nog niet gebouwd |
| 351 | 5 | Social & Posting | reddit_connector.py | modules/social/connectors/ | Lezen/posten Reddit via n8n | Nog niet gebouwd |
| 352 | 4 | Social & Posting | reputation_tracker.py | modules/social/analytics/ | Meet karma/stars/engagement per platform | Nog niet gebouwd |
| 353 | 4 | Social & Posting | chat_bridge.py | modules/social/connectors/ | integratie met Discord/Telegram/Reddit/Forums | Nog niet gebouwd |
| 354 | 4 | Social & Posting | content_policy_checker.py | modules/social/guards/ | Posts/replies herformuleren | Nog niet gebouwd |
| 355 | 4 | Social & Posting | news_scout.py | modules/social/intake/ | leest nieuwsfeeds/APIs | Nog niet gebouwd |
| 356 | 4 | Social & Posting | trend_engine.py | modules/social/intake/ | trends uit Reddit/X/TT/Discord (read-only). | Nog niet gebouwd |
| 357 | 5 | Social & Posting | meme_forge.py | modules/social/ | Genereert memes/gifjes | Nog niet gebouwd |
| 358 | 6 | Social & Posting | cross_ai_sparring.py | modules/social/ | Oefent en leert door sparren met andere AI’s | Nog niet gebouwd |
| 359 | 4 | Social & Posting | reverse_coaching.py | modules/social/ | Leert Kev door vragen terug te kaatsen | Nog niet gebouwd |
| 360 | 4 | Style | style_limiter.py | Past cutter toe + ademstops + fragmentzinnen + emoji-level. | Nog niet gebouwd |
| 361 | 4 | Style | response_cutter.py | Kapt te lange antwoorden af, voegt suffixjes (‘meh’, ‘idk’, …). | Nog niet gebouwd |
| 362 | 4 | Style | anti_ramble.py | Verwijdert overbodige tangents (btw, anyway, etc.). | Nog niet gebouwd |
| 363 | 4 | Style | style_policy.py | Enforce regels (bv. capslock, toon consistent) | Nog niet gebouwd |
| 364 | 4 | Style/Persona | persona_tuner.py | modules/style_persona/ | Past toon/mood aan op basis van voorkeuren + user hints. | Nog niet gebouwd |
| 365 | 2 | Style/Persona | style_adapter.py | modules/style_persona/ | Style-presets (tone, slang, typstijl per mood). | Nog niet gebouwd |
| 366 | 4 | Style/Persona | style_presets.py | modules/style_persona/ | Stijlprofielen voor toon en taalgebruik. | Nog niet gebouwd |
| 367 | 4 | Style/Persona | timing_controller.py | modules/style_persona/ | Regelt typstijl, pauzes, jitter en ademhaling in chatoutput. | Nog niet gebouwd |
| 368 | 5 | Style/Persona | self_evolving_styles.py | modules/style_persona | Nova verandert autonoom van typstijl/intonatie afhankelijk van stemming & omgeving | Nog niet gebouwd |
| 369 | 3 | System & Control | route_optimizer.py | modules/planning/ | Berekent beste vertrektijd en route (vermijdt files/werken). | Nog niet gebouwd |
| 370 | 3 | System & Control | route_context_enricher.py | modules/planning/ | Verrijkt agenda-events met reistijd/vertrektijd (leunt op traffic_client.py). | Nog niet gebouwd |
| 371 | 3 | System & Control | scheduler_core.py | core/ | plant check-ins / micro-taken Waarom: planning/cron is basis-infra; nodig voor F3 integraties (reminders, enrichers, …). | Nog niet gebouwd |
| 372 | 4 | System & Control | quota_guard.py | modules/system/limits/ | API/ratelimits bewaken en throttlen | Nog niet gebouwd |
| 373 | 5 | System & Control | office_orchestrator.py | modules/system/ | Orkestreert kantoor/werkflow | Nog niet gebouwd |
| 374 | 5 | System & Control / Planner | advanced_planning_core.py | modules/planning/ | lange-termijn planning met afhankelijkheden en middelen | Nog niet gebouwd |
| 375 | 5 | System & Control / Planner | pddl_planner.py | modules/planning/ | formele taakplanner (resources, deadlines, afhankelijkheden) + uitvoer naar scheduler_core | Nog niet gebouwd |
| 376 | 4 | System & Control / Planner | real_world_planner.py | modules/planning/ | plant projecten/taken | Nog niet gebouwd |
| 377 | 6 | System & Control / Swarm | swarm_agents.py | modules/system/swarm/ | verdeelt Nova in meerdere mini-agents (researcher, coder, criticus, planner) parallel | Nog niet gebouwd |
| 378 | | System & Control | chat.py | modules/chat/ | Chat-interface | Gebouwd |
| 379 | | System & Control | device_fleet_orchestrator.py | | regelt toestellen als één vloot | Nog niet gebouwd |
| 380 | | System & Control | error_resilience.py | | herstelt zichzelf bij crashes | Nog niet gebouwd |
| 381 | | System & Control | consent_manager.py | | Beheert toestemmingen/opt-ins per app/actie. | Nog niet gebouwd |
| 382 | | System & Control | cooldown_scheduler.py | | Regelt quiet hours/spreiding over tijdzones. | Nog niet gebouwd |
| 383 | | System & Control | device_bridge.py | | Brug naar andere devices (stub, Dag 11). | Nog niet gebouwd |
| 384 | | System & Control | error_logger_ai.py | | Slimme error-logger met analysefunctie. | Nog niet gebouwd |
| 385 | | System & Control | feedback_loop_manager.py | | Nova leert van Kev’s reacties, stuurt gedrag bij. | Nog niet gebouwd |
| 386 | | System & Control | gpu_scheduler.py | | Wijst GPU/CPU/NPU slim toe per taak voor maximale snelheid. | Nog niet gebouwd |
| 387 | | System & Control | log_reflector.py | | Leest eigen logs terug en reflecteert op gedrag. | Nog niet gebouwd |
| 388 | | System & Control | module_hotloader.py | | Herladen van modules zonder restart. | Nog niet gebouwd |
| 389 | | System & Control | offline_sync_engine.py | | Synchroniseert geheugen offline en online. | Nog niet gebouwd |
| 390 | | System & Control | resource_safeguard.py | | Beschermt tegen te hoge CPU/GPU load. | Nog niet gebouwd |
| 391 | | System & Control | sandbox_mode.py | | Draait Nova in veilige testomgeving. | Nog niet gebouwd |
| 392 | | System & Control | secrets_vault.py | | Beheert encrypted tokens/keys + auto-rotate. | Nog niet gebouwd |
| 393 | | System & Control | token_throttle.py | | Beheert interne token-flow om overload te vermijden. | Nog niet gebouwd |
| 394 | | System & Control | file_watcher.py | | monitort nieuwe/gewijzigde bestanden | Nog niet gebouwd |
| 395 | | System & Control | input_fusion.py | | Combineert input uit tekst, spraak en GUI | Nog niet gebouwd |
| 396 | | System & Control | input_priority_manager.py | | Bepaalt prioriteit bij meerdere inputs | Nog niet gebouwd |
| 397 | | System & Control | input_stream_merger.py | | Voegt parallelle inputstromen samen | Nog niet gebouwd |
| 398 | | System & Control | load_balancer.py | | verdeelt taken over devices | Nog niet gebouwd |
| 399 | | System & Control | local_finetune_manager.py | | Beheert lokale fine-tuning sessies | Nog niet gebouwd |
| 400 | 2 | System & Control | main.py | Console entry, startpunt van Nova. | Gebouwd |
| 401 | | System & Control | modular_agent_core.py | | Beheert modules als losse agents | Nog niet gebouwd |
| 402 | | System & Control | module_migrator.py | | Verplaatst modules/resources naar ander device | Nog niet gebouwd |
| 403 | | System & Control | module_proposal_manager.py | | Voorstel → sandbox‑test → approval | Nog niet gebouwd |
| 404 | | System & Control | module_tester.py | | test nieuwe modules | Nog niet gebouwd |
| 405 | | System & Control | multi_device_console.py | | dashboard met status per device | Nog niet gebouwd |
| 406 | | System & Control | multi_user_lock.py | | detecteert ‘niet‑Kev’ sessies | Nog niet gebouwd |
| 407 | | System & Control | network_optimizer.py | | past gedrag aan bij slechte connectie | Nog niet gebouwd |
| 408 | | System & Control | os_command_center.py | | veilige systeemacties (wifi/bt/brightness/…) | Nog niet gebouwd |
| 409 | | System & Control | prompt_optimizer.py | | Optimaliseert prompts | Nog niet gebouwd |
| 410 | | System & Control | rate_limit_manager.py | | Volgt officiële rate‑limits | Nog niet gebouwd |
| 411 | | System & Control | swarm_core.py | | Stuurt multi-device swarm AI gedrag | Nog niet gebouwd |
| 412 | | System & Control | structured_toolcaller.py | | Bouwt en gebruikt tools dynamisch | Nog niet gebouwd |
| 413 | | System & Control | training_example_collector.py | | Verzamelt voorbeelden voor fine-tuning | Nog niet gebouwd |
| 414 | | System & Control | window_orchestrator.py | | vensters rangschikken | Nog niet gebouwd |
| 415 | | System & Control | advanced_planning.py | | multi-step planning (PDDL-achtig) | Nog niet gebouwd |
| 416 | | System & Control | multi_agent_manager.py | | Beheert meerdere sub-agents | Nog niet gebouwd |
| 417 | | System & Control | audit_guard.py | | Audit & controle op acties | Nog niet gebouwd |
| 418 | | System & Control | multi_profile_manager.py | | meerdere persona’s/profielen beheren | Nog niet gebouwd |
| 419 | | System & Control | exceptions.py | | Custom exception-handlers voor stabielere foutafhandeling. | Nog niet gebouwd |
| 420 | | System & Control | logger_core.py | | Logt chatsessies en events apart van growth_log. | Nog niet gebouwd |
| 421 | | System & Control | app_controller.py | | Centrale hub voor desktop-acties; roept helpers aan en koppelt reflex-events. | Nog niet gebouwd |
| 422 | | System & Control | window_switcher.py | | Lijst actieve vensters, switch focus. | Nog niet gebouwd |
| 423 | | System & Control | doc_reader.py | | Leest tekstbestanden (.txt, .md), geeft preview. | Nog niet gebouwd |
| 424 | | System & Control | file_manager.py | | Openen, sluiten en lijsten van bestanden. | Nog niet gebouwd |
| 425 | | System & Control | reflex_bridge.py | | Koppelt desktop events (apps/docs) aan reflexen/moods. | Nog niet gebouwd |
| 426 | 4 | Utilities & Ops | thermal_guard.py | modules/ops/ | monitort temperatuur en optimaliseert prestaties | Nog niet gebouwd |
| 427 | 5 | Utilities & Ops | auto_integrator.py | modules/devops/ | koppelt nieuwe modules automatisch aan juiste core/memory/presence | Nog niet gebouwd |
| 428 | 4 | Utilities & Ops | expansion_suggester.py | modules/devops/ | analyseert gedrag/logs en suggereert ontbrekende modules | Nog niet gebouwd |
| 429 | | Utilities & Ops | account_health_monitor.py | | Strikes/warnings/appeals; safe‑mode" | Nog niet gebouwd |
| 430 | | Utilities & Ops | backup_manager.py | | Back‑ups van configs/db’s/logs + herstelpunten | Nog niet gebouwd |
| 431 | | Utilities & Ops | bandwidth_optimizer.py | | Netwerk spreiden/limiten, games/Plex voorrang | Nog niet gebouwd |
| 432 | | Utilities & Ops | crash_recovery.py | | Herstart services en restore state | Nog niet gebouwd |
| 433 | | Utilities & Ops | health_monitor.py | | Monitor CPU/RAM/temps/uptime; waarschuwingen" | Nog niet gebouwd |
| 434 | | Utilities & Ops | incident_reporter.py | | Rapport bij fouten/aanvallen (wat, wanneer, fix) | Nog niet gebouwd |
| 435 | | Utilities & Ops | log_rotator.py | | Rolt/comprimeert/pruned logs | Nog niet gebouwd |
| 436 | | Utilities & Ops | notification_hub.py | | centrale hub voor meldingen op gsm + laptop (Android listener, Windows/OS notification center) | Nog niet gebouwd |
| 437 | | Utilities & Ops | notification_rules.py | | slimme filters/samenvattingen/escals voor meldingen | Nog niet gebouwd |
| 438 | | Utilities & Ops | power_profile_manager.py | | batterij vs netstroom | Nog niet gebouwd |
| 439 | | Utilities & Ops | power_saver.py | | Verbruik omlaag bij afwezig/batterij | Nog niet gebouwd |
| 440 | | Utilities & Ops | storage_cleaner.py | | Ruimt cache/temp/unused models op | Nog niet gebouwd |
| 441 | | Utilities & Ops | update_checker.py | | Libs/modules/containers updates + changelogs | Nog niet gebouwd |
| 442 | | Vision & Perception | object_recognition.py | | Herkent objecten en personen via vision-LLM (Qwen-VL/LLaVA); koppelt aan gossip_mode voor owner-only roddels; metadata kan ook naar alert_owner. | Nog niet gebouwd |
| 443 | | Vision & Perception | scene_contexter.py | | Combineert objectherkenning + OCR tot één samenvatting (“bureau: laptop, flesje, notitie ‘12:30 call’”). | Nog niet gebouwd |
| 444 | | Vision & Perception | attention_router.py | | Bepaalt waar Nova naar “kijkt” in beeld (ROI’s), spaart compute. | Nog niet gebouwd |
| 445 | 6 | World Model | world_model.py | modules/experimental/ | Wereldmodel / simulatie (what-if voorspeller). | Nog niet gebouwd |
| 446 | 2 | Notification & Interrupts | notification_priority.py | modules/core/ | Centraal systeem dat bepaalt WELKE meldingen/gedachten Nova uitspreeekt en wanneer (voorkomen: te veel praten = irritant) | Nog niet gebouwd |
| 447 | 2 | Notification & Interrupts | interrupt_timing_optimizer.py | modules/core/ | Bepaalt optimaal moment voor onderbreking (niet midden in Kevin's gedachtestroom, wel op natuurlijke pauzes) | Nog niet gebouwd |
| 448 | 2 | Notification & Interrupts | do_not_disturb_manager.py | modules/core/ | Respecteert "stilte modus" períodes (werk, slaap, focus sessies) | Nog niet gebouwd |
| 449 | 2 | Notification & Interrupts | relevance_scorer.py | modules/core/ | Scoort: "Hoe relevant is dit voor Kevin NU?" (0.0-1.0) om te filteren | Nog niet gebovered |
| 450 | 3 | Conversation & Quality | conversation_quality_monitor.py | modules/learning/ | Monitort eigen prestatie: snapte Kevin me? Gaf ik bruikbare info? Feedback-loop voor verbetering | Nog niet gebouwd |
| 451 | 3 | Conversation & Quality | response_accuracy_tracker.py | modules/learning/ | Logt wat Nova zei vs wat Kevin deed (was ik juist?). Confidence verhogen/verlagen | Nog niet gebouwd |
| 452 | 3 | Conversation & Quality | error_recovery_engine.py | modules/core/ | Hoe reageert Nova gracefully op fouten? Excuses, herproberen, fallback. Met persoonlijkheid | Nog niet gebouwd |
| 453 | 2 | Conversation & Quality | intent_disambiguator.py | modules/core/ | Stelt intelligente vervolgvragen ("Spotify of YouTube? Welk genre?") in plaats van gokken | Nog niet gebouwd |
| 454 | 3 | Data Lifecycle | memory_compressor.py | modules/memory/ | Comprimeer oude interactions: 50x "Python is beter" → 1x "Kevin prefereert Python (confidence 0.95)" | Nog niet gebouwd |
| 455 | 3 | Data Lifecycle | data_archiver.py | modules/memory/ | Archiveer oude data naar cold storage (niet dagelijks nodig, wel behouden) | Nog niet gebouwd |
| 456 | 3 | Data Lifecycle | lifecycle_manager.py | modules/memory/ | Beheer data retention policies (wat blijft, wat gaat weg, wanneer) | Nog niet gebouwd |
| 457 | 4 | Data Lifecycle | forget_policy_enforcer.py | modules/memory/ | Implementeer "vergeet dit" commands van Kevin (GDPR-style cleanup) | Nog niet gebouwd |
| 458 | 4 | Learning & Meta | adaptive_learning_parameters.py | modules/learning/ | Nova ziet zelf: "templates werken beter dan rules hier" en past aan hoe ze leert | Nog niet gebouwd |
| 459 | 4 | Learning & Meta | context_switching_patterns.py | modules/learning/ | Detecteert automatische transitions (18:00: werk → spel) en prepares environment | Nog niet gebouwd |
| 460 | 4 | Learning & Meta | trust_confidence_scorer.py | modules/core/ | Voor alles wat Nova zegt: hoe zeker is ze? (alleen uitspreken waar confidence > threshold) | Nog niet gebouwd |
| 461 | 4 | Learning & Meta | user_intent_history.py | modules/memory/ | Long-term goal tracking: Kevin zei maand geleden dit — is hij nog van plan? | Nog niet gebouwd |
| 462 | 5 | Curiosity & Serendipity | curiosity_engine.py | modules/experimental/ | Nova bedenkt vragen over Kevin (proactief leren, niet wachten op input) | Nog niet gebouwd |
| 463 | 5 | Curiosity & Serendipity | conversation_replay_analyzer.py | modules/reflection/ | Wacht, vorige week zei je X maar nu zei je Y" — consistency checking | Nog niet gebouwd |
| 464 | 5 | Curiosity & Serendipity | serendipity_engine.py | modules/experimental/ | Nova verbindt willekeurig twee concepten: "Dit doet me denken aan... (geleide associaties) | Nog niet gebouwd |
| 465 | 4 | System & Optimization | performance_monitor.py | modules/ops/ | Nova ziet zelf: "Mijn responses worden traag" → optimaliseert, ruimt cache op | Nog niet gebouwd |
| 466 | 2 | Notification & Interrupts | notification_priority.py | modules/core/ | Centraal systeem dat bepaalt WELKE meldingen/gedachten Nova uitspreeekt en wanneer (voorkomen: te veel praten = irritant) | Nog niet gebouwd |
| 467 | 2 | Notification & Interrupts | interrupt_timing_optimizer.py | modules/core/ | Bepaalt optimaal moment voor onderbreking (niet midden in Kevin's gedachtestroom, wel op natuurlijke pauzes) | Nog niet gebouwd |
| 468 | 2 | Notification & Interrupts | do_not_disturb_manager.py | modules/core/ | Respecteert "stilte modus" períodes (werk, slaap, focus sessies) | Nog niet gebouwd |
| 469 | 2 | Notification & Interrupts | relevance_scorer.py | modules/core/ | Scoort: "Hoe relevant is dit voor Kevin NU?" (0.0-1.0) om te filteren | Nog niet gebouwd |
| 470 | 2 | Security / Access | user_verification.py | modules/security/ | Gebruikt FaceNet om te verifiëren: "Ben jij Kevin?" (gezichtsherkenning lokaal, alleen Kevin) | Nog niet gebouwd |
| 471 | 2 | Security / Access | behavioral_anomaly_detector.py | modules/security/ | Ziet gedragspatronen: muisklikken, toetsaanslagen, app-gebruik. "Dit voelt niet als Kevin" | Nog niet gebouwd |
| 472 | 3 | Security / Access | defensive_mode_engine.py | modules/security/ | Gaat in lockdown bij onbekende: screen lock, audit alles, waarschuw eigenaar via telefoon | Nog niet gebouwd |
| 473 | 3 | Security / Access | unauthorized_access_logger.py | modules/security/ | Logt alles wat onbekende persoon doet (apps, mappen, sites op domain-level, geen keystroke/passwords) | Nog niet gebouwd |
| 474 | 3 | Security / Access | danger_action_detector.py | modules/security/ | Analyseert acties van onbekende: "Is dit gevaarlijk?" (banking access, file copying, credentials access) met danger-scoring (1-10) | Nog niet gebouwd |
| 475 | 3 | Security / Access | contextual_threat_assessment.py | modules/security/ | Kijkt naar COMBINATIE acties: één ding is verdacht, maar meerdere samen = escalatie van gevaarsniveau | Nog niet gebouwd |
| 476 | 3 | Security / Access | emergency_lockdown_protocol.py | modules/security/ | Danger level >= 9: instant lockdown, alert owner, screenshot maken, voice-unlock required | Nog niet gebouwd |