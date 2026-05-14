const SUGGESTIONS = [
  "燃油泵压力不足如何排查",
  "起落架卡滞可能原因",
  "查询 液压系统 与 维修动作 的关系",
  "检索 实体:燃油系统"
];

const mockGraph = {
  nodes: [
    { id: "故障", label: "燃油泵压力不足", type: "故障现象" },
    { id: "部件", label: "燃油泵", type: "部件" },
    { id: "原因", label: "滤网堵塞", type: "故障原因" },
    { id: "动作", label: "更换滤芯", type: "维修动作" },
    { id: "系统", label: "燃油系统", type: "系统" }
  ],
  links: [
    { source: "故障", target: "部件", label: "涉及" },
    { source: "故障", target: "原因", label: "可能原因" },
    { source: "原因", target: "动作", label: "建议动作" },
    { source: "部件", target: "系统", label: "所属" }
  ]
};

const state = {
  conversations: [],
  activeId: null,
  loading: false,
  status: "等待输入"
};

const config = window.APP_CONFIG || { useMock: true, apiBase: "" };

const dom = {
  historyList: document.getElementById("historyList"),
  newChatBtn: document.getElementById("newChatBtn"),
  messages: document.getElementById("messages"),
  scrollArea: document.getElementById("scrollArea"),
  resultPanel: document.getElementById("resultPanel"),
  composer: document.getElementById("composer"),
  input: document.getElementById("input"),
  statusBadge: document.getElementById("statusBadge"),
  suggestions: document.getElementById("suggestions")
};

function createConversation(seed) {
  return {
    id: `c_${Date.now()}_${Math.random().toString(16).slice(2, 6)}`,
    title: seed ? seed.slice(0, 10) : "新对话",
    preview: seed ? seed.slice(0, 18) : "",
    messages: [],
    results: []
  };
}

function setStatus(text) {
  state.status = text;
  dom.statusBadge.textContent = state.loading ? text : "就绪";
}

function getActiveConversation() {
  return state.conversations.find((item) => item.id === state.activeId) || null;
}

function updateConversation(id, updater) {
  state.conversations = state.conversations.map((item) =>
    item.id === id ? updater(item) : item
  );
}

function renderHistory() {
  dom.historyList.innerHTML = "";
  state.conversations.forEach((item) => {
    const entry = document.createElement("div");
    entry.className = `history-item ${item.id === state.activeId ? "active" : ""}`;
    const title = document.createElement("strong");
    title.textContent = item.title || "未命名对话";
    const preview = document.createElement("p");
    preview.textContent = item.preview || "暂无内容";
    entry.appendChild(title);
    entry.appendChild(preview);
    entry.addEventListener("click", () => {
      state.activeId = item.id;
      render();
    });
    dom.historyList.appendChild(entry);
  });
}

function renderMessages() {
  dom.messages.innerHTML = "";
  if (dom.resultPanel) {
    dom.resultPanel.innerHTML = "";
  }
  const active = getActiveConversation();
  if (!active) return;

  active.messages.forEach((msg) => {
    const bubble = document.createElement("div");
    bubble.className = `message ${msg.role}`;
    bubble.textContent = msg.content;
    dom.messages.appendChild(bubble);
  });

  const latest = active.results[active.results.length - 1];
  if (latest && dom.resultPanel) {
    dom.resultPanel.appendChild(buildResultPanel(latest));
  }

  if (dom.scrollArea) {
    dom.scrollArea.scrollTop = dom.scrollArea.scrollHeight;
  }
}

