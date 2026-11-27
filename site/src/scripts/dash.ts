// The private dashboard (/dash/): fetches /api/dash-data (or ?src= on localhost) and renders every section.
type Any = any;
const $ = (id: string) => document.getElementById(id)!;
const esc = (s: unknown) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const num = (n: unknown) => (n == null || n === "" ? "—" : Number(n).toLocaleString("en-US"));
const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX", "XXXI"];
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const dLabel = (iso: string) => { const [, m, d] = iso.split("-").map(Number); return `${ROMAN[d]} ${MON[m - 1]}`; };
const short = (iso: string) => { const [, m, d] = iso.split("-").map(Number); return `${MON[m - 1]} ${d}`; };
const SPANISH = new Set(["ES", "MX", "AR", "CO", "PE", "VE", "CL", "EC", "GT", "CU", "BO", "DO", "HN", "PY", "SV", "NI", "CR", "PA", "UY", "PR",
  "esp", "mex", "arg", "col", "per", "ven", "chl", "ecu", "gtm", "cub", "bol", "dom", "hnd", "pry", "slv", "nic", "cri", "pan", "ury", "pri"]);

const tile = (v: string, s: string, meter?: number) =>
  `<div class="tile"><div class="v">${v}</div><div class="s">${s}</div>${meter != null ? `<div class="meter"><i style="width:${Math.min(100, Math.max(2, meter * 100))}%"></i></div>` : ""}</div>`;

// hover tooltip for any element with data-tip
const tip = $("tip");
document.addEventListener("pointermove", (e) => {
  const t = (e.target as Element).closest?.("[data-tip]");
  if (!t) return void (tip.hidden = true);
  tip.innerHTML = t.getAttribute("data-tip")!;
  tip.hidden = false;
  const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
  tip.style.left = `${x}px`; tip.style.top = `${e.clientY - tip.offsetHeight - 12}px`;
});

// single-series bars: 2px gaps, rounded data end, a few gridlines
function bars(el: HTMLElement, rows: { label: string; value: number; tip: string }[]) {
  const W = 720, H = 180, L = 36, B = 24, max = Math.max(1, ...rows.map((r) => r.value));
  const step = (W - L) / rows.length, bw = Math.max(2, step - 2);
  const nice = Math.pow(10, Math.floor(Math.log10(max))); const top = Math.ceil(max / nice) * nice;
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(el.previousElementSibling?.textContent)}">`;
  for (const g of [0, top / 2, top]) {
    const y = H - B - ((H - B - 8) * g) / top;
    s += `<line class="grid" x1="${L}" x2="${W}" y1="${y}" y2="${y}"/><text class="axis" x="${L - 6}" y="${y + 4}" text-anchor="end">${num(g)}</text>`;
  }
  rows.forEach((r, i) => {
    const h = ((H - B - 8) * r.value) / top, x = L + i * step + 1, y = H - B - h;
    if (h > 0) s += `<path class="bar" d="M${x},${H - B} V${y + Math.min(4, h)} q0,-${Math.min(4, h)} ${Math.min(4, bw / 2)},-${Math.min(4, h)} H${x + bw - Math.min(4, bw / 2)} q${Math.min(4, bw / 2)},0 ${Math.min(4, bw / 2)},${Math.min(4, h)} V${H - B} Z"/>`;
    s += `<rect class="hit" x="${x - 1}" y="0" width="${step}" height="${H - B}" data-tip="${esc(r.tip)}"/>`;
    if (i % 7 === 0 || i === rows.length - 1) s += `<text class="axis" x="${x + bw / 2}" y="${H - 6}" text-anchor="middle">${esc(r.label)}</text>`;
  });
  el.innerHTML = s + "</svg>";
}

function scatter(el: HTMLElement, pts: { x: number; y: number; tip: string }[]) {
  const W = 720, H = 240, L = 40, B = 28, xs = pts.map((p) => p.x);
  const x0 = Math.max(0, Math.min(...xs) - 2), x1 = Math.max(...xs) + 2;
  const X = (v: number) => L + ((W - L - 8) * (v - x0)) / (x1 - x0), Y = (v: number) => H - B - ((H - B - 8) * v) / 100;
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Average percent viewed by WHO-line word count">`;
  for (const g of [0, 50, 100]) s += `<line class="grid" x1="${L}" x2="${W}" y1="${Y(g)}" y2="${Y(g)}"/><text class="axis" x="${L - 6}" y="${Y(g) + 4}" text-anchor="end">${g}%</text>`;
  for (let v = Math.ceil(x0 / 5) * 5; v <= x1; v += 5) s += `<text class="axis" x="${X(v)}" y="${H - 8}" text-anchor="middle">${v}</text>`;
  for (const p of pts) s += `<circle class="dot" cx="${X(p.x)}" cy="${Y(p.y)}" r="6" data-tip="${esc(p.tip)}"/>`;
  el.innerHTML = s + "</svg>";
}

