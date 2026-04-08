import copy
import json
import logging
import math
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from app import schemas
from app.family_communication_service import generate_family_communication_with_openai

logger = logging.getLogger(__name__)

# ============================================================
# Rule-Based Fallback Engine
# ============================================================

_KEYWORD_RULES: List[Tuple[str, float, str, str]] = [
    (r"sepsis|septic", 0.20, "Possible Sepsis Indicators", "Initiate Sepsis Bundle per SSC 2021 guidelines"),
    (r"leukocytosis|wbc.*(spike|high|elevat)", 0.12, "Leukocytosis Detected", "Monitor WBC trend q6h; consider blood cultures"),
    (r"hypotension|bp.*(drop|low|declin)", 0.15, "Hypotension Risk", "Assess fluid responsiveness; consider vasopressors if MAP <65"),
    (r"tachycardia|heart rate.*(high|elevat)", 0.10, "Tachycardia Noted", "Evaluate for hypovolemia, pain, fever, or cardiac arrhythmia"),
    (r"fever|febrile|temperature.*(high|elevat)", 0.08, "Febrile Episode", "Obtain blood cultures x2; assess for infection source"),
    (r"hypoxia|spo2.*(low|drop)|desaturat", 0.12, "Hypoxia / Desaturation", "Increase FiO2; consider ABG; evaluate for ARDS"),
    (r"lactate.*(high|elevat|spike|\b[3-9]\b)", 0.18, "Elevated Lactate", "Repeat lactate in 2-4h; assess tissue perfusion"),
    (r"oliguria|urine.*(low|decreas)|aki|kidney", 0.10, "Acute Kidney Injury Risk", "Monitor urine output; check creatinine trend; hold nephrotoxins"),
    (r"pneumonia|infiltrat|consolidat", 0.08, "Pulmonary Infiltrate", "Obtain chest imaging; consider empiric antibiotics"),
    (r"intubat|ventilat|ards", 0.12, "Respiratory Support", "Optimize ventilator settings; lung-protective strategy"),
    (r"cardiac|heart failure|chf|bnp", 0.10, "Cardiac Concern", "Obtain BNP/troponin; assess fluid balance"),
    (r"deteriorat|decompens|unstable", 0.12, "Clinical Deterioration", "Escalate care; consider ICU consult if not already admitted"),
    (r"infection|bacteremia|abscess", 0.10, "Active Infection", "Review antibiotic coverage; obtain cultures before changes"),
    (r"bleed|hemorrhag|anemia|hgb.*(low|drop)", 0.10, "Bleeding / Anemia Risk", "Check hemoglobin; type & screen; assess for active bleed"),
    (r"arrhythmia|afib|atrial fibrillat", 0.08, "Arrhythmia Detected", "Continuous telemetry; consider rate vs rhythm control"),
    (r"pain|discomfort|distress", 0.03, "Patient Distress", "Reassess pain management plan"),
    (r"stable|improving|better|resolv", -0.05, "Signs of Improvement", "Continue current management; monitor for relapse"),
]


_FAMILY_LANGUAGE_LABELS: Dict[str, str] = {
    "hi": "Hindi",
    "mr": "Marathi",
    "gu": "Gujarati",
    "ta": "Tamil",
}


