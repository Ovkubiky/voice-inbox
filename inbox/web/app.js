// Voice Inbox: rotating painting hero, capture (voice / text), board grouped by type / project / when / status (drag & drop),
// and a teaser for today's Gazette (C9, /gazette).
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const CHECK = '<svg viewBox="0 0 24 24"><path d="m5 12 5 5 9-10"/></svg>';
const TYPE_LABEL = { task: "task", event: "event", idea: "idea", note: "note" };

const state = {
  items: [], projects: [], query: "", pending: null, fresh: new Set(), recorder: null, chunks: [], recStart: 0, timer: null,
  group: pref("group", "type"),
};
function pref(k, d) { try { return localStorage.getItem(k) || d; } catch { return d; } }
function save(k, v) { try { localStorage.setItem(k, v); } catch {} }

// ---------------------------------------------------------------- data
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
const patch = (id, body) => api(`/items/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
async function load() {
  const [items, projects] = await Promise.all([api("/items?status=all"), state.projects.length ? state.projects : api("/projects")]);
  state.items = items;
  state.projects = projects;
  render();
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 3200);
}

// ---------------------------------------------------------------- dates
const DAY = 864e5;
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
function parseStart(s) {
  if (!s) return null;
  const [d, t] = s.split("T");
  const [y, m, day] = d.split("-").map(Number);
  const [hh, mm] = t ? t.split(":").map(Number) : [0, 0];
  return { date: new Date(y, m - 1, day, hh, mm), hasTime: !!t };
}
function dayDiff(p) { return Math.round((startOfDay(p.date) - startOfDay(new Date())) / DAY); }
function fmtStart(s) {
  const p = parseStart(s);
  if (!p) return "";
  const diff = dayDiff(p);
  let day = diff === 0 ? "Today" : diff === 1 ? "Tomorrow" : diff === -1 ? "Yesterday"
    : p.date.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" });
  if (p.hasTime) day += ", " + p.date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return day;
}
function whenBucket(it) {
  const p = parseStart(it.start);
  if (!p) return "none";
  const diff = dayDiff(p);
  if (diff < 0) return it.status === "done" ? "past" : "overdue";
  if (diff === 0) return "today";
  if (diff === 1) return "tomorrow";
  if (diff <= 7) return "week";
  return "later";
}

// ---------------------------------------------------------------- grouping
function columns() {
  switch (state.group) {
    case "project":
      return [...state.projects.map((p) => ({ key: p.name, label: p.name, drop: true })), { key: "__none", label: "Everything else", drop: true }];
    case "when":
      return [
        { key: "overdue", label: "Running late" }, { key: "today", label: "Today" }, { key: "tomorrow", label: "Tomorrow" },
        { key: "week", label: "This week" }, { key: "later", label: "Later on" }, { key: "none", label: "Whenever" }, { key: "past", label: "Behind you" },
      ];
    case "status":
      return [{ key: "needs", label: "Needs a word from you" }, { key: "open", label: "To do", drop: true }, { key: "done", label: "Done", drop: true }];
    default:
      return [
        { key: "task", label: "Top to-dos", drop: true }, { key: "event", label: "On the calendar", drop: true },
        { key: "idea", label: "Ideas worth keeping", drop: true }, { key: "note", label: "Notes", drop: true },
      ];
  }
}
function keyOf(it) {
  switch (state.group) {
    case "project": return it.project || "__none";
    case "when": return whenBucket(it);
    case "status": return it.status === "done" ? "done" : it.is_incomplete ? "needs" : "open";
    default: return it.type;
  }
}
function patchFor(colKey) {
  switch (state.group) {
    case "project": return colKey === "__none" ? { clear_project: true } : { project: colKey };
    case "status": return colKey === "needs" ? null : { status: colKey };
    case "type": return { type: colKey };
    default: return null;
  }
}
function grouped() {
  const q = state.query.trim().toLowerCase();
  const items = state.items.filter((it) => !q || [it.title, it.source_text, it.project, ...(it.people || [])].join(" ").toLowerCase().includes(q));
  const cols = columns();
  const by = Object.fromEntries(cols.map((c) => [c.key, []]));
  for (const it of items) (by[keyOf(it)] ||= []).push(it);
  for (const k in by) by[k].sort((a, b) => (a.status === "done") - (b.status === "done"));
  return { cols, by };
}

// ---------------------------------------------------------------- item pieces
function metaHTML(it) {
  const parts = [];
  if (it.start) parts.push(`<span class="when ${whenBucket(it) === "overdue" ? "overdue" : ""}">${esc(fmtStart(it.start))}</span>`);
  if (it.people?.length) parts.push(`with ${esc(it.people.join(", "))}`);
  if (state.group !== "type") parts.push(TYPE_LABEL[it.type]);
  if (it.duplicate_of) parts.push(`looks like #${it.duplicate_of}`);
  const quote = it.source_text && it.source_text.toLowerCase() !== it.title.toLowerCase() ? `<span class="quote">“${esc(it.source_text)}”</span>` : "";
  return `<p class="meta">${parts.join(" · ")}${parts.length && quote ? " — " : ""}${quote}</p>`;
}
function askHTML(it) {
  if (!(it.is_incomplete && it.question && it.status !== "done")) return "";
  return `<div class="ask"><p class="ask-q">${esc(it.question)}</p>
    <form data-answer="${it.id}"><input class="underline" placeholder="Type your answer…"><button class="link arrow">Answer →</button></form></div>`;
}
function toolsHTML(it) {
  return `<div class="tools">${it.start ? `<a href="/items/${it.id}.ics">+ calendar</a>` : ""}<button data-act="dismiss">dismiss</button></div>`;
}
const tagHTML = (it) => (it.project && state.group !== "project" ? `<span class="tag">${esc(it.project)}</span>` : "");