const rank = (title: string, rows: { k: string; v: string }[]) =>
  `<div><h3>${esc(title)}</h3>${rows.length ? `<ol class="rank">${rows.map((r) => `<li><span title="${esc(r.k)}">${esc(r.k)}</span><span>${r.v}</span></li>`).join("")}</ol>` : `<p class="empty">Nothing yet.</p>`}</div>`;

// --- the schedule --------------------------------------------------------------------------------
const KIND: Record<string, [string, string]> = { saint: ["Saint", "✝"], lives: ["Lives", "▶"], sung: ["Sung prayer", "℣"],
  music: ["Music", "♪"], seasonal: ["Seasonal", "✦"], compilation: ["Compilation", "❖"] };
const PLAT: Record<string, string> = { instagram: "IG", youtube: "YT", facebook: "FB", threads: "Threads", tiktok: "TikTok", story: "IG Story", fb_story: "FB Story" };
const SWORD: Record<string, [string, string]> = { posted: ["posted", "ok"], published: ["posted", "ok"], approved: ["approved", ""], pending: ["scheduled", ""],
  planned: ["planned", "dim"], review: ["awaiting your Approve", "wait"], waiting: ["retrying", "wait"], partial: ["partly posted", "wait"],
  draft: ["draft", "wait"], skipped: ["stands aside", "dim"], failed: ["failed", "bad"], missing: ["not made yet", "bad"] };
const MARK: Record<string, string> = { posted: "✓", draft: "✓", failed: "✗", skipped: "–" };
const hhmm = (at: string) => { const [h, mi] = at.slice(11, 16).split(":").map(Number); return `${((h + 11) % 12) + 1}:${String(mi).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`; };

function row(it: Any, today: string, withDate = true) {
  const [kw, glyph] = KIND[it.kind] || [it.kind, "·"];
  const [word, cls] = SWORD[it.status] || [it.status, ""];
  const title = it.kind === "saint" && it.slug ? `<a href="/saints/${esc(it.slug)}/">${esc(it.title)}</a>` : esc(it.title || "—");
  const plats = (it.platforms || []).map((p: Any) => {
    const label = `${MARK[p.s] || "·"} ${PLAT[p.p] || p.p}${p.p === "tiktok" && p.s === "draft" ? " draft" : ""}`;
    return p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener" class="p ${p.s}">${esc(label)}</a>` : `<span class="p ${p.s}">${esc(label)}</span>`;
  }).join("");
  return `<li class="${it.date === today ? "today" : ""} k-${it.kind}">
    <span class="d">${withDate ? dLabel(it.date) : ""}<span class="t">${hhmm(it.at)}</span></span>
    <span class="who"><span class="kind" title="${esc(kw)}">${glyph} ${esc(kw)}</span>${title}${it.note ? `<span class="note">${esc(it.note)}</span>` : ""}</span>
    <span class="st ${cls}">${word}</span>
    <span class="plat">${plats}</span></li>`;
}

function list(el: HTMLElement, items: Any[], today: string) {
  let last = "";
  el.innerHTML = items.map((it) => { const r = row(it, today, it.date !== last); last = it.date; return r; }).join("")
    || `<li><span></span><span class="empty">Nothing scheduled.</span></li>`;
}

function schedule(S: Any, today: string) {
  const items: Any[] = S.items;
  const future = items.filter((i) => i.date >= today), past = items.filter((i) => i.date < today).reverse();
  const cut = new Date(today + "T12:00:00"); cut.setDate(cut.getDate() + 21);
  const soon = cut.toISOString().slice(0, 10);
  list($("upcoming"), future.filter((i) => i.date <= soon), today);
  const later = future.filter((i) => i.date > soon);
  if (later.length) {
    $("later").hidden = false;
    $("later-sum").textContent = `Later: ${later.length} more, through ${short(later[later.length - 1].date)}`;
    list($("later-list"), later, today);
  }
  list($("history"), past.filter((i) => i.status !== "skipped"), today);
  calendar(items, today, new Set(S.warnings.map((w: Any) => w.date)));
}

