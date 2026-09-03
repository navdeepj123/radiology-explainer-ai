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

document.getElementById('mainMicBtn').innerHTML = ClearScanVoice.micSvg;
document.getElementById('csMicBtn').innerHTML   = ClearScanVoice.micSvg;

// ─────────────────────────────────────────
// STATE
// ─────────────────────────────────────────
var provider           = 'groq';
var ollamaModel        = 'llama3.2:1b';
var answerLength       = 'standard';
var detailLevel        = 'medium';
var selFile            = null;
var isAnalyzed         = false;
var savedText          = '';
var historyArr         = [];
var lastText           = '';
var lastFile            = null;
var activeConversationId = null;
var chatSearchQuery    = '';

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
// FLOATING CHAT PANEL TOGGLE
// ─────────────────────────────────────────
function toggleChatPanel() {
  var panel = document.getElementById('chatSidebar');
  var overlay = document.getElementById('chatOverlay');
  if (panel.classList.contains('open')) {
    closeChatPanel();
  } else {
    panel.classList.add('open');
    if (overlay) overlay.classList.add('show');
  }
}
function closeChatPanel() {
  document.getElementById('chatSidebar').classList.remove('open');
  var overlay = document.getElementById('chatOverlay');
  if (overlay) overlay.classList.remove('show');
}

// ─────────────────────────────────────────
// LOAD SAVED HISTORY ON PAGE LOAD (radiology only)
// ─────────────────────────────────────────
fetch('/conversations')
  .then(function(res){ return res.json(); })
  .then(function(data){
    historyArr = (data.conversations || [])
      .filter(function(c){ return !c.kind || c.kind === 'radiology'; })
      .map(function(c) {
        return {
          preview: c.preview,
          title:   c.title,
          risk:    (c.risk_level || 'unknown').toLowerCase(),
          prov:    c.provider.toUpperCase(),
          time:    c.date,
          id:      c.id
        };
      });
    renderHistoryList();
  })
  .catch(function(){ /* silently ignore */ });

// ─────────────────────────────────────────
// HISTORY (radiology)
// ─────────────────────────────────────────
function addToHistory(reportText, riskLevel, prov, convId) {
  var now  = new Date();
  var time = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
  historyArr.unshift({
    preview: reportText.substring(0, 80).trim(),
    title:   null,
    risk:    (riskLevel || 'unknown').toLowerCase(),
    prov:    prov.toUpperCase(),
    time:    time,
    id:      convId
  });
  if (historyArr.length > 5) historyArr.pop();
  renderHistoryList();
}

function onChatSearch(val) {
  chatSearchQuery = val.trim().toLowerCase();
  if (typeof HT_ACTIVE !== 'undefined' && HT_ACTIVE) {
    renderHtHistoryList(val);
  } else {
    renderHistoryList();
  }
}

function renderHistoryList() {
  var list  = document.getElementById('sbHistList');
  var empty = document.getElementById('sbHistEmpty');

  var filtered = historyArr.filter(function(item) {
    if (!chatSearchQuery) return true;
    var title = (item.title || item.preview || '').toLowerCase();
    return title.indexOf(chatSearchQuery) !== -1;
  });

  if (empty) {
    empty.style.display = filtered.length ? 'none' : 'block';
    empty.textContent = historyArr.length ? 'No matching chats' : 'No chats yet';
  }

  list.querySelectorAll('.sh-item').forEach(function(el){ el.remove(); });

  filtered.forEach(function(item) {
    var rLabel = item.risk==='high'   ? '🔴 High risk'
               : item.risk==='medium' ? '🟡 Medium risk'
               : item.risk==='low'    ? '🟢 Low risk'
               :                        '⚪ Unknown';
    var displayTitle = item.title || item.preview;
    var div = document.createElement('div');
    div.className = 'sh-item' + (item.id === activeConversationId ? ' active' : '');
    div.style.cursor = 'pointer';
    div.onclick = function(){ loadConversation(item.id); };
    div.innerHTML =
      '<div class="sh-item-actions">'
        + '<button class="sh-icon-btn sh-edit" title="Rename" onclick="event.stopPropagation(); renameConversation(\''+item.id+'\')">'
          + '<svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M7.5 1.5l2 2L3.5 9.5H1.5v-2z" stroke="currentColor" stroke-width="1.1"/></svg>'
        + '</button>'
        + '<button class="sh-icon-btn sh-delete" title="Delete" onclick="event.stopPropagation(); deleteConversation(\''+item.id+'\')">'
          + '<svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M2 3h7M4 3V1.8h3V3M3 3l.5 6.5h4L8 3" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/></svg>'
        + '</button>'
      + '</div>'
      + '<div class="sh-top sh-title-row">'
        + '<span class="sh-prov">'+item.prov+'</span>'
        + '<span class="sh-time">'+item.time+'</span>'
      + '</div>'
      + '<div class="sh-preview">'+escHtml(displayTitle)+'…</div>'
      + '<div class="sh-risk '+item.risk+'">'+rLabel+'</div>';
    list.appendChild(div);
  });
}

