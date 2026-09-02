import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE_DIR, "knowledge_base.json")
OUT_PATH = os.path.join(BASE_DIR, "..", "frontend", "static", "data", "body_regions.json")


REGIONS = {
    "kidney_left":   {"cx": 422, "cy": 473, "label": "Left kidney", "view": "back"},
    "kidney_right":  {"cx": 333, "cy": 477, "label": "Right kidney", "view": "back"},
    "adrenal_left":  {"cx": 422, "cy": 440, "label": "Left adrenal gland", "view": "back"},
    "adrenal_right": {"cx": 333, "cy": 440, "label": "Right adrenal gland", "view": "back"},
    "head":        {"cx": 377, "cy": 42,  "label": "Head / Brain"},
    "neck":        {"cx": 384, "cy": 190, "label": "Neck / Thyroid"},
    "heart":       {"cx": 386, "cy": 330, "label": "Heart"},
    "left_lung":   {"cx": 458, "cy": 352, "label": "Left lung"},
    "right_lung":  {"cx": 310, "cy": 354, "label": "Right lung"},
    "liver":       {"cx": 380, "cy": 440, "label": "Liver"},
    "ribs_left":   {"cx": 470, "cy": 300, "label": "Left rib cage"},
    "ribs_right":  {"cx": 300, "cy": 300, "label": "Right rib cage"},
    "shoulder_left":  {"cx": 555, "cy": 255, "label": "Left shoulder"},
    "shoulder_right": {"cx": 215, "cy": 255, "label": "Right shoulder"},
    "breast_left":  {"cx": 455, "cy": 310, "label": "Left breast"},
    "breast_right": {"cx": 315, "cy": 310, "label": "Right breast"},
    "abdomen":     {"cx": 380, "cy": 538, "label": "Abdomen"},
    "vascular_general": {"cx": 384, "cy": 430, "label": "Vascular system"},
    "pelvis":      {"cx": 390, "cy": 615, "label": "Pelvis"},
    "spine":       {"cx": 384, "cy": 400, "label": "Spine", "view": "back"},
    "arm_left":    {"cx": 635, "cy": 680, "label": "Left arm / wrist"},
    "arm_right":   {"cx": 135, "cy": 680, "label": "Right arm / wrist"},
    "leg_left":    {"cx": 460, "cy": 950, "label": "Left leg / ankle"},
    "leg_right":   {"cx": 310, "cy": 950, "label": "Right leg / ankle"},
    "musculoskeletal_general": {"cx": 384, "cy": 700, "label": "Musculoskeletal (approximate)"},
}

LATERAL_PAIRS = {
    "lung":     ("right_lung", "left_lung"),
    "ribs":     ("ribs_right", "ribs_left"),
    "shoulder": ("shoulder_right", "shoulder_left"),
    "breast":   ("breast_right", "breast_left"),
    "arm":      ("arm_right", "arm_left"),
    "leg":      ("leg_right", "leg_left"),
    "kidney":   ("kidney_right", "kidney_left"),
    "adrenal":  ("adrenal_right", "adrenal_left"),
}


def _lateral_spec(pair_key, default_side="left"):
    right, left = LATERAL_PAIRS[pair_key]
    return {
        "left": left, "right": right,
        "bilateral": [left, right],
        "default": left if default_side == "left" else right,
    }


