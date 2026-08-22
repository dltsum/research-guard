"use strict";

const I18N = {
  "zh-CN": {
    skip: "跳到对话",
    thesis: "科研不是一次回答，而是一条可核验的证据链。",
    checking: "正在核验本机环境",
    ready: "Research Guard 已就绪",
    workspaceLabel: "研究工作区",
    workspaceHint: "Codex 只在你选择的工作区内执行本轮任务。",
    sandboxLabel: "权限",
    workspaceWrite: "可写工作区",
    readOnly: "只读分析",
    focusHeading: "选择本轮重点",
    focusHint: "默认由主 Codex 判断；显式选择时最多三项。",
    gateIdea: "界定问题",
    gateEvidence: "建立证据",
    gateMethod: "冻结方法",
    gateVerify: "执行核验",
    gateAudit: "审计交付",
    conversationHeading: "研究对话",
    newThread: "新会话",
    newThreadButton: "新建",
    consoleNote: "控制台说明",
    welcome: "输入科研任务即可直接调用本机 Codex。界面会显示工具活动、门禁状态、资源占用和可点击引用，不会把所有 Research Guard 模块一次性塞入上下文。",
    starterNovelty: "检查 idea 撞车并给出证据链",
    starterAudit: "审计论文、数字、公式与引用",
    starterFigure: "规划并审计一张科研图",
    messageLabel: "给 Codex 的科研任务",
    messagePlaceholder: "描述问题、目标、文件和你希望保留的约束……",
    readyToSend: "环境核验后即可发送。",
    stop: "停止本轮",
    send: "交给 Codex",
    evidenceHeading: "证据与活动",
    copyTrace: "复制",
    idle: "空闲",
    waitingStatus: "等待本机状态核验",
    privacyHeading: "本地与隐私边界",
    privacyBody: "服务只绑定 127.0.0.1，API 使用每次启动生成的令牌。提示词仍会按你的 Codex 登录与配置发送给 Codex；UI 服务器不另存对话正文。",
    shutdown: "关闭本地 UI 服务",
    userRole: "你的任务",
    assistantRole: "Codex / Research Guard",
    errorRole: "执行错误",
    running: "Codex 正在工作；事件会持续回显，不设整任务超时。",
    completed: "本轮完成",
    stopped: "已请求停止本轮",
    traceCopied: "活动轨迹已复制",
    threadCleared: "已建立新的本地会话入口",
    serverStopped: "本地 UI 服务正在关闭",
    noToken: "缺少本地访问令牌；请重新运行 launch.py。",
    selectedLimit: "显式重点最多选择三项。",
    automatic: "自动判断",
    resumeSandbox: "续接会话沿用原会话权限。",
    workspaceMismatch: "当前 thread 绑定了另一个工作区；请恢复原路径或新建会话。",
  },
  en: {
    skip: "Skip to conversation",
    thesis: "Research is not one answer. It is a verifiable chain of evidence.",
    checking: "Checking the local environment",
    ready: "Research Guard is ready",
    workspaceLabel: "Research workspace",
    workspaceHint: "Codex performs this turn in the workspace you choose.",
    sandboxLabel: "Access",
    workspaceWrite: "Write workspace",
    readOnly: "Read-only analysis",
    focusHeading: "Choose this turn's focus",
    focusHint: "Let the main Codex decide, or explicitly select up to three areas.",
    gateIdea: "Frame the problem",
    gateEvidence: "Build evidence",
    gateMethod: "Freeze method",
    gateVerify: "Execute checks",
    gateAudit: "Audit delivery",
    conversationHeading: "Research conversation",
    newThread: "New thread",
    newThreadButton: "New",
    consoleNote: "Console note",
    welcome: "Enter a research task to use the local Codex directly. The console exposes tool activity, gate states, resource use, and clickable citations without loading every Research Guard module at once.",
    starterNovelty: "Check an idea for collisions and build an evidence chain",
    starterAudit: "Audit a paper, numbers, formulas, and citations",
    starterFigure: "Plan and audit a scientific figure",
    messageLabel: "Research task for Codex",
    messagePlaceholder: "Describe the problem, goal, files, and constraints that must be preserved…",
    readyToSend: "Send after the environment check passes.",
    stop: "Stop turn",
    send: "Send to Codex",
    evidenceHeading: "Evidence & activity",
    copyTrace: "Copy",
    idle: "Idle",
    waitingStatus: "Waiting for local status check",
    privacyHeading: "Local and privacy boundary",
    privacyBody: "The server binds only to 127.0.0.1 and protects APIs with a per-launch token. Prompts still go to Codex under your Codex login and configuration; the UI server does not persist transcript bodies.",
    shutdown: "Shut down local UI server",
    userRole: "Your task",
    assistantRole: "Codex / Research Guard",
    errorRole: "Execution error",
    running: "Codex is working. Events remain visible and there is no whole-task timeout.",
    completed: "Turn completed",
    stopped: "Stop requested for this turn",
    traceCopied: "Activity trace copied",
    threadCleared: "Created a new local conversation entry",
    serverStopped: "The local UI server is shutting down",
    noToken: "The local access token is missing; run launch.py again.",
    selectedLimit: "Select at most three explicit focus areas.",
    automatic: "Automatic judgment",
    resumeSandbox: "A resumed thread preserves its original access policy.",
    workspaceMismatch: "This thread is bound to another workspace. Restore that path or start a new thread.",
  },
};

