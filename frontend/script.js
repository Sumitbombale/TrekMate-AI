/* ============================================================
   TrekMate AI — frontend logic
   All endpoints, request bodies, and response handling
   are unchanged from the original. UI additions are additive.
   ============================================================ */

const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const inr = (n) => "₹" + Number(n).toLocaleString("en-IN");
let history = [];

/* ---------- Theme toggle (respects system by default) ---------- */
(function initTheme() {
  const saved = localStorage.getItem("trekmate-theme");
  if (saved === "dark") document.documentElement.classList.add("dark");
  if (saved === "light") document.documentElement.classList.add("light");
})();
$("#theme-toggle").addEventListener("click", () => {
  const root = document.documentElement;
  const isDark = root.classList.contains("dark") ||
    (!root.classList.contains("light") && matchMedia("(prefers-color-scheme: dark)").matches);
  root.classList.toggle("dark", !isDark);
  root.classList.toggle("light", isDark);
  localStorage.setItem("trekmate-theme", !isDark ? "dark" : "light");
});

/* ---------- API helper (unchanged) ---------- */
async function api(path, body) {
  const res = await fetch(path, body ? {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)} : undefined);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed (" + res.status + ")");
  return data;
}
const list = (items) => "<ul>" + items.map((i) => "<li>" + esc(i) + "</li>").join("") + "</ul>";
const show = (id, html) => ($("#out-" + id).innerHTML = html);
const fail = (id, e) => show(id, '<div class="card warn">' + esc(e.message) + "</div>");
const num = (id) => ($(id).value ? Number($(id).value) : null);

/* ---------- Tab switching (unchanged) ---------- */
document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#tabs button,.tab").forEach((e) => e.classList.remove("active"));
  b.classList.add("active"); $("#" + b.dataset.tab).classList.add("active");
}));

/* ---------- Difficulty chip helper ---------- */
function diffClass(d) {
  const v = String(d || "").toLowerCase();
  if (v.includes("easy")) return "easy";
  if (v.includes("moderate")) return "moderate";
  if (v.includes("difficult") || v.includes("hard")) return "difficult";
  return "moderate";
}

/* ---------- Trek photo gallery (NEW) ---------- */
// Builds a small gallery of 1-2 photos with credit + licence (Wikimedia Commons attribution).
function galleryEl(photos) {
  const wrap = document.createElement("div");
  wrap.className = "msg-gallery";
  photos.forEach((p) => {
    if (!String(p.url).startsWith("https://")) return;
    const fig = document.createElement("figure");
    const a = document.createElement("a");
    a.href = String(p.page || "").startsWith("https://") ? p.page : p.url;
    a.target = "_blank"; a.rel = "noopener";
    const img = document.createElement("img");
    img.src = p.url; img.alt = p.title || "Trek photo"; img.loading = "lazy";
    a.appendChild(img); fig.appendChild(a);
    const cap = document.createElement("figcaption");
    cap.textContent = [p.credit ? "Photo: " + p.credit : "Photo: Wikimedia Commons", p.license].filter(Boolean).join(" · ");
    fig.appendChild(cap);
    wrap.appendChild(fig);
  });
  return wrap;
}

/* ---------- Chat ---------- */
function addMsg(cls, text, meta) {
  const d = document.createElement("div");
  d.className = "msg " + cls; d.textContent = text;
  if (meta) { const s = document.createElement("small"); s.textContent = meta; d.appendChild(s); }
  $("#log").appendChild(d); $("#log").scrollTop = 1e9;
  return d;
}
function addThinking() {
  const d = document.createElement("div");
  d.className = "msg bot";
  d.innerHTML = '<span class="dots"><span></span><span></span><span></span></span>';
  $("#log").appendChild(d); $("#log").scrollTop = 1e9;
  return d;
}

