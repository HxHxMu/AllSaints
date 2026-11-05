// GET /api/dash-data: everything the private dashboard (/dash/) shows. Behind Cloudflare Access
// (Zero Trust → Access → Applications: allholysaints.com/dash and /api/dash-data, Luis's email only), and
// it also checks the Access token itself, so it stays closed if the Access app is ever removed.
// Pages → Settings: KV binding DASH; variables ACCESS_TEAM_DOMAIN (https://<team>.cloudflareaccess.com) and
// ACCESS_AUD (the application's "Application Audience (AUD) Tag"). Beehiiv uses the subscribe form's secrets.
interface Env {
  DASH: KVNamespace;
  ACCESS_TEAM_DOMAIN: string;
  ACCESS_AUD: string;
  BEEHIIV_API_KEY?: string;
  BEEHIIV_PUBLICATION_ID?: string;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "private, no-store" } });

const b64url = (s: string) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

async function accessOk(request: Request, env: Env): Promise<boolean> {
  const token = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!token || !env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD) return false;
  const [h, p, s] = token.split(".");
  if (!h || !p || !s) return false;
  const team = env.ACCESS_TEAM_DOMAIN.replace(/\/$/, "");
  try {
    const header = JSON.parse(new TextDecoder().decode(b64url(h)));
    const payload = JSON.parse(new TextDecoder().decode(b64url(p)));
    const aud = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
    if (payload.iss !== team || !aud.includes(env.ACCESS_AUD) || payload.exp * 1000 < Date.now()) return false;
    const { keys } = await fetch(`${team}/cdn-cgi/access/certs`, { cf: { cacheTtl: 3600 } }).then((r) => r.json<{ keys: JsonWebKey[] }>());
    const jwk = keys.find((k) => (k as { kid?: string }).kid === header.kid);
    if (!jwk) return false;
    const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    return crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64url(s), new TextEncoder().encode(`${h}.${p}`));
  } catch (e) {
    console.log("access", String(e));
    return false;
  }
}

async function beehiiv(env: Env) {
  const pub = String(env.BEEHIIV_PUBLICATION_ID || "").match(/pub_[0-9a-f-]+/i)?.[0];
  if (!env.BEEHIIV_API_KEY || !pub) return null;
  const r = await fetch(`https://api.beehiiv.com/v2/publications/${pub}?expand[]=stats`, {
    headers: { Authorization: `Bearer ${env.BEEHIIV_API_KEY}` },
  });
  if (!r.ok) return { error: `Beehiiv ${r.status}` };
  const s = (await r.json<{ data: { stats?: Record<string, number> } }>()).data.stats || {};
  return { subscribers: s.active_subscriptions ?? null, open_rate: s.average_open_rate ?? null };
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  if (!(await accessOk(request, env))) return json({ error: "forbidden" }, 403);
  if (!env.DASH) return json({ error: "KV binding DASH missing" }, 503);
  const [metrics, kofi, email] = await Promise.all([
    env.DASH.get("metrics", "json"), env.DASH.get("kofi", "json"), beehiiv(env).catch((e) => ({ error: String(e) })),
  ]);
  return json({ metrics, kofi: kofi || [], email, user: request.headers.get("Cf-Access-Authenticated-User-Email") });
};
