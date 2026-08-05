// ─────────────────────────────────────────
// THEME (dark / light)
// ─────────────────────────────────────────
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  var icon = document.getElementById('themeIcon');
  if (icon) icon.textContent = (t === 'light') ? '☀️' : '🌙';
  try { localStorage.setItem('clearscan-theme', t); } catch (e) {}
}
function toggleTheme() {
  var cur = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(cur === 'dark' ? 'light' : 'dark');
}
(function initTheme() {
  var saved = 'dark';
  try { saved = localStorage.getItem('clearscan-theme') || 'dark'; } catch (e) {}
  applyTheme(saved);
})();

ClearScanControls.init("#ctrlSlot");

// ── voice mic icons load karo ──
document.getElementById('mainMicBtn').innerHTML = ClearScanVoice.micSvg;
document.getElementById('csMicBtn').innerHTML   = ClearScanVoice.micSvg;

// ─────────────────────────────────────────
// STATE
// ─────────────────────────────────────────
var provider     = 'groq';
var ollamaModel  = 'llama3.2:1b';
var answerLength = 'standard';
var detailLevel  = 'medium';
var selFile      = null;
var isAnalyzed   = false;
var savedText    = '';
var historyArr   = [];
var lastText     = '';
var lastFile     = null;

var provData = {
  groq:   { tag:'⚡ GROQ',   shortTag:'GROQ',   hint:'Fast and free. Report sent to Groq servers.',   name:'Groq'   },
  gemini: { tag:'✨ GEMINI', shortTag:'GEMINI', hint:'Free via OpenRouter. Report sent to Google.',   name:'Gemini' },
  openai: { tag:'🤖 OPENAI', shortTag:'OPENAI', hint:'GPT-4o-mini. Requires paid API key.',           name:'OpenAI' },
  ollama: { tag:'🖥️ LOCAL',  shortTag:'LOCAL',  hint:'Runs locally on your computer.',               name:'Ollama' }
};

var ollamaHints = {
  'llama3.2:1b': '⚡ Fast responses, good for Q&A.',
  'mistral':     '🧠 Better quality analysis, slower.'
};

// ─────────────────────────────────────────
// HISTORY
// ─────────────────────────────────────────
function addToHistory(reportText, riskLevel, prov) {
  var now  = new Date();
  var time = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
  historyArr.unshift({
    preview: reportText.substring(0, 80).trim(),
    risk:    (riskLevel || 'unknown').toLowerCase(),
    prov:    prov.toUpperCase(),
    time:    time
  });
  if (historyArr.length > 5) historyArr.pop();
  var list  = document.getElementById('sbHistList');
  var empty = document.getElementById('sbHistEmpty');
  if (empty) empty.style.display = 'none';
  list.querySelectorAll('.sh-item').forEach(function(el){ el.remove(); });
  historyArr.forEach(function(item) {
    var rLabel = item.risk==='high'   ? '🔴 High risk'
               : item.risk==='medium' ? '🟡 Medium risk'
               : item.risk==='low'    ? '🟢 Low risk'
               :                        '⚪ Unknown';
    var div = document.createElement('div');
    div.className = 'sh-item';
    div.innerHTML =
      '<div class="sh-top">'
        + '<span class="sh-prov">'+item.prov+'</span>'
        + '<span class="sh-time">'+item.time+'</span>'
      + '</div>'
      + '<div class="sh-preview">'+escHtml(item.preview)+'…</div>'
      + '<div class="sh-risk '+item.risk+'">'+rLabel+'</div>';
    list.appendChild(div);
  });
}

// ─────────────────────────────────────────
// PROVIDER CHANGE
// ─────────────────────────────────────────
function onProviderChange(val) {
  provider = val;
  var d = provData[val] || provData['groq'];
  document.getElementById('sbHint').textContent       = d.hint;
  document.getElementById('provTag').textContent      = d.tag;
  document.getElementById('csChatTag').textContent    = d.shortTag;
  document.getElementById('csNoticeProv').textContent = d.name;

  document.getElementById('sbOllamaWrap').style.display = (val === 'ollama') ? 'block' : 'none';

  var sidebar = document.getElementById('chatSidebar');
  if (val === 'ollama') {
    sidebar.classList.add('hidden');
  } else {
    sidebar.classList.remove('hidden');
  }
}

