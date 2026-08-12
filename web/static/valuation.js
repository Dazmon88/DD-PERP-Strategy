(() => {
  const params = new URLSearchParams(location.search);
  const symbol = (params.get("symbol") || params.get("pair") || "AAPL").toUpperCase();
  const state = {
    symbol,
    range: params.get("range") || "5y",
    series: [],
    mode: "pe", // pe | price
    mean: null,
    zone: null,
    bandLines: [],
  };

  const els = {
    symTitle: document.getElementById("symTitle"),
    symLede: document.getElementById("symLede"),
    hoverLegend: document.getElementById("hoverLegend"),
    chartStatus: document.getElementById("chartStatus"),
    rangePills: document.getElementById("rangePills"),
    tvChart: document.getElementById("tvChart"),
    kpiPe: document.getElementById("kpiPe"),
    kpiZone: document.getElementById("kpiZone"),
    kpiZoneCard: document.getElementById("kpiZoneCard"),
    kpiMed: document.getElementById("kpiMed"),
    kpiPct: document.getElementById("kpiPct"),
    notice: document.getElementById("valNotice"),
    zoneStrip: document.getElementById("zoneStrip"),
  };

  els.symTitle.textContent = symbol;
  document.title = `${symbol} · Trailing P/E · FundRate`;

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
    leftPriceScale: {
      visible: false,
      borderVisible: false,
    },
    timeScale: {
      borderColor: "rgba(255,255,255,0.08)",
      timeVisible: false,
    },
    crosshair: { mode: LightweightCharts.CrosshairMode.Magnet },
  });

  const peSeries = chart.addAreaSeries({
    lineColor: "#e8eefc",
    topColor: "rgba(59, 130, 246, 0.35)",
    bottomColor: "rgba(59, 130, 246, 0.02)",
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: true,
    priceScaleId: "right",
    title: "P/E",
  });

  // 股价形态叠层：独立左轴但不显示刻度，只看形状
  const priceShapeSeries = chart.addLineSeries({
    color: "rgba(134, 239, 172, 0.9)",
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Solid,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: true,
    crosshairMarkerRadius: 3,
    priceScaleId: "left",
    title: "Price",
  });

  // 亏损股仅展示股价时用右轴面积图
  const priceSeries = chart.addAreaSeries({
    lineColor: "#86efac",
    topColor: "rgba(34, 197, 94, 0.28)",
    bottomColor: "rgba(34, 197, 94, 0.02)",
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: true,
    priceScaleId: "right",
    title: "Price",
    visible: false,
  });

  function fmt(v, digits = 2) {
    if (v == null || Number.isNaN(Number(v))) return "—";
    return Number(v).toFixed(digits);
  }

  function syncRangePills() {
    els.rangePills.querySelectorAll(".pill").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.range === state.range);
    });
  }

  function pointAt(time) {
    const pts = state.series;
    if (!pts.length) return null;
    if (time == null) return pts[pts.length - 1];
    for (let i = pts.length - 1; i >= 0; i--) {
      if (pts[i].time <= time) return pts[i];
    }
    return pts[0];
  }

  function zoneForPe(pe, bands) {
    if (pe == null || !bands) return null;
    if (pe < bands.p10) return { label: "极度低估", color: "#22c55e" };
    if (pe < bands.p30) return { label: "低估", color: "#86efac" };
    if (pe <= bands.p70) return { label: "中性", color: "#93c5fd" };
    if (pe <= bands.p90) return { label: "高估", color: "#fbbf24" };
    return { label: "极度高估", color: "#ef4444" };
  }

  function updateLegend(time) {
    const p = pointAt(time);
    if (!p) {
      els.hoverLegend.textContent = "暂无数据";
      return;
    }
    const peTxt = p.pe == null ? "NM（亏损）" : fmt(p.pe, 3);
    const z = state.mode === "pe" ? zoneForPe(p.pe, state.bands) : null;
    const zoneTxt = z ? ` · <strong style="color:${z.color}">${z.label}</strong>` : "";
    const peSwatch = `<i class="legend-swatch" style="background:#e8eefc"></i>`;
    const pxSwatch = `<i class="legend-swatch" style="background:#86efac"></i>`;
    if (state.mode === "pe") {
      els.hoverLegend.innerHTML = `
        <span class="legend-item">${p.time}</span>
        <span class="legend-item">${peSwatch}PE <strong>${peTxt}</strong>${zoneTxt}</span>
        <span class="legend-item">${pxSwatch}股价 <strong>${fmt(p.close, 2)}</strong><span class="legend-hint">形态</span></span>
        <span class="legend-item">TTM EPS <strong>${fmt(p.eps_ttm, 3)}</strong></span>
      `;
      return;
    }
    els.hoverLegend.innerHTML = `
      <span class="legend-item">${pxSwatch}${p.time}</span>
      <span class="legend-item">PE <strong>${peTxt}</strong></span>
      <span class="legend-item">股价 <strong>${fmt(p.close, 2)}</strong></span>
      <span class="legend-item">TTM EPS <strong>${fmt(p.eps_ttm, 3)}</strong></span>
    `;
  }

  function clearBandLines() {
    state.bandLines.forEach((line) => {
      try {
        peSeries.removePriceLine(line);
      } catch (_) {}
    });
    state.bandLines = [];
  }

  function setBandLines(bands, mean) {
    clearBandLines();
    state.mean = mean;
    state.bands = bands || null;
    if (!bands || state.mode !== "pe") return;

    const specs = [
      { key: "p10", title: "P10 低估", color: "rgba(34,197,94,0.75)" },
      { key: "p30", title: "P30", color: "rgba(134,239,172,0.55)" },
      { key: "p70", title: "P70", color: "rgba(251,191,36,0.55)" },
      { key: "p90", title: "P90 高估", color: "rgba(239,68,68,0.75)" },
    ];
    specs.forEach((sp) => {
      const price = bands[sp.key];
      if (price == null) return;
      const line = peSeries.createPriceLine({
        price,
        color: sp.color,
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: sp.title,
      });
      state.bandLines.push(line);
    });
    if (mean != null) {
      const meanLine = peSeries.createPriceLine({
        price: mean,
        color: "rgba(255,255,255,0.45)",
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: "mean",
      });
      state.bandLines.push(meanLine);
    }
  }

  function renderZoneStrip(zones, activeKey) {
    if (!els.zoneStrip) return;
    if (!zones || !zones.length) {
      els.zoneStrip.hidden = true;
      els.zoneStrip.innerHTML = "";
      return;
    }
    els.zoneStrip.hidden = false;
    els.zoneStrip.innerHTML = zones
      .map((z) => {
        const active = z.key === activeKey ? "active" : "";
        return `<div class="zone-chip ${active}" style="border-color:${z.color}55;background:${z.color}14">
          <span class="zone-chip-label" style="color:${z.color}">${z.label}</span>
          <span class="zone-chip-range">PE ${fmt(z.pe_min)} – ${fmt(z.pe_max)}</span>
          <span class="zone-chip-range">分位 ${z.pct_min}–${z.pct_max}%</span>
        </div>`;
      })
      .join("");
  }

  function setNotice(text, isWarn) {
    if (!els.notice) return;
    if (!text) {
      els.notice.hidden = true;
      els.notice.textContent = "";
      return;
    }
    els.notice.hidden = false;
    els.notice.textContent = text;
    els.notice.classList.toggle("warn", !!isWarn);
  }

  async function load() {
    syncRangePills();
    els.chartStatus.textContent = "加载估值曲线…";
    setNotice("");
    try {
      const q = new URLSearchParams({
        symbol: state.symbol,
        range: state.range,
      });
      const res = await fetch(`/api/valuation/pe?${q}`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.error || `HTTP ${res.status}`);
      }
      els.symTitle.textContent = data.symbol || state.symbol;
      els.symLede.textContent = `${data.name || ""} · ${data.note || "Trailing P/E (TTM)"}`;

      const stats = data.stats || {};
      const latest = data.latest || {};
      const all = (data.series || []).map((r) => ({
        time: r.t,
        pe: r.pe,
        close: r.close,
        eps_ttm: r.eps_ttm,
      }));
      const pePts = all.filter((r) => r.pe != null);
      const lossMaking =
        data.loss_making ||
        (pePts.length === 0 && latest.eps_ttm != null && Number(latest.eps_ttm) <= 0);

      state.series = all;
      state.mode = pePts.length ? "pe" : "price";
      state.zone = stats.zone || null;

      if (state.mode === "pe") {
        peSeries.applyOptions({ visible: true, title: "P/E" });
        priceSeries.applyOptions({ visible: false });
        priceShapeSeries.applyOptions({ visible: true });
        peSeries.setData(pePts.map((p) => ({ time: p.time, value: p.pe })));
        priceShapeSeries.setData(
          all
            .filter((p) => p.close != null)
            .map((p) => ({ time: p.time, value: p.close }))
        );
        priceSeries.setData([]);
        setBandLines(stats.bands, stats.mean_pe);
        renderZoneStrip(stats.zones, stats.zone?.key);

        els.kpiPe.textContent = fmt(stats.latest_pe, 2);
        els.kpiZone.textContent = stats.zone?.label || "—";
        if (els.kpiZoneCard && stats.zone?.color) {
          els.kpiZoneCard.style.borderColor = `${stats.zone.color}66`;
          els.kpiZone.style.color = stats.zone.color;
        }
        els.kpiMed.textContent = fmt(stats.median_pe, 2);
        els.kpiPct.textContent =
          stats.percentile == null ? "—" : `${(Number(stats.percentile) * 100).toFixed(0)}%`;

        const labels = document.querySelectorAll(".kpi .kpi-label");
        if (labels[0]) labels[0].textContent = "当前 PE";
        if (labels[1]) labels[1].textContent = "估值区间";
        if (labels[2]) labels[2].textContent = "历史分位";
        if (labels[3]) labels[3].textContent = "区间中位数";

        setNotice(stats.zone_note || "");
      } else {
        peSeries.applyOptions({ visible: false });
        priceShapeSeries.applyOptions({ visible: false });
        priceSeries.applyOptions({ visible: true, title: "Price" });
        peSeries.setData([]);
        priceShapeSeries.setData([]);
        priceSeries.setData(
          all
            .filter((p) => p.close != null)
            .map((p) => ({ time: p.time, value: p.close }))
        );
        setBandLines(null, null);
        renderZoneStrip(null, null);
        els.kpiPe.textContent = "NM";
        els.kpiZone.textContent = "亏损";
        els.kpiZone.style.color = "#fca5a5";
        els.kpiMed.textContent = fmt(latest.eps_ttm, 3);
        els.kpiPct.textContent = fmt(latest.close, 2);
        const labels = document.querySelectorAll(".kpi .kpi-label");
        if (labels[0]) labels[0].textContent = "当前 PE";
        if (labels[1]) labels[1].textContent = "状态";
        if (labels[2]) labels[2].textContent = "最新股价";
        if (labels[3]) labels[3].textContent = "TTM EPS";
        setNotice(
          data.empty_reason ||
            `近四季 TTM EPS 为 ${fmt(latest.eps_ttm, 3)}（亏损），Trailing P/E 无意义；下方展示股价曲线`,
          true
        );
      }

      chart.timeScale().fitContent();
      updateLegend(null);

      const src = data.price_source ? ` · 价格源 ${data.price_source}` : "";
      const cache = data.cached ? " · 缓存" : "";
      const n = state.mode === "pe" ? pePts.length : all.length;
      const kind =
        state.mode === "pe"
          ? `${data.metric_label || "Trailing P/E"} + 股价形态`
          : "股价（PE 不可用）";
      const zoneTxt = state.zone ? ` · ${state.zone.label}` : "";
      els.chartStatus.textContent = `${n} 点 · ${kind}${zoneTxt}${src}${cache}`;
    } catch (err) {
      els.chartStatus.textContent = `加载失败：${err.message}`;
      els.hoverLegend.textContent = err.message;
      setNotice(err.message, true);
      peSeries.setData([]);
      priceShapeSeries.setData([]);
      priceSeries.setData([]);
      setBandLines(null, null);
      renderZoneStrip(null, null);
    }
  }

  chart.subscribeCrosshairMove((param) => {
    updateLegend(param?.time ?? null);
  });

  els.rangePills.addEventListener("click", (e) => {
    const btn = e.target.closest(".pill");
    if (!btn) return;
    state.range = btn.dataset.range || "5y";
    const url = new URL(location.href);
    url.searchParams.set("symbol", state.symbol);
    url.searchParams.set("range", state.range);
    history.replaceState(null, "", url);
    load();
  });

  window.addEventListener("resize", () => {
    chart.applyOptions({
      width: els.tvChart.clientWidth || 800,
      height: els.tvChart.clientHeight || 420,
    });
  });

  // —— 股票搜索下拉 ——
  const searchRoot = document.getElementById("valSearch");
  const searchInput = document.getElementById("tickerSearch");
  const suggestBox = document.getElementById("tickerSuggest");
  const suggestHead = document.getElementById("suggestHead");
  const suggestList = document.getElementById("suggestList");
  const searchState = {
    items: [],
    active: -1,
    open: false,
    mode: "top",
    timer: null,
    seq: 0,
  };

  function goSymbol(sym) {
    const s = String(sym || "").toUpperCase().trim();
    if (!s) return;
    const url = new URL(location.href);
    url.searchParams.set("symbol", s);
    url.searchParams.set("range", state.range || "5y");
    location.href = url.pathname + "?" + url.searchParams.toString();
  }

  function setSuggestOpen(open) {
    searchState.open = open;
    searchRoot.classList.toggle("open", open);
    suggestBox.hidden = !open;
    searchInput.setAttribute("aria-expanded", open ? "true" : "false");
    if (!open) searchState.active = -1;
  }

  function renderSuggest(items, mode) {
    searchState.items = items || [];
    searchState.mode = mode;
    searchState.active = items.length ? 0 : -1;
    suggestHead.textContent = mode === "top" ? "市值前十" : "搜索结果";
    if (!items.length) {
      suggestList.innerHTML = `<div class="val-suggest-empty">未找到匹配股票，试试 AAPL / NVDA</div>`;
      return;
    }
    suggestList.innerHTML = items
      .map((it, i) => {
        const rank =
          mode === "top"
            ? `<span class="val-suggest-rank">#${i + 1}</span>`
            : "";
        return `<button type="button" class="val-suggest-item${mode === "top" ? "" : " no-rank"}${i === 0 ? " active" : ""}" role="option" data-i="${i}" data-symbol="${it.symbol}">
          ${rank}
          <span class="val-suggest-sym">${it.symbol}</span>
          <span class="val-suggest-name">${it.name || ""}</span>
        </button>`;
      })
      .join("");
  }

  function moveActive(delta) {
    const n = searchState.items.length;
    if (!n) return;
    searchState.active = (searchState.active + delta + n) % n;
    suggestList.querySelectorAll(".val-suggest-item").forEach((el, i) => {
      el.classList.toggle("active", i === searchState.active);
    });
    const el = suggestList.querySelector(".val-suggest-item.active");
    if (el) el.scrollIntoView({ block: "nearest" });
  }

  async function loadTop() {
    const seq = ++searchState.seq;
    try {
      const res = await fetch("/api/valuation/tickers/top?limit=10");
      const data = await res.json();
      if (seq !== searchState.seq) return;
      renderSuggest(data.items || [], "top");
    } catch (err) {
      if (seq !== searchState.seq) return;
      suggestList.innerHTML = `<div class="val-suggest-empty">加载失败：${err.message}</div>`;
    }
  }

  async function runSearch(q) {
    const seq = ++searchState.seq;
    const query = String(q || "").trim();
    if (!query) {
      await loadTop();
      return;
    }
    try {
      const res = await fetch(
        `/api/valuation/tickers/search?q=${encodeURIComponent(query)}&limit=12`
      );
      const data = await res.json();
      if (seq !== searchState.seq) return;
      renderSuggest(data.items || [], "search");
    } catch (err) {
      if (seq !== searchState.seq) return;
      suggestList.innerHTML = `<div class="val-suggest-empty">搜索失败：${err.message}</div>`;
    }
  }

  function openSearch() {
    setSuggestOpen(true);
    if (!searchInput.value.trim()) loadTop();
    else runSearch(searchInput.value);
  }

  searchInput.addEventListener("focus", openSearch);
  searchInput.addEventListener("click", openSearch);

  searchInput.addEventListener("input", () => {
    clearTimeout(searchState.timer);
    searchState.timer = setTimeout(() => {
      setSuggestOpen(true);
      runSearch(searchInput.value);
    }, 160);
  });

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      setSuggestOpen(false);
      searchInput.blur();
      return;
    }
    if (!searchState.open) openSearch();
    if (e.key === "ArrowDown") {
      e.preventDefault();
      moveActive(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      moveActive(-1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const it =
        searchState.items[searchState.active] ||
        (searchInput.value.trim()
          ? { symbol: searchInput.value.trim().toUpperCase() }
          : null);
      if (it) goSymbol(it.symbol);
    }
  });

  suggestList.addEventListener("mousedown", (e) => {
    const btn = e.target.closest(".val-suggest-item");
    if (!btn) return;
    e.preventDefault();
    goSymbol(btn.dataset.symbol);
  });

  document.addEventListener("mousedown", (e) => {
    if (!searchRoot.contains(e.target)) setSuggestOpen(false);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || (e.target && e.target.isContentEditable)) {
      return;
    }
    e.preventDefault();
    searchInput.focus();
    openSearch();
  });

  load();
})();