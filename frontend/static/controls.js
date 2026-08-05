// ═══ ClearScan Shared Controls: Font Size + Language ═══
(function () {

  var style = document.createElement("style");
  style.textContent = `
    .ctrl-wrap{position:relative;display:inline-block}
    .ctrl-btn{display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border:1px solid var(--border2,#1e2d45);border-radius:6px;font-size:.78rem;color:var(--muted,#7a8aaa);background:var(--card,#111827);cursor:pointer;font-family:inherit;transition:border-color .15s,color .15s}
    .ctrl-btn:hover{border-color:#2a3f66;color:var(--text,#e8eaf0)}
    .ctrl-dropdown{position:absolute;top:38px;right:0;min-width:150px;max-height:320px;overflow-y:auto;background:var(--card,#111827);border:1px solid var(--border2,#1e2d45);border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.45);display:none;flex-direction:column;padding:.4rem;z-index:400}
    .ctrl-dropdown.open{display:flex}
    .ctrl-item{padding:.5rem .65rem;border-radius:6px;font-size:.8rem;color:var(--text,#e8eaf0);cursor:pointer;transition:background .15s}
    .ctrl-item:hover{background:var(--card2,#141e30)}
    .ctrl-item.active{color:var(--blue,#4f7cff);font-weight:600}
    .ctrl-section{font-size:.62rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--dim,#3d4f6e);padding:.5rem .65rem .25rem}
    html[data-fontsize="s"]{font-size:87.5%}
    html[data-fontsize="m"]{font-size:100%}
    html[data-fontsize="l"]{font-size:112.5%}
    html[data-fontsize="xl"]{font-size:125%}
    html[data-fontsize="xxl"]{font-size:140%}
  `;
  document.head.appendChild(style);

  var LANGUAGES = {
    "English": "en", "Hinglish": "hinglish",
    "__section_indian": "Indian Languages",
    "Hindi": "hi", "Bengali": "bn", "Telugu": "te", "Marathi": "mr",
    "Tamil": "ta", "Urdu": "ur", "Gujarati": "gu", "Kannada": "kn",
    "Malayalam": "ml", "Punjabi": "pa",
    "__section_intl": "International",
    "French": "fr", "Spanish": "es", "Arabic": "ar", "Chinese": "zh",
    "German": "de", "Portuguese": "pt", "Russian": "ru", "Japanese": "ja"
  };
  var FONT_SIZES = ["S", "M", "L", "XL", "XXL"];

  function injectControls(targetSelector) {
    var target = document.querySelector(targetSelector);
    if (!target) return;

    var fontWrap = document.createElement("div");
    fontWrap.className = "ctrl-wrap";
    fontWrap.innerHTML =
      '<button class="ctrl-btn" id="fontBtn">Aa ▾</button>' +
      '<div class="ctrl-dropdown" id="fontDropdown">' +
      FONT_SIZES.map(function (s) {
        return '<div class="ctrl-item" data-size="' + s.toLowerCase() + '">' + s + '</div>';
      }).join("") + '</div>';

    var langWrap = document.createElement("div");
    langWrap.className = "ctrl-wrap";
    var langItemsHtml = "";
    Object.keys(LANGUAGES).forEach(function (key) {
      if (key.indexOf("__section") === 0) {
        langItemsHtml += '<div class="ctrl-section">' + LANGUAGES[key] + '</div>';
      } else {
        langItemsHtml += '<div class="ctrl-item" data-lang="' + LANGUAGES[key] + '" data-langname="' + key + '">' + key + '</div>';
      }
    });
    langWrap.innerHTML =
      '<button class="ctrl-btn" id="langBtn">English ▾</button>' +
      '<div class="ctrl-dropdown" id="langDropdown">' + langItemsHtml + '</div>';

    target.appendChild(fontWrap);
    target.appendChild(langWrap);

    document.getElementById("fontBtn").onclick = function (e) {
      e.stopPropagation();
      document.getElementById("langDropdown").classList.remove("open");
      document.getElementById("fontDropdown").classList.toggle("open");
    };
    document.getElementById("langBtn").onclick = function (e) {
      e.stopPropagation();
      document.getElementById("fontDropdown").classList.remove("open");
      document.getElementById("langDropdown").classList.toggle("open");
    };
    document.addEventListener("click", function () {
      document.getElementById("fontDropdown").classList.remove("open");
      document.getElementById("langDropdown").classList.remove("open");
    });

    document.querySelectorAll("#fontDropdown .ctrl-item").forEach(function (el) {
      el.onclick = function () { setFontSize(this.dataset.size); };
    });
    document.querySelectorAll("#langDropdown .ctrl-item[data-lang]").forEach(function (el) {
      el.onclick = function () { setLanguage(this.dataset.lang, this.dataset.langname); };
    });

    applySavedFontSize();
    applySavedLanguage();
  }

  function setFontSize(size) {
    document.documentElement.setAttribute("data-fontsize", size);
    try { localStorage.setItem("clearscan-fontsize", size); } catch (e) {}
    document.querySelectorAll("#fontDropdown .ctrl-item").forEach(function (el) {
      el.classList.toggle("active", el.dataset.size === size);
    });
  }
  function applySavedFontSize() {
    var saved = "m";
    try { saved = localStorage.getItem("clearscan-fontsize") || "m"; } catch (e) {}
    setFontSize(saved);
  }
  function setLanguage(code, name) {
    try {
      localStorage.setItem("clearscan-lang", code);
      localStorage.setItem("clearscan-lang-name", name);
    } catch (e) {}
    document.getElementById("langBtn").textContent = name + " ▾";
    document.querySelectorAll("#langDropdown .ctrl-item[data-lang]").forEach(function (el) {
      el.classList.toggle("active", el.dataset.lang === code);
    });
  }
  function applySavedLanguage() {
    var code = "en", name = "English";
    try {
      code = localStorage.getItem("clearscan-lang") || "en";
      name = localStorage.getItem("clearscan-lang-name") || "English";
    } catch (e) {}
    setLanguage(code, name);
  }

  window.ClearScanControls = {
    getLanguage: function () {
      try { return localStorage.getItem("clearscan-lang") || "en"; } catch (e) { return "en"; }
    },
    getLanguageName: function () {
      try { return localStorage.getItem("clearscan-lang-name") || "English"; } catch (e) { return "English"; }
    },
    init: injectControls
  };
})();