async function send() {
  const q = $("#q").value.trim(); if (!q) return;
  $("#q").value = "";
  addMsg("user", q);
  const btn = $("#send"); btn.disabled = true;
  const wait = addThinking();
  try {
    const r = await api("/api/chat", {question: q, history: history.slice(-12)});
    wait.remove();
    const bubble = addMsg("bot", r.answer, (r.mode === "gemini" ? "Gemini" : "Offline knowledge base") + (r.sources.length ? " · sources: " + r.sources.join(", ") : ""));
    // NEW: show 1-2 photos when the question was about a known trek
    if (r.photos && r.photos.length) {
      bubble.insertBefore(galleryEl(r.photos), bubble.querySelector("small"));
      $("#log").scrollTop = 1e9;
      // photos load after layout, so scroll again once the first one is ready
      const first = bubble.querySelector("img");
      if (first) first.addEventListener("load", () => ($("#log").scrollTop = 1e9));
    }
    history.push({role:"user", content:q}, {role:"assistant", content:r.answer});
  } catch (e) {
    wait.remove(); addMsg("bot", "⚠️ " + e.message);
  } finally {
    btn.disabled = false; $("#q").focus();
  }
}
$("#send").onclick = send;
$("#q").addEventListener("keydown", (e) => e.key === "Enter" && send());

/* ---------- Example prompt chips ---------- */
document.querySelectorAll("#chips .chip").forEach((c) =>
  c.addEventListener("click", () => { $("#q").value = c.textContent.trim(); send(); })
);

/* ---------- Photo -> predict the trek ---------- */
// Tiny markdown helper for Gemini's answer (bold + bullets + line breaks). Safe: escapes HTML first.
function mdLite(text) {
  return esc(text)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/^\s*[*-]\s+/gm, "• ")
    .replace(/\n/g, "<br>");
}

$("#photo-btn").addEventListener("click", () => $("#photo-input").click());

$("#photo-input").addEventListener("change", async () => {
  const input = $("#photo-input");
  const file = input.files[0];
  input.value = "";                       // lets the user pick the same file again later
  if (!file) return;

  const note = $("#q").value.trim();      // anything typed in the box is sent as a note about the photo
  $("#q").value = "";

  // Show the user's photo (and note) in the chat
  const mine = document.createElement("div");
  mine.className = "msg user";
  const img = document.createElement("img");
  img.className = "msg-photo"; img.alt = "Your photo"; img.src = URL.createObjectURL(file);
  mine.appendChild(img);
  if (note) { const p = document.createElement("div"); p.textContent = note; mine.appendChild(p); }
  $("#log").appendChild(mine); $("#log").scrollTop = 1e9;

  const photoBtn = $("#photo-btn"), sendBtn = $("#send");
  photoBtn.disabled = true; sendBtn.disabled = true;
  const wait = addThinking();
  try {
    const form = new FormData();          // multipart upload, so we don't use the JSON api() helper
    form.append("image", file);
    form.append("note", note);
    const res = await fetch("/api/identify-image", {method: "POST", body: form});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed (" + res.status + ")");

    wait.remove();
    const bot = document.createElement("div");
    bot.className = "msg bot";
    bot.innerHTML = mdLite(data.answer);
    const s = document.createElement("small");
    s.textContent = "Gemini Vision · AI prediction, please verify";
    bot.appendChild(s);
    $("#log").appendChild(bot); $("#log").scrollTop = 1e9;

    // Remember it so follow-ups like "how difficult is the first one?" work
    history.push({role: "user", content: "[Uploaded a trek photo]" + (note ? " Note: " + note : "")},
                 {role: "assistant", content: data.answer});
  } catch (e) {
    wait.remove(); addMsg("bot", "⚠️ " + e.message);
  } finally {
    photoBtn.disabled = false; sendBtn.disabled = false;
  }
});

