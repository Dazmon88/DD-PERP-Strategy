(() => {
  const params = new URLSearchParams(location.search);
  const pair = (params.get("pair") || "AAPL").toUpperCase();
  const ALL_EX = ["ondo", "arcus", "standx", "hype", "lighter"];
  const state = {
    pair,
    interval: params.get("interval") || "5m",
    exchanges: new Set(ALL_EX),
    series: {},
    lineSeries: {},
    colors: {},
    ws: null,
  };

  const els = {
    pairTitle: document.getElementById("pairTitle"),
    hoverLegend: document.getElementById("hoverLegend"),
    chartStatus: document.getElementById("chartStatus"),
    liveDot: document.getElementById("liveDot"),
    connStatus: document.getElementById("connStatus"),
    intervalPills: document.getElementById("intervalPills"),
    exchangePills: document.getElementById("exchangePills"),
    tvChart: document.getElementById("tvChart"),
  };

  els.pairTitle.textContent = pair;

  const labels = {
    ondo: "Ondo",
    arcus: "Arcus",
    standx: "StandX",
    hype: "Hype",
    lighter: "Lighter",
  };

  const chart = LightweightCharts.createChart(els.tvChart, {
    width: els.tvChart.clientWidth || 800,
    height: els.tvChart.clientHeight || 420,
    layout: {
      background: { color: "transparent" },
      textColor: "#8b93a7",
      fontFamily: "JetBrains Mono, Plus Jakarta Sans, sans-serif",
    },
    grid: {
      vertLines: { color: "rgba(255,255,255,0.04)" },
      horzLines: { color: "rgba(255,255,255,0.04)" },
    },
    rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
    timeScale: {
      borderColor: "rgba(255,255,255,0.08)",
      timeVisible: true,
      secondsVisible: false,
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Magnet,
    },
  });

  function renderExchangePills() {
    els.exchangePills.innerHTML = ALL_EX.map((ex) => {
      const on = state.exchanges.has(ex);
      const color = state.colors[ex] || "#888";
      return `<button class="pill ${on ? "active" : "ex-off"}" data-ex="${ex}" style="${on ? `border-color:${color};color:${color}` : ""}">${labels[ex] || ex}</button>`;
    }).join("");
  }

  function upsertSeries(ex, points, color) {
    if (!state.lineSeries[ex]) {
      state.lineSeries[ex] = chart.addLineSeries({
        color: color || "#aaa",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: labels[ex] || ex,
      });
    } else {
      state.lineSeries[ex].applyOptions({ color: color || "#aaa" });
    }
    state.lineSeries[ex].setData(points || []);
    state.lineSeries[ex].applyOptions({
      visible: state.exchanges.has(ex),
    });
  }

  function updateHoverLegend(time) {
    const parts = [];
    for (const ex of ALL_EX) {
      if (!state.exchanges.has(ex)) continue;
      const pts = state.series[ex] || [];
      let val = null;
      if (time != null) {
        // 找 <= time 最近一点
        for (let i = pts.length - 1; i >= 0; i--) {
          if (pts[i].time <= time) {
            val = pts[i].value;
            break;
          }
        }
      } else if (pts.length) {
        val = pts[pts.length - 1].value;
      }
      const color = state.colors[ex] || "#888";
      const txt = val == null ? "—" : Number(val).toFixed(4);
      parts.push(
        `<span class="legend-item"><i class="legend-swatch" style="background:${color}"></i>${labels[ex]} ${txt}</span>`
      );
    }
    els.hoverLegend.innerHTML = parts.length
      ? parts.join("")
      : "移动鼠标查看各所价格";
  }

  chart.subscribeCrosshairMove((param) => {
    if (!param || param.time == null) {
      updateHoverLegend(null);
      return;
    }
    updateHoverLegend(param.time);
  });

  async function loadHistory() {
    els.chartStatus.textContent = "加载历史…";
    const q = new URLSearchParams({
      pair: state.pair,
      interval: state.interval,
      hours: state.interval === "1h" ? "168" : "48",
      exchanges: ALL_EX.join(","),
    });
    const res = await fetch(`/api/prices/history?${q}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.colors = data.colors || {};
    state.series = data.series || {};
    state.symbols = data.symbols || {};
    for (const ex of ALL_EX) {
      upsertSeries(ex, state.series[ex] || [], state.colors[ex]);
    }
    renderExchangePills();
    chart.timeScale().fitContent();
    updateHoverLegend(null);
    const err = Object.keys(data.errors || {});
    const counts = ALL_EX.map((ex) => `${labels[ex]} ${(state.series[ex] || []).length}`).join(" · ");
    const notes = [];
    const arcusSym = (state.symbols.arcus || "").replace(/-USD$/i, "");
    if (arcusSym && arcusSym.toUpperCase() !== state.pair) {
      notes.push(`Arcus=${arcusSym}（该所无 ${state.pair} 合约）`);
    }
    const lightN = (state.series.lighter || []).length;
    if (lightN > 0 && lightN < 30) {
      notes.push("Lighter K线不可用，仅成交/标记价");
    }
    const suffix = notes.length ? ` · ${notes.join(" · ")}` : "";
    els.chartStatus.textContent = err.length
      ? `${counts} · 部分失败: ${err.join(", ")}${suffix}`
      : `${counts}${suffix}`;
  }

  function appendLiveTick(prices, ts) {
    const t = Math.floor(ts);
    for (const ex of ALL_EX) {
      const v = prices?.[ex];
      if (v == null || Number.isNaN(Number(v))) continue;
      if (!state.series[ex]) state.series[ex] = [];
      const pts = state.series[ex];
      const last = pts[pts.length - 1];
      if (last && last.time === t) {
        last.value = Number(v);
      } else if (!last || last.time < t) {
        pts.push({ time: t, value: Number(v) });
      }
      if (state.lineSeries[ex]) {
        state.lineSeries[ex].update({ time: t, value: Number(v) });
      }
    }
    updateHoverLegend(null);
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${location.host}/ws/prices?pair=${encodeURIComponent(state.pair)}`;
    if (state.ws) {
      try {
        state.ws.close();
      } catch (_) {}
    }
    const ws = new WebSocket(url);
    state.ws = ws;
    els.connStatus.textContent = "WSS 连接中…";
    els.liveDot.classList.remove("on");

    ws.onopen = () => {
      els.connStatus.textContent = "实时已连接";
      els.liveDot.classList.add("on");
      ws.send(JSON.stringify({ exchanges: [...state.exchanges] }));
    };
    ws.onclose = () => {
      els.connStatus.textContent = "实时断开，3s 重连…";
      els.liveDot.classList.remove("on");
      setTimeout(connectWs, 3000);
    };
    ws.onerror = () => {
      els.connStatus.textContent = "WSS 错误";
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "tick") {
          if (msg.colors) state.colors = { ...state.colors, ...msg.colors };
          appendLiveTick(msg.prices || {}, msg.ts || Date.now() / 1000);
        }
      } catch (_) {}
    };
  }

  els.intervalPills.addEventListener("click", async (e) => {
    const btn = e.target.closest(".pill");
    if (!btn) return;
    els.intervalPills.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    state.interval = btn.dataset.interval;
    try {
      await loadHistory();
    } catch (err) {
      els.chartStatus.textContent = `加载失败：${err.message}`;
    }
  });

  els.exchangePills.addEventListener("click", (e) => {
    const btn = e.target.closest(".pill");
    if (!btn) return;
    const ex = btn.dataset.ex;
    if (state.exchanges.has(ex)) state.exchanges.delete(ex);
    else state.exchanges.add(ex);
    if (state.lineSeries[ex]) {
      state.lineSeries[ex].applyOptions({ visible: state.exchanges.has(ex) });
    }
    renderExchangePills();
    updateHoverLegend(null);
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify({ exchanges: [...state.exchanges] }));
    }
  });

  window.addEventListener("resize", () => {
    chart.applyOptions({
      width: els.tvChart.clientWidth,
      height: els.tvChart.clientHeight,
    });
  });

  (async () => {
    try {
      await loadHistory();
      connectWs();
    } catch (err) {
      els.chartStatus.textContent = `加载失败：${err.message}`;
    }
  })();
})();