_FAMILY_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "hi": {
        "intro": "पिछले 12 घंटों में ICU टीम आपके परिवार के सदस्य की बहुत करीब से निगरानी कर रही है।",
        "concerns": "टीम को मुख्य रूप से {concerns} को लेकर चिंता है।",
        "severity_high": "स्थिति गंभीर है और टीम लगातार उपचार, दोबारा जांच और बेडसाइड आकलन कर रही है।",
        "severity_medium": "कुछ चेतावनी संकेत हैं, इसलिए टीम इलाज और निगरानी को ध्यान से आगे बढ़ा रही है।",
        "severity_low": "स्थिति अभी अपेक्षाकृत स्थिर दिख रही है, फिर भी ICU टीम नियमित निगरानी जारी रखे हुए है।",
        "actions": "अभी फोकस {actions} पर है।",
        "outlier": "एक नई लैब रिपोर्ट पिछले पैटर्न से मेल नहीं खा रही थी, इसलिए टीम उसे संभावित लैब त्रुटि मानकर दोबारा जांच रही है।",
    },
    "mr": {
        "intro": "मागील 12 तासांपासून ICU टीम तुमच्या कुटुंबातील सदस्यावर बारकाईने लक्ष ठेवून आहे.",
        "concerns": "टीमची मुख्य चिंता {concerns} याबाबत आहे.",
        "severity_high": "स्थिती गंभीर आहे आणि टीम उपचार, पुन्हा तपासण्या आणि बेडसाइड मूल्यांकन सतत करत आहे.",
        "severity_medium": "काही इशारे दिसत आहेत, त्यामुळे टीम उपचार आणि निरीक्षण अधिक काळजीपूर्वक करत आहे.",
        "severity_low": "स्थिती सध्या तुलनेने स्थिर दिसत असली तरी ICU टीमची जवळून निगराणी सुरू आहे.",
        "actions": "सध्या मुख्य भर {actions} यावर आहे.",
        "outlier": "एक नवीन लॅब अहवाल मागील पॅटर्नशी जुळत नसल्यामुळे टीम त्याला संभाव्य लॅब त्रुटी मानून पुन्हा तपासत आहे.",
    },
    "gu": {
        "intro": "છેલ્લા 12 કલાકથી ICU ટીમ તમારા પરિવારના સભ્ય પર ખૂબ નજીકથી નજર રાખી રહી છે.",
        "concerns": "ટીમને મુખ્ય રીતે {concerns} અંગે ચિંતા છે.",
        "severity_high": "પરિસ્થિતિ ગંભીર છે અને ટીમ સતત સારવાર, ફરી તપાસ અને બેડસાઇડ મૂલ્યાંકન કરી રહી છે.",
        "severity_medium": "કેટલાક ચેતવણીના સંકેતો દેખાઈ રહ્યા છે, તેથી ટીમ સારવાર અને મોનિટરિંગ વધુ ધ્યાનથી કરી રહી છે.",
        "severity_low": "પરિસ્થિતિ હાલમાં સરખામણીએ સ્થિર દેખાઈ રહી છે, છતાં ICU ટીમ નજીકથી દેખરેખ રાખી રહી છે.",
        "actions": "હાલમાં મુખ્ય ધ્યાન {actions} પર છે.",
        "outlier": "એક નવી લેબ રિપોર્ટ પહેલાના પેટર્ન સાથે મેળ ખાતી ન હોવાથી ટીમ તેને સંભવિત લેબ ભૂલ માનીને ફરી તપાસી રહી છે.",
    },
    "ta": {
        "intro": "கடந்த 12 மணி நேரமாக ICU குழு உங்கள் குடும்ப உறுப்பினரை மிக நெருக்கமாக கவனித்து வருகிறது.",
        "concerns": "குழுவின் முக்கிய கவலை {concerns} குறித்து உள்ளது.",
        "severity_high": "நிலைமை கவலைக்கிடமாக இருப்பதால் சிகிச்சை, மறுபரிசோதனை மற்றும் படுக்கையருகிலான மதிப்பீடு தொடர்ந்து நடைபெற்று வருகிறது.",
        "severity_medium": "சில எச்சரிக்கை அறிகுறிகள் இருப்பதால் குழு சிகிச்சையையும் கண்காணிப்பையும் மிகவும் கவனமாக மேற்கொள்கிறது.",
        "severity_low": "நிலைமை தற்போது ஒப்பீட்டளவில் நிலையாக இருந்தாலும் ICU குழு தொடர்ந்து நெருக்கமான கண்காணிப்பில் வைத்திருக்கிறது.",
        "actions": "இப்போது முக்கிய கவனம் {actions} மீது உள்ளது.",
        "outlier": "ஒரு புதிய ஆய்வக முடிவு முந்தைய படிமுறையுடன் பொருந்தாமல் இருந்ததால் குழு அதை சாத்தியமான ஆய்வக பிழையாக கருதி மீண்டும் பரிசோதித்து வருகிறது.",
    },
}


