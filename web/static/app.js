const state = {
  source: "demo",
  risk: "medium",
  defaults: [],
  results: [],
  isScanning: false,
  autoTimer: null,
};

const elements = {
  clock: document.querySelector("#clock"),
  autoStatus: document.querySelector("#autoStatus"),
  sourceGroup: document.querySelector("#sourceGroup"),
  riskGroup: document.querySelector("#riskGroup"),
  account: document.querySelector("#accountInput"),
  top: document.querySelector("#topInput"),
  bars: document.querySelector("#barsInput"),
  symbols: document.querySelector("#symbolsInput"),
  csvDir: document.querySelector("#csvDirInput"),
  csvPathControl: document.querySelector("#csvPathControl"),
  resetSymbols: document.querySelector("#resetSymbols"),
  scanButton: document.querySelector("#scanButton"),
  autoRefresh: document.querySelector("#autoRefreshInput"),
  refreshInterval: document.querySelector("#refreshIntervalSelect"),
  errorLine: document.querySelector("#errorLine"),
  regimePanel: document.querySelector("#regimePanel"),
  regimeState: document.querySelector("#regimeState"),
  regimeBias: document.querySelector("#regimeBias"),
  regimeReason: document.querySelector("#regimeReason"),
  regimeNeedle: document.querySelector("#regimeNeedle"),
  benchmarkRow: document.querySelector("#benchmarkRow"),
  buyCount: document.querySelector("#buyCount"),
  watchCount: document.querySelector("#watchCount"),
  avgScore: document.querySelector("#avgScore"),
  riskCapital: document.querySelector("#riskCapital"),
  leaderSymbol: document.querySelector("#leaderSymbol"),
  leaderReason: document.querySelector("#leaderReason"),
  leaderScore: document.querySelector("#leaderScore"),
  leaderSignal: document.querySelector("#leaderSignal"),
  leaderEntry: document.querySelector("#leaderEntry"),
  leaderStop: document.querySelector("#leaderStop"),
  leaderTarget: document.querySelector("#leaderTarget"),
  scanTime: document.querySelector("#scanTime"),
  resultsBody: document.querySelector("#resultsBody"),
};

const money = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
});

function updateClock() {
  elements.clock.textContent = new Intl.DateTimeFormat("no-NO", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());
}

function selectButton(group, attribute, value) {
  group.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset[attribute] === value);
  });
}

async function loadDefaults() {
  const response = await fetch("/api/defaults");
  const data = await response.json();
  state.defaults = data.symbols || [];
  elements.symbols.value = data.symbolsText || state.defaults.join("\n");
}

function bindControls() {
  elements.sourceGroup.addEventListener("click", (event) => {
    const button = event.target.closest("[data-source]");
    if (!button) return;
    state.source = button.dataset.source;
    selectButton(elements.sourceGroup, "source", state.source);
    elements.csvPathControl.classList.toggle("hidden", state.source !== "csv");
  });

  elements.riskGroup.addEventListener("click", (event) => {
    const button = event.target.closest("[data-risk]");
    if (!button) return;
    state.risk = button.dataset.risk;
    selectButton(elements.riskGroup, "risk", state.risk);
  });

  elements.resetSymbols.addEventListener("click", () => {
    elements.symbols.value = state.defaults.join("\n");
  });

  elements.scanButton.addEventListener("click", runScan);
  elements.autoRefresh.addEventListener("change", configureAutoRefresh);
  elements.refreshInterval.addEventListener("change", configureAutoRefresh);
}

async function runScan() {
  if (state.isScanning) return;
  setLoading(true);
  elements.errorLine.textContent = "";

  const payload = {
    source: state.source,
    risk: state.risk,
    account: Number(elements.account.value),
    top: Number(elements.top.value),
    bars: Number(elements.bars.value),
    symbols: elements.symbols.value,
    csvDir: elements.csvDir.value.trim(),
  };

  try {
    const response = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Scan failed");
    }
    state.results = data.results || [];
    render(data);
  } catch (error) {
    elements.errorLine.textContent = error.message;
  } finally {
    setLoading(false);
  }
}

function setLoading(isLoading) {
  document.body.classList.toggle("loading", isLoading);
  state.isScanning = isLoading;
  elements.scanButton.disabled = isLoading;
  elements.scanButton.querySelector("span:last-child").textContent = isLoading ? "Scanner..." : "Kjør scan";
}

function configureAutoRefresh() {
  if (state.autoTimer) {
    clearInterval(state.autoTimer);
    state.autoTimer = null;
  }

  if (!elements.autoRefresh.checked) {
    elements.autoStatus.textContent = "Auto: av";
    elements.autoStatus.classList.remove("live");
    return;
  }

  const seconds = Number(elements.refreshInterval.value) || 60;
  elements.autoStatus.textContent = `Auto: ${seconds < 60 ? `${seconds}s` : `${seconds / 60}m`}`;
  elements.autoStatus.classList.add("live");
  state.autoTimer = setInterval(() => {
    runScan();
  }, seconds * 1000);
}

function render(data) {
  const summary = data.summary || {};
  elements.buyCount.textContent = summary.buyCount ?? 0;
  elements.watchCount.textContent = summary.watchCount ?? 0;
  elements.avgScore.textContent = summary.averageScore ?? 0;
  elements.riskCapital.textContent = formatCompactMoney(summary.totalCapitalAtRisk || 0);
  elements.scanTime.textContent = formatScanTime(data.scannedAt);
  renderRegime(data.regime);
  renderLeader(summary.leader);
  renderTable(data.results || []);
}

