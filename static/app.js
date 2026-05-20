const canvas = document.getElementById("battle-canvas");
const ctx = canvas.getContext("2d");

const form = document.getElementById("experiment-form");
const agentASelect = document.getElementById("agent-a");
const agentBSelect = document.getElementById("agent-b");
const llmModelAPanel = document.getElementById("llm-model-a-panel");
const llmModelBPanel = document.getElementById("llm-model-b-panel");
const llmModelAInput = document.getElementById("llm-model-a");
const llmModelBInput = document.getElementById("llm-model-b");
const hfSearchAInput = document.getElementById("hf-search-a");
const hfSearchBInput = document.getElementById("hf-search-b");
const hfResultsA = document.getElementById("hf-results-a");
const hfResultsB = document.getElementById("hf-results-b");
const numRoundsInput = document.getElementById("num-rounds");
const numBattlefieldsInput = document.getElementById("num-battlefields");
const totalResourcesInput = document.getElementById("total-resources");
const runButton = document.getElementById("run-button");
const downloadHistoryButton = document.getElementById("download-history");
const statusBanner = document.getElementById("status-banner");
const historyLog = document.getElementById("history-log");
const roundScrubber = document.getElementById("round-scrubber");
const prevRoundButton = document.getElementById("prev-round");
const nextRoundButton = document.getElementById("next-round");
const playToggleButton = document.getElementById("play-toggle");

const ui = {
  scoreA: document.getElementById("score-a"),
  scoreB: document.getElementById("score-b"),
  roundCounter: document.getElementById("round-counter"),
  winner: document.getElementById("winner"),
  roundScoreA: document.getElementById("round-score-a"),
  roundScoreB: document.getElementById("round-score-b"),
  actionA: document.getElementById("action-a"),
  actionB: document.getElementById("action-b"),
};

let activeMatch = null;
let activeRoundIndex = -1;
let revealStart = 0;
let replayTimer = null;
let isPlaying = false;
let particles = [];
let displayedScoreA = 0;
let displayedScoreB = 0;
const roundDuration = 3200;
const searchDebounceTimers = {};

function currentBattlefieldCount() {
  if (activeMatch) return activeMatch.num_battlefields;
  return Number(numBattlefieldsInput.value) || 5;
}

function currentTotalResources() {
  if (activeMatch) return activeMatch.total_resources;
  return Number(totalResourcesInput.value) || 100;
}

function battlefieldName(index) {
  return `battlefield_${index + 1}`;
}

function requestJson(path, options = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(options.method || "GET", path);
    xhr.setRequestHeader("Accept", "application/json");
    if (options.body) {
      xhr.setRequestHeader("Content-Type", "application/json");
    }
    xhr.onload = () => {
      let data = {};
      try {
        data = JSON.parse(xhr.responseText || "{}");
      } catch (error) {
        reject(new Error("Invalid JSON response"));
        return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(data.error || `HTTP ${xhr.status}`));
        return;
      }
      resolve(data);
    };
    xhr.onerror = () => reject(new Error("Network error"));
    xhr.send(options.body || null);
  });
}

const LLM_LOCAL_TYPES = ["llm", "llm-local"];
const LLM_API_TYPES = ["llm-api"];
const ALL_LLM_TYPES = LLM_LOCAL_TYPES.concat(LLM_API_TYPES);

function updateLlmModelPanels() {
  updateLlmModelSide(agentASelect.value, llmModelAPanel, llmModelAInput, hfSearchAInput, hfResultsA);
  updateLlmModelSide(agentBSelect.value, llmModelBPanel, llmModelBInput, hfSearchBInput, hfResultsB);
}

function updateLlmModelSide(agentType, panel, modelInput, searchInput, results) {
  const isLocal = LLM_LOCAL_TYPES.includes(agentType);
  const isAPI = LLM_API_TYPES.includes(agentType);
  panel.hidden = !(isLocal || isAPI);
  searchInput.parentElement.hidden = !isLocal;
  results.hidden = !isLocal;

  if (isAPI && !modelInput.dataset.userSet) {
    modelInput.value = "deepseek-v4-pro";
  } else if (isLocal && !modelInput.dataset.userSet) {
    modelInput.value = "Qwen/Qwen2.5-0.5B-Instruct";
  }
}

