// public/chat.js (d:\Chatbot\public\chat.js)
const chat = document.getElementById("chat");
const input = document.getElementById("msg");
const sendBtn = document.getElementById("send");
const planBtn = document.getElementById("plan");
const caloriesInput = document.getElementById("calories");
const avoidInput = document.getElementById("avoid");
const vegInput = document.getElementById("veg");
const micBtn = document.getElementById("mic");
const langSelect = document.getElementById("lang");
const autoSendToggle = document.getElementById("autoSend");
let currentLang = (langSelect && langSelect.value) || "en";
let autoSend = autoSendToggle ? autoSendToggle.checked : true;
if (langSelect) {
  langSelect.onchange = () => {
    currentLang = langSelect.value;
  };
}
if (autoSendToggle) {
  autoSendToggle.onchange = () => {
    autoSend = autoSendToggle.checked;
  };
}

function parseMarkdown(text) {
  // Convert bold text (**text**) to <strong>text</strong>
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  
  // Convert italic text (*text*) to <em>text</em> (avoid conflicts with bold)
  text = text.replace(/(?<!\*)\*(?!\*)(.*?)\*(?!\*)/g, '<em>$1</em>');
  
  // Convert line breaks to <br>
  text = text.replace(/\n/g, '<br>');
  
  // Convert bullet points
  text = text.replace(/^[\s]*•[\s]+(.*)$/gm, '<li>$1</li>');
  text = text.replace(/^[\s]*-[\s]+(.*)$/gm, '<li>$1</li>');
  text = text.replace(/^[\s]*\*[\s]+(.*)$/gm, '<li>$1</li>');
  
  // Wrap consecutive <li> tags in <ul>
  text = text.replace(/(<li>.*?<\/li>)(\s*<li>.*?<\/li>)*/g, '<ul>$&</ul>');
  
  // Convert numbered lists
  text = text.replace(/^[\s]*\d+\.[\s]+(.*)$/gm, '<li>$1</li>');
  
  return text;
}