function renderRegime(regime) {
  if (!regime) return;
  const stateName = regime.state || "UNKNOWN";
  const position = Math.max(0, Math.min(100, ((Number(regime.score) || 0) + 100) / 2));
  elements.regimePanel.dataset.regime = stateName;
  elements.regimeState.textContent = stateName;
  elements.regimeBias.textContent = regime.bias || "-";
  elements.regimeReason.textContent = regime.reason || "-";
  elements.regimeNeedle.parentElement.style.setProperty("--regime-position", position);
  elements.benchmarkRow.innerHTML = (regime.benchmarks || []).map((item) => `
    <span class="benchmark-chip ${escapeHtml(item.status)}">
      <b>${escapeHtml(item.symbol)}</b>
      <small>${escapeHtml(item.status)} ${Number(item.score || 0).toFixed(0)}</small>
    </span>
  `).join("");
}

function renderLeader(leader) {
  if (!leader) {
    elements.leaderSymbol.textContent = "Ingen treff";
    elements.leaderReason.textContent = "Scannen ga ingen resultater.";
    setLeaderMetrics(null);
    return;
  }

  elements.leaderSymbol.textContent = leader.symbol;
  elements.leaderReason.textContent = (leader.reasons || []).slice(0, 2).join(" · ") || "Ingen begrunnelse";
  elements.leaderScore.style.setProperty("--score", leader.score || 0);
  elements.leaderScore.querySelector("span").textContent = Math.round(leader.score || 0);
  setLeaderMetrics(leader);
}

function setLeaderMetrics(leader) {
  const plan = leader?.position_plan;
  elements.leaderSignal.textContent = leader?.signal || "-";
  elements.leaderEntry.textContent = leader ? money.format(leader.close) : "-";
  elements.leaderStop.textContent = plan ? money.format(plan.stop) : "-";
  elements.leaderTarget.textContent = plan ? money.format(plan.target) : "-";
}

function renderTable(results) {
  if (!results.length) {
    elements.resultsBody.innerHTML = `<tr><td colspan="9" class="empty-cell">Ingen data</td></tr>`;
    return;
  }

  elements.resultsBody.innerHTML = results.map((item) => {
    const plan = item.position_plan;
    return `
      <tr>
        <td><strong>${escapeHtml(item.symbol)}</strong></td>
        <td><span class="signal-pill signal-${escapeHtml(item.signal)}">${escapeHtml(item.signal)}</span></td>
        <td>
          <span class="score-meter" style="--score:${Number(item.score) || 0}">
            <span>${Number(item.score || 0).toFixed(1)}</span><i></i>
          </span>
        </td>
        <td>${formatNumber(item.close)}</td>
        <td>${formatMaybe(item.rsi)}</td>
        <td>${item.atr_pct == null ? "-" : `${(item.atr_pct * 100).toFixed(1)}%`}</td>
        <td>${plan ? plan.shares : "-"}</td>
        <td>${plan ? formatNumber(plan.stop) : "-"}</td>
        <td>${plan ? formatNumber(plan.target) : "-"}</td>
      </tr>
    `;
  }).join("");
}

function formatMaybe(value) {
  return value == null ? "-" : Number(value).toFixed(1);
}

function formatNumber(value) {
  return value == null ? "-" : money.format(Number(value));
}

function formatCompactMoney(value) {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatScanTime(value) {
  if (!value) return "Ikke kjørt";
  return new Intl.DateTimeFormat("no-NO", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function initMarketFlow() {
  const canvas = document.querySelector("#marketFlow");
  const ctx = canvas.getContext("2d");
  const palette = [
    "rgba(77,255,157,",
    "rgba(77,216,255,",
    "rgba(255,200,87,",
    "rgba(255,107,107,",
  ];
  const lines = Array.from({ length: 24 }, (_, index) => ({
    phase: Math.random() * Math.PI * 2,
    speed: 0.001 + Math.random() * 0.0022,
    amp: 24 + Math.random() * 78,
    y: Math.random(),
    color: palette[index % palette.length],
    width: 0.8 + Math.random() * 1.8,
  }));

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    canvas.style.width = `${window.innerWidth}px`;
    canvas.style.height = `${window.innerHeight}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw(time) {
    const width = window.innerWidth;
    const height = window.innerHeight;
    ctx.clearRect(0, 0, width, height);

    lines.forEach((line, lineIndex) => {
      ctx.beginPath();
      const baseY = height * line.y;
      for (let x = -40; x <= width + 40; x += 18) {
        const waveA = Math.sin(x * 0.008 + time * line.speed + line.phase) * line.amp;
        const waveB = Math.cos(x * 0.016 + time * line.speed * 0.7 + line.phase) * line.amp * 0.32;
        const y = baseY + waveA + waveB;
        if (x === -40) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `${line.color}${0.10 + (lineIndex % 5) * 0.018})`;
      ctx.lineWidth = line.width;
      ctx.stroke();
    });

    requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(draw);
}

async function init() {
  updateClock();
  setInterval(updateClock, 1000);
  initMarketFlow();
  bindControls();
  await loadDefaults();
  await runScan();
}

init();