function calendar(items: Any[], today: string, warned: Set<string>) {
  const byDay: Record<string, Any[]> = {};
  for (const it of items) (byDay[it.date] ||= []).push(it);
  let [y, mo] = today.split("-").map(Number);
  const first = items[0]?.date.slice(0, 7), lastM = items[items.length - 1]?.date.slice(0, 7);
  $("cal").hidden = false;
  $("cal-key").textContent = Object.values(KIND).filter(([k]) => k !== "Saint").map(([k, g]) => `${g} ${k}`).join("   ");
  const show = (iso: string) => {
    const day = byDay[iso] || [];
    const box = $("cal-day"); box.hidden = false;
    box.innerHTML = `<p class="label">${dLabel(iso)}</p>` + (day.length ? `<ol class="sched">${day.map((i) => row(i, today, false)).join("")}</ol>` : `<p class="empty">Nothing on this day.</p>`);
  };
  const draw = () => {
    const key = `${y}-${String(mo).padStart(2, "0")}`;
    $("cal-month").textContent = new Date(y, mo - 1, 1).toLocaleString("en-US", { month: "long", year: "numeric" });
    ($("cal-prev") as HTMLButtonElement).disabled = !!first && key <= first;
    ($("cal-next") as HTMLButtonElement).disabled = !!lastM && key >= lastM;
    const start = (new Date(y, mo - 1, 1).getDay() + 6) % 7, n = new Date(y, mo, 0).getDate();
    let s = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => `<span class="dow">${d}</span>`).join("");
    s += `<span class="pad"></span>`.repeat(start);
    for (let d = 1; d <= n; d++) {
      const iso = `${key}-${String(d).padStart(2, "0")}`, day = byDay[iso] || [];
      const saint = day.find((i) => i.kind === "saint");
      const marks = day.filter((i) => i.kind !== "saint" && i.status !== "skipped").map((i) => KIND[i.kind]?.[1] || "·");
      const tipTxt = day.map((i) => `${hhmm(i.at)} · ${esc(i.title || "No saint yet")}`).join("<br>") || "Nothing scheduled";
      const cls = [iso === today ? "today" : "", iso < today ? "past" : "", warned.has(iso) ? "warn" : "", saint?.status === "missing" ? "missing" : ""].join(" ");
      s += `<button type="button" class="cell ${cls}" data-day="${iso}" data-tip="${esc(tipTxt)}" aria-label="${esc(dLabel(iso))}: ${day.length} posts">
        <span class="n">${d}</span>${saint?.cover ? `<img src="${esc(saint.cover)}" alt="" loading="lazy">` : ""}
        <span class="m">${[...new Set(marks)].join(" ")}</span></button>`;
    }
    s += `<span class="pad"></span>`.repeat((7 - ((start + n) % 7)) % 7);
    $("cal-grid").innerHTML = s;
  };
  $("cal-prev").onclick = () => { mo--; if (mo < 1) { mo = 12; y--; } draw(); };
  $("cal-next").onclick = () => { mo++; if (mo > 12) { mo = 1; y++; } draw(); };
  $("cal-grid").onclick = (e) => { const c = (e.target as Element).closest<HTMLElement>(".cell"); if (c) show(c.dataset.day!); };
  draw();
}