function cardHTML(it) {
  const done = it.status === "done";
  return `<article class="card ${done ? "done" : ""} ${state.fresh.has(it.id) ? "fresh" : ""}" draggable="true" data-id="${it.id}">
    <button class="check" data-act="${done ? "reopen" : "done"}" title="${done ? "Reopen" : "Mark done"}">${CHECK}</button>
    ${toolsHTML(it)}<h3 class="title">${esc(it.title)}</h3>${tagHTML(it)}${metaHTML(it)}${askHTML(it)}
  </article>`;
}
const pendingHTML = () => (state.pending ? `<div class="pending"><span class="spark"></span>${esc(state.pending)}</div>` : "");

// ---------------------------------------------------------------- render
function render() {
  document.querySelectorAll("#group-seg button").forEach((b) => b.classList.toggle("active", b.dataset.group === state.group));
  const { cols, by } = grouped();
  const shown = cols.filter((c) => by[c.key].length || c.drop);
  const firstKey = shown[0]?.key;
  $("#content").innerHTML = `<div class="board">${shown.map((c) => `
    <div class="col ${c.drop ? "" : "no-drop"}" data-col="${esc(c.key)}">
      <div class="col-head"><h2 class="label">${esc(c.label)}</h2><span class="count">${String(by[c.key].length).padStart(2, "0")}</span></div>
      ${c.key === firstKey ? pendingHTML() : ""}
      ${by[c.key].map(cardHTML).join("") || (c.key === firstKey && state.pending ? "" : `<p class="empty">${c.drop ? "Drop something here." : "Nothing here."}</p>`)}
    </div>`).join("")}</div>`;
  state.fresh.clear();
}
async function renderGazetteTeaser() {
  try {
    const b = await api("/brief?cached_only=true");
    $("#summary-text").textContent = b.headline ? `“${b.headline}.”` : "This morning's edition hasn't been printed yet.";
    document.querySelector("#summary .read").textContent = b.headline ? "Read it →" : "Print it →";
  } catch {}
}

// ---------------------------------------------------------------- hero: paintings + clock
let art = [], artIdx = 0, artFront = "a";
async function initArt() {
  try { art = await api("/static/art/art.json"); } catch { art = []; }
  if (!art.length) return;
  artIdx = Math.floor(Math.random() * art.length);
  showArt(true);
  setInterval(() => { artIdx = (artIdx + 1) % art.length; showArt(false); }, 45000);
}
function showArt(first) {
  const a = art[artIdx];
  const next = first ? $("#art-a") : artFront === "a" ? $("#art-b") : $("#art-a");
  const prev = next.id === "art-a" ? $("#art-b") : $("#art-a");
  next.onload = () => {
    next.classList.add("show");
    prev.classList.remove("show");
    artFront = next.id === "art-a" ? "a" : "b";
    $("#art-caption").textContent = `${a.title}, ${a.artist}, ${a.date}. ${a.medium.toLowerCase()}`;
  };
  next.alt = `${a.title} by ${a.artist}`;
  next.src = `/static/art/${a.file}`;
}
function tickClock() {
  const now = new Date();
  $("#rail-date").textContent = now.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }).toUpperCase();
  $("#dl-date").textContent = now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  $("#dl-no").textContent = Math.floor((now - new Date(now.getFullYear(), 0, 0)) / 864e5);
  $("#rail-time").textContent = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  $("#hero-day").textContent = `${now.toLocaleDateString("en-US", { weekday: "long" })} Inbox`;
}
function drawBurst() {
  const pts = [], n = 16;
  for (let i = 0; i < n * 2; i++) {
    const r = i % 2 ? 80 : 100, a = (Math.PI * i) / n;
    pts.push(`${(100 + r * Math.sin(a)).toFixed(1)},${(100 - r * Math.cos(a)).toFixed(1)}`);
  }
  $("#burst-poly").setAttribute("points", pts.join(" "));
}