KEYWORD_OVERRIDES = [
    ("adrenal",            _lateral_spec("adrenal")),
    ("renal",              _lateral_spec("kidney")),
    ("kidney",             _lateral_spec("kidney")),
    ("hydronephrosis",     _lateral_spec("kidney")),
    ("hepat",              "liver"),
    ("liver",              "liver"),
    ("rib",                _lateral_spec("ribs")),
    ("clavicle",           _lateral_spec("shoulder")),
    ("rotator cuff",       _lateral_spec("shoulder")),
    ("labral",             _lateral_spec("shoulder")),
    ("wrist",              _lateral_spec("arm")),
    ("hand",               _lateral_spec("arm")),
    ("ankle",              _lateral_spec("leg")),
    ("meniscal",           _lateral_spec("leg")),
    ("acl",                _lateral_spec("leg")),
    ("chondromalacia",     _lateral_spec("leg")),
    ("hip",                "pelvis"),
    ("pelvic",             "pelvis"),
    ("sacroiliitis",       "pelvis"),
    ("cervical spine",     "spine"),
    ("thoracic spine",     "spine"),
    ("lumbar spine",       "spine"),
    ("spinal cord",        "spine"),
    ("vertebral",          "spine"),
    ("discitis",           "spine"),
    ("pott's disease",     "spine"),
    ("spondylolisthesis",  "spine"),
    ("disc herniation",    "spine"),
    ("orbital",            "head"),
    ("craniosynostosis",   "head"),
    ("temporomandibular",  "head"),
    ("carotid",            "neck"),
    ("thyroid",            "neck"),
    ("goiter",             "neck"),
    ("flail chest",        "ribs_right"),
    ("deep vein thrombosis", "musculoskeletal_general"),
    ("peripheral artery",  "musculoskeletal_general"),
    ("varicose",           "musculoskeletal_general"),
    ("pulmonary embolism", _lateral_spec("lung")),
    ("aortic",             "abdomen"),
]

SYSTEM_DEFAULT = {
    "Lung":        _lateral_spec("lung"),
    "Heart":       "heart",
    "Abdomen":     "abdomen",
    "Brain":       "head",
    "Pelvis":      "pelvis",
    "Spine":       "spine",
    "Breast":      _lateral_spec("breast"),
    "Endocrine":   "neck",
    "Vascular":    "vascular_general",
    "Joint":       "musculoskeletal_general",
    "Soft tissue": "musculoskeletal_general",
    "Bone":        "musculoskeletal_general",
    "Bone/Joint":  "musculoskeletal_general",
}


HINT_STOPWORDS = {
    "acute", "chronic", "mild", "moderate", "severe", "small", "large",
    "tiny", "minimal", "significant", "insignificant", "extensive",
    "marked", "slight", "gross", "subtle", "borderline", "trace",
    "minor", "major", "extreme", "mid", "considerable",
    "focal", "diffuse", "bilateral", "left", "right", "upper", "lower",
    "anterior", "posterior", "medial", "lateral", "superior", "inferior",
    "proximal", "distal", "central", "peripheral", "adjacent",
    "surrounding", "nearby", "circumferential", "midline", "deep",
    "superficial", "external", "internal", "outer", "inner",
    "dorsal", "ventral", "cranial", "caudal", "apical", "basal",
    "increased", "decreased", "abnormal", "normal", "changes", "change",
    "changed", "changing", "altered", "alteration", "unchanged",
    "stable", "improved", "worsened", "progressive", "progression",
    "regression", "resolved", "resolving", "developing", "evolving",
    "new", "old", "recent", "prior", "previous", "interval",
    "compared", "comparison", "similar", "different",
    "finding", "findings", "lesion", "lesions", "mass", "masses",
    "disease", "syndrome", "pattern", "artifact", "abnormality",
    "abnormalities", "irregularity", "irregular", "irregularities",
    "process", "condition", "state", "status", "phenomenon",
    "with", "without", "from", "into", "this", "that", "than", "were",
    "have", "been", "seen", "noted", "note", "notes", "post", "surgical",
    "pre", "peri", "para", "sub", "supra", "infra", "inter", "intra",
    "extra", "and", "the", "of", "in", "at", "to", "is", "are", "was",
    "there", "these", "those", "which", "such", "also", "may",
    "likely", "possibly", "probable", "probably", "suggestive",
    "suggests", "suggesting", "consider", "considered", "correlate",
    "correlation", "recommend", "recommended", "advised",
    "tear", "fracture", "cyst", "nodule", "effusion", "thickening",
    "enlargement", "collection", "calcification", "sclerosis",
    "reduced", "prominent", "generalized", "loss", "volume", "signal",
    "intensity", "area", "areas", "spot", "spots", "tissue", "wall",
    "walls", "duct", "ducts", "stone", "stones", "polyp", "polyps",
    "adenoma", "carcinoma", "metastases", "metastasis", "tumour",
    "tumor", "injury", "obstruction", "perforation", "leak", "device",
    "artefact", "space", "spaces", "narrowing", "widening", "level",
    "levels", "margin", "margins", "border", "borders", "contour",
    "contours", "extent", "portion", "portions", "region", "regions",
    "structure", "structures", "component", "components", "degree",
    "consistent", "features", "feature", "appearance", "appearances",
    "demonstrates", "demonstrated", "demonstrate", "present",
    "presence", "shows", "showing", "show", "involving",
    "involvement", "extending", "extension", "extends", "measuring",
    "measures", "measurement", "approximately", "estimated",
    "seen", "visualised", "visualized", "visible", "identified",
    "detected", "observed", "revealed", "reveals", "image", "images",
    "imaging", "scan", "study", "sequence", "sequences", "views",
    "view", "projection", "phase", "contrast", "enhancement",
    "enhancing", "density", "densities", "opacity", "opacities",
    "shadow", "shadowing", "echo", "echogenic", "hyperdense",
    "hypodense", "isodense", "hyperintense", "hypointense",
    "again", "still", "now", "currently", "recently", "previously",
    "since", "during", "after", "before", "when", "while",
    "single", "multiple", "few", "several", "numerous", "one", "two",
    "three", "four", "five", "all", "some", "any", "each", "every",
    "none", "other", "another", "additional", "further",
}


