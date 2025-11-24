// public/chat.js (d:\Chatbot\public\chat.js)
const chat = document.getElementById("chat");
const input = document.getElementById("msg");
const sendBtn = document.getElementById("send");

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
  
  // Parse markdown formatting
  const formattedText = parseMarkdown(text);
  bubble.innerHTML = formattedText;
  
  row.appendChild(bubble);
  chat.appendChild(row);
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
  chat.scrollTop = chat.scrollHeight;
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
  addText('bot', message || 'Sorry, something went wrong. Please try again later.', [
    { label: 'Try again', payload: 'Try again' }
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
      body: JSON.stringify({ message: msg })
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
    
    // Display sources if available
    if (data.sources && data.sources.length > 0) {
      let sourcesText = "\n\nSources:\n";
      data.sources.forEach((source, index) => {
        sourcesText += `${index + 1}. ${source.title}`;
        if (source.source === 'google_search' && source.link) {
          sourcesText += ` [🔗 ${source.link}]`;
        } else if (source.similarity) {
          sourcesText += ` (similarity: ${source.similarity})`;
        }
        sourcesText += '\n';
      });
      addText("bot", sourcesText);
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
});
addText("bot", "Welcome to our nutrition assistant. Ask about grains, lentils, legumes, vegetables, and Ayurvedic properties.");