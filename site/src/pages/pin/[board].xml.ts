import type { APIContext } from "astro";
import { boardFeed, boards } from "../../lib/feed";

export const getStaticPaths = () => boards.map((b) => ({ params: { board: b.slug } }));
export const GET = (ctx: APIContext) => boardFeed(ctx.params.board!, ctx.site!);