_FAMILY_PHRASE_MAP: Dict[str, Dict[str, str]] = {
    "hi": {
        "Possible Sepsis Indicators": "संक्रमण या सेप्सिस के संकेत",
        "Leukocytosis Detected": "सफेद रक्त कोशिकाओं की संख्या बढ़ना",
        "Hypotension Risk": "लो ब्लड प्रेशर का जोखिम",
        "Tachycardia Noted": "दिल की धड़कन तेज होना",
        "Febrile Episode": "बुखार",
        "Hypoxia / Desaturation": "ऑक्सीजन स्तर कम होना",
        "Elevated Lactate": "लैक्टेट बढ़ना",
        "Acute Kidney Injury Risk": "किडनी पर असर का जोखिम",
        "Pulmonary Infiltrate": "फेफड़ों में संक्रमण या सूजन",
        "Respiratory Support": "सांस लेने में अतिरिक्त सहायता की जरूरत",
        "Cardiac Concern": "दिल से जुड़ी चिंता",
        "Clinical Deterioration": "क्लिनिकल स्थिति बिगड़ना",
        "Active Infection": "सक्रिय संक्रमण",
        "Bleeding / Anemia Risk": "खून की कमी या रक्तस्राव का जोखिम",
        "Arrhythmia Detected": "दिल की धड़कन की अनियमितता",
        "Patient Distress": "रोगी को असुविधा",
        "Signs of Improvement": "कुछ सुधार के संकेत",
        "Critical Lactate Level": "लैक्टेट का स्तर बहुत अधिक होना",
        "Mild Lactate Elevation": "लैक्टेट थोड़ा बढ़ना",
        "Tachycardia": "दिल की धड़कन तेज होना",
        "Monitor": "निगरानी",
        "Repeat": "दोबारा जांच",
        "Assess": "आकलन",
        "Consider": "विचार",
        "Review": "समीक्षा",
    },
    "mr": {
        "Possible Sepsis Indicators": "संसर्ग किंवा सेप्सिसची चिन्हे",
        "Leukocytosis Detected": "पांढऱ्या रक्तपेशी वाढणे",
        "Hypotension Risk": "कमी रक्तदाबाचा धोका",
        "Tachycardia Noted": "हृदयाचा ठोका वेगाने जाणे",
        "Febrile Episode": "ताप",
        "Hypoxia / Desaturation": "ऑक्सिजन कमी होणे",
        "Elevated Lactate": "लॅक्टेट वाढणे",
        "Acute Kidney Injury Risk": "मूत्रपिंडांवर ताण येण्याचा धोका",
        "Pulmonary Infiltrate": "फुफ्फुसात संसर्ग किंवा दाह",
        "Respiratory Support": "श्वासासाठी अतिरिक्त मदतीची गरज",
        "Cardiac Concern": "हृदयाशी संबंधित चिंता",
        "Clinical Deterioration": "क्लिनिकल स्थिती खालावणे",
        "Active Infection": "सक्रिय संसर्ग",
        "Bleeding / Anemia Risk": "रक्तस्राव किंवा रक्ताल्पतेचा धोका",
        "Arrhythmia Detected": "हृदयाची लय बिघडणे",
        "Patient Distress": "रुग्ण अस्वस्थ असणे",
        "Signs of Improvement": "सुधारण्याची काही चिन्हे",
        "Monitor": "निगराणी",
        "Repeat": "पुन्हा तपासणी",
        "Assess": "मूल्यांकन",
        "Consider": "विचार",
        "Review": "आढावा",
    },
    "gu": {
        "Possible Sepsis Indicators": "ચેપ અથવા સેપ્સિસના સંકેતો",
        "Leukocytosis Detected": "શ્વેત રક્તકણો વધવા",
        "Hypotension Risk": "લો બ્લડ પ્રેશરનો જોખમ",
        "Tachycardia Noted": "હૃદયની ધબકારા ઝડપી થવા",
        "Febrile Episode": "તાવ",
        "Hypoxia / Desaturation": "ઓક્સિજન ઓછું થવું",
        "Elevated Lactate": "લેક્ટેટ વધવું",
        "Acute Kidney Injury Risk": "કિડની પર અસર થવાનો જોખમ",
        "Pulmonary Infiltrate": "ફેફસાંમાં ચેપ અથવા સોજો",
        "Respiratory Support": "શ્વાસ માટે વધારાની મદદની જરૂર",
        "Cardiac Concern": "હૃદય સંબંધિત ચિંતા",
        "Clinical Deterioration": "ક્લિનિકલ સ્થિતિ બગડવી",
        "Active Infection": "સક્રિય ચેપ",
        "Bleeding / Anemia Risk": "રક્તસ્રાવ અથવા એનીમિયાનો જોખમ",
        "Arrhythmia Detected": "હૃદયની અનિયમિત ધબકારા",
        "Patient Distress": "દર્દીને અસ્વસ્થતા",
        "Signs of Improvement": "થોડું સુધારું જોવા મળવું",
        "Monitor": "નિરીક્ષણ",
        "Repeat": "ફરી તપાસ",
        "Assess": "મૂલ્યાંકન",
        "Consider": "વિચાર",
        "Review": "સમીક્ષા",
    },
    "ta": {
        "Possible Sepsis Indicators": "தொற்று அல்லது செப்ஸிஸ் அறிகுறிகள்",
        "Leukocytosis Detected": "வெள்ளை இரத்த அணுக்கள் அதிகரித்தல்",
        "Hypotension Risk": "குறைந்த இரத்த அழுத்த அபாயம்",
        "Tachycardia Noted": "இதய துடிப்பு வேகமாக இருப்பது",
        "Febrile Episode": "காய்ச்சல்",
        "Hypoxia / Desaturation": "ஆக்சிஜன் அளவு குறைதல்",
        "Elevated Lactate": "லாக்டேட் அதிகரித்தல்",
        "Acute Kidney Injury Risk": "சிறுநீரக பாதிப்பு அபாயம்",
        "Pulmonary Infiltrate": "நுரையீரலில் தொற்று அல்லது அழற்சி",
        "Respiratory Support": "சுவாசத்திற்கு கூடுதல் ஆதரவு தேவை",
        "Cardiac Concern": "இதய தொடர்பான கவலை",
        "Clinical Deterioration": "மருத்துவ நிலை மோசமாதல்",
        "Active Infection": "செயலில் உள்ள தொற்று",
        "Bleeding / Anemia Risk": "இரத்தச்சேதம் அல்லது ரத்தசோகை அபாயம்",
        "Arrhythmia Detected": "இதய துடிப்பு ஒழுங்கின்மை",
        "Patient Distress": "நோயாளிக்கு அசௌகரியம்",
        "Signs of Improvement": "சில முன்னேற்ற அறிகுறிகள்",
        "Monitor": "கண்காணிப்பு",
        "Repeat": "மீண்டும் பரிசோதனை",
        "Assess": "மதிப்பீடு",
        "Consider": "பரிசீலனை",
        "Review": "மறுபரிசீலனை",
    },
}


