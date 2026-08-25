import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type Language = "en" | "te" | "hi";

const translations: Record<string, Record<string, string>> = {
  en: {
    nav_dashboard: "Dashboard",
    nav_assistant: "AI Assistant",
    nav_groundwater: "Groundwater",
    nav_gis: "GIS Map",
    nav_reports: "Reports",
    nav_history: "History",
    nav_notifications: "Notifications",
    nav_expert: "Expert",
    nav_admin: "Admin",
    sign_out: "Sign out",
    loading: "Loading…",
    new_chat: "New chat",
    ask_about_gw: "Ask about groundwater…",
    thinking: "Thinking…",
    state: "State",
    district: "District",
    year: "Year",
    category: "Category",
    metric: "Metric",
    all_states: "All states",
    all_districts: "All districts",
    all_years: "All years",
    download_csv: "Download CSV",
    download_pdf: "Download PDF",
    generate: "Generate",
    demo_data: "Demo data",
    refresh: "Refresh",
    search: "Search",
    export: "Export",
    summary: "Summary",
    details: "Details",
    units: "assessment units",
    Data: "Data",
    Map: "Map",
    Trend: "Trend",
    Prediction: "Prediction",
    Explanation: "Explanation",
    Recommendations: "Recommendations",
    Recommendation: "Recommendation",
    annual_extractable_resource: "Annual extractable resource",
    assessment_units: "Assessment units",
    top_districts_by_stage: "Top districts by stage of extraction",
    confidence_band: "95% band",
    stage_of_extraction: "Stage of extraction",
    recharge: "Recharge",
    extraction: "Extraction",
    level_safe: "Safe",
    level_attention: "Needs care",
    level_critical: "Critical",
    level_unknown: "Unknown",
    level_safe_short: "Safe",
    level_attention_short: "Needs care",
    level_critical_short: "Critical",
    Now: "Now",
    Tomorrow: "Tomorrow",
    Today: "Today",
    High: "High",
    Low: "Low",
    Weather: "Weather",
    rain_no: "No rain",
    rain_light: "Light rain",
    rain_moderate: "Moderate rain",
    rain_heavy: "Heavy rain",
    rain_very_heavy: "Very heavy rain",
    Forecast: "Forecast",
    "Linear trend": "Linear trend",
    "Moving average": "Moving average",
    "Exponential smoothing": "Exponential smoothing",
    "ARIMA(1,1,0)": "ARIMA(1,1,0)",
    "Holt's linear trend": "Holt's linear trend",
    "Auto (best validated)": "Auto (best validated)",
    "Ensemble (weighted blend)": "Ensemble (weighted blend)",
    "Deep learning — LSTM": "Deep learning — LSTM",
    "Deep learning — Transformer": "Deep learning — Transformer",
    "Deep learning (best available)": "Deep learning (best available)",
    "River basin": "River basin",
    "No basin (state/district/village)": "No basin (state/district/village)",
    districts: "districts",
    "Confidence band": "Confidence band",
    "Normal (95%)": "Normal (95%)",
    "Bootstrap fan (5–95%)": "Bootstrap fan (5–95%)",
    "Transfer learning — pre-train on the containing state/basin, then fine-tune this scope":
      "Transfer learning — pre-train on the containing state/basin, then fine-tune this scope",
    "Deep-learning models need the optional torch dependency. Without it the forecast falls back to the best statistical model. Install with: pip install -r requirements-ml.txt":
      "Deep-learning models need the optional torch dependency. Without it the forecast falls back to the best statistical model. Install with: pip install -r requirements-ml.txt",
    "Deep learning ready": "Deep learning ready",
    "Deep-learning model": "Deep-learning model",
    "Pre-trained on": "Pre-trained on",
    "fine-tuned": "fine-tuned",
    epochs: "epochs",
    Backtest: "Backtest",
    "Chronological train/test split — forecast the held-out years with each model and compare (lower is better).":
      "Chronological train/test split — forecast the held-out years with each model and compare (lower is better).",
    CRPS: "CRPS",
    Skill: "Skill",
    "Point estimates with a bootstrap 5–95% confidence fan.":
      "Point estimates with a bootstrap 5–95% confidence fan.",
    "Model comparison": "Model comparison",
    "Out-of-sample walk-forward validation scores (lower is better). {n} forecasts tested.":
      "Out-of-sample walk-forward validation scores (lower is better). {n} forecasts tested.",
    Recommended: "Recommended",
    RMSE: "RMSE",
    MAE: "MAE",
    MAPE: "MAPE",
    Tests: "Tests",
    best: "best",
    "The best validated model for this scope is {method}. Switch the model dropdown to Auto to use it automatically.":
      "The best validated model for this scope is {method}. Switch the model dropdown to Auto to use it automatically.",
    "Statistical projection · not official data": "Statistical projection · not official data",
    Model: "Model",
    "Horizon (years)": "Horizon (years)",
    "Projected {year}": "Projected {year}",
    "End of forecast horizon": "End of forecast horizon",
    Change: "Change",
    "Over the forecast horizon": "Over the forecast horizon",
    "Annual trend": "Annual trend",
    "per year": "per year",
    "Loading forecast…": "Loading forecast…",
    "Failed to load the forecast.": "Failed to load the forecast.",
    "Projected trend": "Projected trend",
    "{scope} · {metric} · {method}": "{scope} · {metric} · {method}",
    "Projected category": "Projected category",
    "Model explanation": "Model explanation",
    "At the projected trend, {scope} crosses the over-exploited threshold (100% stage of extraction) in about {count} year(s).":
      "At the projected trend, {scope} crosses the over-exploited threshold (100% stage of extraction) in about {count} year(s).",
    "Forecast points": "Forecast points",
    "Point estimates with a 95% confidence band.": "Point estimates with a 95% confidence band.",
    Lower: "Lower",
    Upper: "Upper",
    Observed: "Observed",
    rising: "rising",
    falling: "falling",
    stable: "stable",
    safe: "safe",
    "semi-critical": "semi-critical",
    critical: "critical",
    "over-exploited": "over-exploited",

    // Knowledge base (Phase 20)
    "Knowledge base": "Knowledge base",
    "Browse the groundwater reference documents used by the AI assistant. Search returns verbatim excerpts with their sources.":
      "Browse the groundwater reference documents used by the AI assistant. Search returns verbatim excerpts with their sources.",
    "Search the knowledge base": "Search the knowledge base",
    "Ask about recharge, stage of extraction, conservation…":
      "Ask about recharge, stage of extraction, conservation…",
    Search: "Search",
    Relevance: "Relevance",
    "{count} result(s) for “{query}”": "{count} result(s) for “{query}”",
    "No matches": "No matches",
    "Nothing found. Try different wording.": "Nothing found. Try different wording.",
    Documents: "Documents",
    "{count} document(s), {chunks} chunk(s) indexed":
      "{count} document(s), {chunks} chunk(s) indexed",
    "Add document": "Add document",
    "No documents yet.": "No documents yet.",
    chunks: "chunks",
    "Remove document": "Remove document",
    "Only admins can add or remove documents.": "Only admins can add or remove documents.",
    "Document added to the knowledge base.": "Document added to the knowledge base.",
    "Failed to upload the document.": "Failed to upload the document.",
    "Document removed.": "Document removed.",
    "Failed to remove the document.": "Failed to remove the document.",
    "Search failed. Check that the knowledge base is available.":
      "Search failed. Check that the knowledge base is available.",
    "knowledge base": "knowledge base",
    RAG: "RAG",

    // Push notifications (Phase 20)
    "Push notifications": "Push notifications",
    "Get groundwater alerts on this device even when the app is closed (installable PWA).":
      "Get groundwater alerts on this device even when the app is closed (installable PWA).",
    Available: "Available",
    "Not available": "Not available",
    "requires HTTPS and a supported browser": "requires HTTPS and a supported browser",
    "This device is registered to receive alerts.": "This device is registered to receive alerts.",
    "Allow alerts to be delivered to this device.": "Allow alerts to be delivered to this device.",
    "Web push is not enabled on the server.": "Web push is not enabled on the server.",
    "Notification permission was denied.": "Notification permission was denied.",
    "Push notifications enabled for this device.": "Push notifications enabled for this device.",
    "Could not enable push notifications.": "Could not enable push notifications.",
    "Push notifications disabled.": "Push notifications disabled.",
    "Could not disable push notifications.": "Could not disable push notifications.",

    // GIS time-lapse & comparison (Phase 20)
    From: "From",
    To: "To",
    Compare: "Compare",
    "Compare years": "Compare years",
    "Play time-lapse": "Play time-lapse",
    Pause: "Pause",
    "Units compared": "Units compared",
    "Category changes": "Category changes",
    "Avg change": "Avg change",
    Improved: "Improved",
    Worsened: "Worsened",
    "No change": "No change",
    "Change over time": "Change over time",
    "Category: {a} → {b}": "Category: {a} → {b}",
    "Click a state or unit to see its change between the two years.":
      "Click a state or unit to see its change between the two years.",

    // Assistant forecast & scenario (Phase 20)
    Scenario: "Scenario",

    // GIS layers & click-to-analyze
    Layers: "Layers",
    "Groundwater Level": "Groundwater Level",
    "Critical Areas": "Critical areas",
    "Monitoring Stations": "Monitoring stations",
    "Monitoring station": "Monitoring station",
    "Click the map to analyze any location.": "Click the map to analyze any location.",
    "Analyzing location…": "Analyzing location…",
    "No groundwater data near this location.": "No groundwater data near this location.",
    "Could not analyze this location.": "Could not analyze this location.",
    Stable: "Stable",
    "m/year": "m/year",
    "AI Prediction": "AI Prediction",
    Risk: "Risk",
    Shallow: "Shallow",
    Deep: "Deep",
"derived from stage of extraction (demo)": "derived from stage of extraction (demo)",
    "Predicted category": "Predicted category",

    // Assessment report
    "Data report": "Data report",
    "Assessment report": "Assessment report",
    "Generate an AI-written report for a state, district and period, with status, trend, prediction, risk, map, graphs, recommendations and data sources, exportable as PDF or Excel.":
      "Generate an AI-written report for a state, district and period, with status, trend, prediction, risk, map, graphs, recommendations and data sources, exportable as PDF or Excel.",
    "Period from": "Period from",
    "Period to": "Period to",
    "Generate report": "Generate report",
    "Executive summary": "Executive summary",
    "Groundwater status": "Groundwater status",
    "Historical trend": "Historical trend",
    "Risk analysis": "Risk analysis",
    Graphs: "Graphs",
    "Data sources": "Data sources",
    "Download PDF": "Download PDF",
    "Download Excel": "Download Excel",
    Current: "Current",
    Projected: "Projected",
    "Generating assessment report…": "Generating assessment report…",
    "No report yet. Choose a scope and period, then click Generate report.":
      "No report yet. Choose a scope and period, then click Generate report.",
    "Failed to generate the assessment report.": "Failed to generate the assessment report.",
    "latest data {year}": "latest data {year}",
    "Stage of extraction, {from}–{latest}": "Stage of extraction, {from}–{latest}",
    "to {year}": "to {year}",
    "status {year}": "status {year}",
  },
  te: {
    nav_dashboard: "డాష్బోర్డ్",
    nav_assistant: "AI సహాయకుడు",
    nav_groundwater: "భూగర్భ జలం",
    nav_gis: "GIS పటం",
    nav_reports: "నివేదికలు",
    nav_history: "చరిత్ర",
    nav_notifications: "నోటిఫికేషన్లు",
    nav_expert: "నిపుణుడు",
    nav_admin: "నిర్వాహకుడు",
    sign_out: "లాగ్ అవుట్",
    loading: "లోడ్ అవుతోంది…",
    new_chat: "కొత్త చాట్",
    ask_about_gw: "భూగర్భ జలం గురించి అడగండి…",
    thinking: "ఆలోచిస్తోంది…",
    state: "రాష్ట్రం",
    district: "జిల్లా",
    year: "సంవత్సరం",
    category: "వర్గం",
    metric: "కొలమానం",
    all_states: "అన్ని రాష్ట్రాలు",
    all_districts: "అన్ని జిల్లాలు",
    all_years: "అన్ని సంవత్సరాలు",
    download_csv: "CSV డౌన్‌లోడ్",
    download_pdf: "PDF డౌన్‌లోడ్",
    generate: "సృష్టించు",
    demo_data: "డెమో డేటా",
    refresh: "రిఫ్రెష్",
    search: "వెతకండి",
    export: "ఎగుమతి",
    summary: "సారాంశం",
    details: "వివరాలు",
    units: "అంచనా యూనిట్లు",
    stage_of_extraction: "వెలికితీత దశ",
    recharge: "పునర్భరణం",
    extraction: "వెలికితీత",
  },
  hi: {
    nav_dashboard: "डैशबोर्ड",
    nav_assistant: "AI सहायक",
    nav_groundwater: "भूजल",
    nav_gis: "GIS मानचित्र",
    nav_reports: "रिपोर्ट",
    nav_history: "इतिहास",
    nav_notifications: "सूचनाएँ",
    nav_expert: "विशेषज्ञ",
    nav_admin: "प्रशासक",
    sign_out: "साइन आउट",
    loading: "लोड हो रहा है…",
    new_chat: "नई चैट",
    ask_about_gw: "भूजल के बारे में पूछें…",
    thinking: "सोच रहा है…",
    state: "राज्य",
    district: "जिला",
    year: "वर्ष",
    category: "श्रेणी",
    metric: "मीट्रिक",
    all_states: "सभी राज्य",
    all_districts: "सभी जिले",
    all_years: "सभी वर्ष",
    download_csv: "CSV डाउनलोड",
    download_pdf: "PDF डाउनलोड",
    generate: "बनाएँ",
    demo_data: "डेमो डेटा",
    refresh: "रिफ़्रेश",
    search: "खोजें",
    export: "निर्यात",
    summary: "सारांश",
    details: "विवरण",
    units: "आकलन इकाइयाँ",
    stage_of_extraction: "निष्कर्षण चरण",
    recharge: "पुनर्भरण",
    extraction: "निष्कर्षण",
  },
};

