// POST /api/subscribe: the email band's form → Beehiiv (double opt-in is on in Beehiiv, so
// nobody is added until they confirm by email). Works without JavaScript: answers with redirects.
// Secrets live in Cloudflare Pages → Settings → Variables and Secrets, never in the repo.
interface Env {
  BEEHIIV_API_KEY: string;
  BEEHIIV_PUBLICATION_ID: string;
  TURNSTILE_SECRET?: string;
}

const back = (request: Request, path: string) => Response.redirect(new URL(path, request.url).toString(), 303);

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const form = await request.formData();
  const lang = form.get("lang") === "es" ? "es" : "en";
  const from = String(form.get("from") || (lang === "es" ? "/es/" : "/"));
  const page = from.startsWith("/") && !from.startsWith("//") ? from : "/";  // never redirect off-site
  const fail = () => back(request, `${page}?signup=error#signup`);
  if (form.get("website")) return back(request, "/check-email/");  // honeypot: bots fill every field
  const email = String(form.get("email") || "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) {
    console.log("bad email");
    return fail();
  }

  if (env.TURNSTILE_SECRET) {
    const check = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      body: new URLSearchParams({
        secret: env.TURNSTILE_SECRET,
        response: String(form.get("cf-turnstile-response") || ""),
        remoteip: request.headers.get("CF-Connecting-IP") || "",
      }),
    }).then((r) => r.json<{ success: boolean; "error-codes"?: string[] }>())
      .catch((e) => ({ success: false, "error-codes": [`fetch: ${e}`] }));
    if (!check.success) {
      console.log("turnstile", JSON.stringify(check["error-codes"] || []));
      return fail();
    }
  }

  if (!env.BEEHIIV_API_KEY || !env.BEEHIIV_PUBLICATION_ID) console.log("beehiiv env missing");
  const r = await fetch(`https://api.beehiiv.com/v2/publications/${env.BEEHIIV_PUBLICATION_ID}/subscriptions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.BEEHIIV_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      email, reactivate_existing: false, send_welcome_email: true,
      utm_source: "allholysaints.com", utm_medium: "website", utm_campaign: lang,
      referring_site: new URL(page, request.url).toString(),
    }),
  });
  if (!r.ok) {
    console.log("beehiiv", r.status, (await r.text()).slice(0, 300));
    return fail();
  }
  return back(request, lang === "es" ? "/check-email/#es" : "/check-email/");
};
