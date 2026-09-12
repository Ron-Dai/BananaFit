"""English presentation overrides; source labels and original evidence stay unchanged."""

from .models import Question
from .specification import FieldDefinition, Specification

SECTION_LABELS = {
    "profile": "Basic background",
    "immediate_screen": "Current symptoms",
    "medical_history": "Medical history",
    "injury_history": "Injuries and surgery",
    "function": "Daily function",
    "asymmetry": "Left-right differences",
    "body_composition": "Body composition",
    "cardiovascular": "Heart rate and circulation",
    "respiratory": "Breathing and existing pulmonary measurements",
    "medication_and_exposure": "Medications, supplements, allergies, and exposures",
    "laboratory_reports": "Existing examination results",
    "reproductive_and_hormonal": "Reproductive and hormonal factors",
    "nutrition_recovery": "Nutrition and recovery",
    "psychosocial_environment": "Psychological and environmental factors",
    "activity_history": "Activity and training history",
    "goals_and_constraints": "Goals and practical constraints",
    "reports_and_update": "Reports and updates",
}

QUESTIONS = {
    "current_chest_discomfort": "Do you currently have new, significant, or unexplained chest pressure, tightness, or pain?",
    "severe_rest_dyspnea": "Are you currently having marked difficulty breathing even at rest?",
    "current_fainting_or_confusion": "Are you currently fainting, close to fainting, or newly confused?",
    "sudden_focal_neurology": "Have you recently developed sudden weakness or numbness on one side, trouble speaking, or a major vision change, even if it has improved?",
    "new_saddle_sensation_change": "Have you recently developed reduced sensation around the groin, anus, or area that rests on a saddle?",
    "new_bladder_bowel_control_change": "Have you recently developed difficulty urinating, loss of bladder sensation, or changed bowel or bladder control? Distinguish this from a stable, previously assessed condition.",
    "new_bilateral_leg_neurology": "Have you recently developed back pain with numbness or weakness in both legs, or rapidly worsening difficulty walking?",
    "major_trauma_or_rapid_pain": "Have you recently had a major injury, sudden severe pain, or rapidly worsening pain?",
    "current_fever_or_acute_illness": "Do you currently have fever, an acute infection, or significant general illness?",
    "age": "What is your current age in years?",
    "sex_for_reference": "If an applicable reference equation needs it, what relevant physiological sex information would you voluntarily like to provide?",
    "gender_pronouns": "What name or pronouns would you like us to use? This is optional and is not used as a physiological reference.",
    "height": "Would you like to share existing height measurements, including units, dates, and how they were measured?",
    "weight": "Would you like to share current or previous weight measurements, including units, dates, and devices?",
    "body_fat_percent": "Do you have an existing body-fat percentage measurement? It is fine if it has not been measured.",
    "ever_injury_or_surgery": "Have you ever had an injury, operation, immobilization, or loss of function, including events that have recovered?",
    "professional_restrictions": "Has a physician or rehabilitation professional given you any activity restrictions or allowed alternatives? Share the wording and source, or explicitly report none.",
    "conditions": "Which diagnosed or currently investigated health conditions would you like to report? Report each separately, or explicitly report none.",
    "symptoms": "Do you have current or recurring symptoms relevant to activity? Include timing and triggers, or explicitly report none.",
    "injuries": "Describe each injury or surgery separately, including timing, side, current function, recovery, and existing restrictions.",
    "medications": "Which prescription or nonprescription medications do you currently or recently use? Include names and existing exercise instructions, or explicitly report none.",
    "current_pain_regions": "Where do you currently have pain or discomfort? Select each relevant region, or explicitly select none.",
    "noticed_difference": "Have you or someone else noticed a left-right difference? This does not by itself establish a medical problem.",
    "progressive_wasting_or_weakness": "Has one side been becoming thinner, progressively weaker, or less able to perform activities?",
    "delayed_exacerbation": "After minor physical or mental activity, do you develop substantial, lasting whole-body worsening hours later or the next day, beyond ordinary local muscle soreness?",
    "delayed_exacerbation_details": "What activity triggers the worsening, how long is the delay, how long does it last, and what helps recovery?",
    "orthostatic_intolerance": "Does standing up repeatedly cause dizziness, palpitations, weakness, or near-fainting? Do not test this by pushing yourself to symptoms.",
    "pregnancy_status": "If relevant and you wish to share, are you pregnant, possibly pregnant, or having this checked?",
    "relevance": "Would you like to share reproductive or hormonal circumstances that may affect exercise?",
    "goals": "What would you like training to help you achieve? Select your goals; you may describe priorities separately.",
    "days_per_week": "How many days per week can you realistically train, from zero to seven?",
    "session_duration": "How many minutes can you allow per session, including preparation, warm-up, and rest?",
    "equipment": "What equipment and space can you use? Name items explicitly, such as none, a chair, a wall, or a stationary bike.",
    "time_preferences": "Which dates or times can you train? You may list weekday names or say that any day is available.",
    "preferences": "Which activities do you prefer or want to avoid? You may explicitly report no preferences.",
    "current_activities": "What activities do you currently do, how often, for how long, at what effort, and with what immediate or next-day response? You may explicitly report none.",
    "training_history": "What training and exercises are you currently familiar with? Distinguish current experience from distant past experience.",
    "exercise_adverse_history": "Have you had adverse reactions during or after exercise? Describe what happened and when, or explicitly report none.",
    "walking_tolerance": "From everyday experience, how long or far can you walk comfortably, and what makes you stop? No test is required.",
    "unmentioned_factors": "Is there anything else about your health, body, past experiences, or circumstances that could affect training?",
    "changes_since_last": "Have there been new symptoms, diagnoses, medications, injuries, or life changes since the last review?",
    "user_corrections": "Is there information you would like to correct, withdraw, or mark uncertain?",
    "pain_intensity": "If this is pain, how would you rate it from 0 to 10? This is not a diagnostic threshold.",
    "current": "Is this symptom still present now?",
    "onset_type": "Did this begin suddenly, gradually, from birth, or as a recurring issue?",
    "side": "Which side or area is affected?",
    "current_function": "What can you currently do, what cannot you do, and what causes discomfort?",
    "symptom_free_but_limited": "Even without pain, is there remaining weakness, stiffness, or reluctance to use the affected area?",
    "original_instruction": "What exactly did the professional say about restrictions or permitted activity? Preserve the original wording.",
    "diagnostic_status": "Was this confirmed by a clinician, still under evaluation, or your own suspicion or recollection?",
    "current_control": "What is the reported current control or activity status of this condition?",
    "resting_heart_rate": "Do you have existing resting heart-rate readings? Include resting position, date, device, and units; an all-day average is different.",
    "spirometry": "Would you like to share existing spirometry results and their dates, units, method, quality, and professional interpretation? No new test is required.",
    "sleep_hours": "Approximately how many hours do you sleep per day, and over what recent period?",
    "sleep_quality": "How have sleep onset, awakenings, daytime sleepiness, and recovery on waking been recently?",
    "fatigue_baseline": "How does everyday fatigue affect you, and how long has it been present?",
    "report_id": "System-generated report identifier.",
    "screen_time": "When were the current symptom answers explicitly checked?",
    "reviewed_at": "When did you last review this information?",
}