function renameConversation(convId) {
  var item = historyArr.find(function(h){ return h.id === convId; });
  if (!item) return;
  var newTitle = prompt('Rename this chat:', item.title || item.preview);
  if (newTitle === null || !newTitle.trim()) return;

  fetch('/conversation/' + convId + '/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: newTitle.trim() })
  })
    .then(function(res){ return res.json(); })
    .then(function(){
      item.title = newTitle.trim();
      renderHistoryList();
    })
    .catch(function(){ showErr('Could not rename chat.'); });
}

function deleteConversation(convId) {
  if (!confirm('Delete this chat? This cannot be undone.')) return;

  fetch('/conversation/' + convId, { method: 'DELETE' })
    .then(function(res){ return res.json(); })
    .then(function(){
      historyArr = historyArr.filter(function(h){ return h.id !== convId; });
      if (convId === activeConversationId) {
        onNewReport();
      }
      renderHistoryList();
    })
    .catch(function(){ showErr('Could not delete chat.'); });
}

// ─────────────────────────────────────────
// PROVIDER CHANGE
// ─────────────────────────────────────────
function onProviderChange(val) {
  provider = val;
  var d = provData[val] || provData['groq'];

  function safeSetText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  safeSetText('sbHint', d.hint);
  safeSetText('provTag', d.tag);
  safeSetText('csChatTag', d.shortTag);
  safeSetText('csNoticeProv', d.name);

    var sidebar = document.getElementById('chatSidebar');
    var ollamaSel = document.getElementById('ollamaModelSel');
    if (ollamaSel) ollamaSel.style.display = (val === 'ollama') ? 'inline-block' : 'none';

  var ollamaSelHt = document.getElementById('ollamaModelSelHt');
  if (ollamaSelHt) ollamaSelHt.style.display = (val === 'ollama') ? 'inline-block' : 'none';

  var provSelHt = document.getElementById('provSelHt');
  if (provSelHt) provSelHt.value = val;
  var provSel = document.getElementById('provSel');
  if (provSel) provSel.value = val;

  if (val === 'ollama') {
    if (sidebar) sidebar.classList.add('hidden');
    closeChatPanel();
  } else {
    if (sidebar) sidebar.classList.remove('hidden');
  }
}

// ─────────────────────────────────────────
// OLLAMA MODEL CHANGE
// ─────────────────────────────────────────
function onOllamaModelChange(val) {
  ollamaModel = val;
  var hintEl = document.getElementById('ollamaModelHint');
  if (hintEl) hintEl.textContent = ollamaHints[val] || '';
}

// ─────────────────────────────────────────
// RESPONSE STYLE CHANGE
// ─────────────────────────────────────────
function onLengthChange(val) {
  answerLength = val;
  var s1 = document.getElementById('lengthSel');
  var s2 = document.getElementById('lengthSelHt');
  if (s1) s1.value = val;
  if (s2) s2.value = val;
}
function onDetailChange(val) {
  detailLevel = val;
  var s1 = document.getElementById('detailSel');
  var s2 = document.getElementById('detailSelHt');
  if (s1) s1.value = val;
  if (s2) s2.value = val;
}

// ─────────────────────────────────────────
// INPUT HELPERS
// ─────────────────────────────────────────
function onMainGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}
function onHtGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}

/* ── Claude-style HT model menu ── */
function toggleHtModelMenu(e) {
  e.stopPropagation();
  var menu = document.getElementById('htModelMenu');
  if (!menu) return;
  menu.style.display = (menu.style.display === 'none' || !menu.style.display) ? 'block' : 'none';
}

