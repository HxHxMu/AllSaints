# Website — live at https://allholysaints.com (launched 2026-10-29)

**Built (v1, English):** Astro 5 in `/site`; home, saint pages (tap-to-play YouTube, story, prayer, sources, Ko-fi), litany calendar with search, about/privacy/terms. Shows `published` episodes only (`SITE_ALL=1 npm run build` previews review/approved locally). Art: release `art.jpg` (clean icon, uploaded by the pipeline), else top crop of `cover.jpg` (`site/scripts/fetch-art.mjs`). Hosting: Cloudflare Pages project `allholysaints` (root `site`, `npm run build`, `dist`, NODE_VERSION 22, build watch paths `site/* state/episodes/* brand/*`), www → apex 301 Redirect Rule, Web Analytics on (beacon allowed in `site/public/_headers` CSP).
**Not built yet:** Spanish `/es/`, Beehiiv signup, Bookshop.org books, long-form story in the pipeline, share cards, RSS.

## Original plan (decisions 2026-10-29)

- **Hosting:** Cloudflare Pages; GitHub branch previews, merge to main = production. Code in `/site` of this repo.
- **Domain:** **allholysaints.com** (bought 2026-10-29). DNS on Cloudflare; email: **hello@allholysaints.com** is a forward-only address (Cloudflare Email Routing → Luis's Gmail; no mailbox). No DNSSEC until the domain moves to Cloudflare Registrar (IONOS can't with external nameservers).
- **Languages:** English + Spanish at launch (`/es/`, hreflang).
- **Stack:** Astro static site built from `state/episodes/*.json`; Tailwind v4 with brand.json tokens; Fontsource fonts; astro-embed YouTube (tap-to-load); Pagefind search; Satori share cards; sitemap/RSS/schema.org.
- **Revenue pieces:** Ko-fi "Light a candle"; Bookshop.org affiliate only (FTC disclosure); Beehiiv weekly Sunday digest (signup via a Pages Function + Turnstile).
- **Privacy/security:** no cookies (Cloudflare Web Analytics), strict security headers/CSP, WCAG 2.2 AA, CAN-SPAM postal address in emails.
- **Look:** decided 2026-10-29, see `DESIGN.md` ("The Night Office": dark throughout, icon on top with tap-to-play, red rubric actions, litany calendar).
- **Cost design:** the script call also writes the long-form story (~600–800 words) + `patronages`/`places` tags (one call, sources read once); the fact-check covers both and returns only corrections; Spanish via Haiku right after generation; book lookup, emails, images and share cards are plain code (no AI, no new image generation).