const state = {
  locale: localStorage.getItem("rg-ui-locale") || "zh-CN",
  token: "",
  ready: false,
  running: false,
  runId: null,
  threadId: localStorage.getItem("rg-ui-thread") || null,
  threadWorkspace: localStorage.getItem("rg-ui-thread-workspace") || null,
  pendingWorkspace: null,
  focus: new Set(["auto"]),
  focusOptions: [],
  startedAt: null,
};

const elements = {};

function t(key) {
  return (I18N[state.locale] && I18N[state.locale][key]) || I18N.en[key] || key;
}

function extractToken() {
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const supplied = fragment.get("token");
  if (supplied) {
    sessionStorage.setItem("rg-ui-token", supplied);
    history.replaceState(null, "", window.location.pathname);
  }
  return supplied || sessionStorage.getItem("rg-ui-token") || "";
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-Research-Guard-Token", state.token);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(path, {...options, headers});
}

function applyLanguage() {
  document.documentElement.lang = state.locale;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    if (I18N[state.locale][key]) {
      node.textContent = I18N[state.locale][key];
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  elements.languageButton.textContent = state.locale === "zh-CN" ? "EN" : "中文";
  renderFocusOptions();
  updateComposerState();
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 4200);
}

function renderFocusOptions() {
  if (!elements.focusOptions || !state.focusOptions.length) return;
  elements.focusOptions.replaceChildren();
  state.focusOptions.forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "focus-option";
    button.dataset.focusId = option.id;
    button.setAttribute("aria-pressed", state.focus.has(option.id) ? "true" : "false");

    const glyph = document.createElement("span");
    glyph.className = "focus-glyph";
    glyph.setAttribute("aria-hidden", "true");
    glyph.textContent = "✓";

    const copy = document.createElement("span");
    copy.className = "focus-copy";
    const label = document.createElement("strong");
    label.textContent = state.locale === "zh-CN" ? option.label_zh : option.label_en;
    const description = document.createElement("small");
    description.textContent = state.locale === "zh-CN" ? option.description_zh : option.description_en;
    copy.append(label, description);
    button.append(glyph, copy);
    button.addEventListener("click", () => toggleFocus(option.id));
    elements.focusOptions.append(button);
  });
}

function toggleFocus(id) {
  if (id === "auto") {
    state.focus = new Set(["auto"]);
  } else {
    state.focus.delete("auto");
    if (state.focus.has(id)) {
      state.focus.delete(id);
    } else if (state.focus.size < 3) {
      state.focus.add(id);
    } else {
      showToast(t("selectedLimit"));
    }
    if (!state.focus.size) state.focus.add("auto");
  }
  renderFocusOptions();
}