// ─────────────────────────────────────────
// OLLAMA MODEL CHANGE
// ─────────────────────────────────────────
function onOllamaModelChange(val) {
  ollamaModel = val;
  document.getElementById('ollamaModelHint').textContent = ollamaHints[val] || '';
}

// ─────────────────────────────────────────
// RESPONSE STYLE CHANGE
// ─────────────────────────────────────────
function onLengthChange(val) {
  answerLength = val;
}
function onDetailChange(val) {
  detailLevel = val;
}

// ─────────────────────────────────────────
// INPUT HELPERS
// ─────────────────────────────────────────
function onMainGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}
function onFocusInput() {
  document.getElementById('mainTa').focus();
}
function onLoadSample() {
  var ta = document.getElementById('mainTa');
  ta.value = 'CHEST X-RAY PA VIEW\n\nFINDINGS: Mild cardiomegaly is noted. Small left pleural effusion is present. Mild bibasal atelectatic changes are seen. No focal consolidation. No pneumothorax. No acute fracture identified.\n\nIMPRESSION:\n1. Mild cardiomegaly.\n2. Small left pleural effusion.\n3. Mild bibasal atelectatic changes.\n4. No emergency chest abnormality detected.';
  onMainGrow(ta);
  ta.focus();
}
function fileExt(name) {
  var i = name.lastIndexOf('.');
  return i > -1 ? name.slice(i + 1).toUpperCase() : 'FILE';
}
function onFileSelect(input) {
  if (!input.files.length) return;
  selFile = input.files[0];
  document.getElementById('attName').textContent  = selFile.name;
  document.getElementById('attBadge').textContent = fileExt(selFile.name);
  document.getElementById('attRow').style.display = 'block';
}
function clearFile() {
  selFile = null;
  document.getElementById('fileInput').value = '';
  document.getElementById('attRow').style.display = 'none';
}

// ─────────────────────────────────────────
// MAIN SEND
// ─────────────────────────────────────────
function onMainSend() {
  var text = document.getElementById('mainTa').value.trim();
  if (!text && !selFile) {
    showErr('Please paste your report or attach a file.');
    return;
  }
  hideErr();
  removeEmpty();
  savedText = text;
  lastText  = text;
  lastFile  = selFile;
  appendUserBubble(text, selFile);
  var ta = document.getElementById('mainTa');
  ta.value = '';
  ta.style.height = 'auto';
  runAnalysis(text, selFile);
  clearFile();
}

// Shared by the send button and the regenerate button
function runAnalysis(text, file) {
  document.getElementById('mainSendBtn').disabled = true;
  document.getElementById('statusPill').textContent = 'Analyzing…';
  var typId = showMainTyping();
  var fd = new FormData();
  if (text) fd.append('report_text', text);
  if (file) fd.append('report_file', file);
  fd.append('provider', provider);
  if (provider === 'ollama') fd.append('ollama_model', ollamaModel);
  fd.append('language', ClearScanControls.getLanguageName());
  fd.append('answer_length', answerLength);
  fd.append('detail_level', detailLevel);
  fetch('/analyze_ajax', { method: 'POST', body: fd })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      removeTyping(typId);
      if (data.error) {
        showErr(data.error);
        document.getElementById('statusPill').textContent = 'Error';
      } else {
        renderBotResult(data);
        activateChatbot();
        addToHistory(savedText, data.risk_level, provider);
        isAnalyzed = true;
        document.getElementById('statusPill').textContent = 'Analysis complete';
        document.getElementById('inputArea').style.display    = 'none';
        document.getElementById('newReportBar').style.display = 'flex';
      }
    })
    .catch(function() {
      removeTyping(typId);
      showErr('Something went wrong. Please check your connection and try again.');
      document.getElementById('statusPill').textContent = 'Error';
    })
    .finally(function() {
      document.getElementById('mainSendBtn').disabled = false;
      document.querySelectorAll('.ub-btn').forEach(function(b){ b.disabled = false; });
    });
}