function selectHtModelOption(el) {
  var type = el.getAttribute('data-type');
  var value = el.getAttribute('data-value');

  // same value clicked, do nothing
  var menu = document.getElementById('htModelMenu');
  menu.querySelectorAll('.mm-item[data-type="' + type + '"]').forEach(function(item) {
    item.classList.remove('active');
  });
  el.classList.add('active');

  if (type === 'provider') {
    provider = value;
    if (typeof onProviderChange === 'function') onProviderChange(value);
  }
  if (type === 'length') {
    answerLength = value;
    if (typeof onLengthChange === 'function') onLengthChange(value);
  }
  if (type === 'detail') {
    detailLevel = value;
    if (typeof onDetailChange === 'function') onDetailChange(value);
  }

  updateHtModelMenuLabel();
}

function updateHtModelMenuLabel() {
  var labels = {
    groq: '⚡ Groq',
    gemini: '✨ Gemini',
    openai: '🤖 OpenAI',
    ollama: '🖥️ Ollama'
  };
  var p = labels[provider] || '⚡ Groq';
  var l = (answerLength || 'standard');
  l = l.charAt(0).toUpperCase() + l.slice(1);
  var d = (detailLevel || 'medium');
  d = d.charAt(0).toUpperCase() + d.slice(1);

  var labelEl = document.getElementById('htModelMenuLabel');
  if (labelEl) labelEl.textContent = p + ' · ' + l + ' · ' + d;
}

// click outside to close the menu
document.addEventListener('click', function() {
  var menu = document.getElementById('htModelMenu');
  if (menu) menu.style.display = 'none';
});

/* ── Claude-style Radiology model menu ── */
function toggleRadModelMenu(e) {
  e.stopPropagation();
  var menu = document.getElementById('radModelMenu');
  if (!menu) return;
  menu.style.display = (menu.style.display === 'none' || !menu.style.display) ? 'block' : 'none';
}

function selectRadModelOption(el) {
  var type = el.getAttribute('data-type');
  var value = el.getAttribute('data-value');

  var menu = document.getElementById('radModelMenu');
  menu.querySelectorAll('.mm-item[data-type="' + type + '"]').forEach(function(item) {
    item.classList.remove('active');
  });
  el.classList.add('active');

  if (type === 'provider') {
    provider = value;
    if (typeof onProviderChange === 'function') onProviderChange(value);
  }
  if (type === 'length') {
    answerLength = value;
    if (typeof onLengthChange === 'function') onLengthChange(value);
  }
  if (type === 'detail') {
    detailLevel = value;
    if (typeof onDetailChange === 'function') onDetailChange(value);
  }

  updateRadModelMenuLabel();
}

function updateRadModelMenuLabel() {
  var labels = {
    groq: '⚡ Groq',
    gemini: '✨ Gemini',
    openai: '🤖 OpenAI',
    ollama: '🖥️ Ollama'
  };
  var p = labels[provider] || '⚡ Groq';
  var l = (answerLength || 'standard');
  l = l.charAt(0).toUpperCase() + l.slice(1);
  var d = (detailLevel || 'medium');
  d = d.charAt(0).toUpperCase() + d.slice(1);

  var labelEl = document.getElementById('radModelMenuLabel');
  if (labelEl) labelEl.textContent = p + ' · ' + l + ' · ' + d;
}

// click outside to close the menu
document.addEventListener('click', function() {
  var htMenu = document.getElementById('htModelMenu');
  if (htMenu) htMenu.style.display = 'none';
  var radMenu = document.getElementById('radModelMenu');
  if (radMenu) radMenu.style.display = 'none';
});

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

  document.getElementById('msgs').innerHTML = '';
  resetChatPanel();

savedText = text;
lastText  = text;
lastFile  = selFile;

if (selFile) {
  // PDF upload → sirf PDF file card dikhao
  appendUserBubble('', selFile);
} else {
  // Normal pasted report → full text dikhao
  appendUserBubble(text, null);
}
  var ta = document.getElementById('mainTa');
  ta.value = '';
  ta.style.height = 'auto';
  runAnalysis(text, selFile);
  clearFile();
}