function addText(role, text, buttons = []) {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  
  // Add avatar for better UX
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "bot" ? "" : "";
  avatar.style.cssText = `
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    background: ${role === "bot" ? "var(--gradient-primary)" : "var(--gradient-secondary)"};
    margin-right: 12px;
    flex-shrink: 0;
  `;
  
  const content = document.createElement("div");
  content.className = "content";
  
  // Add timestamp
  const ts = document.createElement("div");
  ts.className = "timestamp";
  const now = new Date();
  ts.textContent = `${now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
  ts.style.cssText = `
    font-size: 11px;
    color: var(--text-light);
    margin-top: 4px;
    opacity: 0.7;
  `;
  
  // Parse markdown formatting
  const formattedText = parseMarkdown(text);
  content.innerHTML = formattedText;
  
  if (role === "bot") {
    bubble.appendChild(avatar);
  } else {
    bubble.style.flexDirection = "row-reverse";
    avatar.style.marginRight = "0";
    avatar.style.marginLeft = "12px";
    bubble.appendChild(avatar);
  }
  
  bubble.appendChild(content);
  bubble.appendChild(ts);
  if (role === "bot") {
    const controls = document.createElement("div");
    controls.className = "controls";
    const speakBtn = document.createElement("button");
    speakBtn.className = "btn";
    speakBtn.textContent = "🔊 Speak";
    const stopBtn = document.createElement("button");
    stopBtn.className = "btn";
    stopBtn.textContent = "⏹ Stop";
    speakBtn.onclick = () => {
      if (!hasTTS) {
        showError("Voice output not supported");
        return;
      }
      speakBtn.disabled = true;
      speakText(text, currentLang, () => {
        speakBtn.disabled = false;
      });
    };
    stopBtn.onclick = () => {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {}
    };
    controls.appendChild(speakBtn);
    controls.appendChild(stopBtn);
    content.appendChild(controls);
  }
  row.appendChild(bubble);
  chat.appendChild(row);
  if (buttons && buttons.length) {
    const btns = document.createElement("div");
    btns.className = "buttons";
    buttons.forEach((b) => {
      const btn = document.createElement("button");
      btn.className = "btn";
      btn.textContent = b.label;
      btn.onclick = () => {
        if (b.payload === '__retry_voice__') {
          if (micBtn) micBtn.click();
        } else {
          send(b.payload);
        }
      };
      btns.appendChild(btn);
    });
    bubble.appendChild(btns);
  }
  chat.scrollTop = chat.scrollHeight;
}

function stripHtml(html) {
  const div = document.createElement("div");
  div.innerHTML = html;
  return div.textContent || div.innerText || "";
}

function addCarousel(role, cards = [], buttons = []) {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const list = document.createElement("div");
  list.className = "carousel";
  cards.forEach((c) => {
    const card = document.createElement("div");
    card.className = "card";
    if (c.imageUrl) {
      const img = document.createElement("img");
      img.src = c.imageUrl;
      card.appendChild(img);
    }
    const title = document.createElement("div");
    title.className = "card-title";
    title.textContent = c.title || "";
    const desc = document.createElement("div");
    desc.className = "card-desc";
    desc.textContent = c.description || "";
    const action = document.createElement("button");
    action.className = "btn";
    action.textContent = (c.action && c.action.label) || "Learn more";
    action.onclick = () => send((c.action && c.action.payload) || `Learn more about ${c.title}`);
    card.appendChild(title);
    card.appendChild(desc);
    card.appendChild(action);
    list.appendChild(card);
  });
  bubble.appendChild(list);
  if (buttons && buttons.length) {
    const btns = document.createElement("div");
    btns.className = "buttons";
    buttons.forEach((b) => {
      const btn = document.createElement("button");
      btn.className = "btn";
      btn.textContent = b.label;
      btn.onclick = () => send(b.payload);
      btns.appendChild(btn);
    });
    bubble.appendChild(btns);
  }
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}

// Show loading indicator
function showLoading() {
  const loading = document.createElement('div');
  loading.className = 'msg bot';
  loading.id = 'typing-indicator';
  loading.innerHTML = `
    <div class="bubble">
      <div class="typing">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  `;
  chat.appendChild(loading);
  chat.scrollTop = chat.scrollHeight;
  return loading;
}

// Hide loading indicator
function hideLoading(loadingElement) {
  if (loadingElement && loadingElement.parentNode) {
    loadingElement.remove();
  }
}

// Show error message
function showError(message) {
  const msg = message || (currentLang === "hi" ? "क्षमा करें, कुछ गड़बड़ हुई। कृपया फिर प्रयास करें।" : "Sorry, something went wrong. Please try again.");
  const retryVoiceLabel = currentLang === "hi" ? "वॉइस दोबारा" : "Retry Voice";
  const tryAgainLabel = currentLang === "hi" ? "फिर से प्रयास करें" : "Try again";
  addText('bot', msg, [
    { label: retryVoiceLabel, payload: '__retry_voice__' },
    { label: tryAgainLabel, payload: tryAgainLabel }
  ]);
}

async function send(message) {
  const msg = String(message || input.value).trim();
  if (!msg) return;
  
  // Disable input and send button while processing
  input.disabled = true;
  sendBtn.disabled = true;
  
  // Add user message and clear input
  addText("user", msg);
  input.value = "";
  
  // Show typing indicator
  const loadingIndicator = showLoading();
  
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, lang: currentLang })
    });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || 'Failed to get response from server');
    }
    
    const data = await response.json();
    
    // Remove typing indicator
    hideLoading(loadingIndicator);
    
    // Display the response
    addText("bot", data.response || "I'm sorry, I couldn't process your request.");
    if (data.sources && data.sources.length > 0) {
      const panel = document.getElementById("sources-panel");
      if (panel) {
        panel.innerHTML = "";
        data.sources.forEach(src => {
          const c = document.createElement("div");
          c.className = "card";
          const t = document.createElement("div");
          t.className = "card-title";
          t.textContent = src.title || "";
          const d = document.createElement("div");
          d.className = "card-desc";
          d.textContent = src.content || "";
          const tag = document.createElement("div");
          tag.className = "tag";
          tag.textContent = src.source === "knowledge_base" ? "Knowledge Base" : "Source";
          c.appendChild(t);
          c.appendChild(d);
          c.appendChild(tag);
          panel.appendChild(c);
        });
      }
    }
  } catch (error) {
    console.error('Error:', error);
    hideLoading(loadingIndicator);
    showError(error.message || 'An error occurred while processing your request');
  } finally {
    // Re-enable input and send button
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

// Handle send button click
sendBtn.onclick = (e) => {
  e.preventDefault();
  send();
};

// Handle Enter key in input
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

// Focus the input when the page loads
document.addEventListener('DOMContentLoaded', () => {
  input.focus();
  if (hasTTS) initVoices();
});
addText("bot", "Welcome to our nutrition assistant. Ask about grains, lentils, legumes, vegetables, and Ayurvedic properties.");

if (planBtn) {
  planBtn.onclick = () => {
    const cal = String(caloriesInput.value || "").trim();
    const avoid = String(avoidInput.value || "").trim();
    const veg = vegInput.checked ? "vegetarian" : "";
    let msg = "diet plan";
    if (cal) msg += ` ${cal} calories`;
    if (veg) msg += ` ${veg}`;
    if (avoid) msg += ` avoid ${avoid}`;
    send(msg);
  };
}

if (micBtn && (window.SpeechRecognition || window.webkitSpeechRecognition)) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = new SR();
  let listening = false;
  recognizer.continuous = false;
  recognizer.interimResults = true;
  recognizer.maxAlternatives = 1;
  recognizer.onstart = () => {
    listening = true;
    micBtn.classList.add("active");
    micBtn.title = "Listening…";
    micBtn.textContent = "🎙";
    if (listenBanner) listenBanner.hidden = false;
  };
  recognizer.onend = () => {
    listening = false;
    micBtn.classList.remove("active");
    micBtn.title = "Voice Input";
    micBtn.textContent = "🎤";
    if (listenBanner) listenBanner.hidden = true;
  };
  recognizer.onresult = (e) => {
    let finalText = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalText += t;
      else input.value = t;
    }
    if (finalText) {
      input.value = finalText;
      if (autoSend) {
        send(finalText);
      }
    }
  };
  recognizer.onerror = (e) => {
    listening = false;
    micBtn.classList.remove("active");
    micBtn.title = "Voice Input";
    micBtn.textContent = "🎤";
    let msg = (e && e.error) ? `Voice input error: ${e.error}` : "Voice input error";
    if (e && e.error === "network") {
      msg = currentLang === "hi"
        ? "वॉइस इनपुट त्रुटि: नेटवर्क। कृपया इंटरनेट कनेक्शन और ब्राउज़र सेटिंग्स जांचें। VPN/प्रॉक्सी बंद करें, और Chrome/Edge का उपयोग करें।"
        : "Voice input error: network. Check internet connection and browser settings. Disable VPN/proxy and use Chrome/Edge.";
    }
    showError(msg);
    if (listenBanner) listenBanner.hidden = true;
  };
  micBtn.onclick = () => {
    try {
      if (!recognizer) recognizer = new SR();
      if (listening) {
        recognizer.stop();
        return;
      }
      recognizer.lang = currentLang === "hi" ? "hi-IN" : "en-US";
      // Prompt mic permission first to ensure reliable start
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ audio: true })
          .then(() => recognizer.start())
          .catch(() => showError("Microphone permission denied"));
      } else {
        recognizer.start();
      }
    } catch (e) {
      showError("Unable to start voice input");
    }
  };
}
else if (micBtn) {
  micBtn.disabled = true;
  micBtn.title = "Voice input not supported in this browser";
}

document.querySelectorAll(".quick-btn").forEach(btn => {
  btn.onclick = () => {
    const payload = btn.getAttribute("data-msg");
    send(payload);
  };
});
document.querySelectorAll(".chip").forEach(btn => {
  btn.onclick = () => {
    const payload = btn.getAttribute("data-msg");
    send(payload);
  };
});

// Theme Management
const themeToggle = document.getElementById("themeToggle");
if (themeToggle) {
  // Load saved theme
  const savedTheme = localStorage.getItem('chatbot-theme');
  if (savedTheme === 'dark') {
    document.body.classList.add("dark");
    themeToggle.textContent = '☀️';
  }
  
  themeToggle.onclick = () => {
    const isDark = document.body.classList.toggle("dark");
    themeToggle.textContent = isDark ? '☀️' : '🌙';
    localStorage.setItem('chatbot-theme', isDark ? 'dark' : 'light');
  };
}

const listenBanner = document.getElementById("listen-banner");
const hasTTS = typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
let ttsVoices = [];
function initVoices() {
  try {
    ttsVoices = (window.speechSynthesis.getVoices && window.speechSynthesis.getVoices()) || [];
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = () => {
        ttsVoices = (window.speechSynthesis.getVoices && window.speechSynthesis.getVoices()) || [];
      };
    }
  } catch (e) {}
}
function pickVoice(langCode) {
  const lc = (langCode === "hi" ? "hi-IN" : "en-US").toLowerCase();
  let v = ttsVoices.find(v => (v.lang || "").toLowerCase().startsWith(lc));
  if (!v) {
    const base = lc.split("-")[0];
    v = ttsVoices.find(v => (v.lang || "").toLowerCase().startsWith(base));
  }
  if (!v) v = ttsVoices.find(v => v.default) || ttsVoices[0];
  return v;
}
function speakText(txt, langCode, onend) {
  try {
    const utter = new SpeechSynthesisUtterance(stripHtml(txt));
    const lc = langCode === "hi" ? "hi-IN" : "en-US";
    utter.lang = lc;
    const v = pickVoice(langCode);
    if (v) utter.voice = v;
    utter.rate = 1.0;
    utter.onend = () => { if (onend) onend(); };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  } catch (e) {
    showError("Voice output not supported");
  }
}