MATRIX_LABELS = {
    "cardiac_disease": "Coronary disease, heart attack, heart failure, cardiomyopathy, valve disease, or congenital heart disease",
    "arrhythmia": "Arrhythmia or fainting attributed to a heart condition",
    "blood_pressure_disorder": "High, low, or posture-related blood-pressure problems",
    "vascular_thrombotic": "Thrombosis, pulmonary embolism, or peripheral vascular disease",
    "pulmonary": "Asthma, chronic lung disease, lung surgery, or impaired lung function",
    "diabetes": "Diabetes or blood-glucose regulation problems",
    "endocrine": "Thyroid, adrenal, or other endocrine conditions",
    "renal": "Kidney disease, dialysis, or kidney transplant",
    "liver_gi": "Liver, digestive, or malabsorption conditions",
    "hematologic": "Anemia, bleeding disorders, or other blood conditions",
    "bone_health": "Osteoporosis, fractures, or stress injuries",
    "joint_soft_tissue": "Joint, tendon, ligament, or muscle conditions",
    "spinal": "Spine, disc, nerve-root, or spinal-cord conditions",
    "hypermobility_connective": "Joint hypermobility, recurring dislocation, or connective-tissue conditions",
    "stroke_brain": "Stroke, brain injury, or concussion",
    "neuromuscular": "Peripheral nerve, muscle, or motor-control conditions",
    "seizure": "Seizures or episodic loss of consciousness",
    "autonomic": "Autonomic problems, orthostatic intolerance, or diagnosed POTS",
    "fatigue_postinfectious": "ME/CFS, long COVID, or persistent post-infection symptoms",
    "immune_inflammatory": "Autoimmune, chronic inflammatory, or immunosuppressive conditions",
    "cancer": "Cancer and related treatment",
    "vision_hearing_vestibular": "Vision, hearing, or balance conditions affecting activity",
    "sleep_disorder": "Sleep apnea, insomnia, or other sleep conditions",
    "pelvic_abdominal": "Pelvic-floor, hernia, or abdominal conditions",
    "skin_wounds": "Chronic wounds, pressure sores, skin disease, or infection",
    "mental_eating": "Mental-health or eating-related conditions",
    "congenital_disability": "Congenital, developmental, limb, or long-term functional differences",
    "chest_discomfort": "Chest pain, pressure, or tightness",
    "breathlessness": "Breathlessness disproportionate to activity",
    "palpitations": "Palpitations or an irregular heartbeat sensation",
    "faintness": "Dizziness, fainting, or near-fainting",
    "cough_wheeze": "Coughing or wheezing",
    "unusual_fatigue": "Persistent unusual fatigue affecting daily life",
    "weakness_wasting": "Weakness, muscle thinning, or functional decline",
    "numbness_sensation": "Numbness, tingling, or sensation changes",
    "balance_coordination": "Balance, falls, or coordination problems",
    "pain_swelling": "Pain, swelling, stiffness, or joint instability",
    "headache_vision": "Activity-related headache, vision, or cognitive changes",
    "edema_vascular": "Swelling or limb color/temperature changes",
    "heat_cold": "Unusual heat or cold intolerance or sweating",
    "pelvic_bladder_bowel": "Pelvic, bladder, bowel, or abdominal symptoms",
    "delayed_systemic": "Delayed whole-body symptom exacerbation after activity",
    "walk": "Walking on level ground",
    "stairs_up": "Walking upstairs",
    "stairs_down": "Walking downstairs",
    "sit_stand": "Sitting down and rising from a chair",
    "floor_transfer": "Getting down to and up from the floor",
    "standing": "Standing and changing position",
    "bend_reach": "Bending or reaching for objects",
    "squat_daily": "Squatting in daily life",
    "overhead_reach": "Reaching overhead",
    "push_pull": "Pushing and pulling daily objects",
    "grip_carry": "Gripping, lifting, and carrying",
    "dress_reach_back": "Dressing, tying shoes, or reaching behind the back",
    "turn_head_trunk": "Turning the head or trunk",
    "single_limb_daily": "Single-leg support or stepping in daily life",
    "breathing_daily": "Maintaining comfortable breathing during daily activity",
    "device_transfer": "Using mobility aids or getting on and off equipment",
    "other": "Other relevant information",
}