function buildResultPanel(result) {
  const panel = document.createElement("div");
  panel.className = "result-panel";

  const tabs = document.createElement("div");
  tabs.className = "tabs";

  const tabText = document.createElement("button");
  tabText.className = "tab active";
  tabText.textContent = "自然语言结果";

  const tabGraph = document.createElement("button");
  tabGraph.className = "tab";
  tabGraph.textContent = "图谱可视化";

  tabs.appendChild(tabText);
  tabs.appendChild(tabGraph);

  const content = document.createElement("div");
  content.appendChild(buildTextResult(result));

  tabText.addEventListener("click", () => {
    tabText.classList.add("active");
    tabGraph.classList.remove("active");
    content.innerHTML = "";
    content.appendChild(buildTextResult(result));
  });

  tabGraph.addEventListener("click", () => {
    tabGraph.classList.add("active");
    tabText.classList.remove("active");
    content.innerHTML = "";
    content.appendChild(buildGraphResult(result));
  });

  panel.appendChild(tabs);
  panel.appendChild(content);
  return panel;
}

function buildTextResult(result) {
  const wrapper = document.createElement("div");
  const answer = document.createElement("p");
  answer.style.margin = "0";
  answer.style.fontWeight = "600";
  answer.textContent = result.composed.answer || "暂无结果";
  wrapper.appendChild(answer);

  const list = document.createElement("ul");
  (result.composed.highlights || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
  wrapper.appendChild(list);

  const meta = document.createElement("div");
  meta.style.marginTop = "8px";
  meta.style.fontSize = "12px";
  meta.style.color = "#5b6476";
  meta.textContent = `结果条数：${result.executed.records?.length || 0}`;
  wrapper.appendChild(meta);
  return wrapper;
}

function buildGraphResult(result) {
  const wrapper = document.createElement("div");
  wrapper.className = "graph";
  const graph = result.executed.graph;
  if (!graph || !graph.nodes?.length) {
    const placeholder = document.createElement("div");
    placeholder.className = "graph-placeholder";
    placeholder.textContent = "暂无可视化数据";
    wrapper.appendChild(placeholder);
    return wrapper;
  }

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 520 360");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "图谱可视化");

  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
  marker.setAttribute("id", "arrow");
  marker.setAttribute("markerWidth", "10");
  marker.setAttribute("markerHeight", "10");
  marker.setAttribute("refX", "10");
  marker.setAttribute("refY", "5");
  marker.setAttribute("orient", "auto-start-reverse");
  const arrowPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  arrowPath.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  arrowPath.setAttribute("fill", "#ff7f3f");
  marker.appendChild(arrowPath);
  defs.appendChild(marker);
  svg.appendChild(defs);

  const layout = layoutGraph(graph.nodes, graph.links);

  layout.links.forEach((link) => {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", link.sourceNode?.x || 0);
    line.setAttribute("y1", link.sourceNode?.y || 0);
    line.setAttribute("x2", link.targetNode?.x || 0);
    line.setAttribute("y2", link.targetNode?.y || 0);
    line.setAttribute("stroke", "#3c4454");
    line.setAttribute("stroke-width", "1.2");
    line.setAttribute("marker-end", "url(#arrow)");
    svg.appendChild(line);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", (link.sourceNode?.x + link.targetNode?.x) / 2);
    label.setAttribute("y", (link.sourceNode?.y + link.targetNode?.y) / 2);
    label.setAttribute("fill", "#d7d3c8");
    label.setAttribute("font-size", "10");
    label.textContent = link.label || "";
    svg.appendChild(label);
  });

  layout.nodes.forEach((node) => {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", "22");
    circle.setAttribute("fill", "#1f8b7a");
    svg.appendChild(circle);

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", node.x);
    text.setAttribute("y", node.y + 4);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "#fefaf0");
    text.setAttribute("font-size", "10");
    text.textContent = node.label;
    svg.appendChild(text);
  });

  wrapper.appendChild(svg);
  return wrapper;
}

function layoutGraph(nodes, links) {
  if (!nodes.length) return { nodes: [], links: [] };
  const center = nodes[0];
  const rest = nodes.slice(1);
  const radius = 140;
  const positioned = [];
  positioned.push({ ...center, x: 260, y: 180 });
  rest.forEach((node, index) => {
    const angle = (index / rest.length) * Math.PI * 2;
    positioned.push({
      ...node,
      x: 260 + Math.cos(angle) * radius,
      y: 180 + Math.sin(angle) * radius
    });
  });
  const byId = Object.fromEntries(positioned.map((node) => [node.id, node]));
  const resolvedLinks = (links || []).map((link) => ({
    ...link,
    sourceNode: byId[link.source],
    targetNode: byId[link.target]
  }));
  return { nodes: positioned, links: resolvedLinks };
}