def _hint_tokens(text):
    cleaned = re.sub(r"[^a-z\s-]", " ", text.lower())
    words = [w for w in cleaned.split() if w]

    tokens = []

    for w in words:
        if len(w) >= 5 and w not in HINT_STOPWORDS:
            tokens.append(w)

    for i in range(len(words) - 1):
        a, b = words[i], words[i + 1]
        if a in HINT_STOPWORDS and b in HINT_STOPWORDS:
            continue
        if len(a) < 3 or len(b) < 3:
            continue
        tokens.append(f"{a} {b}")

    return tokens


def build_anatomy_hints(kb):
    candidates = {}
    specs = {}

    for item in kb:
        term = item.get("term", "").strip()
        if not term:
            continue

        body_system = item.get("body_system", "")

        if body_system in ("", "General"):
            continue

        region = resolve_region(term, body_system)
        if region is None:
            continue

        key = json.dumps(region, sort_keys=True)
        specs[key] = region

        sources = [term]
        sources += item.get("synonyms_in_report", [])
        sources += item.get("related_terms", [])

        for source in sources:
            for token in _hint_tokens(str(source)):
                candidates.setdefault(token, set()).add(key)

    hints = {}
    for token, spec_keys in candidates.items():
        if len(spec_keys) == 1:
            hints[token] = specs[next(iter(spec_keys))]

    return dict(sorted(hints.items()))


def resolve_region(term_name, body_system):
    name_lower = term_name.lower()
    for keyword, region in KEYWORD_OVERRIDES:
        if keyword in name_lower:
            return region
    return SYSTEM_DEFAULT.get(body_system)


def main():
    with open(KB_PATH, "r", encoding="utf-8") as f:
        kb = json.load(f)

    term_map = {}
    unmapped = []

    for item in kb:
        term = item.get("term", "").strip()
        if not term:
            continue
        region = resolve_region(term, item.get("body_system", ""))
        if region is None:
            unmapped.append(term)
            continue
        term_map[term.lower()] = {"region": region}

    anatomy_hints = build_anatomy_hints(kb)

    output = {
        "_generated_from": "data/knowledge_base.json (body_system field)",
        "_total_kb_terms": len(kb),
        "_mapped_terms": len(term_map),
        "_anatomy_hints": len(anatomy_hints),
        "_unmapped_terms_intentional": sorted(unmapped),
        "viewBox": "0 0 768 1372",
        "regions": REGIONS,
        "term_map": term_map,
        "anatomy_hints": anatomy_hints,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Total KB terms: {len(kb)}")
    print(f"Mapped (will show a pin): {len(term_map)}")
    print(f"Anatomy hints (for generic terms): {len(anatomy_hints)}")
    print(f"Generic / no fixed region (resolved from context): {len(unmapped)}")


if __name__ == "__main__":
    main()