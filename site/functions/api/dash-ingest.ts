// POST /api/dash-ingest: the nightly metrics run (engine/metrics.py, Maintenance workflow) sends the
// dashboard's numbers here; they're kept in KV, never in the public repo.
// Pages → Settings: KV binding DASH (namespace "allsaints-dash"), secret DASH_INGEST_KEY (same value as GitHub's).
interface Env {
  DASH: KVNamespace;
  DASH_INGEST_KEY: string;
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.DASH_INGEST_KEY || !env.DASH) return new Response("not configured", { status: 503 });
  const auth = request.headers.get("Authorization") || "";
  const want = new TextEncoder().encode(`Bearer ${env.DASH_INGEST_KEY}`);
  const got = new TextEncoder().encode(auth);
  // constant-time compare
  let diff = want.length ^ got.length;
  for (let i = 0; i < want.length; i++) diff |= want[i] ^ (got[i] ?? 0);
  if (diff) return new Response("forbidden", { status: 403 });

  const body = await request.text();
  if (body.length > 2_000_000) return new Response("too large", { status: 413 });
  try {
    const data = JSON.parse(body);
    if (!data.generated_at) throw new Error("no generated_at");
  } catch (e) {
    return new Response(`bad json: ${e}`, { status: 400 });
  }
  await env.DASH.put("metrics", body);
  return new Response("ok");
};
