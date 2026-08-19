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
var provider              = 'groq';
var ollamaModel           = 'llama3.2:1b';
var answerLength          = 'standard';
var detailLevel           = 'medium';
var selFile               = null;
var isAnalyzed            = false;
var savedText             = '';
var historyArr            = [];
var lastText              = '';
var lastFile               = null;
var activeConversationId  = null;   // MongoDB conversation currently open
var chatSearchQuery       = '';     // sidebar search filter

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
    overlay.classList.add('show');
  }
}
function closeChatPanel() {
  document.getElementById('chatSidebar').classList.remove('open');
  document.getElementById('chatOverlay').classList.remove('show');
}

// ─────────────────────────────────────────
// LOAD SAVED HISTORY ON PAGE LOAD (from MongoDB)
// ─────────────────────────────────────────
fetch('/conversations')
  .then(function(res){ return res.json(); })
  .then(function(data){
    historyArr = (data.conversations || []).map(function(c) {
      return {
        preview: c.preview,
        title:   c.title,           // custom rename, if set
        risk:    (c.risk_level || 'unknown').toLowerCase(),
        prov:    c.provider.toUpperCase(),
        time:    c.date,
        id:      c.id
      };
    });
    renderHistoryList();
  })
  .catch(function(){ /* silently ignore — sidebar just stays empty */ });

// ─────────────────────────────────────────
// HISTORY
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

// sidebar search
function onChatSearch(val) {
  chatSearchQuery = val.trim().toLowerCase();
  renderHistoryList();
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

// rename a conversation
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

// delete a conversation
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
  document.getElementById('sbHint').textContent       = d.hint;
  document.getElementById('provTag').textContent      = d.tag;
  document.getElementById('csChatTag').textContent    = d.shortTag;
  document.getElementById('csNoticeProv').textContent = d.name;

  document.getElementById('sbOllamaWrap').style.display = (val === 'ollama') ? 'block' : 'none';

  var sidebar = document.getElementById('chatSidebar');
  var fab = document.getElementById('chatFab');
  if (val === 'ollama') {
    sidebar.classList.add('hidden');
    closeChatPanel();
    fab.classList.add('hide');
  } else {
    sidebar.classList.remove('hidden');
    fab.classList.remove('hide');
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

  // fresh report = fresh visual thread — purani conversation ka view clear karo
  document.getElementById('msgs').innerHTML = '';
  resetChatPanel();   // csMsgs ko bhi "submit your report" notice pe wapas laata hai

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
  navigator.clipboard.writeText(