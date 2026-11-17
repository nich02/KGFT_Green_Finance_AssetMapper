import re
import pandas as pd
from collections import Counter

# Retains the original notebook's five activity themes and base keyword weights.
# This is an operational KGFT-informed mapping, not a full official rulebook.
GREEN_TAXONOMY = {
    "Renewable Energy": {
        "solar": 40, "photovoltaic": 40, "pv": 35, "wind": 35,
        "hydropower": 40, "geothermal": 40, "biogas": 35,
        "battery storage": 40, "bess": 40, "green hydrogen": 45, "smart grid": 30
    },
    "Clean Transportation": {
        "electric vehicle": 40, "ev": 35, "bev": 35, "charging station": 40,
        "charging infrastructure": 40, "public transit": 35, "light rail": 35,
        "zero-emission": 40, "e-bus": 40
    },
    "Green Buildings & Efficiency": {
        "leed": 45, "breeam": 45, "energy star": 40, "green building": 40,
        "heat pump": 35, "energy efficiency": 30, "retrofit": 30,
        "insulation": 25, "led": 25, "waste heat recovery": 35
    },
    "Water & Circular Economy": {
        "wastewater": 35, "water treatment": 35, "recycling": 30,
        "circular economy": 35, "composting": 30, "stormwater": 30,
        "desalination": 30, "material recovery": 30
    },
    "Sustainable Land & Climate": {
        "reforestation": 40, "afforestation": 40, "sustainable forestry": 35,
        "biodiversity": 35, "regenerative agriculture": 40, "decarbonization": 35,
        "net zero": 35, "carbon capture": 40, "climate resilience": 35
    }
}
EXCLUSION_KEYWORDS = [
    "coal", "crude oil", "fossil fuel", "natural gas", "diesel",
    "petrol", "gasoline", "lng", "oil exploration", "fracking"
]
PURPOSE_MULTIPLIER = 1.5

# Regex boundaries avoid accidental substring hits (e.g. 'ev' inside unrelated words).
def compile_pattern(keyword):
    return re.compile(r"(?<!\w)" + re.escape(keyword.lower()) + r"(?!\w)", re.IGNORECASE)

EXCLUSION_PATTERNS = [(kw, compile_pattern(kw)) for kw in EXCLUSION_KEYWORDS]
TAXONOMY_PATTERNS = [
    (theme, term, weight, compile_pattern(term))
    for theme, terms in GREEN_TAXONOMY.items()
    for term, weight in terms.items()
]

def screen_loan(row):
    desc = str(row.get("product_description", "") or "").lower()
    purpose = str(row.get("purpose", "") or "").lower()
    combined = f"{desc} {purpose}"
    exclusion_hits = [term for term, pattern in EXCLUSION_PATTERNS if pattern.search(combined)]
    if exclusion_hits:
        return {
            "screening_category": "Excluded / Potential exclusion",
            "taxonomy_theme": "Potential exclusion flag",
            "rule_score": 0,
            "matched_evidence": ", ".join(exclusion_hits),
            "screening_rationale": "Exclusion-related term detected. Confirm the exact activity and applicable KGFT exclusion provision; do not rely on keyword alone."
        }

    theme_scores = Counter()
    evidence = []
    for theme, term, base_weight, pattern in TAXONOMY_PATTERNS:
        in_desc = bool(pattern.search(desc))
        in_purpose = bool(pattern.search(purpose))
        if in_desc or in_purpose:
            score = base_weight * (PURPOSE_MULTIPLIER if in_purpose else 1.0)
            theme_scores[theme] += score
            source = "Purpose & description" if in_desc and in_purpose else ("Purpose" if in_purpose else "Description")
            evidence.append(f"{term} ({source}; weighted={score:.1f})")

    if not theme_scores:
        return {
            "screening_category": "Other / Insufficient evidence",
            "taxonomy_theme": "Unclassified",
            "rule_score": 0,
            "matched_evidence": "No configured positive terms matched",
            "screening_rationale": "No candidate activity identified from the supplied text. This is not proof that the loan is environmentally harmful."
        }

    primary_theme, raw_score = theme_scores.most_common(1)[0]
    score = min(round(raw_score), 100)
    if score >= 70:
        category = "Potential Green — Validation Required"
        rationale = "Strong keyword match. Verify the specific KGFT activity, eligibility and technical criteria, DNSH and minimum social safeguards."
    else:
        category = "Manual Assessment"
        rationale = "Partial or ambiguous keyword match. Obtain supporting documentation and reviewer assessment."
    return {
        "screening_category": category,
        "taxonomy_theme": primary_theme,
        "rule_score": score,
        "matched_evidence": "; ".join(evidence),
        "screening_rationale": rationale
    }

def classify_portfolio(frame):
    if frame.empty:
        result = frame.reset_index(drop=True).copy()
        result["screening_category"] = pd.Series(dtype="object")
        result["taxonomy_theme"] = pd.Series(dtype="object")
        result["rule_score"] = pd.Series(dtype="int64")
        result["matched_evidence"] = pd.Series(dtype="object")
        result["screening_rationale"] = pd.Series(dtype="object")
        return result

    outputs = frame.apply(lambda row: pd.Series(screen_loan(row)), axis=1)
    return pd.concat([frame.reset_index(drop=True), outputs.reset_index(drop=True)], axis=1)
