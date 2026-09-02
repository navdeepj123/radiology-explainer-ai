(function (global) {
  "use strict";

  let _regionsCache = null;

  const SVG_NS = "http://www.w3.org/2000/svg";
  const XLINK_NS = "http://www.w3.org/1999/xlink";

  const DEFAULTS = {
    regionsUrl: "/static/data/body_regions.json",
    realImageFront: "/static/img/body-front.png",
    realImageBack: "/static/img/body-back.png"
  };

  const COLORS = {
    pin: "#f5a623",
    pinBorder: "#0d0e14",
    label: "#d7d8e2"
  };

    const CROP_SIZE = {
    heart: 220,
    left_lung: 260,
    right_lung: 260,
    kidney_left: 240,
    kidney_right: 240,
    adrenal_left: 220,
    adrenal_right: 220,
    head: 240,
    neck: 220,
    spine: 340,
    abdomen: 340,
    vascular_general: 340,
    pelvis: 310,
    ribs_left: 290,
    ribs_right: 290,
    shoulder_left: 240,
    shoulder_right: 240,
    breast_left: 220,
    breast_right: 220,
    arm_left: 260,
    arm_right: 260,
    leg_left: 310,
    leg_right: 310,
    musculoskeletal_general: 380
  };
  const DEFAULT_CROP_SIZE = 340;

  async function _loadRegions(url) {
  if (_regionsCache) {
    return _regionsCache;
  }

  const bustedUrl = url + (url.indexOf("?") === -1 ? "?" : "&") + "t=" + Date.now();
  const res = await fetch(bustedUrl);

    if (!res.ok) {
      throw new Error("Could not load body_regions.json");
    }

    _regionsCache = await res.json();

    return _regionsCache;
  }

  function _parseViewBox(vbString) {
    const parts = (vbString || "0 0 320 710").trim().split(/\s+/).map(Number);
    return {
      minX: parts[0] || 0,
      minY: parts[1] || 0,
      w: parts[2] || 320,
      h: parts[3] || 710
    };
  }

  function _extractSentence(searchText, reportText) {
    if (!reportText || !searchText) {
      return "";
    }

    const lower = reportText.toLowerCase();
    const idx = lower.indexOf(searchText.toLowerCase());

    if (idx === -1) {
      return "";
    }

    const start =
      Math.max(
        lower.lastIndexOf(".", idx),
        lower.lastIndexOf(";", idx),
        lower.lastIndexOf("\n", idx),
        lower.lastIndexOf("*", idx)
      ) + 1;

    let end = lower.indexOf(".", idx);

    if (end === -1) {
      end = lower.length;
    }

    return lower.slice(start, end);
  }

  // FIX 1: "bibasal", "bibasilar" jaise words bhi bilateral treat honge
  function _detectLaterality(sentence) {
    if (!sentence) {
      return "default";
    }

    if (
      /\bbilateral\b/.test(sentence) ||
      /\bboth\b/.test(sentence) ||
      /\bbilaterally\b/.test(sentence) ||
      /\bbibasal\b/.test(sentence) ||
      /\bbibasilar\b/.test(sentence) ||
      /\bbi-basal\b/.test(sentence)
    ) {
      return "bilateral";
    }

    if (/\bleft\b/.test(sentence) || /\blt\b/.test(sentence)) {
      return "left";
    }

    if (/\bright\b/.test(sentence) || /\brt\b/.test(sentence)) {
      return "right";
    }

    return "default";
  }

  function _resolveRegionKeys(regionSpec, laterality) {
    if (typeof regionSpec === "string") {
      return [regionSpec];
    }

    if (!regionSpec) {
      return [];
    }

    if (regionSpec.bilateral && laterality === "bilateral") {
      return regionSpec.bilateral;
    }

    if (regionSpec[laterality]) {
      return [regionSpec[laterality]];
    }

    if (regionSpec.default) {
      return [regionSpec.default];
    }

    return [];
  }

  function _regionFromContext(sentence, anatomyHints) {
    if (!sentence || !anatomyHints) {
      return null;
    }

    let bestHint = null;
    let bestLength = 0;

    Object.keys(anatomyHints).forEach(function (hint) {
      if (hint.length <= bestLength) {
        return;
      }
      if (sentence.indexOf(hint) !== -1) {
        bestHint = hint;
        bestLength = hint.length;
      }
    });

    return bestHint ? anatomyHints[bestHint] : null;
  }

  function _createElement(name, attrs) {
    const el = document.createElementNS(SVG_NS, name);

    Object.keys(attrs || {}).forEach(function (key) {
      el.setAttribute(key, attrs[key]);
    });

    return el;
  }

  function _append(svg, name, attrs) {
    const el = _createElement(name, attrs);
    svg.appendChild(el);
    return el;
  }

  function _buildOrganImage(organKey, imageUrl, region, vb) {
    const wrapper = document.createElement("div");
    wrapper.style.cssText =
      "width:100%;" +
      "max-width:200px;" +
      "aspect-ratio:1/1;" +
      "margin:0 auto;" +
      "overflow:hidden;" +
      "border-radius:8px;" +
      "background:#0b0d14;";

    const svg = document.createElementNS(SVG_NS, "svg");

    if (region && region.cx != null && region.cy != null) {
      const size = CROP_SIZE[organKey] || DEFAULT_CROP_SIZE;
      const half = size / 2;
      svg.setAttribute(
        "viewBox",
        (Number(region.cx) - half) + " " + (Number(region.cy) - half) + " " + size + " " + size
      );
    } else {
      svg.setAttribute("viewBox", vb.minX + " " + vb.minY + " " + vb.w + " " + vb.h);
    }

    svg.setAttribute("preserveAspectRatio", "xMidYMid slice");
    svg.style.cssText = "width:100%; height:100%; display:block;";

    const image = _createElement("image", {
      x: vb.minX,
      y: vb.minY,
      width: vb.w,
      height: vb.h,
      preserveAspectRatio: "xMidYMid slice"
    });

    image.setAttribute("href", imageUrl);
    image.setAttributeNS(XLINK_NS, "href", imageUrl);

    svg.appendChild(image);
    wrapper.appendChild(svg);

    return wrapper;
  }

  function _buildOrganFindingCard(organKey, findings, imageUrl, region, vb) {
    const card = document.createElement("div");
    card.style.cssText =
      "background:#0f1118;" +
      "border:1px solid #242735;" +
      "border-radius:10px;" +
      "padding:14px;" +
      "width:220px;" +
      "text-align:center;" +
      "box-sizing:border-box;";

    card.appendChild(_buildOrganImage(organKey, imageUrl, region, vb));

    const label = document.createElement("div");
    label.style.cssText =
      "font-size:13px; font-weight:600; color:#e5e6ee; margin-top:8px;";
    label.textContent = (region && region.label) || organKey;
    card.appendChild(label);

    findings.forEach(function (f) {
      const line = document.createElement("div");
      line.style.cssText =
        "font-size:11px; color:#aeb0c0; margin-top:6px; line-height:1.4; text-align:left;";

      const termSpan = document.createElement("span");
      termSpan.style.cssText = "color:#f5a623; font-weight:600; text-transform:capitalize;";
      termSpan.textContent = f.term;
      line.appendChild(termSpan);

      if (f.definition) {
        line.appendChild(document.createTextNode(" — " + f.definition));
      }

      if (f.approximate) {
        const note = document.createElement("span");
        note.style.cssText = "color:#6b6f80; font-style:italic;";
        note.textContent = " (approximate location)";
        line.appendChild(note);
      }

      card.appendChild(line);
    });

    return card;
  }

  function _makePopup() {
    let popup = document.getElementById("cs-body-map-popup");

    if (popup) {
      return popup;
    }

    popup = document.createElement("div");
    popup.id = "cs-body-map-popup";

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

    document.body.appendChild(popup);
    return popup;
  }

  // FIX 2 support: popup ab ek se zyada findings dikha sakta hai (merged pin)
  function _showPopup(popup, x, y, findings) {
    let html = "";

    findings.forEach(function (f, idx) {
      html +=
        '<div style="' +
        (idx > 0 ? "margin-top:8px;padding-top:8px;border-top:1px solid #2a2c3a;" : "") +
        '">' +
        '<div style="font-weight:600;color:#8b8cf5;margin-bottom:4px;text-transform:capitalize;">' +
        f.term +
        "</div>" +
        "<div>" +
        (f.definition || "No definition available.") +
        "</div>" +
        "</div>";
    });

    popup.innerHTML = html;
    popup.style.left = x + 14 + "px";
    popup.style.top = y + 14 + "px";
    popup.style.display = "block";
  }

  function _hidePopup(popup) {
    popup.style.display = "none";
  }

  // FIX 2: pin ab ek array of findings leta hai (merged), na ki sirf ek term
  function _drawPin(svg, pin, popup, onPinClick) {
    const group = _append(svg, "g", {
      "data-term": pin.findings.map(function (f) { return f.term; }).join(", ")
    });
    group.style.cursor = "pointer";

    _append(group, "circle", { cx: pin.cx, cy: pin.cy, r: 18, fill: "transparent" });

    const pulse = _append(group, "circle", {
      cx: pin.cx,
      cy: pin.cy,
      r: 13,
      fill: COLORS.pin,
      opacity: "0.22"
    });

    const dot = _append(group, "circle", {
      cx: pin.cx,
      cy: pin.cy,
      r: 6,
      fill: COLORS.pin,
      stroke: COLORS.pinBorder,
      "stroke-width": "2"
    });

    _append(group, "circle", { cx: pin.cx, cy: pin.cy, r: 2, fill: "#fff" });

    // Agar is pin pe ek se zyada finding hai, ek chhota badge number dikhao
    if (pin.findings.length > 1) {
      _append(group, "circle", {
        cx: pin.cx + 8,
        cy: pin.cy - 8,
        r: 6,
        fill: "#8b8cf5",
        stroke: COLORS.pinBorder,
        "stroke-width": "1"
      });

      const badgeText = _append(group, "text", {
        x: pin.cx + 8,
        y: pin.cy - 5,
        fill: "#fff",
        "font-size": "7",
        "font-family": "Arial, sans-serif",
        "text-anchor": "middle",
        "font-weight": "bold"
      });
      badgeText.textContent = String(pin.findings.length);
    }

    group.addEventListener("mouseenter", function (e) {
      _showPopup(popup, e.clientX, e.clientY, pin.findings);
      pulse.setAttribute("r", "17");
      pulse.setAttribute("opacity", "0.35");
      dot.setAttribute("r", "7");
    });

    group.addEventListener("mousemove", function (e) {
      popup.style.left = e.clientX + 14 + "px";
      popup.style.top = e.clientY + 14 + "px";
    });

    group.addEventListener("mouseleave", function () {
      _hidePopup(popup);
      pulse.setAttribute("r", "13");
      pulse.setAttribute("opacity", "0.22");
      dot.setAttribute("r", "6");
    });

    group.addEventListener("click", function () {
      if (typeof onPinClick === "function") {
        pin.findings.forEach(function (f) {
          onPinClick(f.term, f.definition, pin);
        });
      }
    });

    return group;
  }

  function _buildRealImageMap(imageUrl, pins, view, popup, onPinClick, vb) {
    const wrapper = document.createElement("div");
    wrapper.className = "cs-real-anatomy-map";

    wrapper.style.cssText =
      "position:relative;" +
      "width:100%;" +
      "max-width:420px;" +
      "margin:0 auto;" +
      "overflow:hidden;" +
      "border-radius:8px;" +
      "background:#0b0d14;" +
      "line-height:0;";

    const image = document.createElement("img");
    image.src = imageUrl;
    image.alt =
      view === "front"
        ? "Anatomical front view with detected findings"
        : "Anatomical back view with detected findings";
    image.draggable = false;

    image.style.cssText =
      "display:block;" +
      "width:100%;" +
      "height:auto;";

    const overlay = document.createElementNS(SVG_NS, "svg");
    overlay.setAttribute("viewBox", vb.minX + " " + vb.minY + " " + vb.w + " " + vb.h);
    overlay.setAttribute("preserveAspectRatio", "none");

    overlay.style.cssText =
      "position:absolute;" +
      "inset:0;" +
      "width:100%;" +
      "height:100%;" +
      "pointer-events:none;";

    pins.forEach(function (pin) {
      const group = _drawPin(overlay, pin, popup, onPinClick);
      group.style.pointerEvents = "all";
    });

    wrapper.appendChild(image);
    wrapper.appendChild(overlay);

    image.addEventListener("error", function () {
      wrapper.innerHTML =
        '<div style="' +
        "height:200px;" +
        "display:flex;" +
        "align-items:center;" +
        "justify-content:center;" +
        "text-align:center;" +
        "padding:20px;" +
        "box-sizing:border-box;" +
        "color:#777;" +
        "font-size:12px;" +
        '">' +
        "Anatomical image could not be loaded.<br><br><small>" +
        imageUrl +
        "</small></div>";
    });

    return wrapper;
  }

  function _makePanel(title, subtitle) {
    const panel = document.createElement("div");

    panel.style.cssText =
      "width:100%;" +
      "max-width:460px;" +
      "background:#0f1118;" +
      "border:1px solid #242735;" +
      "border-radius:10px;" +
      "padding:12px;" +
      "box-sizing:border-box;";

    const heading = document.createElement("div");
    heading.style.cssText =
      "font-size:13px; font-weight:600; color:#e5e6ee; margin-bottom:3px;";
    heading.textContent = title;

    const sub = document.createElement("div");
    sub.style.cssText = "font-size:10px; color:#777b8c; margin-bottom:10px;";
    sub.textContent = subtitle;

    panel.appendChild(heading);
    panel.appendChild(sub);

    return panel;
  }

  async function renderBodyMap(opts) {
    opts = opts || {};

    const container = opts.container;
    const detectedTerms = opts.detectedTerms || [];
    const reportText = opts.reportText || "";
    const regionsUrl = opts.regionsUrl || DEFAULTS.regionsUrl;
    const realImageFront = opts.realImageFront || DEFAULTS.realImageFront;
    const realImageBack = opts.realImageBack || DEFAULTS.realImageBack;
    const onPinClick = opts.onPinClick || null;

    if (!container) {
      console.error("renderBodyMap: container element required");
      return;
    }

    let regionData;

    try {
      regionData = await _loadRegions(regionsUrl);
    } catch (e) {
      console.error(e);
      container.innerHTML =
        '<p style="text-align:center;color:#888;">Unable to load anatomical map.</p>';
      return;
    }

    const vb = _parseViewBox(regionData.viewBox);
    const anatomyHints = regionData.anatomy_hints || null;

    // FIX 2: pins ab region-key ke hisaab se group hote hain, taaki
    // same jagah pe do findings overlapping alag markers na banayen —
    // ek hi marker mein saari findings ek array ke roop mein rahengi.
    const pinsByKey = { front: {}, back: {} };
    const organFindings = {};
    const usedRegions = new Set();

    detectedTerms.forEach(function (entry) {
      const termName = (entry.term || "").toLowerCase().trim();
      const mapEntry = regionData.term_map ? regionData.term_map[termName] : null;

      const searchText = entry.matched_text || entry.term || "";
      const sentence =
        (entry.context_sentence || "").toLowerCase() ||
        _extractSentence(searchText, reportText);

      const laterality = _detectLaterality(sentence);

      let regionKeys = [];
      let isApproximate = false;

                  if (mapEntry) {
        regionKeys = _resolveRegionKeys(mapEntry.region, laterality);

        if (regionKeys.length === 1 && regionKeys[0] === "musculoskeletal_general" && anatomyHints) {
          const refined = _regionFromContext(sentence, anatomyHints);
          if (refined) {
            regionKeys = _resolveRegionKeys(refined, laterality);
            isApproximate = true;
          }
        }
      } else if (anatomyHints) {
        const hintRegion = _regionFromContext(sentence, anatomyHints);

        if (hintRegion) {
          regionKeys = _resolveRegionKeys(hintRegion, laterality);
          isApproximate = true;
        }
      }

      if (regionKeys.length === 0) {
        return;
      }

      regionKeys.forEach(function (key) {
        const region = regionData.regions[key];

        if (!region) {
          return;
        }

        const dedupeKey = termName + ":" + key;

        if (usedRegions.has(dedupeKey)) {
          return;
        }

        usedRegions.add(dedupeKey);

        const view = region.view === "back" ? "back" : "front";

        const findingEntry = {
          term: entry.term || termName,
          definition: entry.meaning || entry.definition || "",
          severity: entry.severity || null,
          approximate: isApproximate
        };

        // Agar is region+view pe pehle se pin hai, usi mein finding add karo
        if (pinsByKey[view][key]) {
          pinsByKey[view][key].findings.push(findingEntry);
        } else {
          pinsByKey[view][key] = {
            cx: Number(region.cx),
            cy: Number(region.cy),
            findings: [findingEntry]
          };
        }

        if (!organFindings[key]) {
          organFindings[key] = [];
        }

        organFindings[key].push({
          term: entry.term || termName,
          definition: entry.meaning || entry.definition || "",
          approximate: isApproximate
        });
      });
    });

    // pinsByKey ko flat array mein convert karo (front/back ke liye)
    const pins = {
      front: Object.keys(pinsByKey.front).map(function (k) { return pinsByKey.front[k]; }),
      back: Object.keys(pinsByKey.back).map(function (k) { return pinsByKey.back[k]; })
    };

    const totalPins = pins.front.length + pins.back.length;
    const popup = _makePopup();

    container.innerHTML = "";

  if (totalPins === 0) {
  const hasDetectedTerms = detectedTerms.length > 0;

  const emptyPanel = _makePanel(
    "Anatomical Visualization",
    hasDetectedTerms
      ? "Findings detected, but exact location could not be determined from the report text"
      : "No mappable findings detected"
  );

  emptyPanel.appendChild(
    _buildRealImageMap(realImageFront, [], "front", popup, onPinClick, vb)
  );
  container.appendChild(emptyPanel);

  const note = document.createElement("p");
  note.style.cssText =
    "text-align:center; font-size:10px; opacity:0.45; margin-top:8px;";
  note.textContent = hasDetectedTerms
    ? "See the Key Findings and Medical Terms sections above for full details."
    : "Approximate anatomical visualization — not a diagnostic image.";
  container.appendChild(note);

  return;
}

    let currentView = pins.front.length >= pins.back.length ? "front" : "back";

    const header = document.createElement("div");
    header.style.cssText = "margin-bottom:12px;";

    const title = document.createElement("div");
    title.style.cssText = "font-size:14px; font-weight:600; color:#e5e6ee;";
    title.textContent = "Anatomical Findings";

    const subtitle = document.createElement("div");
    subtitle.style.cssText = "font-size:10px; color:#777b8c; margin-top:2px;";
    subtitle.textContent = "Approximate location of detected findings";

    header.appendChild(title);
    header.appendChild(subtitle);

    const toggleWrap = document.createElement("div");
    toggleWrap.style.cssText =
      "display:flex; gap:6px; justify-content:center; margin-bottom:14px;";

    const mapsWrap = document.createElement("div");
    mapsWrap.style.cssText = "display:flex; justify-content:center; width:100%;";

    const findingsContainer = document.createElement("div");
    findingsContainer.id = "cs-organ-findings";
    findingsContainer.style.cssText =
      "display:flex; gap:12px; flex-wrap:wrap; justify-content:center; margin-top:16px; width:100%;";

    function makeToggleBtn(label, viewName) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label + " (" + pins[viewName].length + ")";

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

      btn.addEventListener("mouseenter", function () {
        if (currentView !== viewName) {
          btn.style.borderColor = "#8b8cf5";
        }
      });

      btn.addEventListener("mouseleave", function () {
        if (currentView !== viewName) {
          btn.style.borderColor = "#2a2c3a";
        }
      });

      btn.addEventListener("click", function () {
        currentView = viewName;
        redraw();
      });

      return btn;
    }

    function redraw() {
      toggleWrap.innerHTML = "";

      const frontBtn = makeToggleBtn("Front", "front");
      const backBtn = makeToggleBtn("Back", "back");
      const active = currentView === "front" ? frontBtn : backBtn;

      active.style.background = "#8b8cf5";
      active.style.color = "#fff";
      active.style.borderColor = "#8b8cf5";

      toggleWrap.appendChild(frontBtn);
      toggleWrap.appendChild(backBtn);

      mapsWrap.innerHTML = "";

      const imagePanel = _makePanel(
        "Anatomical Findings",
        "Detected findings on anatomical scan"
      );
      const imageUrl = currentView === "front" ? realImageFront : realImageBack;
      imagePanel.appendChild(
        _buildRealImageMap(imageUrl, pins[currentView], currentView, popup, onPinClick, vb)
      );

      mapsWrap.appendChild(imagePanel);

      findingsContainer.innerHTML = "";

      Object.keys(organFindings).forEach(function (organKey) {
        const region = regionData.regions[organKey];

        if (!region) {
          return;
        }

        const cardImageUrl = region.view === "back" ? realImageBack : realImageFront;

        findingsContainer.appendChild(
          _buildOrganFindingCard(organKey, organFindings[organKey], cardImageUrl, region, vb)
        );
      });
    }

    container.appendChild(header);
    container.appendChild(toggleWrap);
    container.appendChild(mapsWrap);
    container.appendChild(findingsContainer);

    redraw();

    const caption = document.createElement("p");
    caption.style.cssText =
      "text-align:center; font-size:10px; opacity:0.45; margin-top:10px;";
    caption.textContent =
      "Approximate anatomical visualization — not a diagnostic image.";
    container.appendChild(caption);
  }

  global.renderBodyMap = renderBodyMap;

})(window);