function elapsedTime() {
  if (!state.startedAt) return "00:00";
  const seconds = Math.max(0, Math.floor((Date.now() - state.startedAt) / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function addActivity(kind, message) {
  const item = document.createElement("li");
  item.dataset.kind = kind;
  const time = document.createElement("time");
  time.textContent = elapsedTime();
  const copy = document.createElement("span");
  copy.textContent = message;
  item.append(time, copy);
  elements.activityLog.append(item);
  while (elements.activityLog.children.length > 200) {
    elements.activityLog.firstElementChild.remove();
  }
  elements.activityLog.scrollTop = elements.activityLog.scrollHeight;
}

function appendLinkedText(container, text) {
  const pattern = /\[([^\]]+)\]\((https:\/\/[^)\s]+)\)|(https:\/\/[^\s<>()]+)/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      container.append(document.createTextNode(text.slice(cursor, match.index)));
    }
    const rawTarget = match[2] || match[3];
    const trailing = rawTarget.match(/[.,;:!?]+$/);
    const target = trailing ? rawTarget.slice(0, -trailing[0].length) : rawTarget;
    const anchor = document.createElement("a");
    anchor.href = target;
    anchor.textContent = match[1] || target;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    container.append(anchor);
    if (trailing) container.append(document.createTextNode(trailing[0]));
    cursor = pattern.lastIndex;
  }
  if (cursor < text.length) {
    container.append(document.createTextNode(text.slice(cursor)));
  }
}

function appendRichText(container, text) {
  const paragraphs = String(text || "").split(/\n{2,}/);
  paragraphs.forEach((paragraph) => {
    const node = document.createElement("p");
    paragraph.split("\n").forEach((line, index) => {
      if (index) node.append(document.createElement("br"));
      appendLinkedText(node, line);
    });
    container.append(node);
  });
}

function appendMessage(role, text, kind = "assistant") {
  const article = document.createElement("article");
  article.className = `message ${kind}-message`;
  const label = document.createElement("p");
  label.className = "message-role";
  label.textContent = role;
  article.append(label);
  if (kind === "assistant") {
    appendRichText(article, text);
  } else {
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    article.append(paragraph);
  }
  elements.transcript.append(article);
  elements.transcript.scrollTop = elements.transcript.scrollHeight;
}

function formatBytes(value) {
  if (!Number.isFinite(value)) return "—";
  return `${(value / 1048576).toFixed(1)} MiB`;
}

function updateComposerState() {
  elements.sendButton.disabled = !state.ready || state.running;
  elements.stopButton.disabled = !state.running || !state.runId;
  document.body.dataset.running = state.running ? "true" : "false";
  if (state.running) {
    elements.composerState.textContent = t("running");
    elements.runReadout.textContent = elapsedTime();
  } else if (state.ready) {
    elements.composerState.textContent = state.threadId ? t("resumeSandbox") : t("readyToSend");
    elements.runReadout.textContent = t("idle");
  } else {
    elements.composerState.textContent = t("readyToSend");
  }
}