// ─────────────────────────────────────────
// REGENERATE
// ─────────────────────────────────────────
function onRegenerate(btn) {
  if (!lastText && !lastFile) return;
  var row = btn.closest('.msg-row');
  if (!row) return;

  while (row.nextSibling) row.parentNode.removeChild(row.nextSibling);

  resetChatPanel();
  isAnalyzed = false;
  document.querySelectorAll('.ub-btn').forEach(function(b){ b.disabled = true; });
  runAnalysis(lastText, lastFile);
}

function resetChatPanel() {
  document.getElementById('csMsgs').innerHTML =
    '<div class="cs-notice" id="csNotice">'
    + '<div class="cs-notice-icon">🫁</div>'
    + '<p>Submit your radiology report first, then I\'ll be able to answer your questions about it.</p>'
    + '<small>Powered by <span id="csNoticeProv">'
    + (provData[provider]||provData['groq']).name
    + '</span></small>'
    + '</div>';
  document.getElementById('csTa').disabled      = true;
  document.getElementById('csSendBtn').disabled = true;
}

function onCopyUser(btn) {
  var row = btn.closest('.msg-row');
  var bub = row ? row.querySelector('.user-bubble') : null;
  navigator.clipboard.writeText(bub ? bub.innerText : '').then(function() {
    btn.style.color = '#10B981';
    setTimeout(function(){ btn.style.color = ''; }, 1500);
  });
}

// ─────────────────────────────────────────
// NEW REPORT
// ─────────────────────────────────────────
function onNewReport() {
  isAnalyzed = false;
  savedText  = '';
  document.getElementById('inputArea').style.display    = 'block';
  document.getElementById('newReportBar').style.display = 'none';
  document.getElementById('mainTa').value        = '';
  document.getElementById('mainTa').style.height = 'auto';
  document.getElementById('mainTa').placeholder  = 'Paste your radiology report here…';
  document.getElementById('statusPill').textContent     = 'Ready';
  document.getElementById('mainSendBtn').disabled       = false;
  document.getElementById('mainTa').focus();
  document.getElementById('csMsgs').innerHTML =
    '<div class="cs-notice" id="csNotice">'
    + '<div class="cs-notice-icon">🫁</div>'
    + '<p>Submit your radiology report first, then I\'ll be able to answer your questions about it.</p>'
    + '<small>Powered by <span id="csNoticeProv">'
    + (provData[provider]||provData['groq']).name
    + '</span></small>'
    + '</div>';
  document.getElementById('csTa').disabled      = true;
  document.getElementById('csSendBtn').disabled = true;
}