function modelSearchConfig(side) {
  if (side === "a") {
    return {
      modelInput: llmModelAInput,
      searchInput: hfSearchAInput,
      results: hfResultsA,
    };
  }
  return {
    modelInput: llmModelBInput,
    searchInput: hfSearchBInput,
    results: hfResultsB,
  };
}

function renderModelResults(side, models) {
  const { modelInput, results } = modelSearchConfig(side);
  results.innerHTML = "";

  if (!models.length) {
    const empty = document.createElement("div");
    empty.className = "model-result-empty";
    const title = document.createElement("strong");
    title.textContent = "No models found";
    const detail = document.createElement("span");
    detail.textContent = "Try a broader query.";
    empty.append(title, detail);
    results.appendChild(empty);
    return;
  }

  models.forEach((model) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "model-result";

    const title = document.createElement("strong");
    title.className = "model-result-title";
    title.textContent = model.id;

    const detail = document.createElement("span");
    detail.className = "model-result-meta";
    detail.textContent = `downloads=${model.downloads || 0}  likes=${model.likes || 0}`;

    const tag = document.createElement("span");
    tag.className = "model-result-tag";
    tag.textContent = model.pipeline_tag || "model";

    button.append(title, detail, tag);
    button.addEventListener("click", () => {
      modelInput.value = model.id;
      results.innerHTML = "";
    });
    results.appendChild(button);
  });
}

async function searchHuggingFaceModels(side) {
  const { modelInput, searchInput, results } = modelSearchConfig(side);
  const query = (searchInput.value || modelInput.value || "text generation").trim();
  if (!query) return;

  results.innerHTML = "";
  const pending = document.createElement("div");
  pending.className = "model-result-empty";
  const pendingTitle = document.createElement("strong");
  pendingTitle.textContent = "Searching Hugging Face...";
  const pendingDetail = document.createElement("span");
  pendingDetail.textContent = `query=${query}`;
  pending.append(pendingTitle, pendingDetail);
  results.appendChild(pending);

  try {
    const data = await requestJson(
      `/api/huggingface-models?q=${encodeURIComponent(query)}&limit=8`,
    );
    renderModelResults(side, data.models || []);
  } catch (error) {
    results.innerHTML = "";
    const failed = document.createElement("div");
    failed.className = "model-result-empty";
    const failedTitle = document.createElement("strong");
    failedTitle.textContent = "Search failed";
    const failedDetail = document.createElement("span");
    failedDetail.textContent = error.message;
    failed.append(failedTitle, failedDetail);
    results.appendChild(failed);
  }
}