async function loadStatus() {
  if (!state.token) {
    elements.connectionStatus.dataset.state = "error";
    elements.connectionStatus.textContent = t("noToken");
    showToast(t("noToken"));
    return;
  }
  try {
    const response = await api("/api/status");
    const value = await response.json();
    if (!response.ok) throw new Error(value.message || value.code || `HTTP ${response.status}`);
    state.ready = value.status === "READY" && value.codex.ready && value.plugin.ready;
    state.focusOptions = value.focus_options || [];
    elements.codexVersion.textContent = value.codex.version;
    elements.pluginVersion.textContent = value.plugin.version;
    elements.workspaceInput.value = localStorage.getItem("rg-ui-workspace") || value.default_workspace;
    if (state.threadId && !state.threadWorkspace) {
      state.threadWorkspace = elements.workspaceInput.value;
      localStorage.setItem("rg-ui-thread-workspace", state.threadWorkspace);
    }
    elements.connectionStatus.dataset.state = state.ready ? "ready" : "error";
    elements.connectionStatus.textContent = state.ready ? t("ready") : value.status;
    addActivity("status", `${value.codex.version} · Research Guard ${value.plugin.version}`);
    renderFocusOptions();
    updateComposerState();
  } catch (error) {
    state.ready = false;
    elements.connectionStatus.dataset.state = "error";
    elements.connectionStatus.textContent = String(error.message || error);
    addActivity("error", String(error.message || error));
    showToast(String(error.message || error));
  }
}

function summarizeActivity(event) {
  const value = event.event || {};
  if (value.item_type === "command_execution") {
    return value.command ? `command · ${value.command}` : "command execution";
  }
  const parts = [value.item_type || value.event_type || "activity"];
  ["server", "tool", "name", "status"].forEach((key) => {
    if (value[key]) parts.push(value[key]);
  });
  return parts.join(" · ");
}

function handleStreamEvent(event) {
  switch (event.kind) {
    case "run":
      state.runId = event.run_id;
      state.pendingWorkspace = event.workspace || null;
      elements.runReadout.textContent = event.run_id.slice(0, 8);
      addActivity("status", event.resumed ? `resume · ${event.run_id.slice(0, 8)}` : `new run · ${event.run_id.slice(0, 8)}`);
      updateComposerState();
      break;
    case "thread":
      if (event.thread_id) {
        state.threadId = event.thread_id;
        localStorage.setItem("rg-ui-thread", event.thread_id);
        state.threadWorkspace = state.pendingWorkspace;
        if (state.threadWorkspace) localStorage.setItem("rg-ui-thread-workspace", state.threadWorkspace);
        elements.threadLabel.textContent = event.thread_id;
        addActivity("status", `thread · ${event.thread_id}`);
      }
      break;
    case "assistant":
      appendMessage(t("assistantRole"), event.text, "assistant");
      break;
    case "activity":
      addActivity("activity", summarizeActivity(event));
      break;
    case "status":
      addActivity("status", event.message || event.phase || "status");
      break;
    case "warning":
    case "diagnostic":
      addActivity(event.kind, event.message || event.kind);
      break;
    case "resource":
      elements.memoryReadout.textContent = `${formatBytes(event.owned_bytes)} / ${formatBytes(event.limit_bytes)}`;
      break;
    case "usage":
      addActivity("usage", `usage · in ${event.usage.input_tokens || 0} · out ${event.usage.output_tokens || 0}`);
      break;
    case "heartbeat":
      elements.runReadout.textContent = elapsedTime();
      break;
    case "error":
      addActivity("error", `${event.code || "ERROR"} · ${event.message || ""}`);
      appendMessage(t("errorRole"), event.message || event.code || "Error", "error");
      break;
    case "done":
      elements.memoryReadout.textContent = `${formatBytes(event.peak_owned_bytes)} peak / 512 MiB`;
      addActivity(event.success ? "status" : "error", `${event.success ? "PASS" : "FAIL"} · exit ${event.exit_code}`);
      break;
    default:
      addActivity("activity", event.kind || "event");
  }
}

