import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing, random} from 'remotion';
import {geoOrthographic, geoPath, geoGraticule10} from 'd3-geo';
import {feature} from 'topojson-client';
import land110 from 'world-atlas/land-110m.json';
import brand from './brand.json';
import {DISPLAY, TEXT, ACCENT} from './fonts';

export const C = brand.colors;
const LAND = feature(land110, land110.objects.land);
const GRAT = geoGraticule10();
const ease = Easing.bezier(0.25, 0.1, 0.25, 1);

export const src = (p) => (p.startsWith('http') || p.startsWith('data:') ? p : staticFile(p));

/* ---------- Fade helpers ---------- */
export const useFade = (durationInFrames, fadeIn = 18, fadeOut = 0) => {
	const f = useCurrentFrame();
	const a = interpolate(f, [0, fadeIn], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const b = fadeOut ? interpolate(f, [durationInFrames - fadeOut, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
	return Math.min(a, b);
};

const rise = (f, delay = 0, dur = 15) => {
	const t = interpolate(f, [delay, delay + dur], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
	return {opacity: t, transform: `translateY(${(1 - t) * 14}px)`};
};

/* ---------- Art scene with slow Ken Burns ---------- */
export const ArtScene = ({scene, durationInFrames}) => {
	const f = useCurrentFrame();
	const {width: FW, height: FH} = useVideoConfig();
	const {w = 1000, h = 1400, focus = {x: 0.5, y: 0.4}, move = 'in'} = scene;
	const t = interpolate(f, [0, durationInFrames], [0, 1], {extrapolateRight: 'clamp'});
	const base = Math.max(FW / w, FH / h);
	let z0 = 1.04, z1 = 1.12, c0 = {...focus}, c1 = {...focus};
	if (move === 'out') [z0, z1] = [1.13, 1.04];
	if (move === 'left' || move === 'right') {
		z0 = z1 = 1.08;
		const d = move === 'right' ? 0.12 : -0.12;
		c0 = {x: focus.x - d, y: focus.y};
		c1 = {x: focus.x + d, y: focus.y};
	}
	if (move === 'up' || move === 'down') {
		z0 = z1 = 1.08;
		const d = move === 'up' ? -0.1 : 0.1;
		c0 = {x: focus.x, y: focus.y - d};
		c1 = {x: focus.x, y: focus.y + d};
	}
	const z = z0 + (z1 - z0) * t;
	const W = w * base * z, H = h * base * z;
	const cx = (c0.x + (c1.x - c0.x) * t) * W;
	const cy = (c0.y + (c1.y - c0.y) * t) * H;
	const tx = Math.min(0, Math.max(FW - W, FW / 2 - cx));
	const ty = Math.min(0, Math.max(FH - H, FH / 2 - cy));
	const opacity = useFade(durationInFrames, 18, 0);
	return (
		<AbsoluteFill style={{opacity, backgroundColor: C.soot, overflow: 'hidden'}}>
			<Img src={src(scene.image)} style={{position: 'absolute', left: tx, top: ty, width: W, height: H, filter: 'saturate(0.9) contrast(1.04) sepia(0.08)'}} />
		</AbsoluteFill>
	);
};

/* ---------- Globe map scene ---------- */
export const MapScene = ({scene, durationInFrames}) => {
	const f = useCurrentFrame();
	const {width: FW} = useVideoConfig();
	const {lat = 41.9, lon = 12.5, place = ''} = scene;
	const t = interpolate(f, [0, Math.min(45, durationInFrames)], [0, 1], {extrapolateRight: 'clamp', easing: ease});
	const drift = interpolate(f, [0, durationInFrames], [0, 4]);
	const R = 410, cy = 860;
	const proj = geoOrthographic()
		.scale(R * (0.92 + 0.08 * t))
		.translate([FW / 2, cy])
		.rotate([-(lon - 35 * (1 - t)) - drift, -(lat - 8 * (1 - t))])
		.clipAngle(90);
	const path = geoPath(proj);
	const pt = proj([lon, lat]);
	const pulse = 1 + 0.25 * Math.sin(f / 8);
	const opacity = useFade(durationInFrames, 18, 0);
	return (
		<AbsoluteFill style={{opacity, backgroundColor: C.soot}}>
			<AbsoluteFill style={{background: `radial-gradient(circle at 50% ${cy / 19.2}%, ${C.umber} 0%, ${C.soot} 60%)`}} />
			<svg width={FW} height={1920} style={{position: 'absolute'}}>
				<defs>
					<radialGradient id="sea" cx="40%" cy="35%" r="70%">
						<stop offset="0%" stopColor="#1a2432" />
						<stop offset="100%" stopColor="#0b0f15" />
					</radialGradient>
				</defs>
				<path d={path({type: 'Sphere'})} fill="url(#sea)" stroke={C.gilt} strokeWidth={2} />
				<path d={path(GRAT)} fill="none" stroke={C.gilt} strokeOpacity={0.12} strokeWidth={1} />
				<path d={path(LAND)} fill={C.umber} stroke={C.gilt} strokeOpacity={0.55} strokeWidth={1.2} />
				{pt && (
					<g opacity={interpolate(f, [30, 45], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}>
						<circle cx={pt[0]} cy={pt[1]} r={22 * pulse} fill={C.gilt} opacity={0.18} />
						<circle cx={pt[0]} cy={pt[1]} r={8} fill={C.giltLight} />
					</g>
				)}
			</svg>
			{pt && place && (
				<div style={{position: 'absolute', top: pt[1] + 34, left: pt[0] - 320, width: 640, textAlign: 'center', fontFamily: DISPLAY, fontWeight: 600, fontSize: 34, letterSpacing: '0.16em', color: C.giltLight, textTransform: 'uppercase', textShadow: '0 2px 12px rgba(0,0,0,0.95)', ...rise(f, 36)}}>
					{place}
				</div>
			)}
		</AbsoluteFill>
	);
};

/* ---------- Name / title card overlay ---------- */
export const TitleCard = ({saint, durationInFrames}) => {
	const f = useCurrentFrame();
	const out = interpolate(f, [durationInFrames - 12, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const rule = interpolate(f, [0, 20], [0, 1], {extrapolateRight: 'clamp', easing: ease});
	const name = saint.display_name || saint.name;
	const len = name.length;
	const size = len > 26 ? 64 : len > 18 ? 76 : 88;
	return (
		<AbsoluteFill style={{opacity: out, alignItems: 'center', paddingTop: 210}}>
			<div style={{width: 520 * rule, height: 2, background: saint.martyr ? C.martyr : C.gilt, marginBottom: 34}} />
			<div style={{fontFamily: DISPLAY, fontWeight: 600, fontSize: size, letterSpacing: '0.1em', color: C.vellum, textAlign: 'center', textTransform: 'uppercase', lineHeight: 1.12, padding: '0 70px', textShadow: '0 4px 30px rgba(0,0,0,0.8)', ...rise(f, 6)}}>
				{name}
			</div>
			<div style={{fontFamily: TEXT, fontStyle: 'italic', fontSize: 44, color: C.giltLight, marginTop: 22, textShadow: '0 2px 20px rgba(0,0,0,0.9)', ...rise(f, 14)}}>
				{[saint.dates, saint.region].filter(Boolean).join('  ·  ')}
			</div>
			<div style={{width: 520 * rule, height: 2, background: C.gilt, marginTop: 34, opacity: 0.5}} />
		</AbsoluteFill>
	);
};

/* ---------- Devotional close + outro ---------- */
export const CloseScene = ({scene, saint, durationInFrames, outroFrames}) => {
	const f = useCurrentFrame();
	const opacity = useFade(durationInFrames, 18, 0);
	const prayerEnd = durationInFrames - outroFrames;
	const prayerOut = interpolate(f, [prayerEnd - 10, prayerEnd + 6], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const o = f - prayerEnd;
	const glow = 0.5 + 0.08 * Math.sin(f / 5) + 0.05 * Math.sin(f / 2.3);
	return (
		<AbsoluteFill style={{opacity, backgroundColor: C.soot}}>
			{scene.image && (
				<div style={{position: 'absolute', left: 0, top: 0, width: 270, height: 480, transform: 'scale(4.4)', transformOrigin: '0 0', overflow: 'hidden'}}>
					<Img src={src(scene.image)} style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(4px) brightness(0.28) sepia(0.3)'}} />
				</div>
			)}
			<AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 58%, rgba(201,164,76,${0.16 * glow}) 0%, rgba(13,11,9,0) 55%)`}} />
			<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: '0 90px', opacity: prayerOut}}>
				<div style={{fontFamily: ACCENT, fontStyle: 'italic', fontWeight: 500, fontSize: 84, lineHeight: 1.2, color: C.vellum, textAlign: 'center', ...rise(f, 8, 24)}}>
					{scene.text || `${saint.name}, pray for us.`}
				</div>
				<div style={{width: 120, height: 2, background: C.gilt, marginTop: 50, ...rise(f, 20, 20)}} />
			</AbsoluteFill>
			{o > 0 && (
				<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
					<Img src={staticFile('brand/monogram-transparent.svg')} style={{width: 520, height: 520, ...rise(o, 0, 20)}} />
					<div style={{fontFamily: DISPLAY, fontSize: 34, letterSpacing: '0.3em', color: C.gilt, marginTop: 10, ...rise(o, 8, 18)}}>ALL SAINTS</div>
					{saint.feast && (
						<div style={{fontFamily: TEXT, fontStyle: 'italic', fontSize: 38, color: C.ash, marginTop: 26, ...rise(o, 14, 18)}}>Feast day · {saint.feast}</div>
					)}
				</AbsoluteFill>
			)}
		</AbsoluteFill>
	);
};

/* ---------- Word-timed captions ---------- */
const groupWords = (words) => {
	const groups = [];
	let cur = [];
	for (const w of words) {
		cur.push(w);
		const chars = cur.map((x) => x.text).join(' ').length;
		if (/[.,;:!?—]$/.test(w.text) || cur.length >= 4 || chars > 20) {
			groups.push(cur);
			cur = [];
		}
	}
	if (cur.length) groups.push(cur);
	return groups.map((g, i) => ({words: g, start: g[0].start, end: groups[i + 1] ? groups[i + 1][0].start : g[g.length - 1].end + 0.4}));
};

export const Captions = ({words, hideAfter}) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const t = f / fps;
	const groups = React.useMemo(() => groupWords(words), [words]);
	if (hideAfter && t >= hideAfter) return null;
	const g = groups.find((x) => t >= x.start && t < x.end);
	if (!g) return null;
	const local = (t - g.start) * fps;
	const op = interpolate(local, [0, 4], [0, 1], {extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{top: 1150, height: 300, alignItems: 'center', justifyContent: 'flex-start', padding: '0 90px'}}>
			<div style={{fontFamily: TEXT, fontWeight: 600, fontSize: 70, lineHeight: 1.15, textAlign: 'center', color: C.vellum, opacity: op, textShadow: '0 3px 18px rgba(0,0,0,0.95), 0 0 2px rgba(0,0,0,0.9)'}}>
				{g.words.map((w, i) => (
					<span key={i} style={{color: t >= w.start && t < (g.words[i + 1]?.start ?? g.end) ? C.giltLight : C.vellum}}>
						{w.text}{' '}
					</span>
				))}
			</div>
		</AbsoluteFill>
	);
};

/* ---------- Atmosphere: vignette, grain, candle flicker, watermark ---------- */
export const Atmosphere = ({showMark = true}) => {
	const f = useCurrentFrame();
	const flick = 0.1 + 0.03 * Math.sin(f / 4.1) + 0.02 * Math.sin(f / 1.7 + 1) + 0.015 * (random(`fl${Math.floor(f / 3)}`) - 0.5);
	const seed = Math.floor(f / 2) % 12;
	return (
		<>
			<AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(13,11,9,0.55) 0%, rgba(13,11,9,0) 22%, rgba(13,11,9,0) 42%, rgba(13,11,9,0.62) 60%, rgba(13,11,9,0.8) 78%, rgba(13,11,9,0.92) 100%)'}} />
			<AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)'}} />
			<AbsoluteFill style={{background: `radial-gradient(ellipse at 15% 100%, rgba(230,160,70,${flick}) 0%, rgba(0,0,0,0) 45%)`, mixBlendMode: 'screen'}} />
			<AbsoluteFill style={{opacity: 0.08, mixBlendMode: 'overlay', backgroundImage: `url(${staticFile(`brand/grain${seed % 4}.png`)})`, backgroundSize: '512px 512px', backgroundPosition: `${(seed * 137) % 512}px ${(seed * 211) % 512}px`}} />
			{showMark && <Img src={staticFile('brand/initials.svg')} style={{position: 'absolute', left: 64, top: 110, height: 46, opacity: 0.7}} />}
		</>
	);
};

export const Credit = ({text}) => {
	const f = useCurrentFrame();
	if (!text) return null;
	return (
		<div style={{position: 'absolute', left: 64, top: 170, maxWidth: 560, fontFamily: TEXT, fontStyle: 'italic', fontSize: 24, color: C.ash, opacity: interpolate(f, [10, 25], [0, 0.75], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
			{text}
		</div>
	);
};