function debounceModelSearch(side) {
  clearTimeout(searchDebounceTimers[side]);
  searchDebounceTimers[side] = setTimeout(() => {
    searchHuggingFaceModels(side);
  }, 420);
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(320, Math.floor(rect.width * dpr));
  canvas.height = Math.max(320, Math.floor(rect.height * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function canvasSize() {
  const rect = canvas.getBoundingClientRect();
  return { width: rect.width, height: rect.height };
}

function easeOutCubic(value) {
  return 1 - Math.pow(1 - value, 3);
}

function lerp(start, end, amount) {
  return start + (end - start) * amount;
}

function drawRoundedRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function fillRoundedRect(x, y, w, h, r, fill, stroke = null, lineWidth = 1) {
  drawRoundedRect(x, y, w, h, r);
  ctx.fillStyle = fill;
  ctx.fill();
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }
}

function drawBackground(width, height, t) {
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#fffefa");
  gradient.addColorStop(0.52, "#f7f4ea");
  gradient.addColorStop(1, "#f0f4f1");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.globalAlpha = 0.55;
  ctx.strokeStyle = "#e1e5e2";
  ctx.lineWidth = 1;
  for (let x = 0; x < width; x += 32) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y < height; y += 32) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.globalAlpha = 0.22;
  for (let i = 0; i < 18; i += 1) {
    const x = (i * 179) % width;
    const y = (i * 109) % height;
    const color = i % 2 === 0 ? "#f28c38" : "#2d9cdb";
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function battlefieldRects(width, height) {
  const margin = Math.max(16, width * 0.026);
  const gap = Math.max(8, width * 0.012);
  const top = Math.max(142, height * 0.23);
  const count = currentBattlefieldCount();
  const rows = count > 6 ? 2 : 1;
  const columns = Math.ceil(count / rows);
  const available = width - margin * 2 - gap * (columns - 1);
  const cardWidth = available / columns;
  const rowGap = rows > 1 ? Math.max(12, height * 0.02) : 0;
  const cardHeight = Math.min(
    rows > 1 ? 230 : 330,
    Math.max(168, (height - top - 116 - rowGap * (rows - 1)) / rows),
  );

  return Array.from({ length: count }, (_, index) => {
    const row = Math.floor(index / columns);
    const column = index % columns;
    return {
      name: battlefieldName(index),
      x: margin + column * (cardWidth + gap),
      y: top + row * (cardHeight + rowGap) + Math.sin(index * 1.55) * 7,
      w: cardWidth,
      h: cardHeight,
    };
  });
}

function clampActionValue(round, key, index) {
  return round && round[key] && typeof round[key][index] === "number" ? round[key][index] : 0;
}

function fieldWinner(round, index) {
  const a = clampActionValue(round, "action_a", index);
  const b = clampActionValue(round, "action_b", index);
  if (a > b) return "A";
  if (b > a) return "B";
  return "Tie";
}

function winnerColor(winner) {
  if (winner === "A") return "#f28c38";
  if (winner === "B") return "#2d9cdb";
  return "#d5a11e";
}

function drawFlag(x, y, color, side = 1, progress = 1) {
  const drop = (1 - progress) * -36;
  ctx.save();
  ctx.translate(0, drop);
  ctx.globalAlpha = progress;
  ctx.strokeStyle = "#151817";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x, y - 54);
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(x, y - 52);
  ctx.lineTo(x + side * 44, y - 42);
  ctx.lineTo(x, y - 29);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawTroopStack(x, y, count, color, side, progress, compact = false) {
  const visibleCount = Math.min(22, Math.ceil(count / 3.5));
  const columns = compact ? 4 : 7;
  const spacing = compact ? 7 : 10;
  const radius = compact ? 3.8 : 5;
  for (let i = 0; i < visibleCount; i += 1) {
    const row = Math.floor(i / columns);
    const col = i % columns;
    const drift = (1 - progress) * side * (compact ? 42 : 80);
    const px = x + col * spacing + drift;
    const py = y - row * (compact ? 8 : 11) + Math.sin(i * 1.3 + progress * 4) * 1.7;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(px, py, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,0.25)";
    ctx.beginPath();
    ctx.arc(px - 1, py - 1.3, Math.max(1, radius * 0.28), 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawValueChip(x, y, value, color, align = "left", revealed = true, compact = false) {
  const label = revealed ? String(value) : "?";
  const fontSize = compact ? 20 : 28;
  ctx.font = `900 ${fontSize}px ui-monospace, monospace`;
  const width = Math.max(compact ? 38 : 54, ctx.measureText(label).width + (compact ? 16 : 24));
  const height = compact ? 34 : 42;
  const left = align === "right" ? x - width : x;
  fillRoundedRect(left, y, width, height, 8, "rgba(8, 11, 11, 0.58)", color, 1.5);
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, left + width / 2, y + height / 2 + 1);
  ctx.textBaseline = "alphabetic";
}

function drawBattlefield(rect, round, index, revealProgress, t) {
  const count = currentBattlefieldCount();
  const fieldStart = index / count;
  const localProgress = easeOutCubic(Math.max(0, Math.min(1, revealProgress * count - index)));
  const isRevealed = round && revealProgress > fieldStart;
  const winner = round && isRevealed ? fieldWinner(round, index) : null;
  const palette = ["#ffffff", "#fbfaf5", "#f8fbfa", "#fff9ee", "#f7fbff"][index % 5];
  const border = winner ? winnerColor(winner) : "rgba(247,241,228,0.22)";
  const pulse = winner ? 13 + Math.sin(t / 120) * 2 : 4;

  ctx.save();
  ctx.shadowColor = winner ? border : "rgba(38,50,56,0.16)";
  ctx.shadowBlur = pulse;
  ctx.shadowOffsetY = 8;
  fillRoundedRect(rect.x, rect.y, rect.w, rect.h, 7, palette, winner ? border : "#dfe5e2", winner ? 2.2 : 1.1);
  ctx.restore();

  const wash = ctx.createLinearGradient(rect.x, rect.y, rect.x + rect.w, rect.y + rect.h);
  wash.addColorStop(0, "rgba(255,255,255,0.78)");
  wash.addColorStop(0.45, "rgba(255,255,255,0.06)");
  wash.addColorStop(1, "rgba(38,50,56,0.06)");
  fillRoundedRect(rect.x + 1, rect.y + 1, rect.w - 2, rect.h - 2, 7, wash);

  ctx.save();
  ctx.globalAlpha = 0.55;
  ctx.strokeStyle = "#dfe5e2";
  ctx.lineWidth = 1.2;
  for (let i = 0; i < 5; i += 1) {
    ctx.beginPath();
    ctx.moveTo(rect.x + 16, rect.y + 54 + i * 39);
    ctx.lineTo(rect.x + rect.w - 16, rect.y + 54 + i * 39);
    ctx.stroke();
  }
  ctx.restore();

  ctx.fillStyle = "#526168";
  ctx.font = "900 13px ui-monospace, monospace";
  ctx.textAlign = "center";
  ctx.fillText(rect.name, rect.x + rect.w / 2, rect.y + 29);

  const centerX = rect.x + rect.w / 2;
  const actionA = clampActionValue(round, "action_a", index);
  const actionB = clampActionValue(round, "action_b", index);
  const compact = rect.w < 132;
  const chipY = rect.y + (compact ? 58 : 62);

  drawValueChip(rect.x + 10, chipY, actionA, "#f28c38", "left", Boolean(isRevealed), compact);
  drawValueChip(rect.x + rect.w - 10, chipY, actionB, "#2d9cdb", "right", Boolean(isRevealed), compact);

  ctx.save();
  ctx.globalAlpha = 0.5;
  ctx.strokeStyle = "rgba(38,50,56,0.16)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(centerX, rect.y + 104);
  ctx.lineTo(centerX, rect.y + rect.h - 70);
  ctx.stroke();
  ctx.restore();

  const baseY = rect.y + rect.h - 48;
  const stackWidth = compact ? 31 : 61;
  drawTroopStack(rect.x + 14, baseY, actionA, "#f28c38", -1, localProgress, compact);
  drawTroopStack(rect.x + rect.w - 14 - stackWidth, baseY, actionB, "#2d9cdb", 1, localProgress, compact);

  if (winner === "A") drawFlag(centerX - (compact ? 22 : 34), rect.y + 154, "#f28c38", 1, localProgress);
  if (winner === "B") drawFlag(centerX + (compact ? 22 : 34), rect.y + 154, "#2d9cdb", -1, localProgress);
  if (winner === "Tie") {
    ctx.fillStyle = "#d5a11e";
    ctx.font = "900 22px ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.fillText("Tie", centerX, rect.y + 143);
  }
}

function drawHeader(width, round, revealProgress) {
  const panelY = 68;
  const availablePanelW = Math.max(118, (width - 74) / 3);
  const panelW = Math.min(236, availablePanelW);
  const centerW = Math.min(212, availablePanelW);
  const panelH = 56;
  const nameFont = width < 680 ? 18 : 23;

  fillRoundedRect(24, panelY, panelW, panelH, 7, "rgba(255,255,255,0.86)", "rgba(242,140,56,0.42)");
  fillRoundedRect(width - panelW - 24, panelY, panelW, panelH, 7, "rgba(255,255,255,0.86)", "rgba(45,156,219,0.42)");

  ctx.fillStyle = "#f28c38";
  ctx.font = "900 14px ui-monospace, monospace";
  ctx.textAlign = "left";
  ctx.fillText("agent_a", 44, panelY + 23);
  ctx.fillStyle = "#263238";
  ctx.font = `900 ${nameFont}px ui-monospace, monospace`;
  ctx.fillText(activeMatch ? activeMatch.agent_a : "-", 44, panelY + 48);

  ctx.fillStyle = "#2d9cdb";
  ctx.font = "900 14px ui-monospace, monospace";
  ctx.textAlign = "right";
  ctx.fillText("agent_b", width - 44, panelY + 23);
  ctx.fillStyle = "#263238";
  ctx.font = `900 ${nameFont}px ui-monospace, monospace`;
  ctx.fillText(activeMatch ? activeMatch.agent_b : "-", width - 44, panelY + 48);

  const roundText = round ? `round=${round.round}` : "round=0";
  const progressW = Math.max(92, centerW - 36);
  fillRoundedRect(width / 2 - centerW / 2, panelY, centerW, panelH, 7, "rgba(255,255,255,0.9)", "rgba(38,50,56,0.13)");
  ctx.fillStyle = "#d5a11e";
  ctx.font = "900 15px ui-monospace, monospace";
  ctx.textAlign = "center";
  ctx.fillText(roundText, width / 2, panelY + 25);
  fillRoundedRect(width / 2 - progressW / 2, panelY + 36, progressW, 8, 4, "rgba(38,50,56,0.1)");
  fillRoundedRect(width / 2 - progressW / 2, panelY + 36, progressW * revealProgress, 8, 4, "#12a594");
}

function spawnParticles(round) {
  const { width, height } = canvasSize();
  const rects = battlefieldRects(width, height);
  rects.forEach((rect, index) => {
    const color = winnerColor(fieldWinner(round, index));
    for (let i = 0; i < 18; i += 1) {
      particles.push({
        x: rect.x + rect.w / 2,
        y: rect.y + rect.h / 2,
        vx: (Math.random() - 0.5) * 4.8,
        vy: (Math.random() - 0.5) * 3.8 - 0.9,
        life: 42 + Math.random() * 28,
        color,
      });
    }
  });
}

function drawParticles() {
  particles = particles.filter((particle) => particle.life > 0);
  particles.forEach((particle) => {
    particle.x += particle.vx;
    particle.y += particle.vy;
    particle.vy += 0.035;
    particle.life -= 1;
    ctx.globalAlpha = Math.max(0, particle.life / 70);
    ctx.fillStyle = particle.color;
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, 3.1, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
  });
}

function render(t = 0) {
  const { width, height } = canvasSize();
  drawBackground(width, height, t);

  const round = activeMatch?.history?.[activeRoundIndex] || null;
  const rawProgress = round ? Math.min(1, (performance.now() - revealStart) / 1850) : 0;
  const revealProgress = easeOutCubic(rawProgress);

  const targetA = round ? round.total_score_a : 0;
  const targetB = round ? round.total_score_b : 0;
  displayedScoreA = lerp(displayedScoreA, targetA, 0.12);
  displayedScoreB = lerp(displayedScoreB, targetB, 0.12);

  drawHeader(width, round, revealProgress);
  battlefieldRects(width, height).forEach((rect, index) => {
    drawBattlefield(rect, round, index, revealProgress, t);
  });
  drawParticles();

  ui.scoreA.textContent = Math.abs(displayedScoreA - targetA) < 0.03 ? targetA : displayedScoreA.toFixed(1);
  ui.scoreB.textContent = Math.abs(displayedScoreB - targetB) < 0.03 ? targetB : displayedScoreB.toFixed(1);

  requestAnimationFrame(render);
}

function setStatus(text) {
  statusBanner.textContent = text;
}

function formatList(values) {
  return `[${values.join(", ")}]`;
}

function updateRoundUI(round) {
  const totalRounds = activeMatch?.num_rounds || 0;
  if (!round) {
    ui.scoreA.textContent = "0";
    ui.scoreB.textContent = "0";
    ui.roundCounter.textContent = `0 / ${totalRounds}`;
    ui.winner.textContent = "-";
    ui.roundScoreA.textContent = "-";
    ui.roundScoreB.textContent = "-";
    ui.actionA.textContent = "[-]";
    ui.actionB.textContent = "[-]";
    return;
  }

  ui.roundCounter.textContent = `${round.round} / ${totalRounds}`;
  ui.winner.textContent = round.winner;
  ui.roundScoreA.textContent = round.score_a;
  ui.roundScoreB.textContent = round.score_b;
  ui.actionA.textContent = formatList(round.action_a);
  ui.actionB.textContent = formatList(round.action_b);
}

function renderLog(upToIndex) {
  historyLog.innerHTML = "";
  if (!activeMatch) return;

  for (let index = upToIndex; index >= 0; index -= 1) {
    const round = activeMatch.history[index];
    const li = document.createElement("li");
    li.className = round.winner === "A" ? "win-a" : round.winner === "B" ? "win-b" : "";
    li.textContent = `round=${round.round} winner=${round.winner} score_a=${round.score_a} score_b=${round.score_b}`;
    historyLog.appendChild(li);
  }
}

function updateReplayControls() {
  const hasMatch = Boolean(activeMatch);
  const lastIndex = hasMatch ? activeMatch.history.length - 1 : 0;
  roundScrubber.disabled = !hasMatch;
  prevRoundButton.disabled = !hasMatch || activeRoundIndex <= 0;
  nextRoundButton.disabled = !hasMatch || activeRoundIndex >= lastIndex;
  playToggleButton.disabled = !hasMatch;
  downloadHistoryButton.disabled = !hasMatch;
  playToggleButton.textContent = isPlaying ? "Pause" : "Play";

  if (hasMatch) {
    roundScrubber.max = activeMatch.history.length;
    roundScrubber.value = activeRoundIndex + 1;
  } else {
    roundScrubber.max = 1;
    roundScrubber.value = 1;
  }
}

function showRound(index) {
  if (!activeMatch) return;
  activeRoundIndex = Math.max(0, Math.min(index, activeMatch.history.length - 1));
  revealStart = performance.now();
  const round = activeMatch.history[activeRoundIndex];
  updateRoundUI(round);
  renderLog(activeRoundIndex);
  spawnParticles(round);
  setStatus(`round=${round.round} | winner=${round.winner} | action_a=${formatList(round.action_a)} | action_b=${formatList(round.action_b)}`);
  updateReplayControls();
}

function downloadHistoryJson() {
  if (!activeMatch) return;

  const filenameParts = [
    "blotto_history",
    `agent_a-${activeMatch.agent_a}`,
    `agent_b-${activeMatch.agent_b}`,
    `rounds-${activeMatch.num_rounds}`,
    `fields-${activeMatch.num_battlefields}`,
    `resources-${activeMatch.total_resources}`,
  ];
  const blob = new Blob([JSON.stringify(activeMatch, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${filenameParts.join("_")}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function stopReplay() {
  clearTimeout(replayTimer);
  replayTimer = null;
  isPlaying = false;
  updateReplayControls();
}

function queueNextRound() {
  clearTimeout(replayTimer);
  if (!isPlaying || !activeMatch) return;

  replayTimer = setTimeout(() => {
    if (activeRoundIndex >= activeMatch.history.length - 1) {
      stopReplay();
      setStatus(`match_winner=${activeMatch.match_winner} | total_score_a=${activeMatch.total_score_a} | total_score_b=${activeMatch.total_score_b}`);
      return;
    }
    showRound(activeRoundIndex + 1);
    queueNextRound();
  }, roundDuration);
}

function startReplay(match) {
  activeMatch = match;
  activeRoundIndex = -1;
  displayedScoreA = 0;
  displayedScoreB = 0;
  particles = [];
  clearTimeout(replayTimer);
  isPlaying = true;
  historyLog.innerHTML = "";
  updateRoundUI(null);
  setStatus("Running replay...");
  showRound(0);
  queueNextRound();
}

async function loadAgents() {
  const data = await requestJson("/api/agents");
  [agentASelect, agentBSelect].forEach((select) => {
    select.innerHTML = "";
    data.agents.forEach((agent) => {
      const option = document.createElement("option");
      option.value = agent;
      option.textContent = agent;
      select.appendChild(option);
    });
  });
  agentASelect.value = "random";
  agentBSelect.value = "greedy";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  stopReplay();
  runButton.disabled = true;
  setStatus("Running experiment...");

  const payload = {
    agent_a: agentASelect.value,
    agent_b: agentBSelect.value,
    llm_model_a: ALL_LLM_TYPES.includes(agentASelect.value) ? llmModelAInput.value.trim() : null,
    llm_model_b: ALL_LLM_TYPES.includes(agentBSelect.value) ? llmModelBInput.value.trim() : null,
    num_rounds: Number(numRoundsInput.value),
    num_battlefields: Number(numBattlefieldsInput.value),
    total_resources: Number(totalResourcesInput.value),
  };

  if (payload.total_resources < payload.num_battlefields) {
    setStatus("error=total_resources must be greater than or equal to num_battlefields");
    runButton.disabled = false;
    return;
  }

  let pollTimer = null;
  const startTime = Date.now();

  try {
    const { run_id } = await requestJson("/api/run-experiment", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    const poll = async () => {
      try {
        const run = await requestJson(`/api/run/${run_id}`);
        if (run.status === "done") {
          clearInterval(pollTimer);
          runButton.disabled = false;
          startReplay(run.result);
          return;
        }
        if (run.status === "error") {
          clearInterval(pollTimer);
          setStatus(`error=${run.error}`);
          runButton.disabled = false;
          return;
        }
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        if (run.round) {
          setStatus(`Round ${run.round}/${run.total_rounds}  (${elapsed}s)`);
        } else {
          setStatus(`Running experiment... ${elapsed}s`);
        }
      } catch (err) {
        clearInterval(pollTimer);
        setStatus(`error=${err.message}`);
        runButton.disabled = false;
      }
    };

    pollTimer = setInterval(poll, 1000);
    poll();
  } catch (error) {
    setStatus(`error=${error.message}`);
    runButton.disabled = false;
  }
});

prevRoundButton.addEventListener("click", () => {
  stopReplay();
  showRound(activeRoundIndex - 1);
});

nextRoundButton.addEventListener("click", () => {
  stopReplay();
  showRound(activeRoundIndex + 1);
});

playToggleButton.addEventListener("click", () => {
  if (!activeMatch) return;
  if (isPlaying) {
    stopReplay();
    return;
  }
  if (activeRoundIndex >= activeMatch.history.length - 1) {
    showRound(0);
  }
  isPlaying = true;
  updateReplayControls();
  queueNextRound();
});

roundScrubber.addEventListener("input", () => {
  stopReplay();
  showRound(Number(roundScrubber.value) - 1);
});

downloadHistoryButton.addEventListener("click", downloadHistoryJson);

agentASelect.addEventListener("change", () => {
  updateLlmModelPanels();
});

agentBSelect.addEventListener("change", () => {
  updateLlmModelPanels();
});

llmModelAInput.addEventListener("input", () => {
  llmModelAInput.dataset.userSet = "1";
});

llmModelBInput.addEventListener("input", () => {
  llmModelBInput.dataset.userSet = "1";
});

hfSearchAInput.addEventListener("input", () => debounceModelSearch("a"));
hfSearchBInput.addEventListener("input", () => debounceModelSearch("b"));
hfSearchAInput.addEventListener("focus", () => {
  if (!hfResultsA.children.length) searchHuggingFaceModels("a");
});
hfSearchBInput.addEventListener("focus", () => {
  if (!hfResultsB.children.length) searchHuggingFaceModels("b");
});

numBattlefieldsInput.addEventListener("input", () => {
  if (!activeMatch) return;
  stopReplay();
  activeMatch = null;
  historyLog.innerHTML = "";
  particles = [];
  updateRoundUI(null);
  updateReplayControls();
  setStatus("Choose agent_a, agent_b, num_rounds, num_battlefields, and total_resources.");
});

totalResourcesInput.addEventListener("input", () => {
  if (!activeMatch) return;
  stopReplay();
  activeMatch = null;
  historyLog.innerHTML = "";
  particles = [];
  updateRoundUI(null);
  updateReplayControls();
  setStatus("Choose agent_a, agent_b, num_rounds, num_battlefields, and total_resources.");
});

window.addEventListener("resize", resizeCanvas);

resizeCanvas();
updateReplayControls();
loadAgents()
  .then(updateLlmModelPanels)
  .catch((error) => setStatus(`error=${error.message}`));
requestAnimationFrame(render);
