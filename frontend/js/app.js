import { ChatSocket } from "./ws.js";

// ── Application state ────────────────────────────────────────────────────────
let socket          = null;   // ChatSocket instance
let streamingBubble = null;   // the <div> currently receiving streamed tokens
let currentAgent    = null;   // name of the agent whose bubble is open
let sending         = false;  // true while waiting for agent_end
let agentsData      = {};     // id → agent object (cached from /api/agents/)

// ── DOM references ───────────────────────────────────────────────────────────
const output     = document.getElementById("output");
const msgInput   = document.getElementById("msg-input");
const sendBtn    = document.getElementById("send-btn");
const connStatus = document.getElementById("conn-status");
const agentsList = document.getElementById("agents-list");

// Agent detail panel (right sidebar)
const detailPanel  = document.getElementById("agent-detail");
const detailName   = document.getElementById("detail-name");
const detailRole   = document.getElementById("detail-role");
const detailPrompt = document.getElementById("detail-prompt");
const detailTools  = document.getElementById("detail-tools");
const detailSkills = document.getElementById("detail-skills");
const detailClose  = document.getElementById("detail-close");

// ── UI helpers ───────────────────────────────────────────────────────────────

/** Current time string for message timestamps (HH:MM:SS). */
const ts = () =>
  new Date().toLocaleTimeString("th-TH", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });

/** Keep chat scrolled to the latest message. */
function scrollBottom() { output.scrollTop = output.scrollHeight; }

/** Update connection badge in the topbar. */
function setConnected(ok) {
  connStatus.textContent = ok ? "LIVE" : "OFFLINE";
  connStatus.className   = `status ${ok ? "online" : "offline"}`;
}

/** Enable / disable the chat input and send button. */
function setInputEnabled(enabled) {
  msgInput.disabled = !enabled;
  sendBtn.disabled  = !enabled;
  if (enabled) msgInput.focus();
}

// ── Sidebar: load agent list from API ─────────────────────────────────────────

/** Fetch /api/agents/ and populate the left sidebar with agent items. */
async function loadAgents() {
  try {
    const res = await fetch("/api/agents/");
    const groups = await res.json();

    // Flatten all agents into a lookup map
    agentsData = {};
    for (const agents of Object.values(groups)) {
      agents.forEach((a) => { agentsData[a.id] = a; });
    }

    agentsList.innerHTML = "";
    for (const [groupName, agents] of Object.entries(groups)) {
      const label = document.createElement("div");
      label.className = "sidebar-sublabel";
      label.textContent = groupName.toUpperCase();
      agentsList.appendChild(label);

      agents.forEach((agent) => {
        const item = document.createElement("div");
        item.className = `sidebar-item agent-item ${agent.role}`;
        item.dataset.agentId = agent.id;
        item.innerHTML = `<div class="dot online"></div>
          <span class="item-name">${agent.name}</span>
          <span class="agent-badge">${agent.role === "orchestrator" ? "" : "sub"}</span>`;
        item.addEventListener("click", () => showAgentDetail(agent.id));
        agentsList.appendChild(item);
      });
    }
  } catch (err) {
    console.warn("Failed to load agents:", err);
  }
}

// ── Sidebar: agent detail panel (right side) ─────────────────────────────────

/** Open the detail panel showing an agent's role, prompt, tools, skills. */
function showAgentDetail(agentId) {
  const agent = agentsData[agentId];
  if (!agent) return;

  // Highlight active sidebar item
  document.querySelectorAll(".agent-item").forEach((el) => el.classList.remove("active"));
  const active = document.querySelector(`.agent-item[data-agent-id="${agentId}"]`);
  if (active) active.classList.add("active");

  // Fill detail panel
  detailName.textContent = agent.name;
  detailRole.textContent = agent.role === "orchestrator" ? "Orchestrator" : "Subagent";
  detailRole.className = `detail-value role-${agent.role}`;
  detailPrompt.textContent = agent.system_prompt || "(none)";

  // Tools
  detailTools.innerHTML = "";
  if (agent.tools && agent.tools.length > 0) {
    agent.tools.forEach((t) => {
      const card = document.createElement("div");
      card.className = "detail-tool-card";
      card.innerHTML = `
        <div class="detail-tool-name">⚡ ${t.name}</div>
        <div class="detail-tool-desc">${t.description || ""}</div>`;
      detailTools.appendChild(card);
    });
  } else {
    detailTools.innerHTML = `<span class="detail-empty">No direct tools — delegates to subagents</span>`;
  }

  // Skills
  detailSkills.innerHTML = "";
  if (agent.skills && agent.skills.length > 0) {
    agent.skills.forEach((s) => {
      const tag = document.createElement("span");
      tag.className = "detail-skill-tag";
      tag.textContent = s;
      detailSkills.appendChild(tag);
    });
  } else {
    detailSkills.innerHTML = `<span class="detail-empty">—</span>`;
  }

  // Show panel
  detailPanel.classList.remove("hidden");
}