// ---------------------------------------------------------------- capture
const DEFAULT_STATUS = $("#status-line").innerHTML;
const DEFAULT_TITLE = $("#capture-title").innerHTML;
function setCapture(mode, title, status, kicker) {
  $("#capture").className = `capture ${mode}`;
  $("#capture-title").innerHTML = title ?? DEFAULT_TITLE;
  $("#status-line").innerHTML = status ?? DEFAULT_STATUS;
  $("#capture-kicker").textContent = kicker ?? "New note";
}
function setSticker(text) { $("#sticker-text").innerHTML = text; }
async function submitNote(path, body) {
  state.pending = path === "/notes" ? "Listening back to you…" : "Reading your note…";
  render();
  const t1 = setTimeout(() => { state.pending = "Splitting it into things to do…"; render(); }, 3000);
  const t2 = setTimeout(() => { state.pending = "Working out dates, people and projects…"; render(); }, 10000);
  $("#mic").classList.add("busy");
  setSticker("One<br>sec…");
  setCapture("busy", "Reading it back…", "Splitting your note into tasks, events and ideas, then working out the dates. About 20 seconds.", "Processing");
  try {
    setTimeout(loadHistory, 400);
    const note = await api(path, { method: "POST", body });
    note.items.forEach((i) => state.fresh.add(i.id));
    const n = note.items.length;
    toast(n ? `${n} new item${n > 1 ? "s" : ""} from “${note.clean_text.slice(0, 50)}${note.clean_text.length > 50 ? "…" : ""}”` : "Nothing actionable in that one.");
  } catch (e) {
    toast("Something went wrong — " + e.message.slice(0, 80));
  } finally {
    clearTimeout(t1); clearTimeout(t2);
    state.pending = null;
    $("#mic").classList.remove("busy");
    setSticker("Speak<br>now →");
    setCapture("");
    await load();
    loadHistory();
  }
}
async function toggleRecording() {
  if (state.recorder) { state.recorder.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream);
    state.chunks = [];
    rec.ondataavailable = (e) => e.data.size && state.chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      clearInterval(state.timer);
      state.recorder = null;
      $("#mic").classList.remove("recording");
      setCapture("");
      if (Date.now() - state.recStart < 700) { setSticker("Speak<br>now →"); return toast("That was very short — try again."); }
      const fd = new FormData();
      fd.append("file", new Blob(state.chunks, { type: rec.mimeType || "audio/webm" }), (rec.mimeType || "").includes("mp4") ? "note.m4a" : "note.webm");
      submitNote("/notes", fd);
    };
    rec.start();
    state.recorder = rec;
    state.recStart = Date.now();
    $("#mic").classList.add("recording");
    const tick = () => {
      const s = Math.floor((Date.now() - state.recStart) / 1000);
      const t = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
      setSticker("Done<br>→");
      $("#capture-title").innerHTML = `Listening…<span class="timer">${t}</span>`;
    };
    setCapture("recording", "Listening…", "Talk the way you would to a friend. Press <kbd>R</kbd> or the sticker when you're done.", "Recording");
    tick();
    state.timer = setInterval(tick, 500);
  } catch {
    toast("The microphone isn't available — allow it in the browser.");
  }
}

// ---------------------------------------------------------------- events
$("#mic").addEventListener("click", toggleRecording);
$("#text-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#text").value.trim();
  if (!text) return;
  $("#text").value = "";
  const fd = new FormData();
  fd.append("text", text);
  submitNote("/notes/text", fd);
});
$("#group-seg").addEventListener("click", (e) => {
  const g = e.target.closest("button")?.dataset.group;
  if (g) { state.group = g; save("group", g); render(); }
});
$("#search").addEventListener("input", (e) => { state.query = e.target.value; render(); });