function render(all: Any) {
  const m = all.metrics;
  if (!m) { $("updated").textContent = "No numbers yet"; $("error").hidden = false; $("error").textContent = "The nightly metrics run hasn't sent anything yet."; return; }
  const when = new Date(m.generated_at);
  $("updated").textContent = `Updated ${when.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`;
  const notes = [...(m.notes || [])];
  if (all.email?.error) notes.push(all.email.error);
  if (Date.now() - when.getTime() > 36 * 3600e3) notes.unshift("These numbers are more than a day old: check the Maintenance workflow.");
  if (notes.length) { $("notes").hidden = false; $("notes").innerHTML = notes.map((n: string) => `<li>${esc(n)}</li>`).join(""); }

  // 1. schedule (dash_schedule.py) + the old problem list
  const P = m.pipeline, today = P.now.slice(0, 10);
  const probs: string[] = P.problems.map((r: Any) => `${short(r.date)} · ${esc(r.saint || "—")}: ${esc(r.status)}${r.errors?.length ? ` — ${esc(r.errors.join("; "))}` : ""}`);
  const SCH = m.schedule;
  if (SCH) probs.push(...SCH.warnings.map((w: Any) => `${short(w.date)} · ${esc(w.text)}`));
  if (probs.length) {
    $("problems").hidden = false;
    $("problems").innerHTML = `<p class="label">Needs a look</p>` + [...new Set(probs)].map((p) => `<p>${p}</p>`).join("");
  }
  if (SCH) schedule(SCH, today);
  else $("upcoming").innerHTML = `<li><span></span><span class="empty">The schedule arrives with tonight's update.</span></li>`;
  const C = P.cost, [lo, hi] = C.budget;
  $("cost").innerHTML = tile(`$${C.per_30_days.toFixed(2)}`, `a month at today's rate ($${C.per_episode.toFixed(2)} a saint). Budget $${lo}–${hi}.`, C.per_30_days / hi)
    + tile(`$${C.month_to_date.toFixed(2)}`, `for the ${C.episodes} saints of ${MON[Number(C.month.slice(5)) - 1]} made so far (Claude + Gemini)`);

  // 2. audience
  const yt = m.youtube || {}, ig = m.instagram || {}, eps = [...m.episodes].reverse();
  const sum = (f: (e: Any) => number | undefined) => eps.reduce((a: number, e: Any) => a + (f(e) || 0), 0);
  const pcts = eps.map((e: Any) => e.yt?.avg_pct).filter((v: Any) => v != null);
  $("audience").innerHTML = [
    tile(num(yt.subscribers), "YouTube subscribers"),
    tile(num(sum((e) => e.yt?.views)), `views on ${eps.length} Shorts`),
    pcts.length ? tile(`${Math.round(pcts.reduce((a: number, b: number) => a + b, 0) / pcts.length)}%`, "average viewed (YouTube)") : "",
    tile(num(ig.followers), "Instagram followers"),
    tile(num(m.facebook?.followers), "Facebook Page followers"),
    tile(num(m.tiktok?.followers), "TikTok followers"),
    tile(num(m.threads?.followers), "Threads followers"),
    eps.some((e: Any) => e.ig?.views != null) ? tile(num(sum((e) => e.ig?.views)), "Instagram Reel views") : "",
    eps.some((e: Any) => e.tt?.views != null) ? tile(num(sum((e) => e.tt?.views)), "TikTok views") : "",
    eps.some((e: Any) => e.th?.views != null) ? tile(num(sum((e) => e.th?.views)), "Threads views") : "",
    tile(all.email && !all.email.error ? num(all.email.subscribers) : "—", "email subscribers"),
  ].join("");
  if (yt.daily?.length) {
    $("yt-daily-fig").hidden = false;
    bars($("yt-daily"), yt.daily.map((d: Any) => ({ label: short(d.date), value: d.views, tip: `${short(d.date)}: ${num(d.views)} views, ${d.subs >= 0 ? "+" : ""}${d.subs} subscribers` })));
  }
  const pts = eps.filter((e: Any) => e.yt?.avg_pct != null).map((e: Any) => ({ x: e.who_words, y: e.yt.avg_pct, tip: `${esc(e.saint)}<br>${e.who_words} words · ${e.yt.avg_pct}% viewed` }));
  if (pts.length >= 3) { $("scatter-fig").hidden = false; scatter($("scatter"), pts); }
  const best = pcts.length ? Math.max(...pcts) : null;
  $("episodes").querySelector("tbody")!.innerHTML = eps.map((e: Any) => `<tr>
    <td class="numeral">${dLabel(e.date)}</td>
    <td>${e.slug ? `<a href="/saints/${esc(e.slug)}/">${esc(e.saint)}</a>` : esc(e.saint)}</td>
    <td class="n">${num(e.yt?.views)}</td><td class="n ${e.yt?.avg_pct === best ? "best" : ""}">${e.yt?.avg_pct != null ? e.yt.avg_pct + "%" : "—"}</td><td class="n">${e.yt?.stayed_pct != null ? e.yt.stayed_pct + "%" : "—"}</td>
    <td class="n">${num(e.yt?.shares)}</td><td class="n">${num(e.yt?.subs)}</td>
    <td class="n">${num(e.ig?.views)}</td><td class="n">${num(e.fb?.plays)}</td><td class="n">${num(e.tt?.views)}</td><td class="n">${num(e.th?.views)}</td><td class="n">${num(e.ig?.shares)}</td><td class="n">${num(e.ig?.saved)}</td>
    <td class="n">${e.duration ? Math.round(e.duration) + " s" : "—"}</td><td class="n">${e.who_words}</td></tr>`).join("");
  if (yt.countries?.length) {
    const tot = yt.countries.reduce((a: number, c: Any) => a + c.views, 0);
    const es = yt.countries.filter((c: Any) => SPANISH.has(c.country)).reduce((a: number, c: Any) => a + c.views, 0);
    $("countries").innerHTML = rank(`YouTube views by country · ${Math.round((100 * es) / Math.max(1, tot))}% Spanish-speaking`,
      yt.countries.map((c: Any) => ({ k: c.country, v: num(c.views) })));
  }

  // 3. search
  const S = m.search;
  if (!S) { $("search-tiles").innerHTML = `<p class="empty">Search Console isn't connected yet.</p>`; }
  else {
    const clicks = S.daily.reduce((a: number, d: Any) => a + d.clicks, 0), imp = S.daily.reduce((a: number, d: Any) => a + d.impressions, 0);
    $("search-tiles").innerHTML = tile(num(clicks), "Google clicks, 28 days") + tile(num(imp), "times shown in Google results")
      + tile(imp ? `${((100 * clicks) / imp).toFixed(1)}%` : "—", "click-through rate");
    if (S.daily.length) {
      $("gsc-fig").hidden = false; $("gsc-imp-fig").hidden = false;
      bars($("gsc-clicks"), S.daily.map((d: Any) => ({ label: short(d.date), value: d.clicks, tip: `${short(d.date)}: ${num(d.clicks)} clicks` })));
      bars($("gsc-imp"), S.daily.map((d: Any) => ({ label: short(d.date), value: d.impressions, tip: `${short(d.date)}: ${num(d.impressions)} impressions` })));
    }
    const path = (u: string) => { try { return decodeURI(new URL(u).pathname); } catch { return u; } };
    $("search-lists").innerHTML = rank("What people searched · clicks · shown", S.query.map((q: Any) => ({ k: q.key, v: `${num(q.clicks)} · ${num(q.impressions)}` })))
      + rank("Pages found · clicks · shown", S.page.map((q: Any) => ({ k: path(q.key), v: `${num(q.clicks)} · ${num(q.impressions)}` })))
      + rank("Countries · clicks · shown", S.country.map((q: Any) => ({ k: q.key.toUpperCase(), v: `${num(q.clicks)} · ${num(q.impressions)}` })));
  }

  // 4. support
  const K: Any[] = all.kofi || [], month = today.slice(0, 7);
  const by = (list: Any[]) => Object.entries(list.reduce((a: Any, c: Any) => ((a[c.currency] = (a[c.currency] || 0) + c.amount), a), {}))
    .map(([cur, v]) => `${Number(v).toFixed(2)} ${cur}`).join(" + ") || "0";
  const thisMonth = K.filter((c) => c.at.slice(0, 7) === month);
  $("support").innerHTML = tile(num(thisMonth.length), `candles this month (${by(thisMonth)})`)
    + tile(num(K.length), `all time (${by(K)})`) + tile(num(K.filter((c) => c.monthly).length), "monthly supporter payments")
    + tile(`$${C.per_30_days.toFixed(0)}`, "what a month costs to run, for comparison");
  $("candles").innerHTML = K.length ? K.slice(-10).reverse().map((c) => `<li><span class="d">${dLabel(c.at.slice(0, 10))}</span><span class="who">${c.amount.toFixed(2)} ${esc(c.currency)}</span><span class="st">${esc(c.type)}${c.monthly ? " · monthly" : ""}</span></li>`).join("")
    : `<li><span></span><span class="empty">No candles recorded yet. They appear here once the Ko-fi webhook is set.</span></li>`;
}

// local check only: /dash/?src=/some.json on localhost
const q = new URLSearchParams(location.search).get("src");
const url = q && location.hostname === "localhost" && q.startsWith("/") ? q : "/api/dash-data";
if (url !== "/api/dash-data") $("sample").hidden = false;
fetch(url, { credentials: "same-origin" }).then(async (r) => {
  if (!r.ok) throw new Error(r.status === 403 ? "Not signed in (Cloudflare Access)." : `Error ${r.status}`);
  const js = await r.json();
  render(js.metrics !== undefined ? js : { metrics: js, kofi: [], email: null });
}).catch((e) => { $("updated").textContent = "Couldn't load"; $("error").hidden = false; $("error").textContent = String(e.message || e); });