// ─────────────────────────────────────────
// ACTIVATE CHATBOT
// ─────────────────────────────────────────
function activateChatbot() {
  if (provider === 'ollama') {
    var msgs = document.getElementById('msgs');
    var card = document.createElement('div');
    card.className = 'msg-row bot';
    var modelLabel = ollamaModel === 'mistral' ? '🧠 mistral' : '⚡ llama3.2:1b';
    card.innerHTML =
      '<div class="msg-meta">ClearScan Assistant · 🖥️ LOCAL · ' + modelLabel + '</div>'
      + '<div class="ollama-chat">'
        + '<div class="ollama-chat-head">🔒 Local Chat — Ask questions about your report</div>'
        + '<div class="ollama-chat-msgs" id="ocMsgs">'
          + '<div class="oc-bubble bot">Hi! I\'ve read your report. Ask me anything about it 😊 (Running locally via Ollama — fully private)</div>'
        + '</div>'
        + '<div class="ollama-chat-input">'
          + '<textarea class="oc-ta" id="ocTa" rows="1" placeholder="Ask about your report…" onkeydown="onOcKey(event)" oninput="onOcGrow(this)"></textarea>'
          + '<button class="mic-btn" id="ocMicBtn" type="button" title="Speak" onclick="ClearScanVoice.toggleMic(\'ocTa\',\'ocMicBtn\',\'onOcGrow\')"></button>'
          + '<button class="oc-send" id="ocSendBtn" onclick="onOcSend()">'
            + '<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M1 6h10M7 2l4 4-4 4" stroke="white" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
          + '</button>'
        + '</div>'
      + '</div>';
    msgs.appendChild(card);
    document.getElementById('ocMicBtn').innerHTML = ClearScanVoice.micSvg;
    scrollBottom();
    setTimeout(function(){ document.getElementById('ocTa').focus(); }, 100);
    return;
  }

  var notice = document.getElementById('csNotice');
  if (notice) notice.remove();
  var wrap = document.createElement('div');
  wrap.className = 'cs-row';
  wrap.innerHTML = '<div class="cs-bubble bot">'
    + 'Hi! I\'ve read your radiology report. Ask me anything about it 😊'
    + '</div>'
    + '<div class="cs-who">ClearScan Assistant</div>'
    + '<div class="cs-suggestions">'
    + '<div class="cs-sug" onclick="onCsQuickAsk(this)">What does the risk level mean?</div>'
    + '<div class="cs-sug" onclick="onCsQuickAsk(this)">Should I be worried?</div>'
    + '<div class="cs-sug" onclick="onCsQuickAsk(this)">What to ask my doctor?</div>'
    + '<div class="cs-sug" onclick="onCsQuickAsk(this)">Explain the main finding simply</div>'
    + '</div>';
  document.getElementById('csMsgs').appendChild(wrap);
  document.getElementById('csMsgs').scrollTop = 99999;
  document.getElementById('csTa').disabled      = false;
  document.getElementById('csTa').placeholder   = 'Ask about your report…';
  document.getElementById('csSendBtn').disabled = false;
}

// ─────────────────────────────────────────
// OLLAMA INLINE CHAT
// ─────────────────────────────────────────
function onOcGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 80) + 'px';
}
function onOcKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onOcSend(); }
}
function onOcSend() {
  var inp = document.getElementById('ocTa');
  if (!inp) return;
  var msg = inp.value.trim();
  if (!msg) return;
  inp.value = '';
  inp.style.height = 'auto';
  document.getElementById('ocSendBtn').disabled = true;
  var ocMsgs = document.getElementById('ocMsgs');
  var ub = document.createElement('div');
  ub.className = 'oc-bubble user';
  ub.textContent = msg;
  ocMsgs.appendChild(ub);
  ocMsgs.scrollTop = ocMsgs.scrollHeight;
  var tid = 'oct-' + Date.now();
  var typing = document.createElement('div');
  typing.id = tid;
  typing.innerHTML = '<div class="oc-typing"><span></span><span></span><span></span></div>';
  ocMsgs.appendChild(typing);
  ocMsgs.scrollTop = ocMsgs.scrollHeight;
  fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: msg,
      language: ClearScanControls.getLanguageName(),
      answer_length: answerLength,
      detail_level: detailLevel
    })
  })
    .then(function(res){ return res.json(); })
    .then(function(data){
      var t = document.getElementById(tid);
      if (t) t.remove();
      var bb = document.createElement('div');
      bb.className = 'oc-bubble bot';
      bb.innerHTML = data.reply.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
      ocMsgs.appendChild(bb);
      ocMsgs.scrollTop = ocMsgs.scrollHeight;
    })
    .catch(function(){
      var t = document.getElementById(tid);
      if (t) t.remove();
      var bb = document.createElement('div');
      bb.className = 'oc-bubble bot';
      bb.textContent = 'Something went wrong. Please try again.';
      ocMsgs.appendChild(bb);
    })
    .finally(function(){
      var btn = document.getElementById('ocSendBtn');
      if (btn) btn.disabled = false;
    });
}