function renderSuggestions() {
  dom.suggestions.innerHTML = "";
  SUGGESTIONS.forEach((text) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "suggestion";
    btn.textContent = text;
    btn.addEventListener("click", () => {
      dom.input.value = text;
      dom.input.focus();
    });
    dom.suggestions.appendChild(btn);
  });
}

function renderComposer() {
  const active = getActiveConversation();
  const centered = !active || active.messages.length === 0;
  dom.composer.classList.toggle("centered", centered);
  dom.composer.classList.toggle("docked", !centered);
}

function render() {
  renderHistory();
  renderMessages();
  renderComposer();
}

async function postJson(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(`${config.apiBase}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}

async function runSkillPipeline(input, history) {
  if (config.useMock) {
    return buildMockResult(input, "");
  }

  try {
    const parsed = await postJson("/api/skills/parse", { input, history });
    const executed = await postJson("/api/skills/execute", {
      skill: parsed.skill,
      params: parsed.params
    });
    const composed = await postJson("/api/skills/compose", {
      input,
      skill: parsed.skill,
      params: parsed.params,
      result: executed
    });
    return { parsed, executed, composed };
  } catch (error) {
    return buildMockResult(input, error?.message || "");
  }
}

function buildMockResult(input, errorMessage) {
  const isFault = /故障|异常|失效|报警/.test(input);
  const skill = isFault ? "fault_investigation" : "entity_lookup";
  const parsed = {
    skill,
    params: {
      name: input
    }
  };

  const executed = {
    records: [
      { source: "燃油泵", relation: "位于", target: "燃油系统" },
      { source: "燃油泵", relation: "导致", target: "供油压力不足" }
    ],
    graph: mockGraph
  };

  const composed = {
    answer: errorMessage
      ? "当前后端不可用，展示的是本地示例结果。"
      : "已为你定位到燃油泵相关的故障联查路径，可优先检查滤网堵塞并执行更换滤芯动作。",
    highlights: [
      "建议先排查滤网堵塞与电源供给",
      "燃油系统内可同步检测供油压力",
      "维修动作：清洗或更换滤芯"
    ]
  };

  return { parsed, executed, composed };
}

function handleNewChat() {
  const convo = createConversation();
  state.conversations = [convo, ...state.conversations];
  state.activeId = convo.id;
  setStatus("等待输入");
  render();
}

async function handleSubmit(event) {
  event.preventDefault();
  if (state.loading) return;

  const trimmed = dom.input.value.trim();
  if (!trimmed) return;

  let convo = getActiveConversation();
  if (!convo) {
    convo = createConversation(trimmed);
    state.conversations = [convo, ...state.conversations];
    state.activeId = convo.id;
  }

  updateConversation(convo.id, (item) => ({
    ...item,
    title: item.title === "新对话" ? trimmed.slice(0, 10) : item.title,
    preview: trimmed.slice(0, 18),
    messages: [...item.messages, { role: "user", content: trimmed }]
  }));

  dom.input.value = "";
  state.loading = true;
  setStatus("解析技能中");
  render();

  const history = (convo.messages || []).map((msg) => ({
    role: msg.role,
    content: msg.content
  }));

  const pipeline = await runSkillPipeline(trimmed, history);

  setStatus("生成结果中");

  updateConversation(convo.id, (item) => ({
    ...item,
    messages: [...item.messages, { role: "bot", content: pipeline.composed.answer }],
    results: [...item.results, pipeline]
  }));

  state.loading = false;
  setStatus("完成");
  render();
}

function init() {
  renderSuggestions();
  dom.newChatBtn.addEventListener("click", handleNewChat);
  dom.composer.addEventListener("submit", handleSubmit);
  handleNewChat();
}

init();
