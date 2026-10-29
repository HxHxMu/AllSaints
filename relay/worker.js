// Telegram relay for the A.S.† Studio bot (Cloudflare Worker).
//
// Telegram delivers each update here by webhook. The relay answers button taps
// immediately (so the button stops spinning), queues the update in a Durable Object,
// and starts the GitHub poll workflow. The poll reads the queue at GET /updates
// instead of calling Telegram's getUpdates (which stops working once a webhook is set).
//
// Secrets (wrangler secret put): TELEGRAM_BOT_TOKEN, WEBHOOK_SECRET, RELAY_SECRET, GH_TOKEN
// Vars (wrangler.toml): OWNER_CHAT_ID, GH_REPO, GH_WORKFLOW
// GitHub secrets for the poll: TELEGRAM_RELAY_URL (this Worker's URL), TELEGRAM_RELAY_SECRET (= RELAY_SECRET).
// Revert to plain polling: POST /setup?off=1, then delete the TELEGRAM_RELAY_URL secret.
// Check GET /webhook-info that `bot` is the All Saints bot before any POST /setup.
import {DurableObject} from 'cloudflare:workers';

const TOASTS = {
	approve: 'Approved ✅ (saving…)',
	unapprove: 'Back in review',
	newsaint: 'Picking a different saint…',
};

export class Inbox extends DurableObject {
	constructor(ctx, env) {
		super(ctx, env);
		ctx.storage.sql.exec('CREATE TABLE IF NOT EXISTS updates (id INTEGER PRIMARY KEY, body TEXT NOT NULL)');
	}
	add(id, body) {
		this.ctx.storage.sql.exec('INSERT OR IGNORE INTO updates (id, body) VALUES (?, ?)', id, body);
	}
	// Drop what the poll has already committed (ids below its saved offset), return the rest in order.
	take(offset) {
		this.ctx.storage.sql.exec('DELETE FROM updates WHERE id < ?', offset);
		return this.ctx.storage.sql.exec('SELECT body FROM updates ORDER BY id').toArray().map((r) => JSON.parse(r.body));
	}
}

const tg = (env, method, body) =>
	fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
		method: 'POST',
		headers: {'content-type': 'application/json'},
		body: JSON.stringify(body),
	});

const dispatchPoll = (env) =>
	fetch(`https://api.github.com/repos/${env.GH_REPO}/actions/workflows/${env.GH_WORKFLOW}/dispatches`, {
		method: 'POST',
		headers: {
			authorization: `Bearer ${env.GH_TOKEN}`,
			accept: 'application/vnd.github+json',
			'x-github-api-version': '2022-11-28',
			'user-agent': 'allsaints-relay',
			'content-type': 'application/json',
		},
		body: JSON.stringify({ref: 'main'}),
	}).then(async (r) => r.ok || console.log('dispatch failed', r.status, await r.text()));

const authorized = (req, env) => req.headers.get('authorization') === `Bearer ${env.RELAY_SECRET}`;
const inbox = (env) => env.INBOX.get(env.INBOX.idFromName('telegram'));

export default {
	async fetch(req, env, ctx) {
		const url = new URL(req.url);

		if (url.pathname === '/telegram' && req.method === 'POST') {
			if (req.headers.get('x-telegram-bot-api-secret-token') !== env.WEBHOOK_SECRET) return new Response('forbidden', {status: 403});
			const u = await req.json();
			const cq = u.callback_query;
			const chat = cq ? cq.message?.chat?.id : u.message?.chat?.id;
			if (cq && String(chat) === env.OWNER_CHAT_ID) {
				const kind = (cq.data || '').split(':')[0];
				await tg(env, 'answerCallbackQuery', {callback_query_id: cq.id, text: TOASTS[kind]});
				u._answered = true; // the poll skips its own (by then too late) answer
			}
			await inbox(env).add(u.update_id, JSON.stringify(u));
			if (String(chat) === env.OWNER_CHAT_ID) ctx.waitUntil(dispatchPoll(env));
			return new Response('ok'); // always 200, or Telegram keeps retrying
		}

		if (!authorized(req, env)) return new Response('forbidden', {status: 403});

		if (url.pathname === '/updates' && req.method === 'GET') {
			const offset = Number(url.searchParams.get('offset') || 0);
			return Response.json(await inbox(env).take(offset));
		}

		// Telegram's view of webhook delivery (pending count, last error).
		if (url.pathname === '/webhook-info' && req.method === 'GET') {
			const [info, me] = await Promise.all([tg(env, 'getWebhookInfo', {}), tg(env, 'getMe', {})].map((p) => p.then((r) => r.json())));
			return Response.json({...info, bot: me.result?.username});
		}

		// One-time switch of the bot to this relay (POST /setup) or back to polling (POST /setup?off=1).
		if (url.pathname === '/setup' && req.method === 'POST') {
			const r = url.searchParams.get('off')
				? await tg(env, 'deleteWebhook', {drop_pending_updates: false})
				: await tg(env, 'setWebhook', {
						url: `${url.origin}/telegram`,
						secret_token: env.WEBHOOK_SECRET,
						allowed_updates: ['message', 'callback_query'],
						drop_pending_updates: false,
				  });
			return Response.json(await r.json());
		}

		return new Response('not found', {status: 404});
	},
};
