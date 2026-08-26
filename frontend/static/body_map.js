/**
 * body_map.js
 * ClearScan Anatomical Body Map v5
 *
 * Dual visualization:
 * 1. SVG anatomical map
 * 2. Real anatomical image map
 *
 * Both maps use the SAME findings and SAME pins.
 *
 * Features:
 * - Front / Back view
 * - SVG anatomical organs
 * - Real anatomical image
 * - Finding pins on both maps
 * - Left / Right / Bilateral support
 * - Hover information
 * - Click callbacks
 * - body_regions.json integration
 *
 * Required images:
 *
 * /static/images/anatomical_front.png
 * /static/images/anatomical_back.png
 *
 * You can change these paths using:
 *
 * realImageFront
 * realImageBack
 */

(function (global) {
  "use strict";

  let _regionsCache = null;

  // ============================================================
  // CONFIG
  // ============================================================

  const SVG_NS = "http://www.w3.org/2000/svg";

  const DEFAULTS = {
    regionsUrl:
      "/static/data/body_regions.json",

    realImageFront:
      "/static/img/body-front.png",

    realImageBack:
      "/static/img/body-back.png"
  };

  const COLORS = {
    body: "#181a23",
    bodyStroke: "#3b3e50",
    detail: "#303343",

    brain: "#77758c",
    lung: "#596b7b",
    heart: "#a34d5b",
    liver: "#77574b",
    stomach: "#765968",
    kidney: "#704b4b",
    spleen: "#704b5c",
    pancreas: "#98715a",
    intestine: "#886d68",
    bladder: "#596c8b",
    spine: "#777b8e",

    organStroke: "#b5b7c5",

    pin: "#f5a623",
    pinBorder: "#0d0e14",

    label: "#d7d8e2"
  };

  // ============================================================
  // LOAD REGION DATA
  // ============================================================

  async function _loadRegions(url) {
    if (_regionsCache) {
      return _regionsCache;
    }

    const res = await fetch(url);

    if (!res.ok) {
      throw new Error(
        "Could not load body_regions.json"
      );
    }

    _regionsCache = await res.json();

    return _regionsCache;
  }

  // ============================================================
  // LATERALITY
  // ============================================================

  function _detectLaterality(
    searchText,
    reportText
  ) {
    if (!reportText || !searchText) {
      return "default";
    }

    const lower =
      reportText.toLowerCase();

    const search =
      searchText.toLowerCase();

    const idx =
      lower.indexOf(search);

    if (idx === -1) {
      return "default";
    }

    const sentenceStart =
      Math.max(
        lower.lastIndexOf(".", idx),
        lower.lastIndexOf(";", idx),
        lower.lastIndexOf("\n", idx)
      ) + 1;

    let sentenceEnd =
      lower.indexOf(".", idx);

    if (sentenceEnd === -1) {
      sentenceEnd =
        lower.length;
    }

    const sentence =
      lower.slice(
        sentenceStart,
        sentenceEnd
      );

    if (
      /\bbilateral\b/.test(sentence) ||
      /\bboth\b/.test(sentence) ||
      /\bbilaterally\b/.test(sentence)
    ) {
      return "bilateral";
    }

    if (
      /\bleft\b/.test(sentence) ||
      /\blt\b/.test(sentence)
    ) {
      return "left";
    }

    if (
      /\bright\b/.test(sentence) ||
      /\brt\b/.test(sentence)
    ) {
      return "right";
    }

    return "default";
  }

  // ============================================================
  // REGION RESOLUTION
  // ============================================================

  function _resolveRegionKeys(
    mapEntry,
    laterality
  ) {
    const regionSpec =
      mapEntry.region;

    if (
      typeof regionSpec === "string"
    ) {
      return [regionSpec];
    }

    if (!regionSpec) {
      return [];
    }

    if (
      regionSpec.bilateral &&
      laterality === "bilateral"
    ) {
      return regionSpec.bilateral;
    }

    if (
      regionSpec[laterality]
    ) {
      return [
        regionSpec[laterality]
      ];
    }

    if (
      regionSpec.default
    ) {
      return [
        regionSpec.default
      ];
    }

    return [];
  }

  // ============================================================
  // SVG HELPERS
  // ============================================================

  function _createElement(
    name,
    attrs
  ) {
    const el =
      document.createElementNS(
        SVG_NS,
        name
      );

    Object.keys(attrs || {})
      .forEach(function (key) {
        el.setAttribute(
          key,
          attrs[key]
        );
      });

    return el;
  }

  function _append(
    svg,
    name,
    attrs
  ) {
    const el =
      _createElement(
        name,
        attrs
      );

    svg.appendChild(el);

    return el;
  }

  // ============================================================
  // ORGAN PATH
  // ============================================================

  function _addOrganPath(
    svg,
    d,
    fill,
    organName
  ) {
    const path =
      _append(
        svg,
        "path",
        {
          d: d,
          fill: fill,
          stroke:
            COLORS.organStroke,
          "stroke-width": "1.2",
          "stroke-linejoin":
            "round",
          "stroke-linecap":
            "round",
          opacity: "0.88"
        }
      );

    path.dataset.organ =
      organName || "";

    path.style.cursor =
      "pointer";

    path.addEventListener(
      "mouseenter",
      function () {
        path.setAttribute(
          "opacity",
          "1"
        );

        path.setAttribute(
          "stroke-width",
          "2"
        );
      }
    );

    path.addEventListener(
      "mouseleave",
      function () {
        path.setAttribute(
          "opacity",
          "0.88"
        );

        path.setAttribute(
          "stroke-width",
          "1.2"
        );
      }
    );

    return path;
  }

  // ============================================================
  // ORGAN ELLIPSE
  // ============================================================

  function _addOrganEllipse(
    svg,
    cx,
    cy,
    rx,
    ry,
    fill,
    organName,
    rotation
  ) {
    const ellipse =
      _append(
        svg,
        "ellipse",
        {
          cx: cx,
          cy: cy,
          rx: rx,
          ry: ry,
          fill: fill,
          stroke:
            COLORS.organStroke,
          "stroke-width": "1.2",
          opacity: "0.88",
          transform:
            rotation
              ? `rotate(${rotation} ${cx} ${cy})`
              : ""
        }
      );

    ellipse.dataset.organ =
      organName || "";

    ellipse.style.cursor =
      "pointer";

    ellipse.addEventListener(
      "mouseenter",
      function () {
        ellipse.setAttribute(
          "opacity",
          "1"
        );

        ellipse.setAttribute(
          "stroke-width",
          "2"
        );
      }
    );

    ellipse.addEventListener(
      "mouseleave",
      function () {
        ellipse.setAttribute(
          "opacity",
          "0.88"
        );

        ellipse.setAttribute(
          "stroke-width",
          "1.2"
        );
      }
    );

    return ellipse;
  }

  // ============================================================
  // LABEL
  // ============================================================

  function _addLabel(
    svg,
    x,
    y,
    text
  ) {
    const label =
      _append(
        svg,
        "text",
        {
          x: x,
          y: y,
          fill: COLORS.label,
          "font-size": "8",
          "font-family":
            "Arial, sans-serif",
          "text-anchor":
            "middle",
          opacity: "0.7"
        }
      );

    label.textContent =
      text;

    return label;
  }

  // ============================================================
  // BODY SILHOUETTE
  // ============================================================

  function _drawSilhouette(
    svg,
    view
  ) {
    const bodyFill =
      COLORS.body;

    const bodyStroke =
      COLORS.bodyStroke;

    const detail =
      COLORS.detail;

    // HEAD

    _addOrganEllipse(
      svg,
      160,
      54,
      28,
      33,
      bodyFill,
      "head"
    );

    // Face

    _addOrganPath(
      svg,
      "M138 55 C138 73 147 86 160 88 C173 86 182 73 182 55",
      "none",
      "face"
    ).setAttribute(
      "stroke",
      detail
    );

    // NECK

    _addOrganPath(
      svg,
      "M147 81 C148 90 146 97 139 103 C146 108 153 110 160 110 C167 110 174 108 181 103 C174 97 172 90 173 81 Z",
      bodyFill,
      "neck"
    );

    // TORSO

    _addOrganPath(
      svg,
      "M139 101 " +
      "C128 102 118 105 111 111 " +
      "C105 117 103 128 105 141 " +
      "L112 204 " +
      "C114 222 117 244 122 263 " +
      "C124 272 123 281 120 293 " +
      "L116 303 " +
      "C114 314 120 322 130 327 " +
      "C139 332 150 335 160 335 " +
      "C170 335 181 332 190 327 " +
      "C200 322 206 314 204 303 " +
      "L200 293 " +
      "C197 281 196 272 198 263 " +
      "C203 244 206 222 208 204 " +
      "L215 141 " +
      "C217 128 215 117 209 111 " +
      "C202 105 192 102 181 101 " +
      "C176 108 169 111 160 111 " +
      "C151 111 144 108 139 101 Z",
      bodyFill,
      "torso"
    );

    // LEFT ARM

    _addOrganPath(
      svg,
      "M111 111 " +
      "C103 113 98 120 95 130 " +
      "C91 145 88 166 84 187 " +
      "C81 205 78 224 75 242 " +
      "C73 257 71 272 69 287 " +
      "C68 296 71 302 77 305 " +
      "C83 308 90 304 93 296 " +
      "L102 250 " +
      "C106 229 109 207 112 185 " +
      "L121 140 " +
      "C123 128 121 117 111 111 Z",
      bodyFill,
      "left_arm"
    );

    // RIGHT ARM

    _addOrganPath(
      svg,
      "M209 111 " +
      "C217 113 222 120 225 130 " +
      "C229 145 232 166 236 187 " +
      "C239 205 242 224 245 242 " +
      "C247 257 249 272 251 287 " +
      "C252 296 249 302 243 305 " +
      "C237 308 230 304 227 296 " +
      "L218 250 " +
      "C214 229 211 207 208 185 " +
      "L199 140 " +
      "C197 128 199 117 209 111 Z",
      bodyFill,
      "right_arm"
    );

    // LEFT LEG

    _addOrganPath(
      svg,
      "M128 323 " +
      "C126 337 125 352 125 369 " +
      "C124 398 123 428 122 458 " +
      "C121 486 120 516 119 546 " +
      "C118 583 118 625 118 666 " +
      "C117 675 120 682 126 685 " +
      "C132 688 141 687 145 682 " +
      "C148 678 147 671 146 664 " +
      "L148 595 " +
      "C149 550 151 505 153 461 " +
      "C155 426 156 394 155 371 " +
      "C155 350 151 335 146 327 " +
      "C140 326 134 324 128 323 Z",
      bodyFill,
      "left_leg"
    );

    // RIGHT LEG

    _addOrganPath(
      svg,
      "M192 323 " +
      "C194 337 195 352 195 369 " +
      "C196 398 197 428 198 458 " +
      "C199 486 200 516 201 546 " +
      "C202 583 202 625 202 666 " +
      "C203 675 200 682 194 685 " +
      "C188 688 179 687 175 682 " +
      "C172 678 173 671 174 664 " +
      "L172 595 " +
      "C171 550 169 505 167 461 " +
      "C165 426 164 394 165 371 " +
      "C165 350 169 335 174 327 " +
      "C180 326 186 324 192 323 Z",
      bodyFill,
      "right_leg"
    );

    if (view === "front") {
      _drawFrontAnatomy(svg);
    }

    if (view === "back") {
      _drawBackAnatomy(svg);
    }
  }

  // ============================================================
  // FRONT ANATOMY
  // ============================================================

  function _drawFrontAnatomy(
    svg
  ) {
    // BRAIN

    _addOrganEllipse(
      svg,
      160,
      54,
      22,
      26,
      COLORS.brain,
      "brain"
    );

    _addOrganPath(
      svg,
      "M160 30 C158 42 158 65 160 80",
      "none",
      "brain_midline"
    ).setAttribute(
      "stroke",
      "#d1cfe0"
    );

    [
      40,
      48,
      57,
      66
    ].forEach(
      function (y) {
        _addOrganPath(
          svg,
          `M143 ${y} C149 ${y - 3} 154 ${y + 3} 159 ${y}`,
          "none",
          "brain_fold"
        ).setAttribute(
          "stroke",
          "#b0aec1"
        );

        _addOrganPath(
          svg,
          `M161 ${y} C166 ${y + 3} 172 ${y - 3} 177 ${y}`,
          "none",
          "brain_fold"
        ).setAttribute(
          "stroke",
          "#b0aec1"
        );
      }
    );

    // TRACHEA

    _addOrganPath(
      svg,
      "M157 91 L163 91 L164 143 L156 143 Z",
      "#777b82",
      "trachea"
    );

    // LEFT LUNG

    _addOrganPath(
      svg,
      "M156 143 " +
      "C145 133 132 135 126 150 " +
      "C120 166 121 196 130 213 " +
      "C136 224 148 219 155 208 " +
      "C159 199 159 177 156 143 Z",
      COLORS.lung,
      "left_lung"
    );

    // RIGHT LUNG

    _addOrganPath(
      svg,
      "M164 143 " +
      "C175 133 188 135 194 150 " +
      "C200 166 199 196 190 213 " +
      "C184 224 172 219 165 208 " +
      "C161 199 161 177 164 143 Z",
      COLORS.lung,
      "right_lung"
    );

    // HEART

   // ==========================================================
// ANATOMICAL HEART
// ==========================================================

// Main heart silhouette
_addOrganPath(
  svg,

  "M160 151 " +

  // Aorta / superior vessels
  "C158 145 157 139 159 134 " +
  "C161 130 166 130 168 134 " +
  "C169 137 168 141 166 145 " +

  // Left atrium / upper left contour
  "C174 147 181 151 184 158 " +
  "C187 165 184 172 180 177 " +

  // Left ventricle
  "C176 183 173 190 171 197 " +
  "C169 204 166 211 161 218 " +

  // Apex
  "C159 221 157 218 155 214 " +
  "C151 207 148 199 146 191 " +

  // Right ventricle
  "C144 185 140 180 137 175 " +
  "C133 169 132 161 135 156 " +

  // Right atrium
  "C138 151 145 148 151 149 " +

  // Upper connection
  "C154 150 157 152 160 151 Z",

  "#9b4655",
  "heart"
);

// Right atrium
_addOrganPath(
  svg,

  "M151 151 " +
  "C144 149 137 153 135 159 " +
  "C133 166 137 173 143 177 " +
  "C147 179 150 176 152 171 " +
  "C154 165 154 157 151 151 Z",

  "#a65360",
  "right_atrium"
);

// Left atrium
_addOrganPath(
  svg,

  "M163 151 " +
  "C170 147 178 151 182 157 " +
  "C185 163 183 170 179 174 " +
  "C176 177 172 175 169 171 " +
  "C166 165 164 157 163 151 Z",

  "#a95260",
  "left_atrium"
);

// Right ventricle
_addOrganPath(
  svg,

  "M151 170 " +
  "C145 173 143 179 145 187 " +
  "C147 195 151 204 157 214 " +
  "C159 217 160 218 161 217 " +
  "C162 207 161 196 158 187 " +
  "C157 179 155 173 151 170 Z",

  "#91404e",
  "right_ventricle"
);

// Left ventricle
_addOrganPath(
  svg,

  "M163 170 " +
  "C158 178 159 189 162 199 " +
  "C164 207 164 213 161 218 " +
  "C166 211 171 201 174 191 " +
  "C177 182 177 176 173 172 " +
  "C170 169 166 168 163 170 Z",

  "#a84c59",
  "left_ventricle"
);

// Interventricular septum
_addOrganPath(
  svg,

  "M160 158 " +
  "C158 168 158 178 159 188 " +
  "C160 198 161 208 161 217",

  "none",
  "heart_septum"
).setAttribute(
  "stroke",
  "#d58b95"
);

_addOrganPath(
  svg,

  "M153 153 C157 157 160 158 164 154",

  "none",
  "atrial_septum"
).setAttribute(
  "stroke",
  "#d58b95"
);

// Aorta
_addOrganPath(
  svg,

  "M160 153 " +
  "C157 148 155 143 156 138 " +
  "C157 133 160 130 164 131 " +
  "C168 132 170 136 168 140 " +
  "C167 143 165 146 164 150",

  "#7d3845",
  "aorta"
);

// Pulmonary trunk
_addOrganPath(
  svg,

  "M159 153 " +
  "C155 148 151 145 149 141 " +
  "C147 137 149 134 152 133 " +
  "C155 132 158 135 160 139",

  "#75515d",
  "pulmonary_trunk"
);

// Superior vena cava
_addOrganPath(
  svg,

  "M148 143 " +
  "C145 136 145 128 147 121 " +
  "C149 116 153 116 155 120 " +
  "L155 139 ",

  "#687080",
  "superior_vena_cava"
);

// Inferior vena cava
_addOrganPath(
  svg,

  "M148 172 " +
  "C145 184 145 194 148 202 " +
  "C150 208 153 212 157 216",

  "none",
  "inferior_vena_cava"
).setAttribute(
  "stroke",
  "#687080"
);

// Coronary groove
_addOrganPath(
  svg,

  "M137 166 " +
  "C145 169 152 171 160 171 " +
  "C169 171 177 168 183 164",

  "none",
  "coronary_groove"
).setAttribute(
  "stroke",
  "#c87883"
);

// Left coronary vessel
_addOrganPath(
  svg,

  "M160 158 C166 162 171 166 174 173",

  "none",
  "coronary_vessel"
).setAttribute(
  "stroke",
  "#e09aa2"
);

// Right coronary vessel
_addOrganPath(
  svg,

  "M160 158 C153 162 148 166 145 173",

  "none",
  "coronary_vessel"
).setAttribute(
  "stroke",
  "#e09aa2"
);
    // LIVER

    _addOrganPath(
      svg,
      "M127 219 " +
      "C139 211 157 213 177 214 " +
      "C190 215 198 221 195 233 " +
      "C191 246 173 251 152 248 " +
      "C137 247 126 239 127 219 Z",
      COLORS.liver,
      "liver"
    );

    // GALLBLADDER

    _addOrganEllipse(
      svg,
      173,
      241,
      4,
      7,
      "#a39b55",
      "gallbladder",
      -15
    );

    // STOMACH

    _addOrganPath(
      svg,
      "M143 244 " +
      "C131 244 128 256 133 269 " +
      "C138 282 151 283 157 272 " +
      "C161 263 157 248 148 245 Z",
      COLORS.stomach,
      "stomach"
    );

    // SPLEEN

    _addOrganEllipse(
      svg,
      128,
      264,
      7,
      13,
      COLORS.spleen,
      "spleen",
      -20
    );

    // PANCREAS

    _addOrganPath(
      svg,
      "M146 268 C156 263 174 265 183 270 C176 276 156 277 146 273 Z",
      COLORS.pancreas,
      "pancreas"
    );

    // LEFT KIDNEY

    _addOrganPath(
      svg,
      "M138 260 " +
      "C129 255 121 263 122 274 " +
      "C123 285 132 291 139 284 " +
      "C145 277 144 266 138 260 Z",
      COLORS.kidney,
      "left_kidney"
    );

    // RIGHT KIDNEY

    _addOrganPath(
      svg,
      "M182 260 " +
      "C191 255 199 263 198 274 " +
      "C197 285 188 291 181 284 " +
      "C175 277 176 266 182 260 Z",
      COLORS.kidney,
      "right_kidney"
    );

    // ADRENALS

    _addOrganEllipse(
      svg,
      137,
      254,
      5,
      3,
      "#b18b4e",
      "left_adrenal"
    );

    _addOrganEllipse(
      svg,
      183,
      254,
      5,
      3,
      "#b18b4e",
      "right_adrenal"
    );

    _drawIntestines(svg);

    // BLADDER

    _addOrganPath(
      svg,
      "M146 305 " +
      "C146 294 174 294 174 305 " +
      "L173 319 " +
      "C170 329 150 329 147 319 Z",
      COLORS.bladder,
      "bladder"
    );

    // PELVIS

    _addOrganPath(
      svg,
      "M139 326 C146 333 153 337 160 337 C167 337 174 333 181 326",
      "none",
      "pelvis"
    ).setAttribute(
      "stroke",
      COLORS.detail
    );

    // STERNUM

    _addOrganPath(
      svg,
      "M160 137 L160 207",
      "none",
      "sternum"
    ).setAttribute(
      "stroke",
      "#777b8a"
    );

    // LABELS

    _addLabel(
      svg,
      160,
      23,
      "BRAIN"
    );

    _addLabel(
      svg,
      125,
      151,
      "LUNG"
    );

    _addLabel(
      svg,
      194,
      151,
      "LUNG"
    );

    _addLabel(
      svg,
      160,
      213,
      "HEART"
    );

    _addLabel(
      svg,
      185,
      226,
      "LIVER"
    );

    _addLabel(
      svg,
      124,
      290,
      "KIDNEY"
    );

    _addLabel(
      svg,
      196,
      290,
      "KIDNEY"
    );

    _addLabel(
      svg,
      160,
      292,
      "BOWEL"
    );
  }

  // ============================================================
  // INTESTINES
  // ============================================================

  function _drawIntestines(svg) {
    _addOrganPath(
      svg,
      "M132 279 " +
      "C126 287 126 301 134 306 " +
      "C143 311 177 311 186 306 " +
      "C194 301 194 287 188 279 " +
      "M134 306 " +
      "C134 317 143 321 151 321 " +
      "M186 306 " +
      "C186 317 177 321 169 321",
      "none",
      "large_intestine"
    ).setAttribute(
      "stroke",
      COLORS.intestine
    );

    const loops = [
      "M139 286 C148 279 155 291 145 297 C136 303 151 309 160 300",
      "M160 300 C169 291 177 303 168 309 C158 315 148 304 155 297",
      "M146 310 C154 302 162 315 170 309"
    ];

    loops.forEach(
      function (d) {
        _addOrganPath(
          svg,
          d,
          "none",
          "small_intestine"
        ).setAttribute(
          "stroke",
          COLORS.intestine
        );
      }
    );
  }

  // ============================================================
  // BACK ANATOMY
  // ============================================================

  function _drawBackAnatomy(svg) {
    _addOrganEllipse(
      svg,
      160,
      54,
      22,
      26,
      COLORS.brain,
      "brain"
    );

    _addOrganEllipse(
      svg,
      160,
      75,
      13,
      7,
      "#666579",
      "cerebellum"
    );

    // LEFT LUNG

    _addOrganPath(
      svg,
      "M156 143 " +
      "C144 133 131 137 126 152 " +
      "C121 168 123 197 132 214 " +
      "C139 224 150 218 156 207 Z",
      COLORS.lung,
      "left_lung"
    );

    // RIGHT LUNG

    _addOrganPath(
      svg,
      "M164 143 " +
      "C176 133 189 137 194 152 " +
      "C199 168 197 197 188 214 " +
      "C181 224 170 218 164 207 Z",
      COLORS.lung,
      "right_lung"
    );

    // SPINE

    _addOrganPath(
      svg,
      "M156 110 L164 110 L165 320 L155 320 Z",
      COLORS.spine,
      "spine"
    );

    for (
      let y = 120;
      y <= 310;
      y += 13
    ) {
      _append(
        svg,
        "ellipse",
        {
          cx: 160,
          cy: y,
          rx: 5,
          ry: 3,
          fill: "#a5a8b6",
          opacity: "0.8"
        }
      );
    }

    // SCAPULAE

    _addOrganPath(
      svg,
      "M128 137 C138 130 150 137 153 153 C146 164 135 164 127 154 Z",
      "#404456",
      "left_scapula"
    );

    _addOrganPath(
      svg,
      "M192 137 C182 130 170 137 167 153 C174 164 185 164 193 154 Z",
      "#404456",
      "right_scapula"
    );

    // KIDNEYS

    _addOrganPath(
      svg,
      "M138 240 C129 235 122 244 123 257 C124 269 133 275 140 267 C145 259 144 247 138 240 Z",
      COLORS.kidney,
      "left_kidney"
    );

    _addOrganPath(
      svg,
      "M182 240 C191 235 198 244 197 257 C196 269 187 275 180 267 C175 259 176 247 182 240 Z",
      COLORS.kidney,
      "right_kidney"
    );

    // ADRENALS

    _addOrganEllipse(
      svg,
      137,
      235,
      5,
      3,
      "#b18b4e",
      "left_adrenal"
    );

    _addOrganEllipse(
      svg,
      183,
      235,
      5,
      3,
      "#b18b4e",
      "right_adrenal"
    );

    // BACK MUSCLES

    _addOrganPath(
      svg,
      "M130 170 C142 180 149 195 153 220",
      "none",
      "back_muscle"
    ).setAttribute(
      "stroke",
      COLORS.detail
    );

    _addOrganPath(
      svg,
      "M190 170 C178 180 171 195 167 220",
      "none",
      "back_muscle"
    ).setAttribute(
      "stroke",
      COLORS.detail
    );

    // SACRUM

    _addOrganPath(
      svg,
      "M148 300 C152 294 168 294 172 300 L169 323 C165 330 155 330 151 323 Z",
      "#5b5f72",
      "sacrum"
    );

    _addLabel(
      svg,
      160,
      23,
      "BRAIN"
    );

    _addLabel(
      svg,
      160,
      105,
      "SPINE"
    );

    _addLabel(
      svg,
      112,
      248,
      "KIDNEY"
    );

    _addLabel(
      svg,
      208,
      248,
      "KIDNEY"
    );

    _addLabel(
      svg,
      160,
      340,
      "PELVIS"
    );
  }

  // ============================================================
  // POPUP
  // ============================================================

  function _makePopup() {
    let popup =
      document.getElementById(
        "cs-body-map-popup"
      );

    if (popup) {
      return popup;
    }

    popup =
      document.createElement(
        "div"
      );

    popup.id =
      "cs-body-map-popup";

    popup.style.cssText =
      "position:fixed;" +
      "display:none;" +
      "z-index:999999;" +
      "background:#14151c;" +
      "border:1px solid #2a2c3a;" +
      "border-radius:10px;" +
      "padding:12px 14px;" +
      "max-width:280px;" +
      "color:#e6e6ef;" +
      "font-family:inherit;" +
      "font-size:13px;" +
      "line-height:1.4;" +
      "box-shadow:0 8px 24px rgba(0,0,0,0.5);" +
      "pointer-events:none;";

    document.body.appendChild(
      popup
    );

    return popup;
  }

  function _showPopup(
    popup,
    x,
    y,
    title,
    body
  ) {
    popup.innerHTML =
      '<div style="' +
      "font-weight:600;" +
      "color:#8b8cf5;" +
      "margin-bottom:4px;" +
      "text-transform:capitalize;" +
      '">' +
      title +
      "</div>" +
      "<div>" +
      (body ||
        "No definition available.") +
      "</div>";

    popup.style.left =
      x + 14 + "px";

    popup.style.top =
      y + 14 + "px";

    popup.style.display =
      "block";
  }

  function _hidePopup(popup) {
    popup.style.display =
      "none";
  }

  // ============================================================
  // PIN
  // ============================================================

  function _drawPin(
    svg,
    pin,
    popup,
    onPinClick
  ) {
    const group =
      _append(
        svg,
        "g",
        {
          "data-term":
            pin.term || ""
        }
      );

    group.style.cursor =
      "pointer";

    _append(
      group,
      "circle",
      {
        cx: pin.cx,
        cy: pin.cy,
        r: 18,
        fill: "transparent"
      }
    );

    const pulse =
      _append(
        group,
        "circle",
        {
          cx: pin.cx,
          cy: pin.cy,
          r: 13,
          fill: COLORS.pin,
          opacity: "0.22"
        }
      );

    const dot =
      _append(
        group,
        "circle",
        {
          cx: pin.cx,
          cy: pin.cy,
          r: 6,
          fill: COLORS.pin,
          stroke:
            COLORS.pinBorder,
          "stroke-width": "2"
        }
      );

    _append(
      group,
      "circle",
      {
        cx: pin.cx,
        cy: pin.cy,
        r: 2,
        fill: "#fff"
      }
    );

    group.addEventListener(
      "mouseenter",
      function (e) {
        _showPopup(
          popup,
          e.clientX,
          e.clientY,
          pin.term,
          pin.definition
        );

        pulse.setAttribute(
          "r",
          "17"
        );

        pulse.setAttribute(
          "opacity",
          "0.35"
        );

        dot.setAttribute(
          "r",
          "7"
        );
      }
    );

    group.addEventListener(
      "mousemove",
      function (e) {
        popup.style.left =
          e.clientX + 14 + "px";

        popup.style.top =
          e.clientY + 14 + "px";
      }
    );

    group.addEventListener(
      "mouseleave",
      function () {
        _hidePopup(popup);

        pulse.setAttribute(
          "r",
          "13"
        );

        pulse.setAttribute(
          "opacity",
          "0.22"
        );

        dot.setAttribute(
          "r",
          "6"
        );
      }
    );

    group.addEventListener(
      "click",
      function () {
        if (
          typeof onPinClick ===
          "function"
        ) {
          onPinClick(
            pin.term,
            pin.definition,
            pin
          );
        }
      }
    );

    return group;
  }

  // ============================================================
  // REAL IMAGE PANEL
  // ============================================================

  function _buildRealImageMap(
    imageUrl,
    pins,
    view,
    popup,
    onPinClick
  ) {
    const wrapper =
      document.createElement(
        "div"
      );

    wrapper.className =
      "cs-real-anatomy-map";

    wrapper.style.cssText =
      "position:relative;" +
      "width:100%;" +
      "max-width:360px;" +
      "aspect-ratio:320 / 710;" +
      "margin:0 auto;" +
      "overflow:hidden;" +
      "border-radius:8px;" +
      "background:#0b0d14;";

    // IMAGE

    const image =
      document.createElement(
        "img"
      );

    image.src =
      imageUrl;

    image.alt =
      view === "front"
        ? "Realistic front anatomical visualization"
        : "Realistic back anatomical visualization";

    image.draggable =
      false;

    image.style.cssText =
      "position:absolute;" +
      "inset:0;" +
      "width:100%;" +
      "height:100%;" +
      "object-fit:contain;" +
      "display:block;";

    // Overlay SVG

    const overlay =
      document.createElementNS(
        SVG_NS,
        "svg"
      );

    overlay.setAttribute(
      "viewBox",
      "0 0 320 710"
    );

    overlay.setAttribute(
      "preserveAspectRatio",
      "xMidYMid meet"
    );

    overlay.style.cssText =
      "position:absolute;" +
      "inset:0;" +
      "width:100%;" +
      "height:100%;" +
      "pointer-events:none;";

    // IMPORTANT:
    // Pin groups need pointer events.

    pins.forEach(
      function (pin) {
        const group =
          _drawPin(
            overlay,
            pin,
            popup,
            onPinClick
          );

        group.style.pointerEvents =
          "all";
      }
    );

    wrapper.appendChild(
      image
    );

    wrapper.appendChild(
      overlay
    );

    // IMAGE ERROR

    image.addEventListener(
      "error",
      function () {
        wrapper.innerHTML =
          '<div style="' +
          "height:100%;" +
          "display:flex;" +
          "align-items:center;" +
          "justify-content:center;" +
          "text-align:center;" +
          "padding:20px;" +
          "box-sizing:border-box;" +
          "color:#777;" +
          "font-size:12px;" +
          '">' +
          "Real anatomical image could not be loaded.<br><br>" +
          "<small>" +
          imageUrl +
          "</small>" +
          "</div>";
      }
    );

    return wrapper;
  }

  // ============================================================
  // SVG MAP
  // ============================================================

  function _buildSvg(
    regionData,
    pinsForView,
    view,
    popup,
    onPinClick
  ) {
    const svg =
      document.createElementNS(
        SVG_NS,
        "svg"
      );

    svg.setAttribute(
      "viewBox",
      regionData.viewBox ||
      "0 0 320 710"
    );

    svg.setAttribute(
      "width",
      "100%"
    );

    svg.setAttribute(
      "height",
      "auto"
    );

    svg.style.cssText =
      "display:block;" +
      "width:100%;" +
      "max-width:360px;" +
      "margin:0 auto;" +
      "overflow:visible;";

    _drawSilhouette(
      svg,
      view
    );

    pinsForView.forEach(
      function (pin) {
        _drawPin(
          svg,
          pin,
          popup,
          onPinClick
        );
      }
    );

    return svg;
  }

  // ============================================================
  // PANEL TITLE
  // ============================================================

  function _makePanel(
    title,
    subtitle
  ) {
    const panel =
      document.createElement(
        "div"
      );

    panel.style.cssText =
      "flex:1;" +
      "min-width:280px;" +
      "background:#0f1118;" +
      "border:1px solid #242735;" +
      "border-radius:10px;" +
      "padding:12px;" +
      "box-sizing:border-box;";

    const heading =
      document.createElement(
        "div"
      );

    heading.style.cssText =
      "font-size:13px;" +
      "font-weight:600;" +
      "color:#e5e6ee;" +
      "margin-bottom:3px;";

    heading.textContent =
      title;

    const sub =
      document.createElement(
        "div"
      );

    sub.style.cssText =
      "font-size:10px;" +
      "color:#777b8c;" +
      "margin-bottom:10px;";

    sub.textContent =
      subtitle;

    panel.appendChild(
      heading
    );

    panel.appendChild(
      sub
    );

    return panel;
  }

  // ============================================================
  // MAIN BODY MAP
  // ============================================================

  async function renderBodyMap(
    opts
  ) {
    opts =
      opts || {};

    const container =
      opts.container;

    const detectedTerms =
      opts.detectedTerms ||
      [];

    const reportText =
      opts.reportText ||
      "";

    const regionsUrl =
      opts.regionsUrl ||
      DEFAULTS.regionsUrl;

    const realImageFront =
      opts.realImageFront ||
      DEFAULTS.realImageFront;

    const realImageBack =
      opts.realImageBack ||
      DEFAULTS.realImageBack;

    const onPinClick =
      opts.onPinClick ||
      null;

    if (!container) {
      console.error(
        "renderBodyMap: container element required"
      );

      return;
    }

    let regionData;

    try {
      regionData =
        await _loadRegions(
          regionsUrl
        );
    } catch (e) {
      console.error(e);

      container.innerHTML =
        '<p style="text-align:center;color:#888;">' +
        "Unable to load anatomical map." +
        "</p>";

      return;
    }

    // ==========================================================
    // CALCULATE PINS
    // ==========================================================

    const pins = {
      front: [],
      back: []
    };

    const usedRegions =
      new Set();

    detectedTerms.forEach(
      function (entry) {
        const termName =
          (
            entry.term ||
            ""
          )
            .toLowerCase()
            .trim();

        const mapEntry =
          regionData.term_map
            ? regionData.term_map[
                termName
              ]
            : null;

        if (!mapEntry) {
          return;
        }

        const searchText =
          entry.matched_text ||
          entry.term ||
          "";

        const laterality =
          _detectLaterality(
            searchText,
            reportText
          );

        const regionKeys =
          _resolveRegionKeys(
            mapEntry,
            laterality
          );

        regionKeys.forEach(
          function (key) {
            const region =
              regionData.regions[
                key
              ];

            if (!region) {
              return;
            }

            const dedupeKey =
              termName +
              ":" +
              key;

            if (
              usedRegions.has(
                dedupeKey
              )
            ) {
              return;
            }

            usedRegions.add(
              dedupeKey
            );

            const view =
              region.view === "back"
                ? "back"
                : "front";

            pins[
              view
            ].push({
              cx:
                Number(region.cx),

              cy:
                Number(region.cy),

              term:
                entry.term ||
                termName,

              definition:
                entry.meaning ||
                entry.definition ||
                "",

              severity:
                entry.severity ||
                null
            });
          }
        );
      }
    );

    const totalPins =
      pins.front.length +
      pins.back.length;

    const popup =
      _makePopup();

    container.innerHTML =
      "";

    // ==========================================================
    // NO FINDINGS
    // ==========================================================

    if (totalPins === 0) {
      const emptyPanel =
        _makePanel(
          "Anatomical Visualization",
          "No mappable findings detected"
        );

      emptyPanel.appendChild(
        _buildSvg(
          regionData,
          [],
          "front",
          popup,
          onPinClick
        )
      );

      container.appendChild(
        emptyPanel
      );

      const note =
        document.createElement(
          "p"
        );

      note.style.cssText =
        "text-align:center;" +
        "font-size:10px;" +
        "opacity:0.45;" +
        "margin-top:8px;";

      note.textContent =
        "Approximate anatomical visualization — not a diagnostic image.";

      container.appendChild(
        note
      );

      return;
    }

    // ==========================================================
    // CURRENT VIEW
    // ==========================================================

    let currentView =
      pins.front.length >=
      pins.back.length
        ? "front"
        : "back";

    // ==========================================================
    // HEADER
    // ==========================================================

    const header =
      document.createElement(
        "div"
      );

    header.style.cssText =
      "margin-bottom:12px;";

    const title =
      document.createElement(
        "div"
      );

    title.style.cssText =
      "font-size:14px;" +
      "font-weight:600;" +
      "color:#e5e6ee;";

    title.textContent =
      "Anatomical Findings";

    const subtitle =
      document.createElement(
        "div"
      );

    subtitle.style.cssText =
      "font-size:10px;" +
      "color:#777b8c;" +
      "margin-top:2px;";

    subtitle.textContent =
      "Approximate location of detected findings";

    header.appendChild(
      title
    );

    header.appendChild(
      subtitle
    );

    // ==========================================================
    // TOGGLE
    // ==========================================================

    const toggleWrap =
      document.createElement(
        "div"
      );

    toggleWrap.style.cssText =
      "display:flex;" +
      "gap:6px;" +
      "justify-content:center;" +
      "margin-bottom:14px;";

    // ==========================================================
    // MAP WRAPPER
    // ==========================================================

    const mapsWrap =
      document.createElement(
        "div"
      );

    mapsWrap.style.cssText =
      "display:flex;" +
      "gap:14px;" +
      "align-items:flex-start;" +
      "justify-content:center;" +
      "flex-wrap:wrap;" +
      "width:100%;";

    // ==========================================================
    // BUTTON
    // ==========================================================

    function makeToggleBtn(
      label,
      viewName
    ) {
      const btn =
        document.createElement(
          "button"
        );

      btn.type =
        "button";

      btn.textContent =
        label +
        " (" +
        pins[
          viewName
        ].length +
        ")";

      btn.style.cssText =
        "background:transparent;" +
        "border:1px solid #2a2c3a;" +
        "color:#c8c9d6;" +
        "border-radius:7px;" +
        "padding:5px 14px;" +
        "font-size:11px;" +
        "cursor:pointer;" +
        "font-family:inherit;" +
        "transition:all .15s ease;";

      btn.addEventListener(
        "mouseenter",
        function () {
          if (
            currentView !==
            viewName
          ) {
            btn.style.borderColor =
              "#8b8cf5";
          }
        }
      );

      btn.addEventListener(
        "mouseleave",
        function () {
          if (
            currentView !==
            viewName
          ) {
            btn.style.borderColor =
              "#2a2c3a";
          }
        }
      );

      btn.addEventListener(
        "click",
        function () {
          currentView =
            viewName;

          redraw();
        }
      );

      return btn;
    }

    // ==========================================================
    // REDRAW BOTH MAPS
    // ==========================================================

    function redraw() {
      toggleWrap.innerHTML =
        "";

      const frontBtn =
        makeToggleBtn(
          "Front",
          "front"
        );

      const backBtn =
        makeToggleBtn(
          "Back",
          "back"
        );

      const active =
        currentView === "front"
          ? frontBtn
          : backBtn;

      active.style.background =
        "#8b8cf5";

      active.style.color =
        "#fff";

      active.style.borderColor =
        "#8b8cf5";

      toggleWrap.appendChild(
        frontBtn
      );

      toggleWrap.appendChild(
        backBtn
      );

      // CLEAR OLD MAPS

      mapsWrap.innerHTML =
        "";

      // ========================================================
      // SVG PANEL
      // ========================================================

      const svgPanel =
        _makePanel(
          "Anatomical Map",
          "Interactive anatomical regions"
        );

      const svg =
        _buildSvg(
          regionData,
          pins[
            currentView
          ],
          currentView,
          popup,
          onPinClick
        );

      svgPanel.appendChild(
        svg
      );

      // ========================================================
      // REAL IMAGE PANEL
      // ========================================================

      const imagePanel =
        _makePanel(
          "Realistic Anatomy",
          "Image-based anatomical visualization"
        );

      const imageUrl =
        currentView === "front"
          ? realImageFront
          : realImageBack;

      const realMap =
        _buildRealImageMap(
          imageUrl,
          pins[
            currentView
          ],
          currentView,
          popup,
          onPinClick
        );

      imagePanel.appendChild(
        realMap
      );

      // ========================================================
      // ADD BOTH
      // ========================================================

      mapsWrap.appendChild(
        svgPanel
      );

      mapsWrap.appendChild(
        imagePanel
      );
    }

    // ==========================================================
    // RENDER
    // ==========================================================

    container.appendChild(
      header
    );

    container.appendChild(
      toggleWrap
    );

    container.appendChild(
      mapsWrap
    );

    redraw();

    // ==========================================================
    // CAPTION
    // ==========================================================

    const caption =
      document.createElement(
        "p"
      );

    caption.style.cssText =
      "text-align:center;" +
      "font-size:10px;" +
      "opacity:0.45;" +
      "margin-top:10px;";

    caption.textContent =
      "Approximate anatomical visualization — not a diagnostic image.";

    container.appendChild(
      caption
    );
  }

  // ============================================================
  // EXPORT
  // ============================================================

  global.renderBodyMap =
    renderBodyMap;

})(window);