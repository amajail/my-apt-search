"use strict";

// Vanilla JS, no build step. Loads data/index.json -> data/<profile>.json (pre-rendered from
// Azure by scripts/export_web.py) and renders summary + recent-changes + a sortable/filterable
// listings table. No secrets here: the page only reads static JSON.

const state = {
  profile: null,
  doc: null,            // current profile's exported doc
  sortKey: "price",
  sortDir: 1,           // 1 asc, -1 desc
};

const $ = (sel) => document.querySelector(sel);
const fmtUSD = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
const esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

async function getJSON(path) {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

function setStatus(msg) {
  const el = $("#status-msg");
  el.textContent = msg || "";
  el.hidden = !msg;
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

// ---- changes panel ----------------------------------------------------------

const CHANGE_META = {
  NEW: { cls: "badge-new", label: "NEW" },
  PRICE_CHANGE: { cls: "badge-price", label: "PRICE" },
  REMOVED: { cls: "badge-removed", label: "REMOVED" },
  RELISTED: { cls: "badge-relisted", label: "RELISTED" },
};

function renderChanges(changes) {
  const section = $("#changes-section");
  const list = $("#changes-list");
  if (!changes || !changes.length) {
    section.hidden = true;
    return;
  }
  // newest first
  const sorted = [...changes].sort((a, b) =>
    (b.occurred_at || "").localeCompare(a.occurred_at || "")
  );
  list.innerHTML = sorted
    .slice(0, 50)
    .map((e) => {
      const meta = CHANGE_META[e.type] || { cls: "", label: e.type };
      let detail = "";
      if (e.type === "PRICE_CHANGE" && e.old_price != null && e.new_price != null) {
        const arrow = e.new_price < e.old_price ? "▼" : "▲";
        const dir = e.new_price < e.old_price ? "drop" : "rise";
        detail = `<span class="price-move ${dir}">${arrow} USD ${fmtUSD(e.old_price)} → ${fmtUSD(e.new_price)}</span>`;
      } else if (e.new_price != null) {
        detail = `<span class="price-move">USD ${fmtUSD(e.new_price)}</span>`;
      }
      const title = e.url
        ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>`
        : esc(e.title);
      return `<li>
        <span class="badge ${meta.cls}">${meta.label}</span>
        <span class="chg-date">${fmtDate(e.occurred_at)}</span>
        ${detail}
        <span class="chg-title">${title}</span>
      </li>`;
    })
    .join("");
  section.hidden = false;
}

// ---- summary ----------------------------------------------------------------

function renderSummary(doc) {
  const prices = doc.listings.map((l) => l.price).filter((p) => p != null);
  const min = prices.length ? Math.min(...prices) : null;
  const max = prices.length ? Math.max(...prices) : null;
  $("#summary").innerHTML = `
    <div class="stat"><span class="big">${doc.count}</span><span>listings</span></div>
    <div class="stat"><span class="big">USD ${fmtUSD(min)}–${fmtUSD(max)}</span><span>price range</span></div>
    <div class="stat"><span class="big">${doc.changes.length}</span><span>changes (30d)</span></div>`;
  $("#updated").textContent = "Updated " + fmtDate(doc.generated_at);
  const src = $("#source-link");
  if (doc.search_url) {
    src.href = doc.search_url;
    src.hidden = false;
  } else {
    src.hidden = true;
  }
}

// ---- listings table ---------------------------------------------------------

function populateNeighborhoods(listings) {
  const sel = $("#filter-neighborhood");
  const names = [...new Set(listings.map((l) => l.neighborhood).filter(Boolean))].sort();
  sel.innerHTML =
    '<option value="">All</option>' +
    names.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
}

function currentRows() {
  const nb = $("#filter-neighborhood").value;
  const maxRaw = $("#filter-maxprice").value;
  const max = maxRaw === "" ? Infinity : Number(maxRaw);
  let rows = state.doc.listings.filter(
    (l) => (!nb || l.neighborhood === nb) && (l.price == null || l.price <= max)
  );
  const k = state.sortKey;
  rows = rows
    .map((l, i) => ({ ...l, idx: i }))
    .sort((a, b) => {
      let av = a[k], bv = b[k];
      if (typeof av === "string" || typeof bv === "string") {
        av = (av || "").toString().toLowerCase();
        bv = (bv || "").toString().toLowerCase();
        return av < bv ? -state.sortDir : av > bv ? state.sortDir : 0;
      }
      av = av == null ? -Infinity : av;
      bv = bv == null ? -Infinity : bv;
      return (av - bv) * state.sortDir;
    });
  return rows;
}

function renderTable() {
  const rows = currentRows();
  $("#listings-body").innerHTML = rows
    .map(
      (l, i) => `<tr>
        <td class="num">${i + 1}</td>
        <td class="num">${fmtUSD(l.price)}</td>
        <td class="num">${l.rooms ?? "?"}</td>
        <td class="num">${l.area_m2 ?? "?"}</td>
        <td class="num">${l.days_listed ?? "?"}</td>
        <td>${esc(l.neighborhood)}</td>
        <td><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a></td>
      </tr>`
    )
    .join("");
  $("#result-count").textContent = `${rows.length} shown`;
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    const k = th.getAttribute("data-sort");
    th.classList.toggle("sorted", k === state.sortKey);
    th.dataset.dir = k === state.sortKey ? (state.sortDir === 1 ? "asc" : "desc") : "";
  });
}

function wireTableControls() {
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const k = th.getAttribute("data-sort");
      if (state.sortKey === k) state.sortDir *= -1;
      else {
        state.sortKey = k;
        state.sortDir = k === "neighborhood" || k === "title" ? 1 : 1;
      }
      renderTable();
    });
  });
  $("#filter-neighborhood").addEventListener("change", renderTable);
  $("#filter-maxprice").addEventListener("input", renderTable);
}

// ---- load / boot ------------------------------------------------------------

async function loadProfile(name) {
  setStatus("Loading " + name + "…");
  try {
    const doc = await getJSON(`data/${encodeURIComponent(name)}.json`);
    state.profile = name;
    state.doc = doc;
    renderSummary(doc);
    renderChanges(doc.changes);
    populateNeighborhoods(doc.listings);
    renderTable();
    setStatus(doc.listings.length ? "" : "No active listings.");
  } catch (err) {
    setStatus("Could not load data: " + err.message);
  }
}

async function boot() {
  wireTableControls();
  try {
    const index = await getJSON("data/index.json");
    const sel = $("#profile-select");
    sel.innerHTML = index.profiles
      .map((p) => `<option value="${esc(p)}">${esc(p)}</option>`)
      .join("");
    sel.addEventListener("change", () => loadProfile(sel.value));
    if (!index.profiles.length) {
      setStatus("No profiles exported yet.");
      return;
    }
    await loadProfile(index.profiles[0]);
  } catch (err) {
    setStatus("Could not load index: " + err.message);
  }
}

boot();
