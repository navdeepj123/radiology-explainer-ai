"""
generate_body_regions.py

Ye script data/knowledge_base.json ke saare terms ko ek anatomical
region ke saath map karta hai, aur frontend/static/data/body_regions.json
banata/refresh karta hai.

Kab chalani hai: sirf tab jab knowledge_base.json mein naye terms add
hon (Navdeep ke knowledge-base-expansion task se). Roz chalane ki
zarurat nahi hai — Flask app ke runtime ka part nahi hai.

Chalane ka tareeka:
    cd Radiology-Project/data
    python generate_body_regions.py
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE_DIR, "knowledge_base.json")
OUT_PATH = os.path.join(BASE_DIR, "..", "frontend", "static", "data", "body_regions.json")


REGIONS = {
    "kidney_left":   {"cx": 190, "cy": 300, "label": "Left kidney", "view": "back"},
    "kidney_right":  {"cx": 130, "cy": 300, "label": "Right kidney", "view": "back"},
    "adrenal_left":  {"cx": 185, "cy": 270, "label": "Left adrenal gland", "view": "back"},
    "adrenal_right": {"cx": 135, "cy": 270, "label": "Right adrenal gland", "view": "back"},
    "head":        {"cx": 160, "cy": 55,  "label": "Head / Brain"},
    "neck":        {"cx": 160, "cy": 110, "label": "Neck / Thyroid"},
    "heart":       {"cx": 172, "cy": 220, "label": "Heart"},
    "left_lung":   {"cx": 200, "cy": 210, "label": "Left lung"},
    "right_lung":  {"cx": 130, "cy": 210, "label": "Right lung"},
    "ribs_left":   {"cx": 215, "cy": 240, "label": "Left rib cage"},
    "ribs_right":  {"cx": 105, "cy": 240, "label": "Right rib cage"},
    "shoulder_left":  {"cx": 235, "cy": 165, "label": "Left shoulder"},
    "shoulder_right": {"cx": 85,  "cy": 165, "label": "Right shoulder"},
    "breast_left":  {"cx": 195, "cy": 225, "label": "Left breast"},
    "breast_right": {"cx": 135, "cy": 225, "label": "Right breast"},
    "abdomen":     {"cx": 160, "cy": 320, "label": "Abdomen"},
    "vascular_general": {"cx": 160, "cy": 300, "label": "Vascular system"},
    "pelvis":      {"cx": 160, "cy": 400, "label": "Pelvis"},
    "spine":       {"cx": 160, "cy": 280, "label": "Spine"},
    "arm_left":    {"cx": 260, "cy": 330, "label": "Left arm / wrist"},
    "arm_right":   {"cx": 60,  "cy": 330, "label": "Right arm / wrist"},
    "leg_left":    {"cx": 190, "cy": 580, "label": "Left leg / ankle"},
    "leg_right":   {"cx": 130, "cy": 580, "label": "Right leg / ankle"},
    "musculoskeletal_general": {"cx": 160, "cy": 470, "label": "Musculoskeletal (approximate)"},
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

    output = {
        "_generated_from": "data/knowledge_base.json (body_system field)",
        "_total_kb_terms": len(kb),
        "_mapped_terms": len(term_map),
        "_unmapped_terms_intentional": sorted(unmapped),
        "viewBox": "0 0 320 760",
        "regions": REGIONS,
        "term_map": term_map,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Total KB terms: {len(kb)}")
    print(f"Mapped (will show a pin): {len(term_map)}")
    print(f"Intentionally unmapped (too generic, no pin): {len(unmapped)}")


if __name__ == "__main__":
    main()