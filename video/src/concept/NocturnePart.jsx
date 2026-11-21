import React from 'react';
import {AbsoluteFill, Img, Sequence, interpolate, random, staticFile, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {Fog, CandleLight, Finish} from './fx';
import {INK, GROUND, Seg, Hound, Woman, Ground, Beams, Nocturne} from './Nocturne';
import {loadFonts} from '../fonts';
import part from './nocturne-part1.json';

/* "Lives of the Saints", Part I of Saint Margaret of Cortona, animated: Reiniger-style silhouettes over black-and-white
   Expressionist plates with limited colour (cold night tint; amber only for flame). Timing comes from
   nocturne-part1.json (the approved narration + score cut), so the finished audio is laid in afterwards unchanged. */

const FPS = 30;
export const partFrames = () => Math.round(part.segments.reduce((a, s) => a + s.dur, 0) * FPS);
const fr = (s) => Math.round(s * FPS);
const PAPER = '#E2DBCB';

// ---------- more figures (all face right, origin on the ground) ----------

// Kneeling, hands to the face (grief) or raised and joined (prayer).
const Kneeling = ({t = 0, pray = false}) => {
	const tremble = pray ? Math.sin(t * 0.9) * 0.6 : Math.sin(t * 2.3) * 1.6 + Math.sin(t * 5.1) * 0.8;
	return (
		<g transform={`translate(0 ${tremble})`}>
			{pray
				? <path d="M-140 0 C-140 -50 -120 -110 -90 -150 C-84 -220 -80 -300 -50 -350 C-34 -376 -20 -392 0 -398 C-4 -420 6 -444 30 -446 C54 -446 66 -428 64 -410 C70 -404 72 -398 68 -394 C66 -386 62 -382 56 -380 C60 -370 50 -362 40 -362 C40 -340 60 -330 90 -340 C110 -350 124 -372 132 -396 L144 -392 C140 -362 124 -330 100 -312 C80 -298 56 -296 40 -300 C44 -240 70 -100 96 0 Z" fill={INK} />
				: <path d="M-150 0 C-150 -40 -136 -90 -110 -130 C-96 -160 -90 -200 -86 -240 C-80 -300 -50 -350 -6 -372 C10 -380 26 -392 40 -398 C64 -406 92 -398 104 -374 C114 -354 112 -330 100 -312 C112 -300 116 -284 108 -270 C96 -254 76 -258 66 -270 C50 -250 40 -220 40 -190 C60 -140 84 -70 100 0 Z" fill={INK} />}
			{/* the veil falling down her back */}
			<path d="M-6 -380 C-50 -360 -84 -300 -100 -220 C-72 -290 -40 -340 4 -366 Z" fill={INK} />
		</g>
	);
};

// A child on a stool, hunched toward the fire.
const ChildOnStool = ({t}) => (
	<g>
		<path d="M-40 0 L-34 -90 L-26 -90 L-30 0 Z M30 0 L24 -90 L32 -90 L38 0 Z M-52 -98 L52 -98 L52 -86 L-52 -86 Z" fill={INK} />
		<g transform={`translate(0 ${Math.sin(t * 1.4) * 1.5})`}>
			<path d="M-50 -92 C-56 -142 -40 -202 -10 -222 C20 -232 40 -212 44 -182 C50 -142 60 -112 70 -92 Z" fill={INK} />
			<path d="M28 -92 C48 -62 58 -22 62 0 L84 0 C82 -30 70 -70 50 -98 Z" fill={INK} />
			<path d="M-14 -232 C-20 -270 10 -290 34 -276 C46 -268 48 -252 44 -240 C40 -228 22 -222 8 -224 C-6 -224 -12 -226 -14 -232 Z" fill={INK} />
			<path d="M-14 -242 C-32 -240 -44 -226 -50 -210 C-32 -220 -22 -228 -10 -234 Z" fill={INK} />
			<path d="M20 -200 C40 -170 60 -150 76 -140 L70 -128 C50 -140 30 -160 12 -186 Z" fill={INK} />
		</g>
	</g>
);

// A horse at the gallop with two riders: the young nobleman, and Margaret behind him.
const Horse = ({ph}) => {
	const leg = (hx, hy, off) => {
		const u = Math.sin(ph + off) * 38, l = Math.max(0, Math.cos(ph + off)) * 52;
		return (
			<Seg x={hx} y={hy} a={u}>
				<path d="M-16 -4 C-18 30 -12 64 -10 92 L10 92 C12 60 18 30 16 -4 Z" fill={INK} />
				<Seg x={0} y={90} a={l}><path d="M-8 0 L-8 82 L14 90 L14 80 L8 76 L8 0 Z" fill={INK} /></Seg>
			</Seg>
		);
	};
	const bob = Math.sin(ph * 2) * 8, pitch = Math.sin(ph) * 2.5;
	const flutter = Math.sin(ph * 2.4) * 6;
	return (
		<g transform={`translate(0 ${bob - 8}) rotate(${pitch})`}>
			{leg(-118, -206, Math.PI + 0.6)}
			{leg(104, -212, 0.6)}
			<Seg x={-148} y={-236} a={flutter}><path d="M0 0 C-40 -4 -74 22 -100 64 C-66 36 -36 24 0 18 Z" fill={INK} /></Seg>
			<path d="M-152 -232 C-142 -272 -60 -282 20 -278 C80 -276 120 -292 150 -272 C170 -252 165 -212 140 -196 C100 -182 40 -192 -20 -188 C-80 -184 -142 -192 -152 -232 Z" fill={INK} />
			<path d="M118 -272 C148 -322 180 -372 210 -392 L240 -382 C262 -372 290 -342 300 -326 C304 -316 296 -308 286 -310 C266 -316 246 -326 232 -330 C210 -300 180 -262 160 -222 Z" fill={INK} />
			<path d="M214 -390 L222 -416 L230 -390 Z M150 -320 L136 -334 L160 -330 Z M170 -350 L156 -364 L180 -360 Z M190 -376 L178 -392 L198 -386 Z" fill={INK} />
			{/* Margaret behind, veil streaming */}
			<path d="M-62 -280 C-68 -330 -56 -372 -38 -382 L-12 -376 C-2 -342 -8 -302 -12 -280 Z M-62 -284 C-62 -250 -52 -220 -42 -200 L0 -200 C-4 -230 -8 -260 -12 -284 Z" fill={INK} />
			<circle cx={-26} cy={-400} r={21} fill={INK} />
			<g transform={`skewY(${flutter * 0.6})`}><path d="M-38 -414 C-90 -404 -132 -372 -166 -340 C-124 -362 -84 -382 -36 -394 Z" fill={INK} /></g>
			{/* the nobleman, cloak flying */}
			<path d="M18 -280 C8 -342 18 -392 40 -402 L72 -396 C82 -352 78 -312 72 -280 Z M40 -290 L72 -226 L88 -228 L68 -298 Z" fill={INK} />
			<circle cx={58} cy={-424} r={23} fill={INK} />
			<path d="M42 -444 L74 -444 L70 -432 L44 -432 Z" fill={INK} />
			<g transform={`skewY(${-flutter})`}><path d="M24 -392 C-30 -382 -84 -352 -118 -318 C-74 -330 -32 -342 22 -352 Z" fill={INK} /></g>
			<path d="M64 -380 C100 -370 130 -352 150 -336 L144 -326 C122 -340 96 -354 62 -362 Z" fill={INK} />
			{leg(-92, -200, Math.PI)}
			{leg(128, -206, 0)}
		</g>
	);
};

// A babe in arms, held at the chest (drawn inside Woman).
const Babe = () => (
	<g>
		<ellipse cx={40} cy={-392} rx={42} ry={58} fill={INK} transform="rotate(-18 40 -392)" />
		<circle cx={66} cy={-450} r={21} fill={INK} />
		<path d="M10 -420 C40 -404 70 -380 90 -350 L80 -340 C60 -366 34 -388 4 -404 Z" fill={INK} />
	</g>
);

// The fallen man: a cloaked shape on the ground, mostly lost in shadow and mist.
const Fallen = () => (
	<path d="M-200 0 C-206 -30 -186 -50 -160 -48 C-140 -64 -96 -74 -20 -70 C40 -66 100 -52 160 -32 C182 -22 192 -8 192 0 Z" fill={INK} />
);

// ---------- scene frame: plate, grade, camera ----------

const Plate = ({file, push = 0.06, drift = 30, tint = 0.32}) => {
	const f = useCurrentFrame();
	const {durationInFrames: N} = useVideoConfig();
	const c = interpolate(f, [0, N], [0, 1], {easing: Easing.inOut(Easing.quad)});
	return (
		<AbsoluteFill style={{transform: `scale(${1.06 + push * c}) translateX(${(0.5 - c) * drift}px)`}}>
			<Img src={staticFile(`concept/nocturne/${file}.jpg`)} style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'grayscale(1) contrast(1.25)'}} />
			<AbsoluteFill style={{background: '#5E7590', mixBlendMode: 'color', opacity: tint}} />
		</AbsoluteFill>
	);
};

