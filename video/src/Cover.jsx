import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {C, src} from './components';
import {loadFonts, DISPLAY, TEXT} from './fonts';

loadFonts();

// 1080x1920 cover; key content kept inside the 3:4 grid crop (y 240..1680).
export const Cover = ({saint = {}, cover = {}}) => {
	const name = saint.display_name || saint.name || '';
	const size = name.length > 26 ? 70 : name.length > 18 ? 84 : 100;
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
			<AbsoluteFill style={{top: 1260, alignItems: 'center'}}>
				<div style={{width: 360, height: 2, background: saint.martyr ? C.martyr : C.gilt, marginBottom: 30}} />
				<div style={{fontFamily: DISPLAY, fontWeight: 600, fontSize: size, letterSpacing: '0.1em', color: C.vellum, textAlign: 'center', textTransform: 'uppercase', lineHeight: 1.1, padding: '0 80px'}}>{name}</div>
				{saint.feast && <div style={{fontFamily: TEXT, fontStyle: 'italic', fontSize: 42, color: C.giltLight, marginTop: 22}}>{saint.feast}</div>}
			</AbsoluteFill>
		</AbsoluteFill>
	);
};