const uiTe: Record<string, string> = {
  // Groundwater
  "Groundwater Analytics": "భూగర్భ జల విశ్లేషణలు",
  "Recharge, extraction and stage-of-extraction across assessment units.":
    "అంచనా యూనిట్లలో పునర్భరణం, వెలికితీత మరియు వెలికితీత దశ.",
  Filters: "ఫిల్టర్లు",
  "Assessment Year": "అంచనా సంవత్సరం",
  "All categories": "అన్ని వర్గాలు",
  "Assessment Units": "అంచనా యూనిట్లు",
  "Units in scope": "పరిధిలోని యూనిట్లు",
  "Recharge ({unit})": "పునర్భరణం ({unit})",
  "Total annual recharge": "మొత్తం వార్షిక పునర్భరణం",
  "Extraction ({unit})": "వెలికితీత ({unit})",
  "Total annual extraction": "మొత్తం వార్షిక వెలికితీత",
  "Avg Stage of Extraction": "సగటు వెలికితీత దశ",
  "Demand vs availability": "డిమాండ్ vs లభ్యత",
  "Category distribution": "వర్గ పంపిణీ",
  "Assessment units by stage-of-extraction category.":
    "వెలికితీత దశ వర్గం ప్రకారం అంచనా యూనిట్లు.",
  "No data for the current filters.": "ప్రస్తుత ఫిల్టర్లకు డేటా లేదు.",
  "Recharge by year": "సంవత్సరాల వారీగా పునర్భరణం",
  "Extraction by year": "సంవత్సరాల వారీగా వెలికితీత",
  "Total annual recharge in {unit}.": "{unit}లో మొత్తం వార్షిక పునర్భరణం.",
  "Total annual extraction in {unit}.": "{unit}లో మొత్తం వార్షిక వెలికితీత.",
  "Assessment records": "అంచనా రికార్డులు",
  "Detailed stage-of-extraction data.": "వివరణాత్మక వెలికితీత దశ డేటా.",
  "Showing 25 of {count} records.": "{count} రికార్డులలో 25 చూపుతోంది.",
  "No assessment records for the current filters.":
    "ప్రస్తుత ఫిల్టర్లకు అంచనా రికార్డులు లేవు.",
  "Village / Unit": "గ్రామం / యూనిట్",
  "SoE %": "వెలికితీత %",
  Reset: "రీసెట్",
  "Loading groundwater data…": "భూగర్భ జల డేటా లోడ్ అవుతోంది…",
  "Failed to load groundwater data.": "భూగర్భ జల డేటాను లోడ్ చేయడంలో విఫలమైంది.",

  // Forecast (Phase 19)
  Forecast: "అంచనా",
  "Linear trend": "సరళ ధోరణి",
  "Moving average": "సగటు కదలిక",
  "Exponential smoothing": "ఘాతాంక స్మూతింగ్",
  "ARIMA(1,1,0)": "ARIMA(1,1,0)",
  "Holt's linear trend": "హోల్ట్ యొక్క సరళ ధోరణి",
  "Auto (best validated)": "ఆటో (ఉత్తమ ధృవీకరణ)",
  "Ensemble (weighted blend)": "సమిష్టి (బరువు మిశ్రమం)",
  "Deep learning — LSTM": "డీప్ లెర్నింగ్ — LSTM",
  "Deep learning — Transformer": "డీప్ లెర్నింగ్ — ట్రాన్స్‌ఫార్మర్",
  "Deep learning (best available)": "డీప్ లెర్నింగ్ (అందుబాటులో ఉత్తమం)",
  "River basin": "నదీ పరీవాహక ప్రాంతం",
  "No basin (state/district/village)": "పరీవాహకం లేదు (రాష్ట్రం/జిల్లా/గ్రామం)",
  districts: "జిల్లాలు",
  "Confidence band": "విశ్వాస పట్టీ",
  "Normal (95%)": "సాధారణం (95%)",
  "Bootstrap fan (5–95%)": "బూట్‌స్ట్రాప్ ఫ్యాన్ (5–95%)",
  "Transfer learning — pre-train on the containing state/basin, then fine-tune this scope":
    "ట్రాన్స్‌ఫర్ లెర్నింగ్ — చుట్టుపక్కల రాష్ట్రం/పరీవాహకంపై ముందుగా శిక్షణ, ఆపై ఈ పరిధిని ఫైన్-ట్యూన్ చేయండి",
  "Deep-learning models need the optional torch dependency. Without it the forecast falls back to the best statistical model. Install with: pip install -r requirements-ml.txt":
    "డీప్-లెర్నింగ్ మోడల్‌లకు ఐచ్ఛిక torch ఆధారిత ప్యాకేజీ అవసరం. లేకుంటే అంచనా ఉత్తమ గణాంక మోడల్‌కు మారుతుంది. ఇన్‌స్టాల్: pip install -r requirements-ml.txt",
  "Deep learning ready": "డీప్ లెర్నింగ్ సిద్ధంగా ఉంది",
  "Deep-learning model": "డీప్-లెర్నింగ్ మోడల్",
  "Pre-trained on": "ముందుగా శిక్షణ పొందినది",
  "fine-tuned": "ఫైన్-ట్యూన్ చేయబడింది",
  epochs: "ఎపోచ్‌లు",
  Backtest: "బ్యాక్‌టెస్ట్",
  "Chronological train/test split — forecast the held-out years with each model and compare (lower is better).":
    "కాలక్రమానుసార శిక్షణ/పరీక్ష విభజన — ప్రతి మోడల్‌తో నిలిపివేయబడిన సంవత్సరాలను అంచనా వేసి పోల్చండి (తక్కువ మంచిది).",
  CRPS: "CRPS",
  Skill: "నైపుణ్యం",
  "Point estimates with a bootstrap 5–95% confidence fan.":
    "బూట్‌స్ట్రాప్ 5–95% విశ్వాస ఫ్యాన్‌తో పాయింట్ అంచనాలు.",
  "Forecast settings": "అంచనా సెట్టింగ్‌లు",
  "Project groundwater metrics with time-series models — linear trend, moving average, exponential smoothing, ARIMA(1,1,0), Holt's trend, or auto-selection by holdout validation.":
    "సమయ-శ్రేణి నమూనాలతో భూగర్భ జల మెట్రిక్‌లను అంచనా వేయండి — సరళ ధోరణి, సగటు కదలిక, ఘాతాంక స్మూతింగ్, ARIMA(1,1,0), హోల్ట్ ధోరణి, లేదా హోల్డౌట్ ధృవీకరణ ద్వారా ఆటో-ఎంపిక.",
  "Model comparison": "మోడల్ పోలిక",
  "Out-of-sample walk-forward validation scores (lower is better). {n} forecasts tested.":
    "నమూనా-బయటి వాక్-ఫార్వర్డ్ ధృవీకరణ స్కోర్లు (తక్కువ మంచిది). {n} అంచనాలు పరీక్షించబడ్డాయి.",
  Recommended: "సిఫార్సు చేయబడింది",
  RMSE: "RMSE",
  MAE: "MAE",
  MAPE: "MAPE",
  Tests: "పరీక్షలు",
  best: "ఉత్తమం",
  "The best validated model for this scope is {method}. Switch the model dropdown to Auto to use it automatically.":
    "ఈ పరిధికి ఉత్తమ ధృవీకరించబడిన మోడల్ {method}. దీన్ని స్వయంచాలకంగా ఉపయోగించడానికి మోడల్ డ్రాప్‌డౌన్‌ను ఆటోకి మార్చండి.",
  "Statistical projection · not official data":
    "గణాంక అంచనా · అధికారిక డేటా కాదు",
  Model: "మోడల్",
  "Horizon (years)": "క్షితిజం (సంవత్సరాలు)",
  "Projected {year}": "అంచనా {year}",
  "End of forecast horizon": "అంచనా క్షితిజం ముగింపు",
  Change: "మార్పు",
  "Over the forecast horizon": "అంచనా క్షితిజంలో",
  "Annual trend": "వార్షిక ధోరణి",
  "per year": "సంవత్సరానికి",
  "Loading forecast…": "అంచనా లోడ్ అవుతోంది…",
  "Failed to load the forecast.": "అంచనాను లోడ్ చేయడంలో విఫలమైంది.",
  "Projected trend": "అంచనా ధోరణి",
  "{scope} · {metric} · {method}": "{scope} · {metric} · {method}",
  "Projected category": "అంచనా వర్గం",
  "Model explanation": "మోడల్ వివరణ",
  "At the projected trend, {scope} crosses the over-exploited threshold (100% stage of extraction) in about {count} year(s).":
    "అంచనా ధోరణి ప్రకారం, {scope} సుమారు {count} సంవత్సరం(ల)లో అధిక దోపిడీ పరిమితిని (100% వెలికితీత దశ) దాటుతుంది.",
  "Forecast points": "అంచనా పాయింట్లు",
  "Point estimates with a 95% confidence band.":
    "95% విశ్వాస పట్టీతో పాయింట్ అంచనాలు.",
  Lower: "తక్కువ",
  Upper: "ఎక్కువ",
  "Observed value": "గమనించిన విలువ",
  rising: "పెరుగుతోంది",
  falling: "తగ్గుతోంది",
  stable: "స్థిరంగా",
  safe: "సురక్షితం",
  "semi-critical": "అర్ధ-కీలకం",
  critical: "కీలకం",
  "over-exploited": "అధిక దోపిడీ",

  // Knowledge base (Phase 20)
  "Knowledge base": "నాలెడ్జ్ బేస్",
  "Browse the groundwater reference documents used by the AI assistant. Search returns verbatim excerpts with their sources.":
    "AI సహాయకుడు ఉపయోగించే భూగర్భ జల సూచన పత్రాలను బ్రౌజ్ చేయండి. శోధన వాటి మూలాలతో పాటు వాచ్యంగా సారాంశాలను తిరిగి ఇస్తుంది.",
  "Search the knowledge base": "నాలెడ్జ్ బేస్‌ని శోధించండి",
  "Ask about recharge, stage of extraction, conservation…":
    "పునర్భరణం, వెలికితీత దశ, సంరక్షణ గురించి అడగండి…",
  Search: "శోధించు",
  Relevance: "సంబంధితత్వం",
  "{count} result(s) for “{query}”": "“{query}” కోసం {count} ఫలితం(లు)",
  "No matches": "సరిపోలికలు లేవు",
  "Nothing found. Try different wording.": "ఏమీ కనుగొనబడలేదు. వేరే పదాలతో ప్రయత్నించండి.",
  Documents: "పత్రాలు",
  "{count} document(s), {chunks} chunk(s) indexed":
    "{count} పత్రం(లు), {chunks} భాగం(లు) సూచిక చేయబడ్డాయి",
  "Add document": "పత్రం జోడించండి",
  "No documents yet.": "ఇంకా పత్రాలు లేవు.",
  chunks: "భాగాలు",
  "Remove document": "పత్రం తీసివేయండి",
  "Only admins can add or remove documents.": "పత్రాలను జోడించడం లేదా తీసివేయడం అడ్మిన్‌లకు మాత్రమే.",
  "Document added to the knowledge base.": "పత్రం నాలెడ్జ్ బేస్‌కు జోడించబడింది.",
  "Failed to upload the document.": "పత్రాన్ని అప్‌లోడ్ చేయడంలో విఫలమైంది.",
  "Document removed.": "పత్రం తీసివేయబడింది.",
  "Failed to remove the document.": "పత్రాన్ని తీసివేయడంలో విఫలమైంది.",
  "Search failed. Check that the knowledge base is available.":
    "శోధన విఫలమైంది. నాలెడ్జ్ బేస్ అందుబాటులో ఉందో లేదో తనిఖీ చేయండి.",
  "knowledge base": "నాలెడ్జ్ బేస్",
  RAG: "RAG",

  // Push notifications (Phase 20)
  "Push notifications": "పుష్ నోటిఫికేషన్‌లు",
  "Get groundwater alerts on this device even when the app is closed (installable PWA).":
    "యాప్ మూసివేసినప్పటికీ ఈ పరికరంలో భూగర్భ జల హెచ్చరికలను పొందండి (ఇన్‌స్టాలబుల్ PWA).",
  "Not available": "అందుబాటులో లేదు",
  "requires HTTPS and a supported browser": "HTTPS మరియు మద్దతు ఉన్న బ్రౌజర్ అవసరం",
  "This device is registered to receive alerts.": "ఈ పరికరం హెచ్చరికలను స్వీకరించడానికి నమోదు చేయబడింది.",
  "Allow alerts to be delivered to this device.": "ఈ పరికరానికి హెచ్చరికలను అందించడానికి అనుమతించండి.",
  "Web push is not enabled on the server.": "సర్వర్‌లో వెబ్ పుష్ ప్రారంభించబడలేదు.",
  "Notification permission was denied.": "నోటిఫికేషన్ అనుమతి నిరాకరించబడింది.",
  "Push notifications enabled for this device.": "ఈ పరికరానికి పుష్ నోటిఫికేషన్‌లు ప్రారంభించబడ్డాయి.",
  "Could not enable push notifications.": "పుష్ నోటిఫికేషన్‌లను ప్రారంభించలేకపోయాము.",
  "Push notifications disabled.": "పుష్ నోటిఫికేషన్‌లు నిలిపివేయబడ్డాయి.",
  "Could not disable push notifications.": "పుష్ నోటిఫికేషన్‌లను నిలిపివేయలేకపోయాము.",

  // Dashboard
  "Welcome, {name}": "స్వాగతం, {name}",
  "Your multilingual AI assistant for Indian groundwater-resource information.":
    "భారత భూగర్భ జల వనరుల సమాచారం కోసం మీ బహుభాషా AI సహాయకుడు.",
  "{count} states monitored": "{count} రాష్ట్రాలు పర్యవేక్షిస్తున్నాయి",
  "Total Recharge ({unit})": "మొత్తం పునర్భరణం ({unit})",
  "Total Extraction ({unit})": "మొత్తం వెలికితీత ({unit})",
  "Across selected scope": "ఎంచుకున్న పరిధిలో",
  "Assessment category distribution": "అంచనా వర్గ పంపిణీ",
  "Stage-of-extraction categories across assessment units (demo data).":
    "అంచనా యూనిట్లలో వెలికితీత దశ వర్గాలు (డెమో డేటా).",
  "No data available.": "డేటా అందుబాటులో లేదు.",
  "Stage of extraction trend": "వెలికితీత దశ ధోరణి",
  "Annual average across all assessment units (2017–2022).":
    "అన్ని అంచనా యూనిట్లలో వార్షిక సగటు (2017–2022).",
  "Auto-generated insights": "స్వయంచాలకంగా రూపొందించిన అంతర్దృష్టులు",
  "Computed from the latest assessment year.": "తాజా అంచనా సంవత్సరం నుండి లెక్కించబడింది.",
  "No insights available.": "అంతర్దృష్టులు అందుబాటులో లేవు.",
  "Explore groundwater data": "భూగర్భ జల డేటాను అన్వేషించండి",
  "Analytics, maps and reports across the demo states.":
    "డెమో రాష్ట్రాలలో విశ్లేషణలు, పటాలు మరియు నివేదికలు.",
  "{count} more": "మరో {count}",
  "GIS Map": "GIS పటం",
  Analytics: "విశ్లేషణలు",

  // History
  History: "చరిత్ర",
  "Past conversations and expert requests.":
    "గత సంభాషణలు మరియు నిపుణుల అభ్యర్థనలు.",
  "Chat conversations": "చాట్ సంభాషణలు",
  "Expert requests": "నిపుణుల అభ్యర్థనలు",
  "No chat conversations yet.": "ఇంకా చాట్ సంభాషణలు లేవు.",
  "No expert requests yet.": "ఇంకా నిపుణుల అభ్యర్థనలు లేవు.",
  "user {id}": "వినియోగదారు {id}",
  "no priority": "ప్రాధాన్యత లేదు",
  "Location: {location}": "స్థానం: {location}",
  "Resolution: {resolution}": "పరిష్కారం: {resolution}",
  "Loading history…": "చరిత్ర లోడ్ అవుతోంది…",

  // Reports
  "Generate and export groundwater reports (CSV / PDF) from the demo dataset.":
    "డెమో డేటాసెట్ నుండి భూగర్భ జల నివేదికలను (CSV / PDF) రూపొందించండి మరియు ఎగుమతి చేయండి.",
  "Assessment unit detail": "అంచనా యూనిట్ వివరాలు",
  "{count} records · all metrics": "{count} రికార్డులు · అన్ని మెట్రిక్లు",
  "all metrics": "అన్ని మెట్రిక్లు",
  "{type} only": "{type} మాత్రమే",
  "both demo states": "రెండు డెమో రాష్ట్రాలు",
  "Choose a scope and click Generate to preview a report.":
    "ఒక పరిధిని ఎంచుకుని నివేదికను ప్రివ్యూ చేయడానికి Generate క్లిక్ చేయండి.",
  "Failed to generate the report.": "నివేదికను రూపొందించడంలో విఫలమైంది.",
  Unit: "యూనిట్",

  // Assessment report
  "Data report": "డేటా నివేదిక",
  "Assessment report": "అంచనా నివేదిక",
  "Generate an AI-written report for a state, district and period, with status, trend, prediction, risk, map, graphs, recommendations and data sources, exportable as PDF or Excel.":
    "ఒక రాష్ట్రం, జిల్లా మరియు కాలవ్యవధికి AI-రాసిన నివేదికను రూపొందించండి — స్థితి, ధోరణి, అంచనా, ప్రమాదం, పటం, గ్రాఫ్‌లు, సిఫార్సులు మరియు డేటా మూలాలతో, PDF లేదా Excelగా ఎగుమతి చేయవచ్చు.",
  "Period from": "కాలం నుండి",
  "Period to": "కాలం వరకు",
  "Generate report": "నివేదిక రూపొందించండి",
  "Executive summary": "కార్యనిర్వాహక సారాంశం",
  "Groundwater status": "భూగర్భజల స్థితి",
  "Historical trend": "చారిత్రక ధోరణి",
  "Risk analysis": "ప్రమాద విశ్లేషణ",
  Graphs: "గ్రాఫ్‌లు",
  "Data sources": "డేటా మూలాలు",
  "Download PDF": "PDF డౌన్‌లోడ్",
  "Download Excel": "Excel డౌన్‌లోడ్",
  Current: "ప్రస్తుతం",
  Projected: "అంచనా వేయబడింది",
  "Generating assessment report…": "అంచనా నివేదిక రూపొందించబడుతోంది…",
  "No report yet. Choose a scope and period, then click Generate report.":
    "ఇంకా నివేదిక లేదు. పరిధి మరియు కాలవ్యవధిని ఎంచుకుని, Generate report క్లిక్ చేయండి.",
  "Failed to generate the assessment report.": "అంచనా నివేదికను రూపొందించడంలో విఫలమైంది.",
  "latest data {year}": "తాజా డేటా {year}",
  "Stage of extraction, {from}–{latest}": "వెలికితీత దశ, {from}–{latest}",
  "to {year}": "{year} వరకు",
  "status {year}": "స్థితి {year}",

  // Notifications
  Notifications: "నోటిఫికేషన్లు",
  "Alerts when groundwater metrics cross thresholds, plus your alert rules.":
    "భూగర్భ జల మెట్రిక్లు పరిమితులను దాటినప్పుడు హెచ్చరికలు, మరియు మీ అలర్ట్ నియమాలు.",
  "Run alert check": "అలర్ట్ తనిఖీ అమలు",
  "Recent notifications ({unread} unread)": "ఇటీవలి నోటిఫికేషన్లు ({unread} చదవనివి)",
  "Mark all read": "అన్నీ చదివినట్లుగా గుర్తించండి",
  "No notifications yet. Create an alert rule below to be notified when a metric crosses a threshold.":
    "ఇంకా నోటిఫికేషన్లు లేవు. ఒక మెట్రిక్ పరిమితిని దాటినప్పుడు తెలియజేయడానికి క్రింద అలర్ట్ నియమాన్ని సృష్టించండి.",
  "Create alert rule": "అలర్ట్ నియమాన్ని సృష్టించండి",
  "Evaluated against assessment data; a notification is created whenever a unit matches.":
    "అంచనా డేటా ఆధారంగా మూల్యాంకనం; ఒక యూనిట్ సరిపోలినప్పుడు నోటిఫికేషన్ సృష్టించబడుతుంది.",
  "Rule name": "నియమం పేరు",
  Threshold: "పరిమితి",
  "Add rule": "నియమాన్ని జోడించండి",
  "State (optional)": "రాష్ట్రం (ఐచ్ఛికం)",
  "District (optional)": "జిల్లా (ఐచ్ఛికం)",
  "Village (optional)": "గ్రామం (ఐచ్ఛికం)",
  "Your alert rules ({count})": "మీ అలర్ట్ నియమాలు ({count})",
  Name: "పేరు",
  Condition: "షరతు",
  Scope: "పరిధి",
  Status: "స్థితి",
  "Last triggered": "చివరిసారి ట్రిగ్గర్",
  Actions: "చర్యలు",
  Enabled: "ప్రారంభించబడింది",
  Disabled: "నిలిపివేయబడింది",
  Enable: "ప్రారంభించండి",
  Disable: "నిలిపివేయండి",
  never: "ఎప్పుడూ",
  "No alert rules yet. Create one above.": "ఇంకా అలర్ట్ నియమాలు లేవు. పైన ఒకటి సృష్టించండి.",
  "Alert rule created.": "అలర్ట్ నియమం సృష్టించబడింది.",
  "Could not create alert rule.": "అలర్ట్ నియమాన్ని సృష్టించలేకపోయాము.",
  "Could not update rule.": "నియమాన్ని నవీకరించలేకపోయాము.",
  "Could not delete rule.": "నియమాన్ని తొలగించలేకపోయాము.",
  "{count} alert{s} triggered.": "{count} అలర్ట్(లు) ట్రిగ్గర్ అయ్యాయి.",
  "Could not run alert check.": "అలర్ట్ తనిఖీని అమలు చేయలేకపోయాము.",
  "> (greater than)": "> (కంటే ఎక్కువ)",
  "≥ (greater or equal)": "≥ (కంటే ఎక్కువ లేదా సమానం)",
  "< (less than)": "< (కంటే తక్కువ)",
  "≤ (less or equal)": "≤ (కంటే తక్కువ లేదా సమానం)",
  "Extractable resource": "వెలికితీయదగిన వనరు",

  // Admin
  Administration: "నిర్వహణ",
  "Users, audit trail and dataset registry.": "వినియోగదారులు, ఆడిట్ ట్రయిల్ మరియు డేటాసెట్ రిజిస్ట్రీ.",
  "Failed to load admin data (admin role required).":
    "అడ్మిన్ డేటాను లోడ్ చేయడంలో విఫలమైంది (అడ్మిన్ రోల్ అవసరం).",
  "Create user": "వినియోగదారుని సృష్టించండి",
  "Full name": "పూర్తి పేరు",
  Email: "ఇమెయిల్",
  Password: "పాస్వర్డ్",
  Create: "సృష్టించండి",
  "Import dataset (CSV / XLSX)": "డేటాసెట్ను దిగుమతి చేయండి (CSV / XLSX)",
  "Upload assessment data (state, district, assessment_unit, year, recharge, extraction, stage, category). Imported rows are tagged as real data, not demo.":
    "అంచనా డేటాను అప్‌లోడ్ చేయండి (రాష్ట్రం, జిల్లా, అంచనా యూనిట్, సంవత్సరం, పునర్భరణం, వెలికితీత, దశ, వర్గం). దిగుమతి చేసిన వరుసలు డెమో కాకుండా నిజమైన డేటాగా గుర్తించబడతాయి.",
  "Dataset name": "డేటాసెట్ పేరు",
  "Source (e.g. CGWB, State dept.)": "మూలం (ఉదా. CGWB, రాష్ట్ర శాఖ)",
  Import: "దిగుమతి",
  Template: "టెంప్లేట్",
  "Failed to create user.": "వినియోగదారుని సృష్టించడంలో విఫలమైంది.",
  "Failed to update user.": "వినియోగదారుని నవీకరించడంలో విఫలమైంది.",
  "Failed to update role.": "పాత్రను నవీకరించడంలో విఫలమైంది.",
  "Users ({count})": "వినియోగదారులు ({count})",
  Role: "పాత్ర",
  "Last login": "చివరి లాగిన్",
  Active: "క్రియాశీల",
  Datasets: "డేటాసెట్లు",
  Source: "మూలం",
  Version: "వెర్షన్",
  Level: "స్థాయి",
  "Semantic RAG": "సెమాంటిక్ RAG",
  "Hybrid retrieval combines BM25 keyword matching with embedding-based semantic search. Re-embedding recomputes vectors for all knowledge chunks.":
    "హైబ్రిడ్ రిట్రీవల్ BM25 కీవర్డ్ మ్యాచింగ్‌ను ఎంబెడ్డింగ్ ఆధారిత సెమాంటిక్ శోధనతో కలుపుతుంది. రీ-ఎంబెడ్డింగ్ అన్ని నాలెడ్జ్ చంక్‌ల కోసం వెక్టర్‌లను తిరిగి లెక్కిస్తుంది.",
  Available: "అందుబాటులో ఉంది",
  Unavailable: "అందుబాటులో లేదు",
  "{indexed} / {chunks} chunks indexed": "{indexed} / {chunks} చంక్‌లు ఇండెక్స్ చేయబడ్డాయి",
  "mode: {mode}": "మోడ్: {mode}",
  "model: {model}": "మోడల్: {model}",
  "Re-embed": "రీ-ఎంబెడ్",
  "RAG status unavailable.": "RAG స్థితి అందుబాటులో లేదు.",
  "Audit log": "ఆడిట్ లాగ్",
  Time: "సమయం",
  Action: "చర్య",
  Resource: "వనరు",
  "No audit events yet.": "ఇంకా ఆడిట్ ఈవెంట్లు లేవు.",
  "Loading admin panel…": "అడ్మిన్ ప్యానెల్ లోడ్ అవుతోంది…",
  "Could not download the import template.": "దిగుమతి టెంప్లేట్‌ను డౌన్‌లోడ్ చేయలేకపోయాము.",
  "Dataset imported successfully.": "డేటాసెట్ విజయవంతంగా దిగుమతి చేయబడింది.",
  "Import failed. See the message below.": "దిగుమతి విఫలమైంది. క్రింద సందేశం చూడండి.",
  "Failed to import dataset.": "డేటాసెట్ను దిగుమతి చేయడంలో విఫలమైంది.",
  "{rows} row(s) imported ({parsed} parsed). {states} state(s), {districts} district(s), {units} unit(s) created.":
    "{rows} వరుస(లు) దిగుమతి చేయబడ్డాయి ({parsed} పార్స్ చేయబడ్డాయి). {states} రాష్ట్రం(లు), {districts} జిల్లా(లు), {units} యూనిట్(లు) సృష్టించబడ్డాయి.",
  "{alerts} alert(s) triggered.": "{alerts} అలర్ట్(లు) ట్రిగ్గర్ అయ్యాయి.",
  "Re-embedded {updated} knowledge chunks.": "{updated} నాలెడ్జ్ చంక్‌లు రీ-ఎంబెడ్ చేయబడ్డాయి.",
  "Could not re-index embeddings.": "ఎంబెడ్డింగ్‌లను రీ-ఇండెక్స్ చేయలేకపోయాము.",

  // VoiceAdmin
  "Real telephone integration: Twilio / Exotel / Plivo transport with the same LangGraph AI brain as the web app.":
    "నిజమైన టెలిఫోన్ ఇంటిగ్రేషన్: వెబ్ యాప్ వలె అదే LangGraph AI మెదడుతో Twilio / Exotel / Plivo ట్రాన్స్‌పోర్ట్.",
  "Test connection": "కనెక్షన్ పరీక్ష",
  "Run end-to-end test": "ఎండ్-టు-ఎండ్ పరీక్షను అమలు చేయండి",
  "End-to-end test: {question} ({passed}/{total} passed)":
    "ఎండ్-టు-ఎండ్ పరీక్ష: {question} ({passed}/{total} ఆమోదించబడ్డాయి)",
  "language={language} · intent={intent} · location={location}":
    "భాష={language} · ఉద్దేశం={intent} · స్థానం={location}",
  "Response:": "ప్రతిస్పందన:",
  "Total calls": "మొత్తం కాల్స్",
  "Completed / Failed": "పూర్తయినవి / విఫలమైనవి",
  "{count} failed": "{count} విఫలమయ్యాయి",
  "Avg duration": "సగటు వ్యవధి",
  "Escalation rate": "ఎస్కలేషన్ రేటు",
  "Telephony configuration": "టెలిఫోనీ కాన్ఫిగరేషన్",
  "Provider selection and media streaming. API secrets are never shown.":
    "ప్రొవైడర్ ఎంపిక మరియు మీడియా స్ట్రీమింగ్. API సీక్రెట్స్ ఎప్పటికీ చూపబడవు.",
  Provider: "ప్రొవైడర్",
  "STT / TTS": "STT / TTS",
  "Media stream WebSocket": "మీడియా స్ట్రీమ్ WebSocket",
  "Set VOICE_PUBLIC_URL to enable media streaming":
    "మీడియా స్ట్రీమింగ్ ప్రారంభించడానికి VOICE_PUBLIC_URL సెట్ చేయండి",
  "Call log ({count})": "కాల్ లాగ్ ({count})",
  "Caller numbers are masked; languages and intents are captured from the AI.":
    "కాలర్ నంబర్లు మాస్క్ చేయబడతాయి; భాషలు మరియు ఉద్దేశాలు AI నుండి సంగ్రహించబడతాయి.",
  "Call ID": "కాల్ ID",
  Language: "భాష",
  Intent: "ఉద్దేశం",
  Duration: "వ్యవధి",
  State: "స్థితి",
  Confidence: "విశ్వాసం",
  Escalated: "ఎస్కలేట్ చేయబడింది",
  Date: "తేదీ",
  Yes: "అవును",
  'No calls yet. Run an end-to-end test or click "📞 Test Voice Assistant".':
    'ఇంకా కాల్స్ లేవు. ఎండ్-టు-ఎండ్ పరీక్షను అమలు చేయండి లేదా "📞 వాయిస్ అసిస్టెంట్ పరీక్ష" క్లిక్ చేయండి.',
  "Transcript — call #{id}": "ట్రాన్స్క్రిప్ట్ — కాల్ #{id}",
  "Close transcript": "ట్రాన్స్క్రిప్ట్ మూసివేయండి",
  "No transcript recorded.": "ట్రాన్స్క్రిప్ట్ నమోదు కాలేదు.",
  "End-to-end voice test completed.": "ఎండ్-టు-ఎండ్ వాయిస్ పరీక్ష పూర్తయింది.",
  "Voice test failed.": "వాయిస్ పరీక్ష విఫలమైంది.",
  "Could not reach the connection test endpoint.": "కనెక్షన్ పరీక్ష ఎండ్‌పాయింట్‌ను చేరుకోలేకపోయాము.",
  "Could not load transcript.": "ట్రాన్స్క్రిప్ట్ లోడ్ చేయలేకపోయాము.",
  Greeting: "అభివాదం",
  Help: "సహాయం",
  Terminology: "పరిభాష",
  Data: "డేటా",
  Map: "మ్యాప్",
  Trend: "ధోరణి",
  Prediction: "అంచనా",
  Explanation: "వివరణ",
  Recommendations: "సిఫార్సులు",
  Recommendation: "సిఫార్సు",
  annual_extractable_resource: "వార్షిక వెలికితీయదగిన వనరు",
  assessment_units: "అంచనా యూనిట్లు",
  top_districts_by_stage: "వెలికితీత దశ ఆధారంగా అగ్ర జిల్లాలు",
  confidence_band: "95% పరిధి",
  Thanks: "కృతజ్ఞతలు",
  Unclear: "అస్పష్టం",
  "What is the stage of extraction in Telangana?": "తెలంగాణలో వెలికితీత దశ ఎంత?",
  "Recharge in Guntur district": "గుంటూరు జిల్లాలో పునర్భరణం",
  "What is an aquifer?": "జలాశయం అంటే ఏమిటి?",
  "What can you do?": "మీరు ఏమి చేయగలరు?",
  "Failed to load Google Maps.": "Google Maps లోడ్ చేయడంలో విఫలమైంది.",
  "unit.plural": "యూనిట్లు",
  "All villages": "అన్ని గ్రామాలు",
  "Demo data · {source}": "డెమో డేటా · {source}",
  "more": "మరో",
  "+{count} more": "మరో {count}",
  User: "వినియోగదారు",
  "user #{id}": "వినియోగదారు #{id}",
  "e.g. Why is stage of extraction rising in Yadadri despite monsoon recharge?":
    "ఉదా. రుతుపవనాల పునర్భరణం ఉన్నప్పటికీ యాదాద్రిలో వెలికితీత దశ ఎందుకు పెరుగుతోంది?",
  "Location (e.g. Yadadri Bhuvanagiri, Telangana)":
    "స్థానం (ఉదా. యాదాద్రి భువనగిరి, తెలంగాణ)",
  "{count} records": "{count} రికార్డులు",
  "Failed to load map data.": "పటం డేటాను లోడ్ చేయడంలో విఫలమైంది.",
  "Full-India map of all states and union territories with the synthetic demo dataset.":
    "సింథటిక్ డెమో డేటాసెట్తో అన్ని రాష్ట్రాలు మరియు కేంద్రపాలిత ప్రాంతాల పూర్తి భారత పటం.",
  Legend: "లెజెండ్",

  // Expert
  "Expert Desk": "నిపుణుల డెస్క్",
  "Escalate complex groundwater questions to domain experts.":
    "సంక్లిష్ట భూగర్భ జల ప్రశ్నలను నిపుణులకు ఎస్కలేట్ చేయండి.",
  "Escalate a question": "ప్రశ్నను ఎస్కలేట్ చేయండి",
  "Create a request when the assistant cannot answer conclusively.":
    "సహాయకుడు ఖచ్చితంగా సమాధానం ఇవ్వలేనప్పుడు అభ్యర్థనను సృష్టించండి.",
  "Create request": "అభ్యర్థనను సృష్టించండి",
  Requests: "అభ్యర్థనలు",
  "Manage status, priority and resolutions.": "స్థితి, ప్రాధాన్యత మరియు పరిష్కారాలను నిర్వహించండి.",
  "Track your escalations.": "మీ ఎస్కలేషన్లను ట్రాక్ చేయండి.",
  "All statuses": "అన్ని స్థితులు",
  "No requests {withStatus}.": "అభ్యర్థనలు లేవు {withStatus}.",
  "with status {status}": "{status} స్థితితో",
  yet: "ఇంకా",
  ID: "ID",
  Question: "ప్రశ్న",
  From: "నుండి",
  Priority: "ప్రాధాన్యత",
  "Resolved {date}": "{date}న పరిష్కరించబడింది",
  Resolve: "పరిష్కరించండి",
  "Failed to load expert requests.": "నిపుణుల అభ్యర్థనలను లోడ్ చేయడంలో విఫలమైంది.",
  "Failed to create the request.": "అభ్యర్థనను సృష్టించడంలో విఫలమైంది.",
  "Update failed — requires expert or admin role.":
    "నవీకరణ విఫలమైంది — నిపుణుడు లేదా అడ్మిన్ పాత్ర అవసరం.",
  "Addressed by expert desk.": "నిపుణుల డెస్క్ ద్వారా పరిష్కరించబడింది.",

  // Landing
  "Sign in": "సైన్ ఇన్",
  "Get started": "ప్రారంభించండి",
  "Indian Groundwater Resource Estimation System":
    "భారత భూగర్భ జల వనరుల అంచనా వ్యవస్థ",
  "AI-Powered Groundwater Intelligence": "AI ఆధారిత భూగర్భ జల మేధస్సు",
  "Ask questions about India's groundwater resources using text or voice — in English, Telugu or Hindi.":
    "వచనం లేదా వాయిస్ ద్వారా భారతదేశ భూగర్భ జల వనరుల గురించి ప్రశ్నలు అడగండి — ఇంగ్లీష్, తెలుగు లేదా హిందీలో.",
  "Start Asking": "ప్రశ్నించడం ప్రారంభించండి",
  "Explore Groundwater": "భూగర్భ జలాన్ని అన్వేషించండి",
  "Try Voice Assistant": "వాయిస్ అసిస్టెంట్ ప్రయత్నించండి",
  Example: "ఉదాహరణ",
  "Example (Telugu)": "ఉదాహరణ (తెలుగు)",
  "Example (Hindi)": "ఉదాహరణ (హిందీ)",
  "How it works": "ఇది ఎలా పని చేస్తుంది",
  "Built for groundwater research": "భూగర్భ జల పరిశోధన కోసం రూపొందించబడింది",
  "An assistant you can trust with data": "డేటాతో మీరు విశ్వసించగల సహాయకుడు",
  "IN-GRES AI never fabricates official groundwater numbers. Demo and synthetic datasets are always clearly labelled, sources and years are shown, and uncertain questions are escalated to human groundwater experts.":
    "IN-GRES AI అధికారిక భూగర్భ జల గణాంకాలను ఎప్పుడూ రూపొందించదు. డెమో మరియు సింథటిక్ డేటాసెట్లు ఎల్లప్పుడూ స్పష్టంగా లేబుల్ చేయబడతాయి, మూలాలు మరియు సంవత్సరాలు చూపబడతాయి మరియు అనిశ్చిత ప్రశ్నలు మానవ భూగర్భ జల నిపుణులకు ఎస్కలేట్ చేయబడతాయి.",
  "Data trust · Source transparency · Expert escalation":
    "డేటా నమ్మకం · మూల పారదర్శకత · నిపుణుల ఎస్కలేషన్",
  "Indian Groundwater Resource Estimation System — AI Virtual Assistant":
    "భారత భూగర్భ జల వనరుల అంచనా వ్యవస్థ — AI వర్చువల్ అసిస్టెంట్",
  "Phase 1 prototype · Demo data labelled": "ఫేజ్ 1 ప్రోటోటైప్ · డెమో డేటా లేబుల్ చేయబడింది",
  "Multilingual AI": "బహుభాషా AI",
  "Ask in English, Telugu or Hindi — the assistant understands code-switching and answers back in your language.":
    "ఇంగ్లీష్, తెలుగు లేదా హిందీలో అడగండి — సహాయకుడు కోడ్-స్విచింగ్ అర్థం చేసుకుని మీ భాషలో సమాధానం ఇస్తాడు.",
  "Structured queries over recharge, extraction, availability and stage-of-extraction data with charts and trends.":
    "చార్ట్లు మరియు ధోరణులతో పునర్భరణం, వెలికితీత, లభ్యత మరియు వెలికితీత దశ డేటాపై నిర్మాణాత్మక ప్రశ్నలు.",
  "Interactive GIS": "ఇంటరాక్టివ్ GIS",
  "Explore states, districts and assessment units on maps, coloured by assessment category.":
    "అంచనా వర్గం ద్వారా రంగులో, పటాలపై రాష్ట్రాలు, జిల్లాలు మరియు అంచనా యూనిట్లను అన్వేషించండి.",
  "Trusted Knowledge": "నమ్మదగిన జ్ఞానం",
  "Retrieval-augmented answers grounded in documented sources — no invented numbers.":
    "డాక్యుమెంట్ చేయబడిన మూలాల ఆధారంగా రిట్రీవల్-ఆగ్మెంటెడ్ సమాధానాలు — రూపొందించిన సంఖ్యలు లేవు.",
  "Voice Assistant": "వాయిస్ అసిస్టెంట్",
  "Talk to IN-GRES AI over the web or by phone, in multiple Indian languages.":
    "వెబ్ ద్వారా లేదా ఫోన్ ద్వారా, బహుళ భారతీయ భాషలలో IN-GRES AIతో మాట్లాడండి.",
  "Expert Assistance": "నిపుణుల సహాయం",
  "When AI confidence is low, your question is escalated to a groundwater expert.":
    "AI విశ్వాసం తక్కువగా ఉన్నప్పుడు, మీ ప్రశ్న భూగర్భ జల నిపుణుడికి ఎస్కలేట్ చేయబడుతుంది.",
  Ask: "అడగండి",
  "Type or speak a question about groundwater resources in India.":
    "భారతదేశంలోని భూగర్భ జల వనరుల గురించి ఒక ప్రశ్నను టైప్ చేయండి లేదా మాట్లాడండి.",
  Understand: "అర్థం చేసుకోండి",
  "IN-GRES AI detects language, intent, location and the metric you care about.":
    "IN-GRES AI భాష, ఉద్దేశం, స్థానం మరియు మీకు ముఖ్యమైన మెట్రిక్‌ను గుర్తిస్తుంది.",
  Answer: "సమాధానం",
  "Get a clear answer with values, units, year, sources, charts and maps.":
    "విలువలు, యూనిట్లు, సంవత్సరం, మూలాలు, చార్ట్లు మరియు పటాలతో స్పష్టమైన సమాధానం పొందండి.",

  // Login / Register
  "Welcome back": "తిరిగి స్వాగతం",
  "Sign in to your groundwater assistant": "మీ భూగర్భ జల సహాయకుడికి సైన్ ఇన్ చేయండి",
  "Signing in…": "సైన్ ఇన్ అవుతోంది…",
  "No account?": "ఖాతా లేదా?",
  "Create one": "ఒకటి సృష్టించండి",
  "Create your account": "మీ ఖాతాను సృష్టించండి",
  "Start asking about groundwater resources": "భూగర్భ జల వనరుల గురించి ప్రశ్నించడం ప్రారంభించండి",
  "Confirm password": "పాస్వర్డ్ నిర్ధారించండి",
  "Creating account…": "ఖాతా సృష్టిస్తోంది…",
  "Create account": "ఖాతా సృష్టించండి",
  "Already registered?": "ఇప్పటికే నమోదు చేసుకున్నారా?",
  "Passwords do not match": "పాస్వర్డ్‌లు సరిపోలడం లేదు",
  "Password must be at least 8 characters": "పాస్వర్డ్ కనీసం 8 అక్షరాలు ఉండాలి",

  // Assistant
  "No conversations yet.": "ఇంకా సంభాషణలు లేవు.",
  "Delete conversation": "సంభాషణను తొలగించండి",
  "Groundwater Assistant": "భూగర్భ జల సహాయకుడు",
  "Ask about recharge, extraction, stage of extraction or assessment categories for any state, district or village in India — in English, Telugu or Hindi. Use the microphone to speak your question.":
    "భారతదేశంలోని ఏ రాష్ట్రం, జిల్లా లేదా గ్రామానికైనా పునర్భరణం, వెలికితీత, వెలికితీత దశ లేదా అంచనా వర్గాల గురించి అడగండి — ఇంగ్లీష్, తెలుగు లేదా హిందీలో. మీ ప్రశ్నను మాట్లాడటానికి మైక్రోఫోన్ ఉపయోగించండి.",
  "Good morning": "శుభోదయం",
  "Good afternoon": "శుభ మధ్యాహ్నం",
  "Good evening": "శుభ సాయంత్రం",
  "How can I help you with groundwater today?": "ఈరోజు భూగర్భ జలాల గురించి నేను మీకు ఎలా సహాయం చేయగలను?",
  "New conversation": "కొత్త సంభాషణ",
  "Search conversations": "సంభాషణలను వెతకండి",
  "Or try": "లేదా ఇవి ప్రయత్నించండి",
  "Recharge in a state": "ఒక రాష్ట్రంలో పునర్భరణం",
  "Stage of extraction": "వెలికితీత దశ",
  "Assessment categories": "అంచనా వర్గాలు",
  "A specific village": "నిర్దిష్ట గ్రామం",
  "Compare across years": "సంవత్సరాల మధ్య పోల్చండి",
  "Explain a term": "పదాన్ని వివరించండి",
  Copy: "కాపీ",
  Send: "పంపు",
  "Enter to send · Shift+Enter for a new line": "పంపడానికి Enter · కొత్త పంక్తికి Shift+Enter",
  "Ask anything about India's groundwater": "భారతదేశ భూగర్భ జలాల గురించి ఏదైనా అడగండి",
  "Answers come from a labelled synthetic demo dataset — never official IN-GRES/CGWB data.":
    "సమాధానాలు లేబుల్ చేయబడిన సింథటిక్ డెమో డేటాసెట్ నుండి వస్తాయి — అధికారిక IN-GRES/CGWB డేటా కాదు.",
  Explore: "అన్వేషించండి",
  Workspace: "వర్క్స్పేస్",
  "Support & Admin": "సహాయం & నిర్వహణ",
  Overview: "అవలోకనం",
  "Voice Calls": "వాయిస్ కాల్స్",
  Groundwater: "భూగర్భ జలం",
  Reports: "నివేదికలు",
  Voice: "వాయిస్",
  Admin: "నిర్వహణ",
  "Sorry, I could not reach the assistant service. Please try again.":
    "క్షమించండి, సహాయక సేవను చేరుకోలేకపోయాము. దయచేసి మళ్ళీ ప్రయత్నించండి.",
  "Read aloud": "బిగ్గరగా చదవండి",
  "Escalated to expert desk": "నిపుణుల డెస్క్‌కు ఎస్కలేట్ చేయబడింది",
  "Escalate to an expert": "నిపుణుడికి ఎస్కలేట్ చేయండి",
  "Stop listening": "వినడం ఆపండి",
  "Speak your question": "మీ ప్రశ్నను మాట్లాడండి",
  "Speech recognition is not supported in this browser.":
    "ఈ బ్రౌజర్‌లో స్పీచ్ గుర్తింపు మద్దతు లేదు.",
  "Microphone access requires a secure connection. Open the app via http://localhost:5173 or HTTPS.":
    "మైక్రోఫోన్ యాక్సెస్‌కు సురక్షిత కనెక్షన్ అవసరం. http://localhost:5173 లేదా HTTPS ద్వారా యాప్‌ను తెరవండి.",
  "Microphone permission was denied. Allow the microphone in your browser settings and try again.":
    "మైక్రోఫోన్ అనుమతి తిరస్కరించబడింది. బ్రౌజర్ సెట్టింగ్‌లలో మైక్రోఫోన్‌ను అనుమతించి మళ్ళీ ప్రయత్నించండి.",
  "No microphone was found. Connect a microphone and try again.":
    "మైక్రోఫోన్ కనుగొనబడలేదు. మైక్రోఫోన్ కనెక్ట్ చేసి మళ్ళీ ప్రయత్నించండి.",
  "No speech was detected. Please speak clearly and try again.":
    "మాట గుర్తించబడలేదు. దయచేసి స్పష్టంగా మాట్లాడి మళ్ళీ ప్రయత్నించండి.",
  "The speech service could not be reached. Check your internet connection.":
    "స్పీచ్ సేవను చేరుకోలేకపోయాము. మీ ఇంటర్నెట్ కనెక్షన్ తనిఖీ చేయండి.",
  "Speech recognition is not allowed on this connection. Open the app via http://localhost:5173 or HTTPS.":
    "ఈ కనెక్షన్‌లో స్పీచ్ గుర్తింపు అనుమతించబడదు. http://localhost:5173 లేదా HTTPS ద్వారా యాప్‌ను తెరవండి.",
  "Could not capture speech ({code}). Check the microphone permission.":
    "మాటను సంగ్రహించలేకపోయాము ({code}). మైక్రోఫోన్ అనుమతిని తనిఖీ చేయండి.",

  // GIS
  "Map filters": "పటం ఫిల్టర్లు",
  View: "వీక్షణ",
  "All India": "ఆల్ ఇండియా",
  "All India — groundwater overview": "ఆల్ ఇండియా — భూగర్భ జల అవలోకనం",
  "36 states & UTs": "36 రాష్ట్రాలు & కేంద్రపాలిత ప్రాంతాలు",
  "Avg stage of extraction": "సగటు వెలికితీత దశ",
  "Over-exploited units": "అధికంగా దోపిడీకి గురైన యూనిట్లు",
  "Safe (<70%)": "సురక్షితం (<70%)",
  "Semi-critical (70–90%)": "అర్ధ-కీలకం (70–90%)",
  "Critical (90–100%)": "కీలకం (90–100%)",
  "Over-exploited (>100%)": "అధిక దోపిడీ (>100%)",
  "No data in demo dataset": "డెమో డేటాసెట్‌లో డేటా లేదు",
  "Click a state or unit to inspect its value, stage and category.":
    "దాని విలువ, దశ మరియు వర్గాన్ని చూడటానికి ఒక రాష్ట్రం లేదా యూనిట్‌పై క్లిక్ చేయండి.",
  "Reset map": "పటాన్ని రీసెట్ చేయండి",
  "Latest ({year})": "తాజా ({year})",
  "Low → high value (hm³)": "తక్కువ → ఎక్కువ విలువ (hm³)",
  Village: "గ్రామం",

  // GIS layers & click-to-analyze
  Layers: "పొరలు",
  "Groundwater Level": "భూగర్భజల స్థాయి",
  "Critical Areas": "క్లిష్ట ప్రాంతాలు",
  "Monitoring Stations": "పర్యవేక్షణ కేంద్రాలు",
  "Monitoring station": "పర్యవేక్షణ కేంద్రం",
  "Click the map to analyze any location.":
    "ఏదైనా ప్రాంతాన్ని విశ్లేషించడానికి పటంపై క్లిక్ చేయండి.",
  "Analyzing location…": "ప్రాంతాన్ని విశ్లేషిస్తోంది…",
  "No groundwater data near this location.":
    "ఈ ప్రాంతం సమీపంలో భూగర్భజల డేటా లేదు.",
  "Could not analyze this location.": "ఈ ప్రాంతాన్ని విశ్లేషించలేకపోయాము.",
  Stable: "స్థిరం",
  "m/year": "మీ/సంవత్సరం",
  "AI Prediction": "AI అంచనా",
  Risk: "ప్రమాదం",
  Shallow: "లోతులేని",
  Deep: "లోతైన",
  "derived from stage of extraction (demo)":
    "వెలికితీత దశ నుండి ఉత్పన్నం (డెమో)",
  "Predicted category": "అంచనా వేసిన వర్గం",
  Heatmap: "హీట్ మ్యాప్",

  // Map components
  "State / UT": "రాష్ట్రం / కేంద్రపాలిత ప్రాంతం",
  "No assessment data in demo dataset": "డెమో డేటాసెట్‌లో అంచనా డేటా లేదు",
  "unit": "యూనిట్",
  "Avg stage: {stage}% · {category}": "సగటు దశ: {stage}% · {category}",
  "Synthetic demo data": "సింథటిక్ డెమో డేటా",
  "Stage: {stage}% · {category}": "దశ: {stage}% · {category}",
  "No data": "డేటా లేదు",
  "Set VITE_GOOGLE_MAPS_API_KEY to use Google Maps.":
    "Google Maps ఉపయోగించడానికి VITE_GOOGLE_MAPS_API_KEY సెట్ చేయండి.",
  "Loading Google Maps…": "Google Maps లోడ్ అవుతోంది…",
  "Failed to load the Google Maps script.": "Google Maps స్క్రిప్ట్‌ను లోడ్ చేయడంలో విఫలమైంది.",

  Menu: "మెను",

  // GIS time-lapse & comparison (Phase 20)
  To: "వరకు",
  Compare: "పోల్చండి",
  "Compare years": "సంవత్సరాలను పోల్చండి",
  "Play time-lapse": "టైమ్-ల్యాప్స్ ఆడించండి",
  Pause: "విరామం",
  "Units compared": "పోల్చిన యూనిట్లు",
  "Category changes": "వర్గ మార్పులు",
  "Avg change": "సగటు మార్పు",
  Improved: "మెరుగుపడింది",
  Worsened: "తీవ్రమైంది",
  "No change": "మార్పు లేదు",
  "Change over time": "కాలానుగుణ మార్పు",
  "Category: {a} → {b}": "వర్గం: {a} → {b}",
  "Click a state or unit to see its change between the two years.":
    "రెండు సంవత్సరాల మధ్య మార్పు చూడటానికి ఒక రాష్ట్రం లేదా యూనిట్ పై క్లిక్ చేయండి.",

  // Assistant forecast & scenario (Phase 20)
  Scenario: "దృశ్యం",

  // Village-friendly visuals (Phase 26)
  "A quick picture of the groundwater near you.": "మీ చుట్టూ ఉన్న భూగర్భ జలాల స్థితికి ఒక చిన్న పరిచయం.",
  "Areas tracked": "పర్యవేక్షించే ప్రాంతాలు",
  "Water refilling the ground": "నేలలోకి చేరే నీరు",
  "Water pumped out": "నేల నుండి తోడే నీరు",
  "Each year": "ప్రతి సంవత్సరం",
  "How much water do we use?": "మేము ఎంత నీరు వాడుతున్నాము?",
  "Share of the fresh water that gets pumped up each year.":
    "ప్రతి సంవత్సరం తోడే తాజా నీటి వాటా.",
  "Condition of the areas": "ప్రాంతాల స్థితి",
  "Every area is marked Safe, Needs Care or Critical.":
    "ప్రతి ప్రాంతానికి సురక్షితం, జాగ్రత్త లేదా ప్రమాదకరం అని గుర్తు.",
  "{count} of {total} areas are using more water than is safe.":
    "{total} ప్రాంతాలలో {count} ప్రాంతాలు అవసరం కంటే ఎక్కువ నీరు వాడుతున్నాయి.",
  "The largest group is {category} ({count} areas).":
    "పెద్ద సమూహం {category} ({count} ప్రాంతాలు).",
  "Good news: all {total} areas are in the Safe group.":
    "శుభవార్త: మొత్తం {total} ప్రాంతాలు సురక్షిత సమూహంలో ఉన్నాయి.",
  "Water use over the years": "సంవత్సరాల వారీ నీటి వినియోగం",
  "Share of fresh water pumped up, year by year.":
    "ప్రతి సంవత్సరం తోడే తాజా నీటి వాటా.",
  "Going up": "పెరుగుతోంది",
  "Coming down": "తగ్గుతోంది",
  Steady: "అలాగే ఉంది",
  "In {year}, people used about {pct}% of the fresh water.":
    "{year}లో, ప్రజలు సుమారు {pct}% తాజా నీటిని వాడారు.",
  "Use keeps increasing — water needs care.":
    "వినియోగం పెరుగుతూనే ఉంది — నీటిపై జాగ్రత్త అవసరం.",
  "Use is coming down — a good sign.":
    "వినియోగం తగ్గుతోంది — ఇది మంచి సంకేతం.",
  "Use has stayed about the same.": "వినియోగం దాదాపు అలాగే ఉంది.",
  "What your village should know": "మీ గ్రామం తెలుసుకోవాల్సినవి",
  "Short answers from the latest data.": "తాజా డేటా నుండి చిన్న సమాధానాలు.",
  "Ask a question": "ప్రశ్న అడగండి",
  "What does this mean?": "దీని అర్థం ఏమిటి?",
  "See the water situation for any state, district or village.":
    "ఏ రాష్ట్రం, జిల్లా లేదా గ్రామం యొక్క నీటి పరిస్థితినైనా చూడండి.",
  "Water that refills the ground each year, in {unit}.":
    "ప్రతి సంవత్సరం నేలలోకి చేరే నీరు, {unit}లో.",
  "In {from}, {valueA} went into the ground; in {to}, it was {valueB}.":
    "{from}లో {valueA} నేలలోకి చేరింది; {to}లో {valueB} చేరింది.",
  "Water pumped out each year, in {unit}.": "ప్రతి సంవత్సరం తోడే నీరు, {unit}లో.",
  "In {from}, {valueA} was pumped out; in {to}, it was {valueB}.":
    "{from}లో {valueA} తోడుబడింది; {to}లో {valueB} తోడుబడింది.",
  "Water usage level": "నీటి వినియోగ స్థాయి",
  level_safe: "సురక్షితం",
  level_attention: "జాగ్రత్త అవసరం",
  level_critical: "ప్రమాదకరం",
  level_unknown: "తెలియదు",
  level_safe_short: "సురక్షితం",
  level_attention_short: "జాగ్రత్త",
  level_critical_short: "ప్రమాదం",

  // Weather map (Phase 26)
  Now: "ఇప్పుడు",
  Tomorrow: "రేపు",
  Today: "ఈరోజు",
  High: "గరిష్ఠ",
  Low: "కనిష్ఠ",
  Weather: "వాతావరణం",
  "7-day forecast": "7 రోజుల అంచనా",
  "{pct}% rain": "{pct}% వర్షం",
  rain_no: "వర్షం లేదు",
  rain_light: "తక్కువ వర్షం",
  rain_moderate: "మోస్తరు వర్షం",
  rain_heavy: "భారీ వర్షం",
  rain_very_heavy: "అతి భారీ వర్షం",
  "Rain is likely within the next 3 hours ({pct}% chance).":
    "ముఖాంతర 3 గంటల్లో వర్షం సాధ్యమే ({pct}%).",
  "Heavy rainfall may occur today (about {mm} mm). Take care around streams and low areas.":
    "ఈరోజు భారీ వర్షం సాధ్యమే (సుమారు {mm} mm). చెరువులు, తక్కువ ప్రాంతాల చుట్టూ జాగ్రత్త.",
  "Very hot tomorrow — about {deg}°C. Stay hydrated.":
    "రేపు చాలా వేడి — సుమారు {deg}°C. నీరు బాగుండా తాగండి.",
  "Very hot today — about {deg}°C.": "ఈరోజు చాలా వేడి — సుమారు {deg}°C.",
  "Strong winds expected today.": "ఈరోజు బలమైన గాలులు ఉండవచ్చు.",
  "When will it rain?": "వర్షం ఎప్పుడు పడుతుంది?",
  "Next 24 hours": "తర్వాత 24 గంటలు",
  "Chance of rain over the next 24 hours": "తర్వాత 24 గంటల్లో వర్ష అవకాశం",
  "{word} expected today (about {mm} mm). Highest chance: {pct}%.":
    "ఈరోజు {word} అంచనా (సుమారు {mm} mm). ఎక్కువ అవకాశం: {pct}%.",
  "No rain expected in the next 24 hours.": "తర్వాత 24 గంటల్లో వర్షం ఉండదు.",
  "The map colours every area by {layer}. Tap any spot on the map to see its exact numbers.":
    "మ్యాప్‌లో ప్రతి ప్రాంతం {layer} ఆధారంగా రంగులు చూపుతుంది. ఖచ్చితమైన సంఖ్యల కోసం మ్యాప్‌లో ఎక్కైనా నొక్కండి.",
  "Open the Layers menu and pick Temperature or Rainfall to colour the map. Tap any spot for detailed weather.":
    "లేయర్ల మెనూ నుండి ఉష్ణోగ్రత లేదా వర్షం ఎంచుకుని మ్యాప్‌ను రంగులలో చూడండి. వివరమైన వాతావరణం కోసం ఎక్కైనా నొక్కండి.",
};