// rim = a pale moonlit halo that lifts a silhouette off a dark plate
const Stage = ({children, rim = 0}) => <svg width={1080} height={1920} style={{position: 'absolute', filter: rim ? `drop-shadow(0 0 ${rim}px rgba(214,222,234,0.75)) drop-shadow(0 0 ${rim * 2.5}px rgba(214,222,234,0.35))` : undefined}}>{children}</svg>;

const Flame = ({x, y, s = 1}) => {
	const f = useCurrentFrame();
	const h = 1 + 0.18 * Math.sin(f / 2.3) + 0.1 * (random(`fx${Math.floor(f / 2)}`) - 0.5);
	return (
		<svg width={1080} height={1920} style={{position: 'absolute', mixBlendMode: 'screen'}}>
			<g transform={`translate(${x} ${y}) scale(${s} ${s * h})`}>
				<path d="M0 -26 C8 -14 10 -4 6 4 C4 8 -4 8 -6 4 C-10 -4 -8 -14 0 -26 Z" fill="#F7C46A" />
				<path d="M0 -14 C4 -8 4 -2 2 2 C0 4 -2 4 -2 2 C-4 -2 -3 -8 0 -14 Z" fill="#FFF1C8" />
			</g>
		</svg>
	);
};

// ---------- the eight scenes ----------