// ─────────────────────────────────────────
// RENDER RESULT
// ─────────────────────────────────────────
function removeEmpty() {
  var e = document.getElementById('emptyState');
  if (e) e.remove();
}
function appendUserBubble(txt, file) {
  var msgs = document.getElementById('msgs');
  var row  = document.createElement('div');
  row.className = 'msg-row user';

  var html = '<div class="msg-meta">You</div>';

  if (file) {
    html += '<div class="bub-att">'
          +   '<div class="bub-att-name">' + escHtml(file.name) + '</div>'
          +   '<span class="bub-att-badge">' + fileExt(file.name) + '</span>'
          + '</div>';
  }
  if (txt) {
    html += '<div class="user-bubble">' + escHtml(txt) + '</div>';
  }

  var now  = new Date();
  var time = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');

  html += '<div class="ub-actions">'
        +   '<span class="ub-time">' + time + '</span>'
        +   '<button class="ub-btn" type="button" onclick="onRegenerate(this)" title="Regenerate">'
        +     '<svg width="12" height="12" viewBox="0 0 12 12" fill="none">'
        +       '<path d="M10.5 6a4.5 4.5 0 11-1.32-3.18M10.5 1.2v3h-3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>'
        +     '</svg>'
        +   '</button>'
        +   '<button class="ub-btn" type="button" onclick="onCopyUser(this)" title="Copy">'
        +     '<svg width="12" height="12" viewBox="0 0 12 12" fill="none">'
        +       '<rect x="4" y="4" width="6.5" height="6.5" rx="1.4" stroke="currentColor" stroke-width="1.2"/>'
        +       '<path d="M8.2 1.5H2.6a1.1 1.1 0 00-1.1 1.1v5.6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>'
        +     '</svg>'
        +   '</button>'
        + '</div>';

  row.innerHTML = html;
  msgs.appendChild(row);
  scrollBottom();
}
function showMainTyping() {
  var msgs = document.getElementById('msgs');
  var id   = 'typ-' + Date.now();
  var el   = document.createElement('div');
  el.id    = id;
  el.className = 'typing-row';
  el.innerHTML = '<div class="t-ring"></div><span class="t-txt">Analyzing your report…</span>';
  msgs.appendChild(el);
  scrollBottom();
  return id;
}
function removeTyping(id) {
  var el = document.getElementById(id);
  if (el) el.remove();
}
function renderBotResult(d) {
  var msgs  = document.getElementById('msgs');
  var risk  = ((d.risk_level || 'unknown') + '').toLowerCase();
  var rLbl  = risk==='high' ? '🔴 HIGH' : risk==='medium' ? '🟡 MEDIUM' : risk==='low' ? '🟢 LOW' : '⚪ UNKNOWN';
  var pTag  = (provData[provider] || provData['groq']).tag;
  if (provider === 'ollama') {
    pTag = ollamaModel === 'mistral' ? '🧠 MISTRAL' : '⚡ LLAMA3.2:1B';
  }
  var findHtml = '';
  if (d.findings && d.findings.length) {
    findHtml = '<div><div class="rs-title"><span class="rs-dot blue"></span>Key Findings</div>'
      + '<div class="findings-list">'
      + d.findings.map(function(f){ return '<div class="fi"><span class="fi-dash">—</span><span>'+escHtml(f)+'</span></div>'; }).join('')
      + '</div></div>';
  }
  var termHtml = '';
  if (d.terms && d.terms.length) {
    termHtml = '<div><div class="rs-title"><span class="rs-dot amber"></span>Medical Terms Decoded</div>'
      + '<div class="terms-list">'
      + d.terms.map(function(t){
          var def = t.meaning || t.patient_explanation || t.simple_meaning || '';
          return '<div class="ti"><span class="ti-name">'+escHtml(t.term)+'</span><span class="ti-def">'+escHtml(def)+'</span></div>';
        }).join('')
      + '</div></div>';
  }
  var row = document.createElement('div');
  row.className = 'msg-row bot';
  row.innerHTML = '<div class="msg-meta">ClearScan · ' + pTag + '</div>'
    + '<div class="bot-card">'
      + '<div class="risk-strip ' + risk + '">'
        + '<div><div class="risk-lbl">Risk Level</div><div class="risk-val">'+rLbl+'</div></div>'
        + '<div class="risk-reason">'+escHtml(d.risk_reason||'See summary below.')+'</div>'
      + '</div>'
      + '<div class="bot-body">'
        + '<div><div class="rs-title"><span class="rs-dot teal"></span>Plain-Language Summary</div>'
        + '<div class="rs-content">'+(d.summary||'')+'</div></div>'
        + findHtml + termHtml
      + '</div>'
      + '<div class="bot-actions">'
        + '<button class="ba-btn" onclick="window.print()">🖨 Print</button>'
        + '<button class="ba-btn" onclick="onCopyResult(this)">📋 Copy</button>'
        + '<button class="ba-btn speak-btn" onclick="ClearScanVoice.speakText(this.closest(\'.bot-card\').querySelector(\'.rs-content\').innerHTML, this)">🔊 Read Aloud</button>'
        + '<button class="ba-btn" onclick="onNewReport()">↺ New Report</button>'
      + '</div>'
    + '</div>'
    + '<div style="font-size:.63rem;color:var(--dim);padding:.15rem .2rem">⚠️ Educational use only. Always discuss with your healthcare provider.</div>';
  msgs.appendChild(row);
  scrollBottom();
}
function onCopyResult(btn) {
  var card = btn.closest('.bot-card');
  navigator.clipboard.writeText(card.innerText).then(function() {
    btn.textContent = '✓ Copied';
    setTimeout(function(){ btn.textContent = '📋 Copy'; }, 2000);
  });
}

