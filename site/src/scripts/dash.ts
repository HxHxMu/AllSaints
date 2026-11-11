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

function render(all: Any) {
  const m = all.metrics;
  if (!m) { $("updated").textContent = "No numbers yet"; $("error").hidden = false; $("error").textContent = "The nightly metrics run hasn't sent anything yet."; return; }
  const when = new Date(m.generated_at);
  $("updated").textContent = `Updated ${when.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`;
  const notes = [...(m.notes || [])];
  if (all.email?.error) notes.push(all.email.error);
  if (Date.now() - when.getTime() > 36 * 3600e3) notes.unshift("These numbers are more than a day old: check the Maintenance workflow.");
  if (notes.length) { $("notes").hidden = false; $("notes").innerHTML = notes.map((n: string) => `<li>${esc(n)}</li>`).join(""); }

  // 1. pipeline
  const P = m.pipeline, today = P.now.slice(0, 10);
  const ST: Record<string, [string, string]> = { published: ["posted", "ok"], approved: ["approved", ""], publishing: ["posting now", "wait"],
    review: ["awaiting your Approve", "wait"], generating: ["being made", ""], redo_requested: ["redo requested", "wait"], failed: ["failed", "bad"], missing: ["not made yet", "bad"] };
  $("upcoming").innerHTML = P.upcoming.slice(0, 8).map((r: Any) => {
    const [word, cls] = ST[r.status] || [r.status, ""];
    const plat = r.status === "published" ? ["instagram", "youtube", "facebook", "threads", "tiktok", "story"].map((k) => `${r[k] ? "✓" : "·"} ${k === "tiktok" ? "tiktok draft" : k}`).join("  ") : "";
    return `<li class="${r.date === today ? "today" : ""}"><span class="d">${dLabel(r.date)}</span><span class="who">${esc(r.saint || "—")}</span><span class="st ${cls}">${word}</span><span class="plat">${plat}</span></li>`;
  }).join("");
  if (P.problems.length) {
    $("problems").hidden = false;
    $("problems").innerHTML = `<p class="label">Needs a look</p>` + P.problems.map((r: Any) => `<p>${short(r.date)} · ${esc(r.saint || "—")}: ${esc(r.status)}${r.errors?.length ? ` — ${esc(r.errors.join("; "))}` : ""}</p>`).join("");
  }
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
    <td class="n">${num(e.yt?.views)}</td><td class="n ${e.yt?.avg_pct === best ? "best" : ""}">${e.yt?.avg_pct != null ? e.yt.avg_pct + "%" : "—"}</td>
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