OPTION_LABELS = {
    "none": "No difficulty",
    "mild": "Mild difficulty",
    "moderate": "Noticeable difficulty; independent",
    "severe": "Severe difficulty",
    "unable": "Unable",
    "assistance": "Requires assistance or equipment",
    "avoided": "Not attempted or avoided",
    "unknown": "Unknown",
    "not_applicable": "Not applicable",
    "clinician_confirmed": "Confirmed by a clinician",
    "historical_unverified": "Recalled historical diagnosis; unverified",
    "stable_as_reported": "Reported stable",
    "active_or_flare": "Active or flaring",
    "uncontrolled_as_reported": "Reported uncontrolled",
    "hypertrophy": "Build muscle",
    "fat_loss": "Reduce body fat",
    "cardio": "Improve aerobic tolerance",
    "health": "General health",
    "mobility": "Comfortable range of motion",
    "clinician_program": "Follow an existing professional program",
}


def english_name(identifier: str) -> str:
    """Humanize stable English DSL names for secondary optional field prompts."""
    return (
        identifier.replace("_", " ")
        .replace("hrv", "HRV")
        .replace("spo2", "SpO2")
        .replace("fev1", "FEV1")
        .replace("fvc", "FVC")
    )


def question(
    spec: Specification,
    path: str,
    field: FieldDefinition,
    reason: str = "Optional information relevant to your training.",
) -> Question:
    """Build deterministic English questions so a model cannot omit screening qualifiers."""
    text = QUESTIONS.get(
        field.id,
        f"Please share {english_name(field.id)} for this {english_name(path.split('.')[1])}. You may skip or say you do not know.",
    )
    parts = path.split(".")
    if len(parts) == 3 and spec.sections[parts[0]][parts[1]].type.startswith("matrix:"):
        label = MATRIX_LABELS.get(field.id, english_name(field.id))
        prefix = {
            "condition_screen": "Have you been diagnosed with or evaluated for",
            "symptom_screen": "Currently or repeatedly in the past 12 months, have you experienced",
            "activities": "From everyday experience, how difficult is",
        }[parts[1]]
        text = f"{prefix} {label.lower()}?"
    options = {}
    if field.type.startswith(("enum:", "multi:")):
        options = {
            key: OPTION_LABELS.get(key, english_name(key).capitalize())
            for key in spec.enums[field.type.split(":")[1]]
        }
    return Question(
        question_id=path,
        field_path=path,
        text=text,
        answer_type=field.type,
        unit=field.unit,
        options=options,
        reason=reason,
    )