def _translate_family_text(text: str, language_code: str) -> str:
    translated = text
    replacements = sorted(
        _FAMILY_PHRASE_MAP.get(language_code, {}).items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for source, target in replacements:
        translated = re.sub(re.escape(source), target, translated, flags=re.IGNORECASE)
    return translated


def _build_family_translation(
    *,
    language_code: str,
    concerns_text: str,
    actions_text: str,
    severity_key: str,
    include_outlier: bool,
) -> schemas.FamilyTranslation:
    copy_block = _FAMILY_TRANSLATIONS[language_code]
    sections = [
        copy_block["intro"],
        copy_block["concerns"].format(
            concerns=_translate_family_text(concerns_text, language_code).lower()
        ),
        copy_block[severity_key],
        copy_block["actions"].format(
            actions=_translate_family_text(actions_text, language_code).lower()
        ),
    ]
    if include_outlier:
        sections.append(copy_block["outlier"])

    return schemas.FamilyTranslation(
        code=language_code,
        label=_FAMILY_LANGUAGE_LABELS[language_code],
        text=" ".join(sections),
    )


def _detect_probable_lab_error(data: schemas.PatientData) -> Optional[schemas.OutlierAlert]:
    grouped: Dict[str, List[schemas.LabResult]] = defaultdict(list)
    for lab in data.lab_results:
        grouped[lab.item_id.lower()].append(lab)

    best_candidate = None
    best_score = 0.0

    for label, labs in grouped.items():
        if len(labs) < 4:
            continue

        ordered = sorted(labs, key=lambda item: item.timestamp)
        prior = ordered[:-1]
        latest = ordered[-1]
        prior_values = [lab.value for lab in prior[-5:]]

        if len(prior_values) < 3:
            continue

        mean = sum(prior_values) / len(prior_values)
        variance = sum((value - mean) ** 2 for value in prior_values) / len(prior_values)
        std_dev = math.sqrt(variance)
        tolerance = max(abs(mean) * 0.18, 0.5)
        coefficient_of_variation = (std_dev / abs(mean)) if mean not in (0, 0.0) else 0.0
        deviation = abs(latest.value - mean)
        ratio = abs(latest.value / mean) if mean not in (0, 0.0) else float("inf")
        z_score = deviation / std_dev if std_dev > 0 else float("inf")

        if coefficient_of_variation > 0.15:
            continue

        if deviation <= max(3 * std_dev, tolerance):
            continue

        if 0.55 <= ratio <= 1.8:
            continue

        confidence = z_score if math.isfinite(z_score) else deviation
        if confidence > best_score:
            best_score = confidence
            best_candidate = schemas.OutlierAlert(
                isProbableLabError=True,
                affectedLab=ordered[-1].item_id,
                affectedValue=ordered[-1].value,
                message=(
                    f"The newest {ordered[-1].item_id} result ({ordered[-1].value:.1f}) sharply contradicts the prior trend "
                    f"of roughly {mean:.1f}. This looks like a probable mislabeled or erroneous lab result."
                ),
                actionRequired="Hold diagnosis revision and request a confirmed redraw before changing the care plan.",
            )

    return best_candidate


def _filter_outlier_from_data(
    data: schemas.PatientData,
    outlier_alert: Optional[schemas.OutlierAlert],
) -> schemas.PatientData:
    if not outlier_alert or not outlier_alert.isProbableLabError:
        return data

    filtered = copy.deepcopy(data)
    removed = False
    safe_labs = []
    for lab in filtered.lab_results:
        if (
            not removed
            and lab.item_id == outlier_alert.affectedLab
            and abs(lab.value - outlier_alert.affectedValue) < 1e-9
        ):
            removed = True
            continue
        safe_labs.append(lab)
    filtered.lab_results = safe_labs
    return filtered


def _generate_family_communication_fallback(
    report: schemas.AnalysisReport,
    outlier_alert: Optional[schemas.OutlierAlert],
) -> schemas.FamilyCommunication:
    concerns = report.detected_anomalies[:3] or ["important clinical changes"]
    actions = report.recommendations[:2] or ["close monitoring and treatment review"]
    concerns_text = ", ".join(concerns)
    actions_text = "; ".join(actions)

    if report.risk_score >= 0.75:
        severity_line = "The current condition is serious, and the team is watching for quick changes."
        severity_key = "severity_high"
    elif report.risk_score >= 0.5:
        severity_line = "There are warning signs, so the team is monitoring closely and adjusting care as needed."
        severity_key = "severity_medium"
    else:
        severity_line = "The condition appears relatively stable right now, but close ICU monitoring is still continuing."
        severity_key = "severity_low"

    include_outlier = bool(outlier_alert and outlier_alert.isProbableLabError)
    outlier_line = ""
    if include_outlier:
        outlier_line = (
            " One new lab result did not match the recent trend, so the team is treating it as a possible lab error "
            "and repeating the test before making any major diagnostic change."
        )

    english = (
        "Over the last 12 hours, the ICU team has been following your family member closely. "
        f"The main concerns right now are {concerns_text.lower()}. "
        f"{severity_line} "
        f"Current care is focused on {actions_text.lower()}.{outlier_line}"
    )

    translations = [
        _build_family_translation(
            language_code=language_code,
            concerns_text=concerns_text,
            actions_text=actions_text,
            severity_key=severity_key,
            include_outlier=include_outlier,
        )
        for language_code in _FAMILY_LANGUAGE_LABELS
    ]

    default_translation = translations[0]
    return schemas.FamilyCommunication(
        updatedWindow="Last 12 hours",
        english=english,
        regionalLanguage=default_translation.label,
        regional=default_translation.text,
        translations=translations,
    )

    concern = ", ".join(report.detected_anomalies[:3]) if report.detected_anomalies else "some important changes"

    if report.risk_score >= 0.75:
        english_tone = "The team is concerned and is watching your family member very closely."
        hindi_tone = "टीम को चिंता है और आपके परिवार के सदस्य पर बहुत करीबी निगरानी रखी जा रही है।"
    elif report.risk_score >= 0.5:
        english_tone = "The team is seeing warning signs and is monitoring things closely."
        hindi_tone = "टीम कुछ चेतावनी संकेत देख रही है और स्थिति पर करीबी निगरानी रख रही है।"
    else:
        english_tone = "The patient appears relatively stable, but the ICU team is continuing close checks."
        hindi_tone = "मरीज फिलहाल अपेक्षाकृत स्थिर लग रहे हैं, लेकिन आईसीयू टीम लगातार करीबी निगरानी कर रही है।"

    outlier_english = ""
    outlier_hindi = ""
    if outlier_alert and outlier_alert.isProbableLabError:
        outlier_english = (
            f" One new lab result looked inconsistent with the last few days, so the team is treating it as a possible lab mistake "
            f"and is repeating the test before making any major change in diagnosis."
        )
        outlier_hindi = (
            " एक नई लैब रिपोर्ट पिछले कई दिनों के पैटर्न से मेल नहीं खा रही थी, इसलिए टीम उसे संभावित लैब गलती मानकर दोबारा जाँच करा रही है "
            "और पुष्टि होने तक निदान में बड़ा बदलाव नहीं कर रही है।"
        )

    english = (
        f"Over the last 12 hours, the ICU team has been following your family member closely. "
        f"They have been seeing {concern.lower()}. {english_tone} Treatment, repeat checks, and bedside assessment are continuing.{outlier_english}"
    )
    regional = (
        f"पिछले 12 घंटों में आईसीयू टीम आपके परिवार के सदस्य की लगातार निगरानी कर रही है। "
        f"उन्हें {concern} जैसे संकेत दिखे हैं। {hindi_tone} इलाज, दोबारा जाँच और सीधे बेडसाइड मूल्यांकन जारी है।{outlier_hindi}"
    )

    return schemas.FamilyCommunication(
        updatedWindow="Last 12 hours",
        english=english,
        regionalLanguage="Hindi",
        regional=regional,
    )


def _generate_family_communication(
    report: schemas.AnalysisReport,
    outlier_alert: Optional[schemas.OutlierAlert],
) -> schemas.FamilyCommunication:
    try:
        return generate_family_communication_with_openai(report, outlier_alert)
    except Exception as exc:
        logger.info("OpenAI family communication fallback engaged: %s", exc)
        return _generate_family_communication_fallback(report, outlier_alert)


def _rule_based_analysis(
    data: schemas.PatientData,
    outlier_alert: Optional[schemas.OutlierAlert] = None,
) -> schemas.AnalysisReport:
    all_text = ""
    for note in data.clinical_notes:
        all_text += " " + note.text_content.lower()
    for lab in data.lab_results:
        all_text += f" {lab.item_id.lower()} {lab.value}"
    for vital in data.vital_signs:
        all_text += f" {vital.type.lower()} {vital.value}"

    base_risk = 0.10
    anomalies = []
    recommendations = []

    for pattern, weight, anomaly, rec in _KEYWORD_RULES:
        if re.search(pattern, all_text, re.IGNORECASE):
            base_risk += weight
            if weight > 0:
                anomalies.append(anomaly)
            recommendations.append(rec)

    lactate_vals = [l.value for l in data.lab_results if "lactate" in l.item_id.lower()]
    if lactate_vals:
        max_lac = max(lactate_vals)
        if max_lac > 4.0:
            base_risk += 0.15
            if "Elevated Lactate" not in anomalies:
                anomalies.append(f"Critical Lactate Level ({max_lac:.1f} mmol/L)")
                recommendations.append("Aggressive fluid resuscitation; repeat lactate in 2h")
        elif max_lac > 2.0:
            base_risk += 0.08
            if "Elevated Lactate" not in anomalies:
                anomalies.append(f"Mild Lactate Elevation ({max_lac:.1f} mmol/L)")

    hr_vals = [v.value for v in data.vital_signs if v.type == "Heart Rate"]
    if hr_vals:
        max_hr = max(hr_vals)
        if max_hr > 120:
            base_risk += 0.12
            if "Tachycardia Noted" not in anomalies:
                anomalies.append(f"Tachycardia (HR peak {max_hr:.0f} bpm)")
        elif max_hr > 100:
            base_risk += 0.06

    map_vals = [v.value for v in data.vital_signs if v.type == "MAP"]
    if map_vals:
        min_map = min(map_vals)
        if min_map < 65:
            base_risk += 0.12
            if "Hypotension Risk" not in anomalies:
                anomalies.append(f"Hypotension (MAP nadir {min_map:.0f} mmHg)")
                recommendations.append("Target MAP >=65 mmHg with fluids/vasopressors")

    wbc_labels = ["white blood cells", "wbc", "white blood cell count"]
    wbc_vals = [l.value for l in data.lab_results if l.item_id.lower() in wbc_labels]
    if wbc_vals:
        latest_wbc = wbc_vals[-1]
        if latest_wbc > 12:
            base_risk += 0.08
            if "Leukocytosis Detected" not in anomalies:
                anomalies.append(f"Leukocytosis (WBC {latest_wbc:.1f} K/uL)")
        elif latest_wbc < 4:
            base_risk += 0.10
            anomalies.append(f"Leukopenia (WBC {latest_wbc:.1f} K/uL)")

    final_risk = max(0.05, min(0.98, base_risk))

    if not anomalies:
        anomalies = ["No significant anomalies detected in available data"]
        recommendations = ["Continue routine ICU monitoring", "Reassess in 4-6 hours"]

    if outlier_alert and outlier_alert.isProbableLabError:
        anomalies.append(f"Probable Lab Error: {outlier_alert.affectedLab}")
        recommendations.insert(0, outlier_alert.actionRequired)
        recommendations.insert(0, outlier_alert.message)

    recommendations.append("Correlate with bedside clinical assessment")

    summary = f"Rule-based analysis identified {len(anomalies)} finding(s). "
    if outlier_alert and outlier_alert.isProbableLabError:
        summary += "A contradictory lab value was withheld from diagnosis revision pending redraw. "
    if final_risk >= 0.75:
        summary += "HIGH RISK - Immediate clinical attention recommended."
    elif final_risk >= 0.50:
        summary += "MODERATE RISK - Close monitoring and reassessment advised."
    elif final_risk >= 0.25:
        summary += "LOW-MODERATE RISK - Continue current management with periodic review."
    else:
        summary += "LOW RISK - Patient appears stable based on available data."

    anomalies = list(dict.fromkeys(anomalies))
    recommendations = list(dict.fromkeys(recommendations))

    report = schemas.AnalysisReport(
        risk_score=round(final_risk, 2),
        detected_anomalies=anomalies,
        recommendations=[summary] + recommendations,
        handover_summary=[
            f"Bullet 1: Overall trajectory is {'worsening' if final_risk >= 0.5 else 'relatively stable'} with key issues including {', '.join(anomalies[:2]).lower()}.",
            "Bullet 2: Continue current interventions and trend vitals/labs closely; no reliable automated treatment-response summary was available.",
            "Bullet 3: Watch for further deterioration, reassess bedside status, and repeat critical labs on schedule.",
        ],
        outlier_alert=outlier_alert,
    )
    report.family_communication = _generate_family_communication(report, outlier_alert)
    return report


_chief_agent = None


def _get_chief_agent():
    global _chief_agent
    if _chief_agent is None:
        try:
            from src.agents import run_chief_agent

            _chief_agent = run_chief_agent
        except Exception as e:
            logger.warning("AI agent pipeline not available: %s", str(e))
            _chief_agent = False
    return _chief_agent


def _merge_outlier_guardrails(
    report: schemas.AnalysisReport,
    outlier_alert: Optional[schemas.OutlierAlert],
) -> schemas.AnalysisReport:
    if not outlier_alert or not outlier_alert.isProbableLabError:
        report.family_communication = _generate_family_communication(report, None)
        return report

    anomalies = list(dict.fromkeys(report.detected_anomalies + [f"Probable Lab Error: {outlier_alert.affectedLab}"]))
    recommendations = list(
        dict.fromkeys(
            [
                f"Diagnosis held pending redraw. {outlier_alert.message}",
                outlier_alert.actionRequired,
                *report.recommendations,
            ]
        )
    )
    report.detected_anomalies = anomalies
    report.recommendations = recommendations
    report.outlier_alert = outlier_alert
    if report.handover_summary:
        report.handover_summary[2] = (
            f"Bullet 3: {outlier_alert.actionRequired} Continue bedside reassessment and do not change diagnosis on the anomalous value alone."
        )
    report.family_communication = _generate_family_communication(report, outlier_alert)
    return report


async def analyze_patient_data(data: schemas.PatientData) -> schemas.AnalysisReport:
    logger.info("Starting patient analysis...")

    outlier_alert = _detect_probable_lab_error(data)
    safe_data = _filter_outlier_from_data(data, outlier_alert)
    run_chief = _get_chief_agent()

    if not run_chief:
        logger.info("LLM not available - using rule-based engine")
        return _rule_based_analysis(safe_data, outlier_alert)

    try:
        notes_text = "\n".join([note.text_content for note in safe_data.clinical_notes])
        labs_text = "\n".join([f"{lab.timestamp}: {lab.item_id} - {lab.value}" for lab in safe_data.lab_results])
        wbc_labels = ["white blood cells", "wbc", "white blood cell count"]
        wbc_array = [
            float(lab.value) for lab in safe_data.lab_results if lab.item_id.lower() in wbc_labels
        ]

        ai_json_response = run_chief(notes_text, labs_text, wbc_array)
        report_dict = json.loads(ai_json_response)

        risk = report_dict.get("risk_score", None)
        if risk is not None:
            risk = float(risk)
            if risk > 1.0:
                risk = risk / 100.0
        else:
            risk = _rule_based_analysis(safe_data, outlier_alert).risk_score

        risk = max(0.05, min(0.98, risk))
        anomalies = report_dict.get("key_risks", []) or []
        timeline = report_dict.get("timeline_summary", "") or ""

        if not anomalies or not timeline:
            rule_report = _rule_based_analysis(safe_data, outlier_alert)
            if not anomalies:
                anomalies = rule_report.detected_anomalies
            if not timeline:
                timeline = rule_report.recommendations[0] if rule_report.recommendations else ""

        report = schemas.AnalysisReport(
            risk_score=round(risk, 2),
            detected_anomalies=anomalies,
            handover_summary=report_dict.get("handover_summary", []) or [],
            recommendations=[timeline] if timeline else ["Analysis complete"],
        )
        report = _merge_outlier_guardrails(report, outlier_alert)
        if report.family_communication is None:
            report.family_communication = _generate_family_communication(report, outlier_alert)
        if not report.handover_summary:
            report.handover_summary = _rule_based_analysis(safe_data, outlier_alert).handover_summary
        return report

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM output parse failed (%s) - falling back to rule-based engine", e)
        return _rule_based_analysis(safe_data, outlier_alert)
    except Exception as e:
        logger.warning("LLM call failed (%s) - falling back to rule-based engine", e)
        return _rule_based_analysis(safe_data, outlier_alert)
