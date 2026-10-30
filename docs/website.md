# Website — planned, not built (decisions 2026-10-29)

- **Hosting:** Cloudflare Pages; GitHub branch previews, merge to main = production. Code in `/site` of this repo (add `site/CLAUDE.md` when it exists).
- **Domain:** **allholysaints.com** (bought 2026-10-29). DNS on Cloudflare; email: **hello@allholysaints.com** is a forward-only address (Cloudflare Email Routing → Luis's Gmail; no mailbox). No DNSSEC until the domain moves to Cloudflare Registrar (IONOS can't with external nameservers).
- **Languages:** English + Spanish at launch (`/es/`, hreflang).
- **Stack:** Astro static site built from `state/episodes/*.json`; Tailwind v4 with brand.json tokens; Fontsource fonts; astro-embed YouTube (tap-to-load); Pagefind search; Satori share cards; sitemap/RSS/schema.org.
- **Revenue pieces:** Ko-fi "Light a candle"; Bookshop.org affiliate only (FTC disclosure); Beehiiv weekly Sunday digest (signup via a Pages Function + Turnstile).
- **Privacy/security:** no cookies (Cloudflare Web Analytics), strict security headers/CSP, WCAG 2.2 AA, CAN-SPAM postal address in emails.
- **Look:** decided 2026-10-29, see `DESIGN.md` ("The Night Office": dark throughout, icon on top with tap-to-play, red rubric actions, litany calendar).
- **Cost design:** the script call also writes the long-form story (~600–800 words) + `patronages`/`places` tags (one call, sources read once); the fact-check covers both and returns only corrections; Spanish via Haiku right after generation; book lookup, emails, images and share cards are plain code (no AI, no new image generation).