async function sendMessage(event) {
  event.preventDefault();
  if (!state.ready || state.running) return;
  const message = elements.messageInput.value.trim();
  if (!message) return;
  const payload = {
    message,
    workspace: elements.workspaceInput.value.trim(),
    sandbox: elements.sandboxSelect.value,
    focus: [...state.focus],
    locale: state.locale,
    thread_id: state.threadId,
  };
  if (state.threadId && state.threadWorkspace && payload.workspace !== state.threadWorkspace) {
    showToast(t("workspaceMismatch"));
    addActivity("warning", t("workspaceMismatch"));
    return;
  }
  localStorage.setItem("rg-ui-workspace", payload.workspace);
  appendMessage(t("userRole"), message, "user");
  elements.messageInput.value = "";
  state.running = true;
  state.runId = null;
  state.startedAt = Date.now();
  updateComposerState();

  try {
    const response = await api("/api/chat", {method: "POST", body: JSON.stringify(payload)});
    if (!response.ok) {
      const value = await response.json();
      throw new Error(`${value.code || response.status}: ${value.message || "Request failed"}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split("\n");
      buffer = lines.pop();
      lines.filter(Boolean).forEach((line) => handleStreamEvent(JSON.parse(line)));
    }
    buffer += decoder.decode();
    if (buffer.trim()) handleStreamEvent(JSON.parse(buffer));
  } catch (error) {
    const messageText = String(error.message || error);
    addActivity("error", messageText);
    appendMessage(t("errorRole"), messageText, "error");
    showToast(messageText);
  } finally {
    state.running = false;
    state.runId = null;
    state.pendingWorkspace = null;
    state.startedAt = null;
    updateComposerState();
  }
}

async function stopRun() {
  if (!state.runId) return;
  const response = await api("/api/cancel", {method: "POST", body: JSON.stringify({run_id: state.runId})});
  if (response.ok) {
    addActivity("warning", t("stopped"));
    showToast(t("stopped"));
  }
}

function newThread() {
  if (state.running) return;
  state.threadId = null;
  localStorage.removeItem("rg-ui-thread");
  localStorage.removeItem("rg-ui-thread-workspace");
  state.threadWorkspace = null;
  state.pendingWorkspace = null;
  elements.threadLabel.textContent = t("newThread");
  const messages = [...elements.transcript.querySelectorAll(".message:not(.system-message)")];
  messages.forEach((message) => message.remove());
  addActivity("status", t("threadCleared"));
  updateComposerState();
}

async function copyTrace() {
  const lines = [...elements.activityLog.querySelectorAll("li")].map((item) => item.innerText.trim());
  await navigator.clipboard.writeText(lines.join("\n"));
  showToast(t("traceCopied"));
}

async function shutdownServer() {
  const response = await api("/api/shutdown", {method: "POST", body: "{}"});
  if (response.ok) {
    state.ready = false;
    updateComposerState();
    showToast(t("serverStopped"));
  }
}

function bindElements() {
  [
    "connectionStatus", "languageButton", "workspaceInput", "sandboxSelect", "focusOptions",
    "threadLabel", "newThreadButton", "transcript", "composer", "messageInput", "composerState",
    "stopButton", "sendButton", "copyTraceButton", "codexVersion", "pluginVersion", "memoryReadout",
    "runReadout", "activityLog", "shutdownButton", "toast",
  ].forEach((id) => { elements[id] = document.getElementById(id); });
}

function initialize() {
  bindElements();
  state.token = extractToken();
  if (!I18N[state.locale]) state.locale = "zh-CN";
  if (state.threadId) elements.threadLabel.textContent = state.threadId;
  applyLanguage();
  elements.languageButton.addEventListener("click", () => {
    state.locale = state.locale === "zh-CN" ? "en" : "zh-CN";
    localStorage.setItem("rg-ui-locale", state.locale);
    applyLanguage();
  });
  elements.composer.addEventListener("submit", sendMessage);
  elements.stopButton.addEventListener("click", stopRun);
  elements.newThreadButton.addEventListener("click", newThread);
  elements.copyTraceButton.addEventListener("click", copyTrace);
  elements.shutdownButton.addEventListener("click", shutdownServer);
  document.querySelectorAll(".starter").forEach((button) => {
    button.addEventListener("click", () => {
      elements.messageInput.value = t(button.dataset.promptKey);
      elements.messageInput.focus();
    });
  });
  window.setInterval(() => {
    if (state.running) updateComposerState();
  }, 1000);
  loadStatus();
}

document.addEventListener("DOMContentLoaded", initialize);