$("#content").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const id = btn.closest("[data-id]").dataset.id;
  const status = { done: "done", reopen: "open", dismiss: "dismissed" }[btn.dataset.act];
  await patch(id, { status });
  if (status === "dismissed") toast("Dismissed.");
  load();
});
$("#content").addEventListener("submit", async (e) => {
  const form = e.target.closest("form[data-answer]");
  if (!form) return;
  e.preventDefault();
  const answer = form.querySelector("input").value.trim();
  if (!answer) return;
  const fd = new FormData();
  fd.append("answer", answer);
  const it = await api(`/items/${form.dataset.answer}/answer`, { method: "POST", body: fd });
  state.fresh.add(it.id);
  toast(it.is_incomplete ? "Still missing something — try saying it differently." : "Got it.");
  load();
});

// drag & drop (Board view)
let dragId = null;
const content = $("#content");
content.addEventListener("dragstart", (e) => {
  const card = e.target.closest(".card");
  if (!card) return;
  dragId = card.dataset.id;
  card.classList.add("dragging");
  e.dataTransfer.effectAllowed = "move";
});
content.addEventListener("dragend", (e) => { e.target.closest(".card")?.classList.remove("dragging"); });
content.addEventListener("dragover", (e) => {
  const col = e.target.closest(".col");
  if (!col || col.classList.contains("no-drop")) return;
  e.preventDefault();
  document.querySelectorAll(".col.over").forEach((c) => c !== col && c.classList.remove("over"));
  col.classList.add("over");
});
content.addEventListener("dragleave", (e) => {
  const col = e.target.closest(".col");
  if (col && !col.contains(e.relatedTarget)) col.classList.remove("over");
});
content.addEventListener("drop", async (e) => {
  const col = e.target.closest(".col");
  document.querySelectorAll(".col.over").forEach((c) => c.classList.remove("over"));
  if (!col || !dragId || col.classList.contains("no-drop")) return;
  e.preventDefault();
  const body = patchFor(col.dataset.col);
  const id = Number(dragId);
  dragId = null;
  const it = state.items.find((i) => i.id === id);
  if (!body || (it && keyOf(it) === col.dataset.col)) return;
  await patch(id, body);
  state.fresh.add(id);
  load();
});

// keyboard
document.addEventListener("keydown", (e) => {
  const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName);
  if (e.key === "Escape") { document.activeElement?.blur(); closeDrawer(); return; }
  if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
  if ("rRкК".includes(e.key)) { e.preventDefault(); toggleRecording(); }
  if (e.key === "/" || e.key === ".") { e.preventDefault(); $("#text").focus(); }
});

// evaluation drawer
function closeDrawer() { $("#drawer").classList.remove("open"); $("#scrim").classList.remove("open"); }
$("#drawer-close").addEventListener("click", closeDrawer);
$("#scrim").addEventListener("click", closeDrawer);
$("#evals-btn").addEventListener("click", async () => {
  $("#drawer").classList.add("open");
  $("#scrim").classList.add("open");
  const evs = await api("/evals");
  const order = ["c1", "c3", "c4", "c5", "c5_heldout", "c6", "c7", "c8", "e2e_text", "e2e_audio"];
  const rank = (c) => { const i = order.findIndex((o) => c === o || c.startsWith(o + "_q")); return i < 0 ? 99 : i; };
  evs.sort((a, b) => rank(a.component) - rank(b.component) || a.component.localeCompare(b.component));
  $("#drawer-body").innerHTML = evs.map((ev) => `
    <div class="ev">
      <div class="ev-head"><span class="ev-name">${esc(ev.component)}</span><span class="ev-model">${esc(ev.model || "")}</span></div>
      ${Object.entries(ev.metrics).filter(([, v]) => typeof v === "number").map(([k, v]) => {
        const bar = v >= 0 && v <= 1 ? `<span class="ev-bar"><i style="width:${v * 100}%"></i></span>` : "";
        return `<div class="ev-row"><span class="k">${esc(k)}</span>${bar}<span class="v">${Number.isInteger(v) ? v : v.toFixed(3)}</span></div>`;
      }).join("")}
    </div>`).join("");
});

// boot
drawBurst();
tickClock();
setInterval(tickClock, 15000);
initArt();
api("/health").then((h) => {
  $("#status-dot").classList.add("ok");
  $("#status-text").textContent = "LOCAL";
  $("#foot-llm").textContent = h.llm;
}).catch(() => { $("#status-text").textContent = "SERVER OFFLINE"; });
load().catch((e) => toast("Can't reach the server — " + e.message));
renderGazetteTeaser();

// keep in sync with notes recorded from the menu-bar app
setInterval(() => {
  if (!state.pending && !document.hidden && !dragId && !document.activeElement?.closest?.(".ask, .write")) load().catch(() => {});
}, 5000);


