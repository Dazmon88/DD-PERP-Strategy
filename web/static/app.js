(() => {
  const state = {
    category: "rwa",
    display: "rate_1h",
    arbOnly: false,
    timer: null,
    query: "",
    lastData: null,
  };

  const els = {
    categoryPills: document.getElementById("categoryPills"),
    displayPills: document.getElementById("displayPills"),
    arbOnly: document.getElementById("arbOnly"),
    refreshBtn: document.getElementById("refreshBtn"),
    status: document.getElementById("status"),
    table: document.getElementById("matrixTable"),
    thead: document.querySelector("#matrixTable thead"),
    tbody: document.querySelector("#matrixTable tbody"),
    fetchedAt: document.getElementById("fetchedAt"),
    liveDot: document.getElementById("liveDot"),
    pairSearch: document.getElementById("pairSearch"),
    weekBoard: document.getElementById("weekBoard"),
    calendarLede: document.getElementById("calendarLede"),
    hotList: document.getElementById("hotList"),
  };

  function fmtPct(v, display) {
    if (v == null || Number.isNaN(v)) return "—";
    const n = Number(v);
    if (display === "apr") return `${(n * 100).toFixed(2)}%`;
    return `${(n * 100).toFixed(4)}%`;
  }

  function spreadToApr(spread, display) {
    if (spread == null || Number.isNaN(spread)) return null;
    const n = Number(spread);
    if (display === "apr") return n;
    if (display === "rate_8h") return (n / 8) * 24 * 365;
    return n * 24 * 365;
  }

  function fmtApr(v) {
    if (v == null || Number.isNaN(v)) return "—";
    return `${(Number(v) * 100).toFixed(2)}%`;
  }

  function exchangeLabel(ex) {
    return (
      {
        ondo: "Ondo",
        arcus: "Arcus",
        hype: "Hype",
        lighter: "Lighter",
        standx: "StandX",
      }[ex] || ex
    );
  }

  function goChart(pair) {
    window.location.href = `/chart?pair=${encodeURIComponent(pair)}`;
  }

  function filterRows(rows) {
    let out = rows.slice();
    if (state.arbOnly) out = out.filter((r) => r.arb && r.venue_count >= 2);
    const q = state.query.trim().toUpperCase();
    if (q) {
      out = out.filter(
        (r) =>
          String(r.pair || "").includes(q) ||
          String(r.name || "").toUpperCase().includes(q) ||
          String(r.category || "").toUpperCase().includes(q)
      );
    }
    return out;
  }

  function avatarColor(seed) {
    let h = 0;
    const s = String(seed || "");
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
    return `hsl(${h} 42% 38%)`;
  }

  function tickerLogoHtml(symbol) {
    const sym = String(symbol || "").toUpperCase();
    if (!sym) {
      return `<span class="event-avatar">?</span>`;
    }
    const initials = sym.slice(0, 2);
    const src = `https://img.loadlogo.com/ticker/${encodeURIComponent(sym)}?size=64&format=png`;
    return `<img class="event-avatar logo" src="${src}" alt="${sym}" loading="lazy" referrerpolicy="no-referrer" data-fallback="${initials}" data-bg="${avatarColor(sym)}" />`;
  }

  function bindLogoFallbacks(root) {
    root.querySelectorAll("img.event-avatar.logo").forEach((img) => {
      img.addEventListener("error", () => {
        const span = document.createElement("span");
        span.className = "event-avatar";
        span.textContent = img.dataset.fallback || "?";
        span.style.background = img.dataset.bg || "#334155";
        img.replaceWith(span);
      }, { once: true });
    });
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function ecoTipHtml(ev) {
    const rows = [];
    const country = String(ev.country_code || "").toUpperCase() === "JP" ? "日本" : "美国";
    const consensus = String(ev.consensus || "").trim();
    const previous = String(ev.previous || "").trim();
    const actual = String(ev.actual || "").trim();
    rows.push(`<div class="eco-tip-row"><span>国家</span><strong>${country}</strong></div>`);
    rows.push(`<div class="eco-tip-row"><span>预期</span><strong>${escapeHtml(consensus || "—")}</strong></div>`);
    rows.push(`<div class="eco-tip-row"><span>前值</span><strong>${escapeHtml(previous || "—")}</strong></div>`);
    rows.push(
      `<div class="eco-tip-row actual"><span>公布</span><strong>${escapeHtml(actual || "—")}</strong></div>`
    );
    return `<div class="eco-tip" role="tooltip">${rows.join("")}</div>`;
  }

  function renderWeek(data) {
    const cols = data.columns || [];
    const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Hong_Kong" });
    if (els.calendarLede) {
      const errN = Object.keys(data.errors || {}).length;
      els.calendarLede.textContent = errN
        ? `本周 ${data.week_start} → ${data.week_end} · 时间香港 · 部分日期拉取失败`
        : `本周 ${data.week_start} → ${data.week_end} · 时间香港 · 美/日经济数据 + 财报 BMO≈08:00ET / AMC≈16:05ET`;
    }
    if (!cols.length) {
      els.weekBoard.innerHTML = `<div class="muted calendar-loading">本周暂无日历数据</div>`;
      return;
    }
    els.weekBoard.innerHTML = cols
      .map((col) => {
        const events = col.events || [];
        const rows = events.length
          ? events
              .map((ev) => {
                const hkt = ev.time_hkt || "—";
                if (ev.type === "economic") {
                  const isJp = String(ev.country_code || "").toUpperCase() === "JP";
                  const tag = isJp ? "JP" : "US";
                  const avatar = isJp ? "J" : "U";
                  const actual = String(ev.actual || "").trim();
                  const consensus = String(ev.consensus || "").trim();
                  const printBadge = actual
                    ? `<span class="badge-print has-actual">${escapeHtml(actual)}</span>`
                    : consensus
                      ? `<span class="badge-print">预期 ${escapeHtml(consensus)}</span>`
                      : "";
                  return `<div class="event-row eco">
                    <span class="event-avatar macro ${isJp ? "jp" : "us"}">${avatar}</span>
                    <div class="event-main">
                      <span class="event-symbol macro-name">${escapeHtml(ev.name)}</span>
                      <div class="event-sub">
                        <span class="badge-mkt macro ${isJp ? "jp" : ""}">${tag}</span>
                        ${printBadge}
                      </div>
                    </div>
                    <div class="event-tags">
                      <span class="event-clock">${escapeHtml(hkt)}</span>
                    </div>
                    ${ecoTipHtml(ev)}
                  </div>`;
                }
                const session = (ev.hour_label || "TBD").toUpperCase();
                const tipParts = [
                  ev.name || ev.symbol,
                  "点击查看 Trailing P/E",
                  ev.time_et && `美东 ${ev.time_et}`,
                  hkt !== "—" && `香港 ${hkt}`,
                ].filter(Boolean);
                return `<a class="event-row" href="/valuation?symbol=${encodeURIComponent(ev.symbol)}" title="${tipParts.join(" · ")}">
                  ${tickerLogoHtml(ev.symbol)}
                  <div class="event-main">
                    <span class="event-symbol">${escapeHtml(ev.symbol)}</span>
                    <div class="event-sub">
                      <span class="badge-hour ${ev.hour || "tbd"}">${session}</span>
                    </div>
                  </div>
                  <div class="event-tags">
                    <span class="event-clock">${escapeHtml(hkt)}</span>
                  </div>
                </a>`;
              })
              .join("")
          : `<div class="day-empty">暂无精选事件</div>`;
        return `<article class="card day-col ${col.date === today ? "is-today" : ""}">
          <h3 class="day-label">${col.label}</h3>
          <div class="event-list">${rows}</div>
        </article>`;
      })
      .join("");
    bindLogoFallbacks(els.weekBoard);
  }

  async function loadCalendar(force = false) {
    try {
      const q = force ? "?force=true" : "";
      const res = await fetch(`/api/calendar/week${q}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderWeek(data);
    } catch (err) {
      els.weekBoard.innerHTML = `<div class="muted calendar-loading">日历加载失败：${err.message}</div>`;
    }
  }

  function renderHot(rows, display) {
    const ranked = rows
      .filter((r) => r.arb && r.arb.spread != null)
      .slice()
      .sort((a, b) => Math.abs(b.arb.spread) - Math.abs(a.arb.spread));
    if (!ranked.length) {
      els.hotList.innerHTML = `<li class="muted">暂无热点价差</li>`;
      return;
    }
    els.hotList.innerHTML = ranked
      .slice(0, 5)
      .map((r, i) => {
        const a = spreadToApr(r.arb.spread, display);
        return `<li>
          <a href="/chart?pair=${encodeURIComponent(r.pair)}">
            <span class="hot-rank">${i + 1}</span>
            <span class="hot-name">${r.pair}</span>
            <span class="hot-meta">${fmtApr(a)}</span>
          </a>
        </li>`;
      })
      .join("");
  }

  async function load(force = false) {
    els.refreshBtn.disabled = true;
    els.status.hidden = false;
    els.status.textContent = "拉取公开资金费率…";

    const params = new URLSearchParams();
    params.set("display", state.display);
    params.set("exchanges", "ondo,arcus,standx,hype,lighter");
    params.set("min_venues", state.arbOnly ? "2" : "1");
    if (state.category) params.set("category", state.category);
    else params.set("category", "");
    if (force) params.set("force", "true");

    try {
      const res = await fetch(`/api/funding/matrix?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.lastData = data;
      render(data);
      els.liveDot.classList.add("on");
      els.fetchedAt.textContent = data.fetched_at
        ? `更新 ${new Date(data.fetched_at).toLocaleTimeString()}`
        : "已更新";
      const lighterErr = (data.errors || {}).lighter || "";
      if (/pending|timeout|background/i.test(lighterErr) && !state._lighterRetry) {
        state._lighterRetry = true;
        setTimeout(() => {
          state._lighterRetry = false;
          load(false);
        }, 15000);
      }
    } catch (err) {
      els.liveDot.classList.remove("on");
      els.status.hidden = false;
      els.status.textContent = `加载失败：${err.message}`;
      els.table.hidden = true;
      els.hotList.innerHTML = `<li class="muted">${err.message}</li>`;
    } finally {
      els.refreshBtn.disabled = false;
    }
  }

  function render(data) {
    const exchanges = data.exchanges || [];
    const rows = filterRows(data.rows || []);

    const errKeys = Object.keys(data.errors || {});
    const errText = errKeys.length ? ` · 部分失败：${errKeys.join(", ")}` : "";
    const staleText = data.stale ? " · 缓存刷新中" : "";
    els.status.textContent = `${rows.length} 个交易对 · ${data.display}${staleText}${errText}`;
    els.table.hidden = false;

    renderHot(data.rows || [], data.display);

    els.thead.innerHTML = "";
    const hr = document.createElement("tr");
    hr.innerHTML = `<th class="pair-col">市场</th>${exchanges
      .map((ex) => `<th>${exchangeLabel(ex)}</th>`)
      .join("")}<th class="arb-col">套利差</th>`;
    els.thead.appendChild(hr);

    els.tbody.innerHTML = "";
    if (!rows.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td class="pair-col" colspan="${exchanges.length + 2}">暂无数据</td>`;
      els.tbody.appendChild(tr);
      return;
    }

    for (const row of rows) {
      const tr = document.createElement("tr");
      const pair = String(row.pair || "");
      const initials = pair.slice(0, 2).toUpperCase() || "?";
      const pairCell = `<td class="pair-col">
        <div class="pair-cell">
          <span class="pair-avatar" style="background:${avatarColor(pair)}">${initials}</span>
          <span class="pair-name">${pair}</span>
        </div>
      </td>`;

      const cells = exchanges
        .map((ex) => {
          const cell = row.cells?.[ex];
          if (!cell || cell.display_value == null) {
            return `<td><span class="rate empty">—</span></td>`;
          }
          const v = cell.display_value;
          const cls = v < 0 ? "neg" : "";
          return `<td><span class="rate ${cls}" title="${cell.symbol || ""}">${fmtPct(v, data.display)}</span></td>`;
        })
        .join("");

      let arbHtml = `<td class="arb-col"><span class="rate empty">—</span></td>`;
      if (row.arb) {
        const spread = Number(row.arb.spread);
        const spreadCls = spread > 0 ? "pos" : spread < 0 ? "neg" : "";
        const apr = spreadToApr(row.arb.spread, data.display);
        arbHtml = `<td class="arb-col">
          <span class="spread ${spreadCls}">${fmtPct(row.arb.spread, data.display)}</span>
          <span class="spread-apr">${fmtApr(apr)} APR</span>
          <span class="spread-hint">多 ${exchangeLabel(row.arb.long_exchange)} · 空 ${exchangeLabel(row.arb.short_exchange)}</span>
        </td>`;
      }

      tr.innerHTML = pairCell + cells + arbHtml;
      tr.title = `查看 ${row.pair} 跨所价格折线`;
      tr.addEventListener("click", () => goChart(row.pair));
      els.tbody.appendChild(tr);
    }
  }

  els.categoryPills.addEventListener("click", (e) => {
    const btn = e.target.closest(".cat");
    if (!btn) return;
    els.categoryPills.querySelectorAll(".cat").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    state.category = btn.dataset.category ?? "rwa";
    load();
  });

  els.displayPills.addEventListener("click", (e) => {
    const btn = e.target.closest(".display-pill");
    if (!btn) return;
    els.displayPills.querySelectorAll(".display-pill").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    state.display = btn.dataset.display || "rate_1h";
    load();
  });

  els.arbOnly.addEventListener("change", () => {
    state.arbOnly = els.arbOnly.checked;
    if (state.lastData) render(state.lastData);
    else load();
  });

  els.refreshBtn.addEventListener("click", () => {
    load(true);
    loadCalendar(true);
  });

  let searchTimer = null;
  els.pairSearch.addEventListener("input", () => {
    state.query = els.pairSearch.value || "";
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      if (state.lastData) render(state.lastData);
    }, 120);
  });

  // 估值股票搜索（与估值页相同）
  const searchRoot = document.getElementById("valSearch");
  const searchInput = document.getElementById("tickerSearch");
  const suggestBox = document.getElementById("tickerSuggest");
  const suggestHead = document.getElementById("suggestHead");
  const suggestList = document.getElementById("suggestList");
  if (searchRoot && searchInput && suggestBox && suggestHead && suggestList) {
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
      location.href = `/valuation?symbol=${encodeURIComponent(s)}`;
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
        suggestList.innerHTML =
          `<div class="val-suggest-empty">未找到匹配股票，试试 AAPL / NVDA</div>`;
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
  }

  load();
  loadCalendar();
  state.timer = setInterval(() => {
    load(false);
    loadCalendar(false);
  }, 45000);
})();