function runAnalysis(text, file) {
  document.getElementById('mainSendBtn').disabled = true;
  document.getElementById('statusPill').textContent = 'Analyzing…';
  var typId = showMainTyping();
  var fd = new FormData();
  if (text) fd.append('report_text', text);
if (file) {
    fd.append('report_file', file);
    fd.append('original_filename', file.name);
    fd.append('source_type', 'pdf');
} else {
    fd.append('source_type', 'text');
}  fd.append('provider', provider);
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
        activeConversationId = data.conversation_id;
        addToHistory(savedText, data.risk_level, provider, data.conversation_id);
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
  activeConversationId = null;
  document.getElementById('msgs').innerHTML = '';
  document.getElementById('inputArea').style.display    = 'block';
  document.getElementById('newReportBar').style.display = 'none';
  document.getElementById('mainTa').value        = '';
  document.getElementById('mainTa').style.height = 'auto';
  document.getElementById('mainTa').placeholder  = 'Paste your radiology report here…';
  document.getElementById('statusPill').textContent     = 'Ready';
  document.getElementById('mainSendBtn').disabled       = false;
  document.getElementById('mainTa').focus();
  closeChatPanel();
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
  renderHistoryList();
}

// ─────────────────────────────────────────
// LOAD PREVIOUS CONVERSATION (sidebar click) — radiology
// ─────────────────────────────────────────
function loadConversation(convId) {
  if (!convId || convId === activeConversationId) return;

  fetch('/conversation/' + convId)
    .then(function(res){ return res.json(); })
    .then(function(conv) {
      if (conv.error) { showErr('Could not load that report.'); return; }

      activeConversationId = convId;
      provider    = conv.provider;
      ollamaModel = conv.ollama_model || ollamaModel;
      answerLength = conv.answer_length || 'standard';
      detailLevel  = conv.detail_level  || 'medium';

      document.getElementById('csMsgs').innerHTML =
        '<div class="cs-notice" id="csNotice">'
        + '<div class="cs-notice-icon">🫁</div>'
        + '<p>Submit your radiology report first, then I\'ll be able to answer your questions about it.</p>'
        + '<small>Powered by <span id="csNoticeProv"></span></small>'
        + '</div>';

      onProviderChange(provider);

      var provSel = document.getElementById('provSel');
      if (provSel) provSel.value = provider;
      var ollamaSel = document.getElementById('ollamaModelSel');
      if (ollamaSel) ollamaSel.value = ollamaModel;
      var lengthSel = document.getElementById('lengthSel');
      if (lengthSel) lengthSel.value = answerLength;
      var detailSel = document.getElementById('detailSel');
      if (detailSel) detailSel.value = detailLevel;

      document.getElementById('msgs').innerHTML = '';
    if (conv.source_type === 'pdf') {
    // PDF upload → show filename
    appendUserBubble('', {
        name: conv.original_filename || 'report.pdf'
    });
} else {
    // Normal text → complete text
    appendUserBubble(conv.report_text || '', null);
}
      conv.results.report_text = conv.report_text;
      renderBotResult(conv.results);
      activateChatbot();

      document.getElementById('csMsgs').innerHTML = '';
      conv.chat_messages.forEach(function(m) {
        csAppend(m.content, m.role === 'user' ? 'user' : 'bot');
      });

      isAnalyzed = true;
      document.getElementById('inputArea').style.display    = 'none';
      document.getElementById('newReportBar').style.display = 'flex';
      document.getElementById('statusPill').textContent     = 'Analysis complete';

      renderHistoryList();
    })
    .catch(function(err){
      console.error('loadConversation ERROR:', err);
      showErr('Could not load that report.');
    });
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

  toggleChatPanel();
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
      detail_level: detailLevel,
      conversation_id: activeConversationId,
      provider: provider,
      ollama_model: ollamaModel
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
  var verifyHtml = '';
  if (d.verification && d.verification.checked_count > 0) {
    if (d.verification.passed) {
      verifyHtml = '<div class="verify-badge verify-pass">✓ Verified against ' + d.verification.checked_count + ' confirmed finding(s)</div>';
    } else {
      verifyHtml = '<div class="verify-badge verify-fail">⚠ ' + d.verification.failed_terms.length + ' finding(s) need review: ' + escHtml(d.verification.failed_terms.join(', ')) + '</div>';
    }
  }

  var reportContainerId = 'reportText-' + Date.now();
  var reportHtml = '';
  if (d.report_text) {
    reportHtml = '<div><div class="rs-title"><span class="rs-dot amber"></span>Original Report (click highlighted terms)</div>'
      + '<div class="report-text-block" id="' + reportContainerId + '"></div></div>';
  }

  var bodyMapContainerId = 'bodyMap-' + Date.now();
  var bodyMapHtml = '';
  if (d.terms && d.terms.length) {
    bodyMapHtml = '<div><div class="rs-title"><span class="rs-dot blue"></span>Body Map</div>'
      + '<div id="' + bodyMapContainerId + '"></div></div>';
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
       + reportHtml
       + bodyMapHtml
        + '<div><div class="rs-title"><span class="rs-dot teal"></span>Plain-Language Summary</div>'
        + '<div class="rs-content">'+(d.summary||'')+'</div></div>'
        + findHtml + termHtml
        + verifyHtml
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

    if (d.report_text) {
    renderHighlightedReport(reportContainerId, d.report_text, d.highlighted_terms || []);
  }
  if (d.terms && d.terms.length) {
    renderBodyMap({
      container: document.getElementById(bodyMapContainerId),
      detectedTerms: d.terms,
      reportText: d.report_text || '',
      regionsUrl: '/static/data/body_regions.json',
      onPinClick: function(term, definition) {
        openTermPopup({ term: term, meaning: definition });
      }
    });
  }
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
// CLOUD CHATBOT SIDEBAR (used by BOTH radiology and health tools)
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

  var isHt = (typeof HT_ACTIVE !== 'undefined' && HT_ACTIVE);
  var url = isHt ? ('/api/health-tools/' + HT_ACTIVE + '/chat') : '/chat';
  var body = isHt
    ? {
        message: msg,
        conversation_id: (typeof htActiveConversationId !== 'undefined') ? htActiveConversationId : null,
        provider: provider,
        answer_length: answerLength,
        detail_level: detailLevel,
        ollama_model: ollamaModel
      }
    : {
        message: msg,
        language: ClearScanControls.getLanguageName(),
        answer_length: answerLength,
        detail_level: detailLevel,
        conversation_id: activeConversationId
      };

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
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

// ─────────────────────────────────────────
// MEDICAL TERM HIGHLIGHTING
// ─────────────────────────────────────────
function renderHighlightedReport(containerId, reportText, highlightedTerms) {
  var container = document.getElementById(containerId);
  if (!container) return;

  if (!reportText) { container.textContent = ''; return; }
  if (!highlightedTerms || highlightedTerms.length === 0) {
    container.textContent = reportText;
    return;
  }

  var sorted = highlightedTerms.slice().sort(function(a, b) { return a.start - b.start; });
  var html = '';
  var cursor = 0;

  sorted.forEach(function(h, i) {
    html += escHtml(reportText.slice(cursor, h.start));
    html += '<span class="med-term" data-index="' + i + '">' + escHtml(h.matched_text) + '</span>';
    cursor = h.end;
  });
  html += escHtml(reportText.slice(cursor));
  container.innerHTML = html;

  container.querySelectorAll('.med-term').forEach(function(span) {
    span.addEventListener('click', function() {
      var idx = parseInt(span.dataset.index, 10);
      openTermPopup(sorted[idx]);
    });
  });
}

function openTermPopup(termData) {
  document.getElementById('termPopupTitle').textContent = termData.term;
  document.getElementById('termPopupDefinition').textContent = termData.meaning || 'No definition available.';
  var img = document.getElementById('termPopupImage');
  if (termData.image_url) {
    img.src = termData.image_url;
    img.style.display = 'block';
  } else {
    img.style.display = 'none';
  }
  document.getElementById('termPopupOverlay').classList.add('active');
}

function closeTermPopup() {
  document.getElementById('termPopupOverlay').classList.remove('active');
}

var termPopupOverlayEl = document.getElementById('termPopupOverlay');
if (termPopupOverlayEl) {
  termPopupOverlayEl.addEventListener('click', function(e) {
    if (e.target.id === 'termPopupOverlay') closeTermPopup();
  });
}