// ---------------------------------------------------------------- recent notes (history + live status)
const STAGE_LABEL = {
  queued: "Waiting…", transcribing: "Transcribing the audio…", cleaning: "Cleaning up the text…",
  splitting: "Splitting into items…", saving: "Saving…",
};
const hist = { open: false, activeIds: "", fast: null };
const hhmm = (iso) => { const d = new Date(iso.replace(" ", "T")); return isNaN(d) ? "" : d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }); };
const dayLabel = (iso) => {
  const d = new Date(iso.replace(" ", "T")); if (isNaN(d)) return "";
  const diff = Math.round((startOfDay(new Date()) - startOfDay(d)) / DAY);
  return diff === 0 ? "" : diff === 1 ? "Yesterday " : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) + " ";
};
function activeRow(j) {
  const failed = j.status === "failed";
  const stage = STAGE_LABEL[j.stage] || (j.stage.startsWith("reading") ? `Reading ${j.stage.slice(8)}…` : j.stage);
  return `<li class="h-row ${failed ? "failed" : "working"}">
    <span class="h-time mono">${hhmm(j.started_at)}</span>
    <span class="h-status">${failed ? "✕ Failed" : `<i class="pulse"></i>${esc(stage)}`}</span>
    <span class="h-text">${j.preview ? `“${esc(j.preview)}”` : (j.kind === "voice" ? "Voice note" : "")}${failed ? ` <span class="h-err">${esc(j.error || "")}</span>` : ""}</span>
    <span class="h-items">${failed ? `<button class="link mono" data-dismiss="${j.job}">dismiss</button>` : ""}</span>
  </li>`;
}
function noteRow(n) {
  const items = n.items.filter((i) => i.status !== "dismissed");
  const ask = items.some((i) => i.is_incomplete && i.status === "open");
  const status = !(n.clean_text || "").trim() ? "Empty recording" : !items.length ? "Nothing to do" : ask ? "Needs an answer" : `Done · ${items.length} item${items.length > 1 ? "s" : ""}`;
  const text = n.clean_text || "";
  return `<li class="h-row ${ask ? "ask" : "ok"}" data-items="${items.map((i) => i.id).join(",")}">
    <span class="h-time mono">${dayLabel(n.recorded_at)}${hhmm(n.recorded_at)}</span>
    <span class="h-status">${n.voice ? "🎙 " : "✎ "}${status}</span>
    <span class="h-text">${text.trim() ? `“${esc(text.length > 110 ? text.slice(0, 110) + "…" : text)}”` : "<span class=\"h-err\" style=\"color:var(--grey)\">no speech detected</span>"}</span>
    <span class="h-items">${items.map((i) => `<span class="chip ${i.status === "done" ? "done" : ""}">${esc(i.type)}</span>`).join("")}</span>
  </li>`;
}
async function loadHistory() {
  let data;
  try { data = await api(`/notes/recent?limit=${hist.open ? 20 : 4}`); } catch { return; }
  const rows = data.active.map(activeRow).concat(data.notes.map(noteRow));
  $("#history-list").innerHTML = rows.join("") || '<li class="h-empty">No notes yet — say something.</li>';
  $("#history-count").textContent = data.active.some((j) => j.status === "processing") ? "processing" : "";
  $("#history-more").hidden = !hist.open && data.notes.length < 4;
  $("#history-more").textContent = hist.open ? "Show less ↑" : "Show more ↓";
  // a job just finished (e.g. from the menu-bar app) -> refresh the board
  const ids = data.active.filter((j) => j.status === "processing").map((j) => j.job).join(",");
  if (hist.activeIds && hist.activeIds !== ids && !state.pending) load().catch(() => {});
  hist.activeIds = ids;
  // poll fast while something is processing
  clearTimeout(hist.fast);
  if (ids || state.pending) hist.fast = setTimeout(loadHistory, 1200);
}
$("#history-more").addEventListener("click", () => { hist.open = !hist.open; loadHistory(); });
$("#history-list").addEventListener("click", async (e) => {
  const d = e.target.closest("[data-dismiss]");
  if (d) { await api(`/notes/jobs/${d.dataset.dismiss}`, { method: "DELETE" }); return loadHistory(); }
  const row = e.target.closest("[data-items]");
  if (!row || !row.dataset.items) return;
  const ids = row.dataset.items.split(",").map(Number);
  ids.forEach((i) => state.fresh.add(i));
  render();
  document.querySelector(`.card[data-id="${ids[0]}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
});
loadHistory();
setInterval(() => { if (!document.hidden) loadHistory(); }, 5000);