// ─────────────────────────────────────────
// CLOUD CHATBOT SIDEBAR
// ─────────────────────────────────────────
function onCsGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 80) + 'px';
}
function onCsKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onCsSend(); }
}
function onCsQuickAsk(el) {
  document.getElementById('csTa').value = el.textContent;
  onCsSend();
}
function onCsSend() {
  var inp = document.getElementById('csTa');
  var msg = inp.value.trim();
  if (!msg) return;
  inp.value = '';
  inp.style.height = 'auto';
  document.getElementById('csSendBtn').disabled = true;
  csAppend(msg, 'user');
  var tid = csTyping();
  fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: msg,
      language: ClearScanControls.getLanguageName(),
      answer_length: answerLength,
      detail_level: detailLevel
    })
  })
    .then(function(res){ return res.json(); })
    .then(function(data){
      csRemoveTyping(tid);
      csAppend(data.reply, 'bot');
    })
    .catch(function(){
      csRemoveTyping(tid);
      csAppend('Something went wrong. Please try again.', 'error');
    })
    .finally(function(){
      document.getElementById('csSendBtn').disabled = false;
    });
}
function csAppend(text, role) {
  var msgs = document.getElementById('csMsgs');
  var wrap = document.createElement('div');
  wrap.className = 'cs-row';
  var bubble = document.createElement('div');
  bubble.className = 'cs-bubble ' + role;
  bubble.innerHTML = text.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
  var who = document.createElement('div');
  who.className = 'cs-who';
  who.textContent = role === 'user' ? 'You' : 'ClearScan Assistant';
  wrap.appendChild(bubble);
  wrap.appendChild(who);
  if (role === 'bot') {
    wrap.appendChild(ClearScanVoice.createSpeakButton(function(){ return text; }, true));
  }
  msgs.appendChild(wrap);
  msgs.scrollTop = msgs.scrollHeight;
}
function csTyping() {
  var msgs = document.getElementById('csMsgs');
  var id   = 'cst-' + Date.now();
  var el   = document.createElement('div');
  el.id = id;
  el.innerHTML = '<div class="cs-typing"><span></span><span></span><span></span></div>';
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
  return id;
}
function csRemoveTyping(id) {
  var el = document.getElementById(id);
  if (el) el.remove();
}

// ─────────────────────────────────────────
// UTILS
// ─────────────────────────────────────────
function scrollBottom() {
  var m = document.getElementById('msgs');
  m.scrollTop = m.scrollHeight;
}
function showErr(msg) {
  var e = document.getElementById('errBar');
  e.textContent = '⚠ ' + msg;
  e.style.display = 'block';
}
function hideErr() {
  document.getElementById('errBar').style.display = 'none';
}
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}