const SCENES = {
	// 1. The hound alone in the castle gate; its long shadow reaches toward us.
	gate: () => {
		const f = useCurrentFrame();
		const x = interpolate(f, [0, 120], [400, 470], {extrapolateRight: 'clamp'});
		const ph = Math.min(f, 120) * 0.22;
		const look = interpolate(f, [130, 150], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		return (
			<>
				<Plate file="gate" push={0.08} />
				<Fog y={0.66} opacity={0.4} speed={0.4} />
				<Stage>
					<g transform={`translate(${x} 1330) scale(0.62)`} opacity={0.45}>
						<g transform="scale(1 -2.4) skewX(-12)"><Hound phase={ph} look={look} /></g>
					</g>
					<g transform={`translate(${x} 1330) scale(0.62)`}><Hound phase={ph} look={look} /></g>
				</Stage>
				<Ground x={0} floor />
			</>
		);
	},
	// 2. Margaret at the farmhouse door, stepping out into the light.
	farm: () => {
		const f = useCurrentFrame();
		const x = interpolate(f, [10, 120], [260, 400], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const walking = f > 10 && f < 120;
		return (
			<>
				<Plate file="farm" push={0.05} drift={-30} />
				<Beams />
				<Stage><g transform={`translate(${x} ${GROUND}) scale(1.05)`}><Woman phase={walking ? f * 0.16 : f * 0.05} lantern={false} walk={walking} /></g></Stage>
				<Ground x={10} />
			</>
		);
	},
	// 3. The child by a dying fire; a woman's shadow rises across the wall.
	hearth: () => {
		const f = useCurrentFrame();
		const {durationInFrames: N} = useVideoConfig();
		const grow = interpolate(f, [20, N - 20], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
		return (
			<>
				<Plate file="hearth" push={0.05} />
				<CandleLight x={0.17} y={0.66} size={0.4} strength={0.5} />
				<svg width={1080} height={1920} style={{position: 'absolute', filter: 'blur(1.5px)', opacity: 0.78 * grow}}>
					<g transform={`translate(${300 + 40 * grow} ${1250}) scale(${-(1.4 + 0.5 * grow)} ${1.4 + 0.5 * grow})`}><Woman phase={f * 0.05} lantern={false} walk={false} /></g>
				</svg>
				<Stage rim={6}><g transform={`translate(330 ${GROUND}) scale(1.1)`}><ChildOnStool t={f / FPS} /></g></Stage>
				<Ground x={0} floor />
			</>
		);
	},
	// 4. The night ride toward the castle.
	road: () => {
		const f = useCurrentFrame();
		const {durationInFrames: N} = useVideoConfig();
		const x = interpolate(f, [0, N], [-380, 1340]);
		return (
			<>
				<Plate file="road" push={0.05} drift={60} />
				<Fog y={0.74} opacity={0.35} speed={-1.2} />
				<Stage rim={10}><g transform={`translate(${x} 1400) scale(0.78)`}><Horse ph={f * 0.42} /></g></Stage>
				<Ground x={interpolate(f, [0, N], [40, -40])} />
			</>
		);
	},
	// 5. At the castle window with her son.
	window: () => {
		const f = useCurrentFrame();
		const rock = Math.sin(f / 22) * 1.6;
		return (
			<>
				<Plate file="window" push={0.06} drift={-30} />
				<div style={{position: 'absolute', inset: 0, transform: 'scaleX(-1)'}}><Beams /></div>
				<Stage>
					<g transform={`translate(560 ${GROUND}) scale(1.15) rotate(${rock})`}>
						<Woman phase={f * 0.04} lantern={false} walk={false}><Babe /></Woman>
					</g>
				</Stage>
				<Ground x={0} floor />
			</>
		);
	},
	// 6. The hound leads her into the forest (the approved sample shot).
	'forest-bw': () => {
		const {durationInFrames: N} = useVideoConfig();
		return <Nocturne frames={N} finish={false} />;
	},
	// 7. She kneels where she found him; the hound beside her.
	clearing: () => {
		const f = useCurrentFrame();
		return (
			<>
				<Plate file="clearing" push={0.07} />
				<Beams />
				<Fog y={0.66} opacity={0.45} speed={0.3} />
				<Stage>
					<g transform={`translate(760 1440) scale(0.85)`}><Fallen /></g>
					<g transform={`translate(150 ${GROUND}) scale(0.8)`}><Hound phase={0.3} look={0} /></g>
					<g transform={`translate(430 ${GROUND}) scale(1.15)`}><Kneeling t={f / FPS} /></g>
				</Stage>
				<Fog y={0.8} opacity={0.5} speed={-0.5} />
				<Ground x={0} />
			</>
		);
	},
	// 8. A candle in a chapel; she kneels in prayer.
	chapel: () => {
		const f = useCurrentFrame();
		return (
			<>
				<Plate file="chapel" push={0.05} />
				<CandleLight x={0.62} y={0.52} size={0.42} strength={0.55} />
				<Flame x={672} y={985} s={1.4} />
				<Stage rim={6}><g transform={`translate(400 ${GROUND}) scale(0.9)`}><Kneeling t={f / FPS} pray /></g></Stage>
				<Ground x={0} floor />
			</>
		);
	},
};

// ---------- cards, captions, film ----------

const Card = ({file}) => <Img src={staticFile(`concept/nocturne/${file}.jpg`)} style={{width: '100%', height: '100%'}} />;

const Caption = ({text}) => {
	const f = useCurrentFrame();
	const {durationInFrames: N} = useVideoConfig();
	const o = interpolate(f, [0, 6, N - 6, N], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<div style={{position: 'absolute', left: 60, right: 60, top: 1668, textAlign: 'center', fontFamily: 'EB Garamond', fontWeight: 500, fontSize: 50, lineHeight: 1.3, color: PAPER, opacity: o}}>{text}</div>
	);
};

// dip to black at every cut, like an iris on a silent print
const Dip = ({children}) => {
	const f = useCurrentFrame();
	const {durationInFrames: N} = useVideoConfig();
	const o = interpolate(f, [0, 7, N - 7, N], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>;
};

export const NocturnePart = () => {
	loadFonts();
	const f = useCurrentFrame();
	const flick = 1 + 0.035 * Math.sin(f * 1.9) + 0.03 * (random(`fl${Math.floor(f / 2)}`) - 0.5);
	const wx = Math.sin(f * 0.17) * 2.5, wy = Math.cos(f * 0.13) * 2.5; // gate weave
	return (
		<AbsoluteFill style={{background: INK}}>
			<AbsoluteFill style={{filter: `brightness(${flick}) contrast(1.06)`, transform: `translate(${wx}px, ${wy}px) scale(1.01)`}}>
				{part.segments.map((s, i) => {
					const Scene = s.kind === 'scene' ? SCENES[s.plate] : null;
					return (
						<Sequence key={i} from={fr(s.start)} durationInFrames={fr(s.start + s.dur) - fr(s.start)}>
							<Dip>
								{Scene ? <Scene /> : <Card file={`card-${s.kind}`} />}
							</Dip>
							{s.kind === 'scene' && <Caption text={s.text} />}
						</Sequence>
					);
				})}
			</AbsoluteFill>
			<Finish mark={false} />
		</AbsoluteFill>
	);
};