function hideAgentDetail() {
  detailPanel.classList.add("hidden");
  document.querySelectorAll(".agent-item").forEach((el) => el.classList.remove("active"));
}

detailClose.addEventListener("click", hideAgentDetail);

// ── Chat bubble builders ─────────────────────────────────────────────────────

/** Append a gray system-status message (e.g. "Connected to SeaMate"). */
function appendStatus(text) {
  const el = document.createElement("div");
  el.className = "msg status";
  el.innerHTML = `<div class="msg-bubble">${text}</div>`;
  output.appendChild(el);
  scrollBottom();
}

/** Append a red error message. */
function appendError(text) {
  const el = document.createElement("div");
  el.className = "msg error";
  el.innerHTML = `<div class="msg-meta">${ts()}</div><div class="msg-bubble">${text}</div>`;
  output.appendChild(el);
  scrollBottom();
}

/** Create an empty bubble with a blinking cursor, ready to receive tokens. */
function createStreamBubble(label, type) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${type}`;
  wrap.innerHTML = `<div class="msg-meta">${label} · ${ts()}</div><div class="msg-bubble cursor"></div>`;
  output.appendChild(wrap);
  scrollBottom();
  return wrap.querySelector(".msg-bubble");
}

/** Convert raw text → HTML via marked.js, with syntax highlighting + copy buttons. */
function renderMarkdown(raw) {
  const html = marked.parse(raw);
  // Wrap in a temp container to inject copy buttons
  const tmp = document.createElement("div");
  tmp.innerHTML = html;
  tmp.querySelectorAll("pre > code").forEach((block) => {
    // Syntax highlight
    if (window.hljs) hljs.highlightElement(block);
    // Wrap pre in a container with copy button + language label
    const pre = block.parentElement;
    if (pre._wrapped) return;
    pre._wrapped = true;
    const wrapper = document.createElement("div");
    wrapper.className = "code-block";
    const lang = (block.className.match(/language-(\S+)/) || [])[1] || "";
    const header = document.createElement("div");
    header.className = "code-block-header";
    header.innerHTML = `<span class="code-lang">${lang}</span><button class="code-copy-btn" title="Copy">Copy</button>`;
    header.querySelector(".code-copy-btn").addEventListener("click", (e) => {
      navigator.clipboard.writeText(block.textContent).then(() => {
        e.target.textContent = "Copied!";
        setTimeout(() => { e.target.textContent = "Copy"; }, 1500);
      });
    });
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(header);
    wrapper.appendChild(pre);
  });
  return tmp.innerHTML;
}

/** Append a streamed token to the active bubble and re-render markdown. */
function appendToken(bubble, content) {
  bubble.classList.remove("cursor");
  bubble._raw = (bubble._raw || "") + content;
  bubble.innerHTML = renderMarkdown(bubble._raw);
  bubble.classList.add("cursor");
  scrollBottom();
}

/** Remove the blinking cursor and do a final markdown render. */
function finalizeStreamBubble(bubble) {
  if (!bubble) return;
  bubble.classList.remove("cursor");
  if (bubble._raw) bubble.innerHTML = renderMarkdown(bubble._raw);
}

// ── Sidebar busy indicators ──────────────────────────────────────────────────

/** Show a pulsing yellow dot on a sidebar agent while it's working. */
function setAgentBusy(agentId) {
  const dot = document.querySelector(`.agent-item[data-agent-id="${agentId}"] .dot`);
  if (dot) { dot.classList.remove("online"); dot.classList.add("busy"); }
}

/** Reset all sidebar dots back to green (idle). */
function clearAllBusyDots() {
  document.querySelectorAll(".agent-item .dot.busy").forEach((d) => {
    d.classList.remove("busy");
    d.classList.add("online");
  });
}

// ── Interrupt cards (human-in-the-loop approval) ─────────────────────────────

/** Show an approve/reject card when a dangerous tool needs user approval. */
function buildInterruptCard({ interrupt_id, tool, args, description }) {
  const card = document.createElement("div");
  card.className = "interrupt-card";
  card.id = `interrupt-${interrupt_id}`;
  card.innerHTML = `
    <div class="interrupt-title">Approval Required</div>
    <div class="interrupt-tool"><strong>${tool}</strong></div>
    <pre class="interrupt-args">${JSON.stringify(args, null, 2)}</pre>
    <div class="interrupt-actions">
      <button class="approve-btn">Approve</button>
      <button class="reject-btn">Reject</button>
    </div>`;
  card.querySelector(".approve-btn").addEventListener("click", () =>
    resolveInterrupt(interrupt_id, "approve")
  );
  card.querySelector(".reject-btn").addEventListener("click", () =>
    resolveInterrupt(interrupt_id, "reject")
  );
  output.appendChild(card);
  scrollBottom();
}

/** Send the user's approve/reject decision and dim the card. */
function resolveInterrupt(id, decision) {
  socket.sendInterruptResponse(id, decision);
  const card = document.getElementById(`interrupt-${id}`);
  if (card) {
    card.classList.add("resolved");
    card.querySelector(".interrupt-actions").innerHTML =
      `<span class="resolved-label">${decision === "approve" ? "Approved" : "Rejected"}</span>`;
  }
}

// ── Send user message ────────────────────────────────────────────────────────

/** Validate input, show user bubble, and send the message over WebSocket. */
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || !socket?.ready || sending) return;
  sending = true;
  msgInput.value = "";
  setInputEnabled(false);

  // Show user message
  const userWrap = document.createElement("div");
  userWrap.className = "msg user";
  userWrap.innerHTML = `<div class="msg-meta">you · ${ts()}</div><div class="msg-bubble">${renderMarkdown(text)}</div>`;
  output.appendChild(userWrap);
  scrollBottom();

  socket.sendMessage(text);
}

sendBtn.addEventListener("click", sendMessage);
msgInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

// ── WebSocket connection ─────────────────────────────────────────────────────

/** Create the ChatSocket and wire up all event handlers. */
function connectChat() {
  socket = new ChatSocket({
    onStatus: (msg) => {
      setConnected(true);
      setInputEnabled(true);
      appendStatus(msg);
    },
    onDisconnect: () => {
      setConnected(false);
      setInputEnabled(false);
    },
    onError: (err) => {
      appendError(err);
      setInputEnabled(true);
      sending = false;
    },
    onAgentStart: () => {
      currentAgent = null;
      streamingBubble = null;
    },
    onToken: (content, agent) => {
      // If agent changed, finalize old bubble and start new one
      if (agent !== currentAgent) {
        finalizeStreamBubble(streamingBubble);
        const type = agent === "seamate" ? "agent" : "subagent";
        streamingBubble = createStreamBubble(agent, type);
        currentAgent = agent;

        // Update sidebar busy dot for subagents
        if (agent !== "seamate") setAgentBusy(agent);
      }
      if (!streamingBubble) {
        const type = agent === "seamate" ? "agent" : "subagent";
        streamingBubble = createStreamBubble(agent, type);
        currentAgent = agent;
      }
      appendToken(streamingBubble, content);
    },
    onInterrupt: (data) => {
      // Finalize any streaming bubble before showing interrupt card
      finalizeStreamBubble(streamingBubble);
      streamingBubble = null;
      buildInterruptCard(data);
    },
    onAgentEnd: () => {
      finalizeStreamBubble(streamingBubble);
      streamingBubble = null;
      currentAgent = null;
      sending = false;
      clearAllBusyDots();
      setInputEnabled(true);
    },
  });

  socket.connect();
}

// ── Dark / light theme toggle ────────────────────────────────────────────────
const themeToggle = document.getElementById("theme-toggle");
const THEME_STORAGE_KEY = "seamate-theme";

/** Apply a theme ("dark" | "light") and persist to localStorage. */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeToggle.textContent = theme === "dark" ? "☀" : "🌙";
  themeToggle.title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
  localStorage.setItem(THEME_STORAGE_KEY, theme);
  // Switch highlight.js theme
  const darkSheet  = document.getElementById("hljs-theme-dark");
  const lightSheet = document.getElementById("hljs-theme-light");
  if (darkSheet && lightSheet) {
    darkSheet.disabled  = theme !== "dark";
    lightSheet.disabled = theme !== "light";
  }
}

applyTheme(localStorage.getItem(THEME_STORAGE_KEY) || "dark");

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next);
});

// ── Bootstrap ────────────────────────────────────────────────────────────────
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight(code, lang) {
    if (window.hljs && lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    if (window.hljs) return hljs.highlightAuto(code).value;
    return code;
  },
});
loadAgents();
connectChat();