/* ---------- Find a Trek (same endpoint, same shape) ---------- */
$("#go-find").onclick = async () => {
  const btn = $("#go-find"); btn.disabled = true;
  try {
    const r = await api("/api/recommend", {difficulty: $("#f-diff").value || null, max_days: num("#f-days"), max_budget: num("#f-budget"), month: $("#f-month").value || null, state: $("#f-state").value || null});
    show("find", r.results.length ? r.results.map((t) => `
      <div class="trek-card">
        <div class="trek-banner" aria-hidden="true" data-photo-q="${esc(t.name + " " + t.state)}">
          <svg viewBox="0 0 400 90" preserveAspectRatio="none">
            <path d="M0 90 L80 30 L140 70 L210 20 L280 65 L340 35 L400 90 Z" fill="rgba(255,255,255,0.25)"/>
            <path d="M0 90 L60 55 L130 85 L200 45 L270 80 L340 55 L400 90 Z" fill="rgba(255,255,255,0.35)"/>
          </svg>
        </div>
        <div class="trek-body">
          <div class="trek-title">
            <h3>${esc(t.name)}</h3>
            <span class="badge">TrekMatch ${esc(t.trekmatch)}%</span>
          </div>
          <div class="trek-meta">
            <span>📍 ${esc(t.state)}</span>
            <span>⏱ ${esc(t.duration_days)} days</span>
            <span>⛰ ${esc(t.max_altitude_m)} m</span>
            <span>💸 ${inr(t.cost_inr)}</span>
            <span>🗓 ${esc(t.best_season)}</span>
          </div>
          <div><span class="diff ${diffClass(t.difficulty)}">${esc(t.difficulty)}</span></div>
          <p class="trek-desc">${esc(t.description)}</p>
          ${t.reasons.length ? '<div class="muted">' + list(t.reasons) + "</div>" : ""}
          <div class="trek-actions">
            <button class="btn-ghost" type="button" data-plan-trek="${esc(t.name)}">Plan this trek</button>
          </div>
        </div>
      </div>`).join("") : '<div class="card">No treks match.</div>');

    // Wire "Plan this trek" → jump to Planner with trek preselected
    document.querySelectorAll("#out-find [data-plan-trek]").forEach((b) =>
      b.addEventListener("click", () => {
        $("#p-trek").value = b.dataset.planTrek;
        document.querySelector('#tabs button[data-tab="plan"]').click();
      })
    );

    // NEW: replace each card's drawn banner with a real photo when one is found
    document.querySelectorAll("#out-find .trek-banner[data-photo-q]").forEach(async (b) => {
      try {
        const p = await api("/api/photos?q=" + encodeURIComponent(b.dataset.photoQ) + "&n=1");
        if (p.photos.length && String(p.photos[0].url).startsWith("https://")) {
          b.style.backgroundImage = 'url("' + p.photos[0].url + '")';
          b.title = "Photo: " + (p.photos[0].credit || "Wikimedia Commons") + (p.photos[0].license ? " · " + p.photos[0].license : "");
          b.classList.add("has-photo");
        }
      } catch (e) { /* keep the drawn banner if no photo is found */ }
    });
  } catch (e) { fail("find", e); }
  finally { btn.disabled = false; }
};

/* ---------- Planner (unchanged) ---------- */
$("#go-plan").onclick = async () => {
  const btn = $("#go-plan"); btn.disabled = true;
  try {
    const r = await api("/api/plan", {trek: $("#p-trek").value, days: num("#p-days"), month: $("#p-month").value || null, group_size: num("#p-group") || 1});
    show("plan", `<div class="card"><h3>${esc(r.trek)} · ${r.days} days</h3>
      <div class="muted">Estimate: ${inr(r.budget.per_person_inr)} per person · ${inr(r.budget.total_inr)} for ${r.budget.group_size}. ${esc(r.budget.note)}</div>
      ${r.warnings.length ? '<div class="warn">' + list(r.warnings) + "</div>" : ""}</div>` +
      r.itinerary.map((d) => `<div class="card"><strong>Day ${d.day}: ${esc(d.title)}</strong><p>${esc(d.detail)}</p></div>`).join(""));
  } catch (e) { fail("plan", e); }
  finally { btn.disabled = false; }
};