const uiHi: Record<string, string> = {
  // Groundwater
  "Groundwater Analytics": "भूजल विश्लेषण",
  "Recharge, extraction and stage-of-extraction across assessment units.":
    "आकलन इकाइयों में पुनर्भरण, निष्कर्षण और निष्कर्षण चरण।",
  Filters: "फ़िल्टर",
  "Assessment Year": "आकलन वर्ष",
  "All categories": "सभी श्रेणियां",
  "Assessment Units": "आकलन इकाइयां",
  "Units in scope": "दायरे में इकाइयां",
  "Recharge ({unit})": "पुनर्भरण ({unit})",
  "Total annual recharge": "कुल वार्षिक पुनर्भरण",
  "Extraction ({unit})": "निष्कर्षण ({unit})",
  "Total annual extraction": "कुल वार्षिक निष्कर्षण",
  "Avg Stage of Extraction": "औसत निष्कर्षण चरण",
  "Demand vs availability": "मांग बनाम उपलब्धता",
  "Category distribution": "श्रेणी वितरण",
  "Assessment units by stage-of-extraction category.":
    "निष्कर्षण चरण श्रेणी के अनुसार आकलन इकाइयाँ।",
  "No data for the current filters.": "मौजूदा फ़िल्टर के लिए डेटा नहीं।",
  "Recharge by year": "वर्षवार पुनर्भरण",
  "Extraction by year": "वर्षवार निष्कर्षण",
  "Total annual recharge in {unit}.": "{unit} में कुल वार्षिक पुनर्भरण।",
  "Total annual extraction in {unit}.": "{unit} में कुल वार्षिक निष्कर्षण।",
  "Assessment records": "आकलन रिकॉर्ड",
  "Detailed stage-of-extraction data.": "विस्तृत निष्कर्षण चरण डेटा।",
  "Showing 25 of {count} records.": "{count} रिकॉर्ड में से 25 दिखाए जा रहे हैं।",
  "No assessment records for the current filters.":
    "मौजूदा फ़िल्टर के लिए कोई आकलन रिकॉर्ड नहीं।",
  "Village / Unit": "गाँव / इकाई",
  "SoE %": "निष्कर्षण %",
  Reset: "रीसेट",
  "Loading groundwater data…": "भूजल डेटा लोड हो रहा है…",
  "Failed to load groundwater data.": "भूजल डेटा लोड करने में विफल।",

  // Forecast (Phase 19)
  Forecast: "पूर्वानुमान",
  "Linear trend": "रैखिक प्रवृत्ति",
  "Moving average": "चल औसत",
  "Exponential smoothing": "घातांकीय स्मूथिंग",
  "ARIMA(1,1,0)": "ARIMA(1,1,0)",
  "Holt's linear trend": "होल्ट की रैखिक प्रवृत्ति",
  "Auto (best validated)": "ऑटो (सर्वश्रेष्ठ सत्यापित)",
  "Ensemble (weighted blend)": "एन्सेम्बल (भारित मिश्रण)",
  "Deep learning — LSTM": "डीप लर्निंग — LSTM",
  "Deep learning — Transformer": "डीप लर्निंग — ट्रांसफॉर्मर",
  "Deep learning (best available)": "डीप लर्निंग (सर्वश्रेष्ठ उपलब्ध)",
  "River basin": "नदी बेसिन",
  "No basin (state/district/village)": "कोई बेसिन नहीं (राज्य/जिला/गाँव)",
  districts: "जिले",
  "Confidence band": "विश्वास बैंड",
  "Normal (95%)": "सामान्य (95%)",
  "Bootstrap fan (5–95%)": "बूटस्ट्रैप फैन (5–95%)",
  "Transfer learning — pre-train on the containing state/basin, then fine-tune this scope":
    "ट्रांसफर लर्निंग — संबंधित राज्य/बेसिन पर पूर्व-प्रशिक्षण, फिर इस दायरे को फाइन-ट्यून करें",
  "Deep-learning models need the optional torch dependency. Without it the forecast falls back to the best statistical model. Install with: pip install -r requirements-ml.txt":
    "डीप-लर्निंग मॉडल को वैकल्पिक torch निर्भरता की आवश्यकता है। इसके बिना पूर्वानुमान सर्वश्रेष्ठ सांख्यिकीय मॉडल पर वापस चला जाता है। इंस्टॉल करें: pip install -r requirements-ml.txt",
  "Deep learning ready": "डीप लर्निंग तैयार",
  "Deep-learning model": "डीप-लर्निंग मॉडल",
  "Pre-trained on": "पूर्व-प्रशिक्षित",
  "fine-tuned": "फाइन-ट्यून्ड",
  epochs: "एपोक",
  Backtest: "बैकटेस्ट",
  "Chronological train/test split — forecast the held-out years with each model and compare (lower is better).":
    "कालानुक्रमिक ट्रेन/टेस्ट विभाजन — प्रत्येक मॉडल से आरक्षित वर्षों का पूर्वानुमान लगाकर तुलना करें (कम बेहतर है)।",
  CRPS: "CRPS",
  Skill: "कौशल",
  "Point estimates with a bootstrap 5–95% confidence fan.":
    "बूटस्ट्रैप 5–95% विश्वास फैन के साथ बिंदु अनुमान।",
  "Forecast settings": "पूर्वानुमान सेटिंग्स",
  "Project groundwater metrics with time-series models — linear trend, moving average, exponential smoothing, ARIMA(1,1,0), Holt's trend, or auto-selection by holdout validation.":
    "समय-श्रृंखला मॉडल से भूजल मेट्रिक्स का पूर्वानुमान लगाएं — रैखिक प्रवृत्ति, चल औसत, घातांकीय स्मूथिंग, ARIMA(1,1,0), होल्ट प्रवृत्ति, या होल्डआउट सत्यापन द्वारा ऑटो-चयन।",
  "Model comparison": "मॉडल तुलना",
  "Out-of-sample walk-forward validation scores (lower is better). {n} forecasts tested.":
    "नमूने-से-बाहर वॉक-फॉरवर्ड सत्यापन स्कोर (कम बेहतर है)। {n} पूर्वानुमानों का परीक्षण किया गया।",
  Recommended: "अनुशंसित",
  RMSE: "RMSE",
  MAE: "MAE",
  MAPE: "MAPE",
  Tests: "परीक्षण",
  best: "सर्वश्रेष्ठ",
  "The best validated model for this scope is {method}. Switch the model dropdown to Auto to use it automatically.":
    "इस दायरे के लिए सर्वश्रेष्ठ सत्यापित मॉडल {method} है। इसे स्वचालित रूप से उपयोग करने के लिए मॉडल ड्रॉपडाउन को ऑटो पर स्विच करें।",
  "Statistical projection · not official data":
    "सांख्यिकीय प्रक्षेपण · आधिकारिक डेटा नहीं",
  Model: "मॉडल",
  "Horizon (years)": "क्षितिज (वर्ष)",
  "Projected {year}": "अनुमानित {year}",
  "End of forecast horizon": "पूर्वानुमान क्षितिज का अंत",
  Change: "परिवर्तन",
  "Over the forecast horizon": "पूर्वानुमान क्षितिज में",
  "Annual trend": "वार्षिक प्रवृत्ति",
  "per year": "प्रति वर्ष",
  "Loading forecast…": "पूर्वानुमान लोड हो रहा है…",
  "Failed to load the forecast.": "पूर्वानुमान लोड करने में विफल।",
  "Projected trend": "अनुमानित प्रवृत्ति",
  "{scope} · {metric} · {method}": "{scope} · {metric} · {method}",
  "Projected category": "अनुमानित श्रेणी",
  "Model explanation": "मॉडल स्पष्टीकरण",
  "At the projected trend, {scope} crosses the over-exploited threshold (100% stage of extraction) in about {count} year(s).":
    "अनुमानित प्रवृत्ति के अनुसार, {scope} लगभग {count} वर्ष(ों) में अत्यधिक दोहन सीमा (100% निष्कर्षण चरण) पार कर जाएगा।",
  "Forecast points": "पूर्वानुमान बिंदु",
  "Point estimates with a 95% confidence band.":
    "95% विश्वास बैंड के साथ बिंदु अनुमान।",
  Lower: "निम्न",
  Upper: "उच्च",
  "Observed value": "अवलोकित मान",
  rising: "बढ़ रहा",
  falling: "गिर रहा",
  stable: "स्थिर",
  safe: "सुरक्षित",
  "semi-critical": "अर्ध-संकट",
  critical: "संकट",
  "over-exploited": "अत्यधिक दोहन",

  // Knowledge base (Phase 20)
  "Knowledge base": "ज्ञानकोष",
  "Browse the groundwater reference documents used by the AI assistant. Search returns verbatim excerpts with their sources.":
    "AI सहायक द्वारा उपयोग किए जाने वाले भूजल संदर्भ दस्तावेज़ ब्राउज़ करें। खोज स्रोतों के साथ शब्दशः अंश लौटाती है।",
  "Search the knowledge base": "ज्ञानकोष खोजें",
  "Ask about recharge, stage of extraction, conservation…":
    "पुनर्भरण, निष्कर्षण चरण, संरक्षण के बारे में पूछें…",
  Search: "खोजें",
  Relevance: "प्रासंगिकता",
  "{count} result(s) for “{query}”": "“{query}” के लिए {count} परिणाम",
  "No matches": "कोई मिलान नहीं",
  "Nothing found. Try different wording.": "कुछ नहीं मिला। अलग शब्दों में प्रयास करें।",
  Documents: "दस्तावेज़",
  "{count} document(s), {chunks} chunk(s) indexed":
    "{count} दस्तावेज़, {chunks} खंड अनुक्रमित",
  "Add document": "दस्तावेज़ जोड़ें",
  "No documents yet.": "अभी तक कोई दस्तावेज़ नहीं।",
  chunks: "खंड",
  "Remove document": "दस्तावेज़ हटाएं",
  "Only admins can add or remove documents.": "दस्तावेज़ केवल व्यवस्थापक जोड़ या हटा सकते हैं।",
  "Document added to the knowledge base.": "दस्तावेज़ ज्ञानकोष में जोड़ा गया।",
  "Failed to upload the document.": "दस्तावेज़ अपलोड करने में विफल।",
  "Document removed.": "दस्तावेज़ हटा दिया गया।",
  "Failed to remove the document.": "दस्तावेज़ हटाने में विफल।",
  "Search failed. Check that the knowledge base is available.":
    "खोज विफल। जांचें कि ज्ञानकोष उपलब्ध है या नहीं।",
  "knowledge base": "ज्ञानकोष",
  RAG: "RAG",

  // Push notifications (Phase 20)
  "Push notifications": "पुश सूचनाएँ",
  "Get groundwater alerts on this device even when the app is closed (installable PWA).":
    "ऐप बंद होने पर भी इस डिवाइस पर भूजल अलर्ट प्राप्त करें (इंस्टॉलेबल PWA)।",
  "Not available": "उपलब्ध नहीं",
  "requires HTTPS and a supported browser": "HTTPS और समर्थित ब्राउज़र की आवश्यकता है",
  "This device is registered to receive alerts.": "यह डिवाइस अलर्ट प्राप्त करने के लिए पंजीकृत है।",
  "Allow alerts to be delivered to this device.": "इस डिवाइस पर अलर्ट भेजने की अनुमति दें।",
  "Web push is not enabled on the server.": "सर्वर पर वेब पुश सक्षम नहीं है।",
  "Notification permission was denied.": "सूचना अनुमति अस्वीकार कर दी गई।",
  "Push notifications enabled for this device.": "इस डिवाइस के लिए पुश सूचनाएँ सक्षम।",
  "Could not enable push notifications.": "पुश सूचनाएँ सक्षम नहीं की जा सकीं।",
  "Push notifications disabled.": "पुश सूचनाएँ अक्षम की गईं।",
  "Could not disable push notifications.": "पुश सूचनाएँ अक्षम नहीं की जा सकीं।",

  // Dashboard
  "Welcome, {name}": "स्वागत है, {name}",
  "Your multilingual AI assistant for Indian groundwater-resource information.":
    "भारतीय भूजल संसाधन जानकारी के लिए आपका बहुभाषी AI सहायक।",
  "{count} states monitored": "{count} राज्य निगरानी में",
  "Total Recharge ({unit})": "कुल पुनर्भरण ({unit})",
  "Total Extraction ({unit})": "कुल निष्कर्षण ({unit})",
  "Across selected scope": "चयनित दायरे में",
  "Assessment category distribution": "आकलन श्रेणी वितरण",
  "Stage-of-extraction categories across assessment units (demo data).":
    "आकलन इकाइयों में निष्कर्षण चरण श्रेणियाँ (डेमो डेटा)।",
  "No data available.": "डेटा उपलब्ध नहीं है।",
  "Stage of extraction trend": "निष्कर्षण चरण की प्रवृत्ति",
  "Annual average across all assessment units (2017–2022).":
    "सभी आकलन इकाइयों में वार्षिक औसत (2017–2022)।",
  "Auto-generated insights": "स्वतः उत्पन्न अंतर्दृष्टि",
  "Computed from the latest assessment year.": "नवीनतम आकलन वर्ष से गणना की गई।",
  "No insights available.": "कोई अंतर्दृष्टि उपलब्ध नहीं।",
  "Explore groundwater data": "भूजल डेटा देखें",
  "Analytics, maps, reports and voice — across the demo states.":
    "डेमो राज्यों में विश्लेषण, मानचित्र, रिपोर्ट और वॉइस।",
  "{count} more": "{count} और",
  "GIS Map": "GIS मानचित्र",
  Analytics: "विश्लेषण",

  // History
  History: "इतिहास",
  "Past conversations, simulated voice calls and expert requests.":
    "पिछली बातचीत, सिम्युलेटेड वॉइस कॉल और विशेषज्ञ अनुरोध।",
  "Chat conversations": "चैट बातचीत",
  "Voice calls": "वॉइस कॉल्स",
  "Expert requests": "विशेषज्ञ अनुरोध",
  "No chat conversations yet.": "अभी कोई चैट बातचीत नहीं।",
  "No voice calls yet. Simulate one from the Voice page.":
    "अभी कोई वॉइस कॉल नहीं। वॉइस पेज से एक सिम्युलेट करें।",
  "Call #{id} · {direction} · {provider}": "कॉल #{id} · {direction} · {provider}",
  "{minutes} min": "{minutes} मिनट",
  "No expert requests yet.": "अभी कोई विशेषज्ञ अनुरोध नहीं।",
  "user {id}": "उपयोगकर्ता {id}",
  "no priority": "कोई प्राथमिकता नहीं",
  "Location: {location}": "स्थान: {location}",
  "Resolution: {resolution}": "समाधान: {resolution}",
  "Loading history…": "इतिहास लोड हो रहा है…",
  inbound: "इनबाउंड",

  // Reports
  "Generate and export groundwater reports (CSV / PDF) from the demo dataset.":
    "डेमो डेटासेट से भूजल रिपोर्ट (CSV / PDF) बनाएं और निर्यात करें।",
  "Assessment unit detail": "आकलन इकाई विवरण",
  "{count} records · all metrics": "{count} रिकॉर्ड · सभी मेट्रिक्स",
  "all metrics": "सभी मेट्रिक्स",
  "{type} only": "केवल {type}",
  "both demo states": "दोनों डेमो राज्य",
  "Choose a scope and click Generate to preview a report.":
    "एक दायरा चुनें और रिपोर्ट देखने के लिए Generate पर क्लिक करें।",
  "Failed to generate the report.": "रिपोर्ट बनाने में विफल।",
  Unit: "इकाई",

  // Voice
  "Simulate an inbound IVR call to the assistant. Run the Twilio provider to go live.":
    "सहायक को इनबाउंड IVR कॉल सिम्युलेट करें। लाइव होने के लिए Twilio प्रदाता चलाएं।",
  "Simulate a call": "कॉल सिम्युलेट करें",
  "Demo data — no real phone call is placed.": "डेमो डेटा — कोई वास्तविक फ़ोन कॉल नहीं।",
  "Phone number": "फ़ोन नंबर",
  "e.g. 1800 123 456": "जैसे 1800 123 456",
  Script: "स्क्रिप्ट",
  "Custom transcript (one line per utterance)": "कस्टम ट्रांसक्रिप्ट (हर वाक्य के लिए एक पंक्ति)",
  "Simulate call": "कॉल सिम्युलेट करें",
  "Recent calls ({count})": "हाल की कॉल्स ({count})",
  "No calls yet — simulate one above.": "अभी कोई कॉल नहीं — ऊपर एक सिम्युलेट करें।",
  "Call #{id} · {direction}": "कॉल #{id} · {direction}",
  "Failed to simulate the call.": "कॉल सिम्युलेट करने में विफल।",

  // Notifications
  Notifications: "सूचनाएँ",
  "Alerts when groundwater metrics cross thresholds, plus your alert rules.":
    "जब भूजल मेट्रिक्स सीमा पार करते हैं तो अलर्ट, साथ ही आपके अलर्ट नियम।",
  "Run alert check": "अलर्ट जाँच चलाएं",
  "Recent notifications ({unread} unread)": "हाल की सूचनाएँ ({unread} अपठित)",
  "Mark all read": "सभी पढ़ी हुई चिह्नित करें",
  "No notifications yet. Create an alert rule below to be notified when a metric crosses a threshold.":
    "अभी कोई सूचना नहीं। जब कोई मेट्रिक सीमा पार करे तो सूचित होने के लिए नीचे अलर्ट नियम बनाएं।",
  "Create alert rule": "अलर्ट नियम बनाएं",
  "Evaluated against assessment data; a notification is created whenever a unit matches.":
    "आकलन डेटा के आधार पर मूल्यांकन; जब कोई इकाई मेल खाती है तो सूचना बनाई जाती है।",
  "Rule name": "नियम का नाम",
  Threshold: "सीमा",
  "Add rule": "नियम जोड़ें",
  "State (optional)": "राज्य (वैकल्पिक)",
  "District (optional)": "जिला (वैकल्पिक)",
  "Village (optional)": "गाँव (वैकल्पिक)",
  "Your alert rules ({count})": "आपके अलर्ट नियम ({count})",
  Name: "नाम",
  Condition: "शर्त",
  Scope: "दायरा",
  Status: "स्थिति",
  "Last triggered": "अंतिम ट्रिगर",
  Actions: "क्रियाएँ",
  Enabled: "सक्षम",
  Disabled: "अक्षम",
  Enable: "सक्षम करें",
  Disable: "अक्षम करें",
  never: "कभी नहीं",
  "No alert rules yet. Create one above.": "अभी कोई अलर्ट नियम नहीं। ऊपर एक बनाएं।",
  "Alert rule created.": "अलर्ट नियम बनाया गया।",
  "Could not create alert rule.": "अलर्ट नियम नहीं बना सके।",
  "Could not update rule.": "नियम अपडेट नहीं कर सके।",
  "Could not delete rule.": "नियम हटा नहीं सके।",
  "{count} alert{s} triggered.": "{count} अलर्ट ट्रिगर हुए।",
  "Could not run alert check.": "अलर्ट जाँच नहीं चला सके।",
  "> (greater than)": "> (से अधिक)",
  "≥ (greater or equal)": "≥ (से अधिक या बराबर)",
  "< (less than)": "< (से कम)",
  "≤ (less or equal)": "≤ (से कम या बराबर)",
  "Extractable resource": "निकालने योग्य संसाधन",

  // Admin
  Administration: "प्रशासन",
  "Users, audit trail and dataset registry.": "उपयोगकर्ता, ऑडिट ट्रेल और डेटासेट रजिस्ट्री।",
  "Failed to load admin data (admin role required).":
    "एडमिन डेटा लोड करने में विफल (एडमिन भूमिका आवश्यक)।",
  "Create user": "उपयोगकर्ता बनाएं",
  "Full name": "पूरा नाम",
  Email: "ईमेल",
  Password: "पासवर्ड",
  Create: "बनाएँ",
  "Import dataset (CSV / XLSX)": "डेटासेट आयात करें (CSV / XLSX)",
  "Upload assessment data (state, district, assessment_unit, year, recharge, extraction, stage, category). Imported rows are tagged as real data, not demo.":
    "आकलन डेटा अपलोड करें (राज्य, जिला, आकलन इकाई, वर्ष, पुनर्भरण, निष्कर्षण, चरण, श्रेणी)। आयात की गई पंक्तियाँ डेमो नहीं, वास्तविक डेटा के रूप में चिह्नित होती हैं।",
  "Dataset name": "डेटासेट नाम",
  "Source (e.g. CGWB, State dept.)": "स्रोत (जैसे CGWB, राज्य विभाग)",
  Import: "आयात",
  Template: "टेम्पलेट",
  "Failed to create user.": "उपयोगकर्ता बनाने में विफल।",
  "Failed to update user.": "उपयोगकर्ता अपडेट करने में विफल।",
  "Failed to update role.": "भूमिका अपडेट करने में विफल।",
  "Users ({count})": "उपयोगकर्ता ({count})",
  Role: "भूमिका",
  "Last login": "अंतिम लॉगिन",
  Active: "सक्रिय",
  Datasets: "डेटासेट",
  Source: "स्रोत",
  Version: "संस्करण",
  Level: "स्तर",
  "Semantic RAG": "सिमेंटिक RAG",
  "Hybrid retrieval combines BM25 keyword matching with embedding-based semantic search. Re-embedding recomputes vectors for all knowledge chunks.":
    "हाइब्रिड रिट्रीवल BM25 कीवर्ड मिलान को एम्बेडिंग-आधारित सिमेंटिक खोज के साथ जोड़ता है। री-एम्बेडिंग सभी नॉलेज चंक्स के लिए वेक्टर दोबारा गणना करता है।",
  Available: "उपलब्ध",
  Unavailable: "अनुपलब्ध",
  "{indexed} / {chunks} chunks indexed": "{indexed} / {chunks} चंक्स अनुक्रमित",
  "mode: {mode}": "मोड: {mode}",
  "model: {model}": "मॉडल: {model}",
  "Re-embed": "री-एम्बेड",
  "RAG status unavailable.": "RAG स्थिति अनुपलब्ध।",
  "Audit log": "ऑडिट लॉग",
  Time: "समय",
  Action: "क्रिया",
  Resource: "संसाधन",
  "No audit events yet.": "अभी कोई ऑडिट घटना नहीं।",
  "Loading admin panel…": "एडमिन पैनल लोड हो रहा है…",
  "Could not download the import template.": "आयात टेम्पलेट डाउनलोड नहीं कर सके।",
  "Dataset imported successfully.": "डेटासेट सफलतापूर्वक आयात हुआ।",
  "Import failed. See the message below.": "आयात विफल। नीचे संदेश देखें।",
  "Failed to import dataset.": "डेटासेट आयात करने में विफल।",
  "{rows} row(s) imported ({parsed} parsed). {states} state(s), {districts} district(s), {units} unit(s) created.":
    "{rows} पंक्ति(याँ) आयात हुईं ({parsed} पार्स की गईं)। {states} राज्य, {districts} जिला, {units} इकाई बनाई गईं।",
  "{alerts} alert(s) triggered.": "{alerts} अलर्ट ट्रिगर हुए।",
  "Re-embedded {updated} knowledge chunks.": "{updated} नॉलेज चंक्स री-एम्बेड हुए।",
  "Could not re-index embeddings.": "एम्बेडिंग री-इंडेक्स नहीं कर सके।",

  // VoiceAdmin
  "Real telephone integration: Twilio / Exotel / Plivo transport with the same LangGraph AI brain as the web app.":
    "वास्तविक टेलीफोन एकीकरण: वेब ऐप के समान LangGraph AI दिमाग के साथ Twilio / Exotel / Plivo ट्रांसपोर्ट।",
  "Test connection": "कनेक्शन परीक्षण",
  "Run end-to-end test": "एंड-टू-एंड परीक्षण चलाएं",
  "End-to-end test: {question} ({passed}/{total} passed)":
    "एंड-टू-एंड परीक्षण: {question} ({passed}/{total} पास)",
  "language={language} · intent={intent} · location={location}":
    "भाषा={language} · इरादा={intent} · स्थान={location}",
  "Response:": "प्रतिक्रिया:",
  "Total calls": "कुल कॉल्स",
  "Completed / Failed": "पूर्ण / विफल",
  "{count} failed": "{count} विफल",
  "Avg duration": "औसत अवधि",
  "Escalation rate": "एस्केलेशन दर",
  "Telephony configuration": "टेलीफोनी कॉन्फ़िगरेशन",
  "Provider selection and media streaming. API secrets are never shown.":
    "प्रदाता चयन और मीडिया स्ट्रीमिंग। API रहस्य कभी नहीं दिखाए जाते।",
  Provider: "प्रदाता",
  "STT / TTS": "STT / TTS",
  "Media stream WebSocket": "मीडिया स्ट्रीम WebSocket",
  "Set VOICE_PUBLIC_URL to enable media streaming":
    "मीडिया स्ट्रीमिंग सक्षम करने के लिए VOICE_PUBLIC_URL सेट करें",
  "Call log ({count})": "कॉल लॉग ({count})",
  "Caller numbers are masked; languages and intents are captured from the AI.":
    "कॉलर नंबर छिपाए जाते हैं; भाषाएँ और इरादे AI से लिए जाते हैं।",
  "Call ID": "कॉल ID",
  Language: "भाषा",
  Intent: "इरादा",
  Duration: "अवधि",
  State: "स्थिति",
  Confidence: "विश्वास",
  Escalated: "एस्केलेटेड",
  Date: "दिनांक",
  Yes: "हाँ",
  'No calls yet. Run an end-to-end test or click "📞 Test Voice Assistant".':
    'अभी कोई कॉल नहीं। एंड-टू-एंड परीक्षण चलाएं या "📞 वॉइस असिस्टेंट परीक्षण" पर क्लिक करें।',
  "Transcript — call #{id}": "ट्रांसक्रिप्ट — कॉल #{id}",
  "Close transcript": "ट्रांसक्रिप्ट बंद करें",
  "No transcript recorded.": "कोई ट्रांसक्रिप्ट दर्ज नहीं।",
  "End-to-end voice test completed.": "एंड-टू-एंड वॉइस परीक्षण पूर्ण।",
  "Voice test failed.": "वॉइस परीक्षण विफल।",
  "Could not reach the connection test endpoint.": "कनेक्शन परीक्षण एंडपॉइंट तक नहीं पहुँच सके।",
  "Could not load transcript.": "ट्रांसक्रिप्ट लोड नहीं कर सके।",
  Greeting: "अभिवादन",
  Help: "सहायता",
  Terminology: "पारिभाषिक शब्द",
  Data: "डेटा",
  Map: "मानचित्र",
  Trend: "प्रवृत्ति",
  Prediction: "पूर्वानुमान",
  Explanation: "व्याख्या",
  Recommendations: "सिफारिशें",
  Recommendation: "सिफारिश",
  annual_extractable_resource: "वार्षिक निकालने योग्य संसाधन",
  assessment_units: "आकलन इकाइयाँ",
  top_districts_by_stage: "निष्कर्षण चरण के अनुसार शीर्ष जिले",
  confidence_band: "95% सीमा",
  Thanks: "धन्यवाद",
  Unclear: "अस्पष्ट",
  "What is the stage of extraction in Telangana?": "तेलंगाना में निष्कर्षण चरण क्या है?",
  "Recharge in Guntur district": "गुंटूर जिले में पुनर्भरण",
  "What is an aquifer?": "जलभृत क्या है?",
  "What can you do?": "आप क्या कर सकते हैं?",
  "Failed to load Google Maps.": "Google Maps लोड करने में विफल।",
  "unit.plural": "इकाइयाँ",
  "All villages": "सभी गाँव",
  "Demo data · {source}": "डेमो डेटा · {source}",
  "more": "और",
  "+{count} more": "{count} और",
  User: "उपयोगकर्ता",
  "user #{id}": "उपयोगकर्ता #{id}",
  "e.g. Why is stage of extraction rising in Yadadri despite monsoon recharge?":
    "जैसे मानसून पुनर्भरण के बावजूद यादाद्री में निष्कर्षण चरण क्यों बढ़ रहा है?",
  "Location (e.g. Yadadri Bhuvanagiri, Telangana)":
    "स्थान (जैसे यादाद्री भुवनगिरि, तेलंगाना)",
  "{count} records": "{count} रिकॉर्ड",
  "Failed to load map data.": "मानचित्र डेटा लोड करने में विफल।",
  "Full-India map of all states and union territories with the synthetic demo dataset.":
    "सिंथेटिक डेमो डेटासेट के साथ सभी राज्यों और केंद्र शासित प्रदेशों का पूरा भारत मानचित्र।",
  Legend: "लीजेंड",

  // Expert
  "Expert Desk": "विशेषज्ञ डेस्क",
  "Escalate complex groundwater questions to domain experts.":
    "जटिल भूजल प्रश्नों को विशेषज्ञों तक एस्केलेट करें।",
  "Escalate a question": "प्रश्न एस्केलेट करें",
  "Create a request when the assistant cannot answer conclusively.":
    "जब सहायक निश्चित उत्तर न दे सके तो अनुरोध बनाएं।",
  "Create request": "अनुरोध बनाएं",
  Requests: "अनुरोध",
  "Manage status, priority and resolutions.": "स्थिति, प्राथमिकता और समाधान प्रबंधित करें।",
  "Track your escalations.": "अपने एस्केलेशन देखें।",
  "All statuses": "सभी स्थितियाँ",
  "No requests {withStatus}.": "कोई अनुरोध नहीं {withStatus}।",
  "with status {status}": "{status} स्थिति के साथ",
  yet: "अभी तक",
  ID: "ID",
  Question: "प्रश्न",
  From: "से",
  Priority: "प्राथमिकता",
  "Resolved {date}": "{date} को हल किया गया",
  Resolve: "हल करें",
  "Failed to load expert requests.": "विशेषज्ञ अनुरोध लोड करने में विफल।",
  "Failed to create the request.": "अनुरोध बनाने में विफल।",
  "Update failed — requires expert or admin role.":
    "अपडेट विफल — विशेषज्ञ या एडमिन भूमिका आवश्यक।",
  "Addressed by expert desk.": "विशेषज्ञ डेस्क द्वारा संबोधित।",

  // Landing
  "Sign in": "साइन इन",
  "Get started": "शुरू करें",
  "Indian Groundwater Resource Estimation System": "भारतीय भूजल संसाधन आकलन प्रणाली",
  "AI-Powered Groundwater Intelligence": "AI-संचालित भूजल खुफिया",
  "Ask questions about India's groundwater resources using text or voice — in English, Telugu or Hindi.":
    "टेक्स्ट या वॉइस से भारत के भूजल संसाधनों के बारे में पूछें — अंग्रेज़ी, तेलुगु या हिंदी में।",
  "Start Asking": "पूछना शुरू करें",
  "Explore Groundwater": "भूजल देखें",
  "Try Voice Assistant": "वॉइस असिस्टेंट आज़माएं",
  Example: "उदाहरण",
  "Example (Telugu)": "उदाहरण (तेलुगु)",
  "Example (Hindi)": "उदाहरण (हिंदी)",
  "How it works": "यह कैसे काम करता है",
  "Built for groundwater research": "भूजल अनुसंधान के लिए बनाया गया",
  "An assistant you can trust with data": "डेटा पर भरोसा करने योग्य सहायक",
  "IN-GRES AI never fabricates official groundwater numbers. Demo and synthetic datasets are always clearly labelled, sources and years are shown, and uncertain questions are escalated to human groundwater experts.":
    "IN-GRES AI आधिकारिक भूजल आँकड़े कभी नहीं बनाता। डेमो और सिंथेटिक डेटासेट हमेशा स्पष्ट रूप से लेबल होते हैं, स्रोत और वर्ष दिखाए जाते हैं, और अनिश्चित प्रश्न मानव भूजल विशेषज्ञों तक एस्केलेट होते हैं।",
  "Data trust · Source transparency · Expert escalation":
    "डेटा विश्वास · स्रोत पारदर्शिता · विशेषज्ञ एस्केलेशन",
  "Indian Groundwater Resource Estimation System — AI Virtual Assistant":
    "भारतीय भूजल संसाधन आकलन प्रणाली — AI वर्चुअल असिस्टेंट",
  "Phase 1 prototype · Demo data labelled": "चरण 1 प्रोटोटाइप · डेमो डेटा लेबल",
  "Multilingual AI": "बहुभाषी AI",
  "Ask in English, Telugu or Hindi — the assistant understands code-switching and answers back in your language.":
    "अंग्रेज़ी, तेलुगु या हिंदी में पूछें — सहायक कोड-स्विचिंग समझता है और आपकी भाषा में उत्तर देता है।",
  "Structured queries over recharge, extraction, availability and stage-of-extraction data with charts and trends.":
    "चार्ट और रुझानों के साथ पुनर्भरण, निष्कर्षण, उपलब्धता और निष्कर्षण चरण डेटा पर संरचित क्वेरी।",
  "Interactive GIS": "इंटरैक्टिव GIS",
  "Explore states, districts and assessment units on maps, coloured by assessment category.":
    "आकलन श्रेणी द्वारा रंगे मानचित्रों पर राज्यों, जिलों और आकलन इकाइयों को देखें।",
  "Trusted Knowledge": "विश्वसनीय ज्ञान",
  "Retrieval-augmented answers grounded in documented sources — no invented numbers.":
    "दस्तावेजित स्रोतों पर आधारित रिट्रीवल-ऑगमेंटेड उत्तर — कोई काल्पनिक संख्या नहीं।",
  "Voice Assistant": "वॉइस असिस्टेंट",
  "Talk to IN-GRES AI over the web or by phone, in multiple Indian languages.":
    "कई भारतीय भाषाओं में वेब या फ़ोन द्वारा IN-GRES AI से बात करें।",
  "Expert Assistance": "विशेषज्ञ सहायता",
  "When AI confidence is low, your question is escalated to a groundwater expert.":
    "जब AI विश्वास कम होता है, तो आपका प्रश्न भूजल विशेषज्ञ को एस्केलेट होता है।",
  Ask: "पूछें",
  "Type or speak a question about groundwater resources in India.":
    "भारत में भूजल संसाधनों के बारे में प्रश्न टाइप करें या बोलें।",
  Understand: "समझें",
  "IN-GRES AI detects language, intent, location and the metric you care about.":
    "IN-GRES AI भाषा, इरादा, स्थान और आपके लिए महत्वपूर्ण मेट्रिक का पता लगाता है।",
  Answer: "उत्तर",
  "Get a clear answer with values, units, year, sources, charts and maps.":
    "मान, इकाइयों, वर्ष, स्रोतों, चार्ट और मानचित्रों के साथ स्पष्ट उत्तर पाएं।",

  // Login / Register
  "Welcome back": "वापस स्वागत है",
  "Sign in to your groundwater assistant": "अपने भूजल सहायक में साइन इन करें",
  "Signing in…": "साइन इन हो रहा है…",
  "No account?": "खाता नहीं है?",
  "Create one": "एक बनाएं",
  "Create your account": "अपना खाता बनाएं",
  "Start asking about groundwater resources": "भूजल संसाधनों के बारे में पूछना शुरू करें",
  "Confirm password": "पासवर्ड की पुष्टि करें",
  "Creating account…": "खाता बन रहा है…",
  "Create account": "खाता बनाएं",
  "Already registered?": "पहले से पंजीकृत?",
  "Passwords do not match": "पासवर्ड मेल नहीं खाते",
  "Password must be at least 8 characters": "पासवर्ड कम से कम 8 अक्षरों का होना चाहिए",

  // Assistant
  "No conversations yet.": "अभी कोई बातचीत नहीं।",
  "Delete conversation": "बातचीत हटाएं",
  "Groundwater Assistant": "भूजल सहायक",
  "Ask about recharge, extraction, stage of extraction or assessment categories for any state, district or village in India — in English, Telugu or Hindi. Use the microphone to speak your question.":
    "भारत के किसी भी राज्य, जिले या गाँव के लिए पुनर्भरण, निष्कर्षण, निष्कर्षण चरण या आकलन श्रेणियों के बारे में पूछें — अंग्रेज़ी, तेलुगु या हिंदी में। अपना प्रश्न बोलने के लिए माइक्रोफ़ोन का उपयोग करें।",
  "Good morning": "सुप्रभात",
  "Good afternoon": "शुभ अपराह्न",
  "Good evening": "शुभ संध्या",
  "How can I help you with groundwater today?": "आज भूजल के बारे में मैं आपकी कैसे मदद कर सकता हूँ?",
  "New conversation": "नई बातचीत",
  "Search conversations": "बातचीत खोजें",
  "Or try": "या इन्हें आज़माएँ",
  "Recharge in a state": "किसी राज्य में पुनर्भरण",
  "Stage of extraction": "निष्कर्षण चरण",
  "Assessment categories": "आकलन श्रेणियाँ",
  "A specific village": "कोई विशिष्ट गाँव",
  "Compare across years": "वर्षों की तुलना करें",
  "Explain a term": "कोई शब्द समझाएँ",
  Copy: "कॉपी",
  Send: "भेजें",
  "Enter to send · Shift+Enter for a new line": "भेजने के लिए Enter · नई पंक्ति के लिए Shift+Enter",
  "Ask anything about India's groundwater": "भारत के भूजल के बारे में कुछ भी पूछें",
  "Answers come from a labelled synthetic demo dataset — never official IN-GRES/CGWB data.":
    "उत्तर लेबल वाले सिंथेटिक डेमो डेटासेट से आते हैं — कभी भी आधिकारिक IN-GRES/CGWB डेटा नहीं।",
  Explore: "खोजें",
  Workspace: "कार्यक्षेत्र",
  "Support & Admin": "सहायता और प्रशासन",
  Overview: "अवलोकन",
  "Voice Calls": "वॉयस कॉल्स",
  Groundwater: "भूजल",
  Reports: "रिपोर्ट्स",
  Voice: "वॉयस",
  Admin: "प्रशासन",
  "Sorry, I could not reach the assistant service. Please try again.":
    "क्षमा करें, सहायक सेवा तक नहीं पहुँच सके। कृपया पुनः प्रयास करें।",
  "Read aloud": "जोर से पढ़ें",
  "Escalated to expert desk": "विशेषज्ञ डेस्क को एस्केलेट किया गया",
  "Escalate to an expert": "विशेषज्ञ को एस्केलेट करें",
  "Stop listening": "सुनना बंद करें",
  "Speak your question": "अपना प्रश्न बोलें",
  "Speech recognition is not supported in this browser.":
    "इस ब्राउज़र में स्पीच पहचान समर्थित नहीं है।",
  "Microphone access requires a secure connection. Open the app via http://localhost:5173 or HTTPS.":
    "माइक्रोफ़ोन पहुंच के लिए सुरक्षित कनेक्शन आवश्यक है। ऐप http://localhost:5173 या HTTPS से खोलें।",
  "Microphone permission was denied. Allow the microphone in your browser settings and try again.":
    "माइक्रोफ़ोन अनुमति अस्वीकृत। ब्राउज़र सेटिंग में माइक्रोफ़ोन की अनुमति दें और पुनः प्रयास करें।",
  "No microphone was found. Connect a microphone and try again.":
    "कोई माइक्रोफ़ोन नहीं मिला। माइक्रोफ़ोन कनेक्ट करें और पुनः प्रयास करें।",
  "No speech was detected. Please speak clearly and try again.":
    "कोई वाणी नहीं मिली। कृपया स्पष्ट बोलें और पुनः प्रयास करें।",
  "The speech service could not be reached. Check your internet connection.":
    "स्पीच सेवा तक नहीं पहुँच सके। अपना इंटरनेट कनेक्शन जाँचें।",
  "Speech recognition is not allowed on this connection. Open the app via http://localhost:5173 or HTTPS.":
    "इस कनेक्शन पर स्पीच पहचान की अनुमति नहीं है। ऐप http://localhost:5173 या HTTPS से खोलें।",
  "Could not capture speech ({code}). Check the microphone permission.":
    "वाणी कैप्चर नहीं कर सके ({code})। माइक्रोफ़ोन अनुमति जाँचें।",

  // GIS
  "Map filters": "मानचित्र फ़िल्टर",
  View: "दृश्य",
  "All India": "पूरा भारत",
  "All India — groundwater overview": "पूरा भारत — भूजल अवलोकन",
  "36 states & UTs": "36 राज्य और केंद्र शासित प्रदेश",
  "Avg stage of extraction": "औसत निष्कर्षण चरण",
  "Over-exploited units": "अत्यधिक दोहन वाली इकाइयाँ",
  "Safe (<70%)": "सुरक्षित (<70%)",
  "Semi-critical (70–90%)": "अर्ध-संकट (70–90%)",
  "Critical (90–100%)": "संकट (90–100%)",
  "Over-exploited (>100%)": "अत्यधिक दोहन (>100%)",
  "No data in demo dataset": "डेमो डेटासेट में कोई डेटा नहीं",
  "Click a state or unit to inspect its value, stage and category.":
    "मान, चरण और श्रेणी देखने के लिए किसी राज्य या इकाई पर क्लिक करें।",
  "Reset map": "मानचित्र रीसेट करें",
  "Latest ({year})": "नवीनतम ({year})",
  "Low → high value (hm³)": "निम्न → उच्च मान (hm³)",
  Village: "गाँव",

  // Assessment report
  "Data report": "डेटा रिपोर्ट",
  "Assessment report": "आकलन रिपोर्ट",
  "Generate an AI-written report for a state, district and period, with status, trend, prediction, risk, map, graphs, recommendations and data sources, exportable as PDF or Excel.":
    "किसी राज्य, जिले और अवधि के लिए AI-लिखित रिपोर्ट तैयार करें — स्थिति, रुझान, पूर्वानुमान, जोखिम, मानचित्र, ग्राफ़, सिफ़ारिशें और डेटा स्रोतों के साथ, PDF या Excel में निर्यात करने योग्य।",
  "Period from": "अवधि से",
  "Period to": "अवधि तक",
  "Generate report": "रिपोर्ट बनाएँ",
  "Executive summary": "कार्यकारी सारांश",
  "Groundwater status": "भूजल स्थिति",
  "Historical trend": "ऐतिहासिक रुझान",
  "Risk analysis": "जोखिम विश्लेषण",
  Graphs: "ग्राफ़",
  "Data sources": "डेटा स्रोत",
  "Download PDF": "PDF डाउनलोड",
  "Download Excel": "Excel डाउनलोड",
  Current: "वर्तमान",
  Projected: "अनुमानित",
  "Generating assessment report…": "आकलन रिपोर्ट तैयार हो रही है…",
  "No report yet. Choose a scope and period, then click Generate report.":
    "अभी कोई रिपोर्ट नहीं। परिधि और अवधि चुनें, फिर Generate report पर क्लिक करें।",
  "Failed to generate the assessment report.": "आकलन रिपोर्ट तैयार करने में विफल।",
  "latest data {year}": "नवीनतम डेटा {year}",
  "Stage of extraction, {from}–{latest}": "निष्कर्षण चरण, {from}–{latest}",
  "to {year}": "{year} तक",
  "status {year}": "स्थिति {year}",

  // GIS layers & click-to-analyze
  Layers: "परतें",
  "Groundwater Level": "भूजल स्तर",
  "Critical Areas": "संकटग्रस्त क्षेत्र",
  "Monitoring Stations": "निगरानी केंद्र",
  "Monitoring station": "निगरानी केंद्र",
  "Click the map to analyze any location.":
    "किसी भी स्थान का विश्लेषण करने के लिए मानचित्र पर क्लिक करें।",
  "Analyzing location…": "स्थान का विश्लेषण हो रहा है…",
  "No groundwater data near this location.":
    "इस स्थान के पास भूजल डेटा नहीं है।",
  "Could not analyze this location.": "इस स्थान का विश्लेषण नहीं कर सके।",
  Stable: "स्थिर",
  "m/year": "मी/वर्ष",
  "AI Prediction": "AI पूर्वानुमान",
  Risk: "जोखिम",
  Shallow: "उथला",
  Deep: "गहरा",
  "derived from stage of extraction (demo)":
    "निष्कर्षण चरण से व्युत्पन्न (डेमो)",
  "Predicted category": "अनुमानित श्रेणी",
  Heatmap: "हीटमैप",

  // Map components
  "State / UT": "राज्य / केंद्र शासित प्रदेश",
  "No assessment data in demo dataset": "डेमो डेटासेट में कोई आकलन डेटा नहीं",
  "unit": "इकाई",
  "Avg stage: {stage}% · {category}": "औसत चरण: {stage}% · {category}",
  "Synthetic demo data": "सिंथेटिक डेमो डेटा",
  "Stage: {stage}% · {category}": "चरण: {stage}% · {category}",
  "No data": "कोई डेटा नहीं",
  "Set VITE_GOOGLE_MAPS_API_KEY to use Google Maps.":
    "Google Maps उपयोग करने के लिए VITE_GOOGLE_MAPS_API_KEY सेट करें।",
  "Loading Google Maps…": "Google Maps लोड हो रहा है…",
  "Failed to load the Google Maps script.": "Google Maps स्क्रिप्ट लोड करने में विफल।",

  Menu: "मेनू",

  // GIS time-lapse & comparison (Phase 20)
  To: "तक",
  Compare: "तुलना करें",
  "Compare years": "वर्षों की तुलना करें",
  "Play time-lapse": "टाइम-लैप्स चलाएँ",
  Pause: "विराम",
  "Units compared": "तुलना की गई इकाइयाँ",
  "Category changes": "श्रेणी परिवर्तन",
  "Avg change": "औसत परिवर्तन",
  Improved: "सुधार हुआ",
  Worsened: "खराब हुआ",
  "No change": "कोई बदलाव नहीं",
  "Change over time": "समय के साथ परिवर्तन",
  "Category: {a} → {b}": "श्रेणी: {a} → {b}",
  "Click a state or unit to see its change between the two years.":
    "दो वर्षों के बीच परिवर्तन देखने के लिए किसी राज्य या इकाई पर क्लिक करें।",

  // Assistant forecast & scenario (Phase 20)
  Scenario: "परिदृश्य",

  // Village-friendly visuals (Phase 26)
  "A quick picture of the groundwater near you.": "आपके आसपास के भूजल की एक झलक।",
  "Areas tracked": "निगरानी वाले क्षेत्र",
  "Water refilling the ground": "ज़मीन में जोड़ा जाने वाला पानी",
  "Water pumped out": "ज़मीन से निकाला गया पानी",
  "Each year": "हर साल",
  "How much water do we use?": "हम कितना पानी इस्तेमाल कर रहे हैं?",
  "Share of the fresh water that gets pumped up each year.":
    "हर साल निकाले जाने वाले ताज़े पानी का हिस्सा।",
  "Condition of the areas": "क्षेत्रों की स्थिति",
  "Every area is marked Safe, Needs Care or Critical.":
    "हर क्षेत्र को सुरक्षित, सावधानी या गंभीर चिह्नित किया गया है।",
  "{count} of {total} areas are using more water than is safe.":
    "{total} में से {count} क्षेत्र सुरक्षित मात्रा से अधिक पानी इस्तेमाल कर रहे हैं।",
  "The largest group is {category} ({count} areas).":
    "सबसे बड़ा समूह {category} ({count} क्षेत्र) है।",
  "Good news: all {total} areas are in the Safe group.":
    "अच्छी खबर: सभी {total} क्षेत्र सुरक्षित समूह में हैं।",
  "Water use over the years": "वर्षों में पानी का उपयोग",
  "Share of fresh water pumped up, year by year.":
    "हर साल निकाले गए ताज़े पानी का हिस्सा।",
  "Going up": "बढ़ रहा है",
  "Coming down": "घट रहा है",
  Steady: "स्थिर",
  "In {year}, people used about {pct}% of the fresh water.":
    "{year} में, लोगों ने लगभग {pct}% ताज़ा पानी इस्तेमाल किया।",
  "Use keeps increasing — water needs care.":
    "उपयोग बढ़ता जा रहा है — पानी का ध्यान रखें।",
  "Use is coming down — a good sign.":
    "उपयोग घट रहा है — यह अच्छा संकेत है।",
  "Use has stayed about the same.": "उपयोग लगभग पहले जैसा ही है।",
  "What your village should know": "आपके गाँव को क्या जानना चाहिए",
  "Short answers from the latest data.": "नवीनतम डेटा से छोटे उत्तर।",
  "Ask a question": "प्रश्न पूछें",
  "What does this mean?": "इसका क्या मतलब है?",
  "See the water situation for any state, district or village.":
    "किसी भी राज्य, जिले या गाँव की पानी की स्थिति देखें।",
  "Water that refills the ground each year, in {unit}.":
    "हर साल ज़मीन में जोड़ा जाने वाला पानी, {unit} में।",
  "In {from}, {valueA} went into the ground; in {to}, it was {valueB}.":
    "{from} में {valueA} पानी ज़मीन में गया; {to} में {valueB} गया।",
  "Water pumped out each year, in {unit}.": "हर साल निकाला जाने वाला पानी, {unit} में।",
  "In {from}, {valueA} was pumped out; in {to}, it was {valueB}.":
    "{from} में {valueA} पानी निकाला गया; {to} में {valueB} निकाला गया।",
  "Water usage level": "पानी उपयोग स्तर",
  level_safe: "सुरक्षित",
  level_attention: "सावधानी",
  level_critical: "गंभीर",
  level_unknown: "अज्ञात",
  level_safe_short: "सुरक्षित",
  level_attention_short: "सावधानी",
  level_critical_short: "गंभीर",

  // Weather map (Phase 26)
  Now: "अभी",
  Tomorrow: "कल",
  Today: "आज",
  High: "अधिकतम",
  Low: "न्यूनतम",
  Weather: "मौसम",
  "7-day forecast": "7 दिनों का पूर्वानुमान",
  "{pct}% rain": "{pct}% बारिश",
  rain_no: "बारिश नहीं",
  rain_light: "हल्की बारिश",
  rain_moderate: "मध्यम बारिश",
  rain_heavy: "भारी बारिश",
  rain_very_heavy: "बहुत भारी बारिश",
  "Rain is likely within the next 3 hours ({pct}% chance).":
    "अगले 3 घंटों में बारिश संभव है ({pct}% संभावना)।",
  "Heavy rainfall may occur today (about {mm} mm). Take care around streams and low areas.":
    "आज भारी बारिश हो सकती है (लगभग {mm} mm)। नालों और निचले इलाकों में सावधानी रखें।",
  "Very hot tomorrow — about {deg}°C. Stay hydrated.":
    "कल बहुत गर्मी — लगभग {deg}°C। पानी पीते रहें।",
  "Very hot today — about {deg}°C.": "आज बहुत गर्मी — लगभग {deg}°C।",
  "Strong winds expected today.": "आज तेज़ हवाएँ चल सकती हैं।",
  "When will it rain?": "बारिश कब होगी?",
  "Next 24 hours": "अगले 24 घंटे",
  "Chance of rain over the next 24 hours": "अगले 24 घंटों में बारिश की संभावना",
  "{word} expected today (about {mm} mm). Highest chance: {pct}%.":
    "आज {word} की संभावना (लगभग {mm} mm)। सबसे अधिक: {pct}%।",
  "No rain expected in the next 24 hours.": "अगले 24 घंटों में बारिश की संभावना नहीं है।",
  "The map colours every area by {layer}. Tap any spot on the map to see its exact numbers.":
    "नक्शा हर क्षेत्र को {layer} के आधार पर रंग दिखाता है। सटीक संख्याओं के लिए नक्शे पर कहीं भी टैप करें।",
  "Open the Layers menu and pick Temperature or Rainfall to colour the map. Tap any spot for detailed weather.":
    "लेयर्स मेन्यू से तापमान या बारिश चुनें और नक्शा रंगीन देखें। विस्तृत मौसम के लिए कहीं भी टैप करें।",
};

Object.assign(translations.te, uiTe);
Object.assign(translations.hi, uiHi);

interface LanguageContextValue {
  lang: Language;
  setLang: (lang: Language) => void;
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>(() => {
    const saved = localStorage.getItem("ingres_lang");
    return saved === "te" || saved === "hi" || saved === "en" ? saved : "en";
  });

  useEffect(() => {
    localStorage.setItem("ingres_lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (next: Language) => setLangState(next);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number | null | undefined>) => {
      let value = translations[lang][key] ?? translations.en[key] ?? key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          value = value.replaceAll(`{${k}}`, String(v ?? ""));
        }
      }
      return value;
    },
    [lang]
  );

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider");
  return ctx;
}