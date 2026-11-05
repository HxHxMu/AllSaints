// POST /api/kofi: Ko-fi's webhook (ko-fi.com → Settings → API → Webhook URL https://allholysaints.com/api/kofi).
// Keeps only date, amount, currency and type for the dashboard: no names, emails or messages.
// Pages → Settings: KV binding DASH, secret KOFI_TOKEN (Ko-fi's "Verification Token").
interface Env {
  DASH: KVNamespace;
  KOFI_TOKEN: string;
}

interface Candle { at: string; amount: number; currency: string; type: string; monthly: boolean; id: string }

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.KOFI_TOKEN || !env.DASH) return new Response("not configured", { status: 503 });
  const form = await request.formData();
  let d: Record<string, unknown>;
  try {
    d = JSON.parse(String(form.get("data") || ""));
  } catch {
    return new Response("bad data", { status: 400 });
  }
  if (d.verification_token !== env.KOFI_TOKEN) return new Response("forbidden", { status: 403 });

  const list: Candle[] = (await env.DASH.get("kofi", "json")) || [];
  const id = String(d.kofi_transaction_id || d.message_id || "");
  if (!list.some((c) => c.id === id)) {
    list.push({
      at: String(d.timestamp || new Date().toISOString()), amount: Number(d.amount) || 0,
      currency: String(d.currency || "USD"), type: String(d.type || "Donation"),
      monthly: Boolean(d.is_subscription_payment), id,
    });
    await env.DASH.put("kofi", JSON.stringify(list.slice(-2000)));
  }
  return new Response("ok");  // Ko-fi retries anything but 200
};
