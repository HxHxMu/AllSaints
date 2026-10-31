import type { APIContext } from "astro";
import { feed } from "../../lib/feed";

export const GET = (ctx: APIContext) => feed("es", ctx.site!);
