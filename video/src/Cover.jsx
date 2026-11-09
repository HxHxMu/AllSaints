import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {C, src} from './components';
import {loadFonts, DISPLAY, TEXT} from './fonts';

loadFonts();

const EM = {A: 0.815, B: 0.745, C: 0.873, D: 0.921, E: 0.713, F: 0.677, G: 0.924, H: 0.945, I: 0.47, J: 0.464, K: 0.824, L: 0.698, M: 1.046,
	N: 0.957, O: 0.965, P: 0.73, Q: 0.967, R: 0.824, S: 0.644, T: 0.75, U: 0.909, V: 0.832, W: 1.075, X: 0.807, Y: 0.789, Z: 0.758,
	'.': 0.308, "'": 0.29, '’': 0.327, '-': 0.48, ',': 0.315, ' ': 0.35, '\u00a0': 0.35};

// 1080x1920 cover; key content kept inside the 3:4 grid crop (y 240..1680).
export const Cover = ({saint = {}, cover = {}}) => {
	const name = saint.display_name || saint.name || '';
	// largest size that sets the name in two lines (three for long names, never under 100 px) across the 960 px measure
	// ("St." stays with the name); EM: Cinzel SemiBold cap widths plus the 0.1 em tracking
	const title = name.replace(/^(Sts?\.)\s+/i, '$1\u00a0');
	const em = (word) => [...word.toUpperCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')].reduce((t, c) => t + (EM[c] ?? 0.8), 0);
	const lines = (s) => {
		let n = 1, w = 0;
		for (const word of title.split(' ')) {
			const ww = em(word) * s;
			if (ww > 960) return 9;
			if (w && w + EM[' '] * s + ww > 960) { n++; w = ww; } else w = w ? w + EM[' '] * s + ww : ww;
		}
		return n;
	};
	const sizes = [124, 116, 108, 100, 92, 84, 76];
	const size = sizes.find((s) => s >= 100 && lines(s) <= 2) || sizes.find((s) => lines(s) <= 3) || 70;
	const {w = 1000, h = 1400, focus = {x: 0.5, y: 0.4}} = cover;
	const base = Math.max(1080 / w, 1920 / h) * 1.04;
	const W = w * base, H = h * base;
	const tx = Math.min(0, Math.max(1080 - W, 540 - focus.x * W));
	const ty = Math.min(0, Math.max(1920 - H, 900 - focus.y * H));
	return (
		<AbsoluteFill style={{backgroundColor: C.soot}}>
			{cover.image && <Img src={src(cover.image)} style={{position: 'absolute', left: tx, top: ty, width: W, height: H, filter: 'saturate(0.9) sepia(0.1)'}} />}
			<AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(13,11,9,0.6) 0%, rgba(13,11,9,0) 28%, rgba(13,11,9,0) 52%, rgba(13,11,9,0.85) 76%, rgba(13,11,9,0.95) 100%)'}} />
			<AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.5) 100%)'}} />
			<Img src={staticFile('brand/initials.svg')} style={{position: 'absolute', left: 0, right: 0, margin: '0 auto', top: 290, height: 52, opacity: 0.9}} />
			<AbsoluteFill style={{height: 1660, alignItems: 'center', justifyContent: 'flex-end'}}>
				<div style={{width: 360, height: 2, background: saint.martyr ? C.martyr : C.gilt, marginBottom: 30}} />
				<div style={{fontFamily: DISPLAY, fontWeight: 600, fontSize: size, letterSpacing: '0.1em', color: C.vellum, textAlign: 'center', textTransform: 'uppercase', lineHeight: 1.1, padding: '0 60px'}}>{title}</div>
				{saint.feast && <div style={{fontFamily: TEXT, fontStyle: 'italic', fontSize: 60, color: C.giltLight, marginTop: 24}}>{saint.feast}</div>}
			</AbsoluteFill>
		</AbsoluteFill>
	);
};
