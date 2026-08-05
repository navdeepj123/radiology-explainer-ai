// ═══ ClearScan Voice: Speech-to-Text (mic) + Text-to-Speech (speaker) ═══
// Pure browser-based, koi API key/cost nahi. Chrome/Edge mein best kaam karta hai.

(function () {

  // ── STYLES (auto-injected) ──
  var style = document.createElement("style");
  style.textContent = `
    .mic-btn{width:30px;height:30px;flex-shrink:0;display:flex;align-items:center;justify-content:center;background:transparent;border:none;cursor:pointer;color:var(--muted,#7a8aaa);border-radius:6px;transition:background .15s,color .15s}
    .mic-btn:hover{background:var(--card,#111827);color:var(--text,#e8eaf0)}
    .mic-btn.listening{color:#ef4444;animation:mic-pulse 1.2s ease-in-out infinite}
    @keyframes mic-pulse{0%,100%{opacity:1}50%{opacity:.4}}
    .speak-btn{font-size:.69rem;color:var(--muted,#7a8aaa);background:transparent;border:1px solid var(--border,#1a2540);padding:3px 9px;border-radius:5px;cursor:pointer;transition:color .15s,border-color .15s;display:inline-flex;align-items:center;gap:4px}
    .speak-btn:hover{color:var(--text,#e8eaf0);border-color:var(--border2,#1e2d45)}
    .speak-btn.speaking{color:var(--blue,#4f7cff);border-color:var(--blue,#4f7cff)}
    .bubble-speak{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;margin-top:4px;background:transparent;border:none;cursor:pointer;color:var(--dim,#3d4f6e);border-radius:4px;transition:color .15s,background .15s;font-size:.8rem}
    .bubble-speak:hover{color:var(--text,#e8eaf0);background:var(--card2,#141e30)}
    .bubble-speak.speaking{color:var(--blue,#4f7cff)}
  `;
  document.head.appendChild(style);

  // ── STATE ──
  var SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
  var activeRecognition = null;
  var activeMicBtn      = null;
  var activeUtterance   = null;
  var activeSpeakBtn    = null;

  // ── MIC ICON SVG (reused everywhere) ──
  var MIC_SVG =
    '<svg width="15" height="15" viewBox="0 0 15 15" fill="none">' +
    '<path d="M7.5 1.5a2 2 0 012 2v4a2 2 0 01-4 0v-4a2 2 0 012-2z" stroke="currentColor" stroke-width="1.4"/>' +
    '<path d="M3.5 7.5a4 4 0 008 0M7.5 11.5v2M5.5 13.5h4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>' +
    '</svg>';

  // ── PUBLIC: create a mic button element ──
  function createMicButton(textareaId, growFnName) {
    var btnId = 'mic-' + textareaId + '-' + Math.random().toString(36).slice(2, 7);
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.id = btnId;
    btn.className = 'mic-btn';
    btn.title = 'Speak';
    btn.innerHTML = MIC_SVG;
    btn.onclick = function () { toggleMic(textareaId, btnId, growFnName); };
    return btn;
  }

  // ── SPEECH-TO-TEXT ──
  function toggleMic(textareaId, micBtnId, growFnName) {
    if (!SpeechRecognitionAPI) {
      alert('Voice input is not supported in this browser. Please use Chrome or Edge.');
      return;
    }

    var micBtn = document.getElementById(micBtnId);
    var ta = document.getElementById(textareaId);
    if (!micBtn || !ta) return;

    if (activeRecognition) {
      activeRecognition.stop();
      return;
    }

    var recognition = new SpeechRecognitionAPI();
    recognition.lang = 'en-IN';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = function () {
      activeRecognition = recognition;
      activeMicBtn = micBtn;
      micBtn.classList.add('listening');
    };

    recognition.onresult = function (event) {
      var transcript = event.results[0][0].transcript;
      var existing = ta.value.trim();
      ta.value = existing ? existing + ' ' + transcript : transcript;
      if (growFnName && window[growFnName]) window[growFnName](ta);
      ta.focus();
    };

    recognition.onerror = function () {
      micBtn.classList.remove('listening');
      activeRecognition = null;
    };

    recognition.onend = function () {
      micBtn.classList.remove('listening');
      activeRecognition = null;
      activeMicBtn = null;
    };

    recognition.start();
  }

  // ── TEXT-TO-SPEECH ──
  function speakText(text, btn) {
    if (!window.speechSynthesis) {
      alert('Voice output is not supported in this browser.');
      return;
    }

    if (activeUtterance && activeSpeakBtn === btn) {
      window.speechSynthesis.cancel();
      btn.classList.remove('speaking');
      activeUtterance = null;
      activeSpeakBtn = null;
      return;
    }

    window.speechSynthesis.cancel();
    if (activeSpeakBtn) activeSpeakBtn.classList.remove('speaking');

    var tmp = document.createElement('div');
    tmp.innerHTML = text;
    var plainText = tmp.textContent || tmp.innerText || '';

    var utter = new SpeechSynthesisUtterance(plainText);
    utter.rate = 0.95;
    utter.onend = function () {
      btn.classList.remove('speaking');
      activeUtterance = null;
      activeSpeakBtn = null;
    };

    activeUtterance = utter;
    activeSpeakBtn = btn;
    btn.classList.add('speaking');
    window.speechSynthesis.speak(utter);
  }

  // ── PUBLIC: create a "Read Aloud" button for a bot bubble ──
  function createSpeakButton(getTextFn, small) {
    var btn = document.createElement('button');
    btn.type = 'button';
    if (small) {
      btn.className = 'bubble-speak';
      btn.title = 'Read aloud';
      btn.innerHTML = '🔊';
    } else {
      btn.className = 'ba-btn speak-btn';
      btn.innerHTML = '🔊 Read Aloud';
    }
    btn.onclick = function () { speakText(getTextFn(), btn); };
    return btn;
  }

  window.ClearScanVoice = {
    toggleMic: toggleMic,
    speakText: speakText,
    createMicButton: createMicButton,
    createSpeakButton: createSpeakButton,
    micSvg: MIC_SVG
  };
})();