/* ---------- Compare (unchanged shape, table wrapped for scroll) ---------- */
$("#go-compare").onclick = async () => {
  const names = [...document.querySelectorAll("#c-list input:checked")].map((c) => c.value);
  const btn = $("#go-compare"); btn.disabled = true;
  try {
    const r = await api("/api/compare", {treks: names});
    const rows = [["State","state"],["Difficulty","difficulty"],["Days","duration_days"],["Max altitude (m)","max_altitude_m"],["Best season","best_season"],["Approx cost (₹)","cost_inr"]];
    const s = r.summary;
    show("compare", `<div class="table-wrap"><table><thead><tr><th></th>${r.treks.map((t) => "<th>" + esc(t.name) + "</th>").join("")}</tr></thead>
      <tbody>${rows.map(([l,k]) => "<tr><td><b>" + l + "</b></td>" + r.treks.map((t) => "<td>" + esc(t[k]) + "</td>").join("") + "</tr>").join("")}</tbody></table></div>
      <div class="card">Easiest: <b>${esc(s.easiest)}</b> · Hardest: <b>${esc(s.hardest)}</b> · Cheapest: <b>${esc(s.cheapest)}</b> · Shortest: <b>${esc(s.shortest)}</b> · Highest: <b>${esc(s.highest)}</b></div>`);
  } catch (e) { fail("compare", e); }
  finally { btn.disabled = false; }
};

/* ---------- Packing (unchanged; checkboxes remain interactive) ---------- */
$("#go-packing").onclick = async () => {
  const btn = $("#go-packing"); btn.disabled = true;
  try {
    const r = await api("/api/packing", {trek: $("#k-trek").value, month: $("#k-month").value || null});
    show("packing", Object.entries(r.checklist).map(([cat, items]) => `<div class="card"><h3>${esc(cat)}</h3>${items.map((i) => '<label style="flex-direction:row;color:inherit"><input type="checkbox"> ' + esc(i) + "</label>").join("")}</div>`).join(""));
  } catch (e) { fail("packing", e); }
  finally { btn.disabled = false; }
};

/* ---------- Safety (unchanged) ---------- */
$("#go-safety").onclick = async () => {
  const btn = $("#go-safety"); btn.disabled = true;
  try {
    const p = new URLSearchParams(); if ($("#s-trek").value) p.set("trek", $("#s-trek").value); if ($("#s-topic").value) p.set("topic", $("#s-topic").value);
    const r = await api("/api/safety?" + p);
    show("safety", Object.entries(r).filter(([k]) => k !== "disclaimer").map(([k, v]) => `<div class="card"><h3>${esc(k.replace("_", " "))}</h3>${list(v)}</div>`).join("") + `<div class="muted">${esc(r.disclaimer)}</div>`);
  } catch (e) { fail("safety", e); }
  finally { btn.disabled = false; }
};

/* ---------- Weather (unchanged) ---------- */
$("#go-weather").onclick = async () => {
  const btn = $("#go-weather"); btn.disabled = true;
  try {
    const r = await api("/api/weather?trek=" + encodeURIComponent($("#w-trek").value));
    show("weather", r.enabled === false ? `<div class="card">${esc(r.message)}</div>` : r.error ? `<div class="card warn">${esc(r.error)}</div>` :
      `<div class="card"><h3>${esc(r.trek)} (base location)</h3>${r.temp_c}°C (feels ${r.feels_like_c}°C) · ${esc(r.description)} · humidity ${r.humidity}% · wind ${r.wind_mps} m/s</div>`);
  } catch (e) { fail("weather", e); }
  finally { btn.disabled = false; }
};

/* ---------- Init (unchanged endpoints; welcome message added) ---------- */
async function init() {
  document.querySelectorAll("select.months").forEach((s) => (s.innerHTML = '<option value="">Any</option>' + MONTHS.map((m, i) => `<option value="${i + 1}">${m}</option>`).join("")));
  addMsg("bot", "Namaste! I'm your trekking companion. Ask me about trails, planning, packing, safety or weather — in Hindi or English.");
  try {
    const [treks, st] = await Promise.all([api("/api/treks"), api("/api/status")]);
    const opts = treks.map((t) => `<option>${esc(t.name)}</option>`).join("");
    document.querySelectorAll("select.treks").forEach((s) => (s.innerHTML = (s.classList.contains("optional") ? '<option value="">None</option>' : "") + opts));
    $("#c-list").innerHTML = treks.map((t) => `<label><input type="checkbox" value="${esc(t.name)}"> ${esc(t.name)}</label>`).join("");
    $("#status").textContent = (st.gemini_configured ? "Gemini ✓" : "Gemini: no key") + " · " + (st.weather_configured ? "Weather ✓" : "Weather: no key");
  } catch (e) { $("#status").textContent = "Backend not reachable"; }
}
init();