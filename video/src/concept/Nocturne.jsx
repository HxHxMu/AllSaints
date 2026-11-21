import React from 'react';
import {AbsoluteFill, Img, interpolate, random, staticFile, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {Fog, CandleLight, Finish} from './fx';

/* "Lives of the Saints" sample shot: Lotte Reiniger-style silhouette cutouts (flat black jointed figures) over a
   black-and-white Expressionist "living painting" backdrop with limited colour (a cold night tint, amber only in the
   lantern; Luis, 2026-11-18: closer to the Faust film look) (parallax, push-in, light beams, mist, lantern glow, grain, flicker).
   Part I, beat 6: the hound leads Margaret, lantern in hand, into the forest. */

export const NOCTURNE_FRAMES = 254; // beat 6 of Part I: 8.47 s
export const INK = '#030303';
export const GROUND = 1590; // feet line, px

// ---------- jointed figures (drawn facing right, origin at the feet) ----------

export const Seg = ({x, y, a, children}) => <g transform={`translate(${x} ${y}) rotate(${a})`}>{children}</g>;

// A hound in profile, ~250 px tall. phase: walk cycle in radians; look: head turn back (0..1).
export const Hound = ({phase, look = 0}) => {
	const leg = (hx, hy, off, front) => {
		const s = Math.sin(phase + off);
		const upper = s * 24, lower = front ? Math.max(0, -Math.cos(phase + off)) * 30 : -Math.max(0, Math.cos(phase + off)) * 32;
		return (
			<Seg x={hx} y={hy} a={upper}>
				<path d={front ? 'M-15 -6 C-16 30 -11 55 -9 72 L9 72 C11 50 15 25 15 -6 Z' : 'M-20 -10 C-24 20 -10 50 -9 72 L10 72 C12 46 22 16 20 -10 Z'} fill={INK} />
				<Seg x={0} y={70} a={lower}>
					<path d="M-8 0 L-7 56 C-7 64 2 66 16 66 L18 59 L8 55 L8 0 Z" fill={INK} />
				</Seg>
			</Seg>
		);
	};
	const bob = Math.sin(phase * 2) * 3;
	const back = look > 0.5;
	return (
		<g transform={`translate(0 ${-136 + bob})`}>
			{leg(-84, 0, Math.PI, false)}
			{leg(80, -4, 0, true)}
			<path d="M-124 -22 C-114 -68 -40 -66 20 -62 C70 -60 104 -74 122 -52 C138 -30 130 16 102 26 C72 36 42 22 10 20 C-30 18 -70 32 -102 24 C-126 18 -132 0 -124 -22 Z" fill={INK} />
			<Seg x={-120} y={-32} a={-30 + Math.sin(phase * 1.3) * 10}>
				<path d="M0 -4 C-30 -16 -64 -10 -92 10 C-64 4 -34 8 0 12 Z" fill={INK} />
			</Seg>
			{/* neck rising forward, then the head: broad skull, long muzzle, ear hanging */}
			<Seg x={110} y={-50} a={0}>
				<path d="M-22 10 C-14 -24 0 -50 18 -62 L44 -54 C36 -30 26 -6 18 18 Z" fill={INK} />
				<g transform={`translate(30 -66) scale(${back ? -1 : 1} 1)`}>
					<path d="M-20 -2 C-22 -30 0 -42 20 -36 C30 -33 36 -28 40 -22 L82 -18 C92 -17 94 -4 88 2 L84 8 L42 10 C24 14 6 20 -20 -2 Z" fill={INK} />
					<path d="M-4 -26 C-22 -26 -30 -6 -26 18 C-20 30 -12 30 -10 18 C-10 4 -6 -10 2 -22 Z" fill={INK} />
				</g>
			</Seg>
			{leg(-62, 2, 0.4, false)}
			{leg(98, -2, Math.PI + 0.4, true)}
		</g>
	);
};

// Margaret in profile, ~560 px tall: veiled head, long cloak, arm forward holding a lantern.
export const Woman = ({phase, lantern = true, walk = true, children}) => {
	const bob = walk ? Math.abs(Math.sin(phase)) * 5 : 0;
	const sway = walk ? Math.sin(phase) * 3 : Math.sin(phase) * 0.8; // hem sway, degrees of skew
	const arm = lantern ? 38 + Math.sin(phase) * 4 : 78;
	return (
		<g transform={`translate(0 ${-bob})`}>
			{/* cloak and gown: one flat shape, the hem skewed by the step */}
			<g transform={`skewX(${sway})`} style={{transformOrigin: '0px -560px'}}>
				<path d="M-34 -420 C-60 -360 -78 -240 -96 -120 C-110 -50 -124 -14 -130 0 L118 0 C104 -30 86 -90 70 -170 C56 -250 44 -340 34 -420 Z" fill={INK} />
				{/* a lifted fold of the hem at the front foot */}
				<path d="M60 -40 C80 -30 104 -14 124 0 L70 0 Z" fill={INK} />
			</g>
			{/* shoulders and veil falling behind */}
			<path d="M-40 -430 C-40 -470 -20 -500 6 -506 C36 -508 52 -480 48 -440 C46 -420 30 -410 0 -410 C-20 -410 -38 -416 -40 -430 Z" fill={INK} />
			<path d="M-8 -520 C-40 -520 -66 -470 -78 -380 C-86 -300 -96 -230 -100 -190 C-80 -260 -50 -360 -24 -440 Z" fill={INK} />
			{/* head with veil: brow, nose, chin in profile */}
			<path d="M-24 -500 C-30 -546 -6 -574 22 -572 C40 -570 50 -556 52 -540 C54 -532 60 -528 62 -522 C58 -518 54 -516 52 -512 C54 -506 52 -500 46 -498 C42 -490 36 -486 26 -486 C10 -486 -16 -486 -24 -500 Z" fill={INK} />
			<path d="M-30 -510 C-34 -560 -8 -590 22 -588 C46 -586 58 -568 56 -548 C44 -566 24 -574 4 -568 C-14 -560 -22 -536 -30 -510 Z" fill={INK} />
			{children}
			{/* the arm, forward and down, holding the lantern on a short chain */}
			{lantern && <Seg x={26} y={-430} a={arm}>
				<path d="M-10 -6 C30 -12 90 -10 150 -4 L150 12 C90 14 30 14 -10 12 Z" fill={INK} />
				<Seg x={150} y={4} a={-arm + Math.sin(phase + 0.8) * 6}>
					<line x1={0} y1={0} x2={0} y2={34} stroke={INK} strokeWidth={4} />
					{/* lantern: a cage with a lit pane (the only colour on the figures) */}
					<g transform="translate(0 34)">
						<path d="M-18 0 L18 0 L22 10 L22 52 L-22 52 L-22 10 Z" fill={INK} />
						<rect x={-14} y={14} width={28} height={32} fill="#F2B35A" />
						<path d="M-14 30 h28 M0 14 v32" stroke={INK} strokeWidth={3} />
						<path d="M-26 52 h52 v6 h-52 Z M-8 -8 h16 v8 h-16 Z" fill={INK} />
					</g>
				</Seg>
			</Seg>}
		</g>
	);
};

// ---------- set pieces ----------

export const Ground = ({x, floor = false}) => (
	<svg width={1600} height={420} viewBox="0 0 1600 420" style={{position: 'absolute', left: x - 260, top: GROUND - 30}}>
		<path d={floor ? 'M0 32 L1600 32 L1600 420 L0 420 Z' : undefined} fill={INK} />
		{!floor && <path d="M0 40 C120 20 200 50 320 34 C460 16 560 44 700 30 C860 14 980 46 1120 28 C1260 12 1400 40 1600 26 L1600 420 L0 420 Z" fill={INK} />}
		{/* grass tufts and roots along the edge */}
		{!floor && Array.from({length: 46}, (_, i) => {
			const gx = i * 35 + random(`g${i}`) * 20, h = 14 + random(`gh${i}`) * 26, lean = (random(`gl${i}`) - 0.5) * 16;
			return <path key={i} d={`M${gx} 40 L${gx + lean} ${40 - h} L${gx + 5} 40 Z`} fill={INK} />;
		})}
		{!floor && <path d="M180 36 C150 10 120 0 90 6 C120 10 140 22 160 40 Z M1300 30 C1340 0 1380 -6 1420 2 C1380 8 1350 20 1330 34 Z" fill={INK} />}
	</svg>
);

// Framing trees in the foreground, cut paper with twisted branches; they slide faster than the backdrop.
export const FrontTrees = ({x}) => (
	<svg width={1500} height={1920} viewBox="0 0 1500 1920" style={{position: 'absolute', left: x - 70, top: 0}}>
		<path d="M0 0 L120 0 C110 300 140 560 120 820 C100 1100 150 1400 170 1920 L0 1920 Z" fill={INK} />
		<path d="M100 420 C220 380 300 300 380 210 C420 170 470 150 520 160 C460 180 420 220 390 270 C340 350 250 430 116 480 Z" fill={INK} />
		<path d="M360 250 C380 190 360 120 330 60 C370 110 400 180 392 240 Z M450 170 C500 140 560 140 610 170 C560 160 510 170 470 190 Z" fill={INK} />
		<path d="M1500 0 L1390 0 C1400 260 1360 520 1380 760 C1400 1000 1350 1300 1340 1920 L1500 1920 Z" fill={INK} />
		<path d="M1392 560 C1300 520 1220 460 1150 380 C1110 336 1060 316 1010 320 C1070 344 1110 380 1140 420 C1200 500 1290 570 1386 610 Z" fill={INK} />
		<path d="M1160 410 C1130 360 1130 300 1150 250 C1120 300 1110 360 1130 420 Z" fill={INK} />
	</svg>
);

// Pale shafts of light from the upper left, breathing slowly.
export const Beams = () => {
	const f = useCurrentFrame();
	const b = (a, x, w, k) => {
		const o = a * (0.75 + 0.25 * Math.sin(f / 40 + k));
		return <polygon key={k} points={`${x},-50 ${x + w},-50 ${x + w + 760},1700 ${x + 520},1700`} fill="url(#beam)" opacity={o} />;
	};
	return (
		<svg width={1080} height={1920} style={{position: 'absolute', mixBlendMode: 'screen', filter: 'blur(14px)'}}>
			<defs>
				<linearGradient id="beam" x1="0" y1="0" x2="0.4" y2="1">
					<stop offset="0" stopColor="rgba(236,240,245,0.5)" />
					<stop offset="1" stopColor="rgba(236,240,245,0)" />
				</linearGradient>
			</defs>
			{b(0.5, -120, 90, 0)}
			{b(0.35, 60, 60, 2)}
			{b(0.28, 230, 110, 4)}
		</svg>
	);
};

// ---------- the shot ----------

export const Nocturne = ({frames, finish = true}) => {
	const f = useCurrentFrame();
	const {durationInFrames} = useVideoConfig();
	const N = frames || durationInFrames;
	const p = f / N;
	const cam = interpolate(f, [0, N], [0, 1], {easing: Easing.inOut(Easing.quad)});
	// walkers: the hound ahead, she follows; both cross toward the path into the trees
	const walk = (x0, x1, speed) => ({x: interpolate(f, [0, N], [x0, x1]), phase: f * speed});
	const hound = walk(-180, 760, 0.30);
	const her = walk(-330, 430, 0.16);
	const look = interpolate(f, [120, 150, 190, 215], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const flick = 1 + 0.035 * Math.sin(f * 1.9) + 0.03 * (random(`fl${Math.floor(f / 2)}`) - 0.5);
	// lantern position for its glow (approximate: hand ahead of her at chest height)
	const lx = (her.x + 150) / 1080, ly = (GROUND - 330) / 1920;
	return (
		<AbsoluteFill style={{background: INK, filter: `brightness(${flick}) contrast(1.06)`}}>
			{/* backdrop: slow push and a little truck with the walkers */}
			<AbsoluteFill style={{transform: `scale(${1.08 + 0.06 * cam}) translateX(${(0.5 - cam) * 30}px)`}}>
				<Img src={staticFile('concept/nocturne/forest-bw.jpg')} style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'grayscale(1) contrast(1.25)'}} />
				{/* limited colour: a faint cold night tint, like a tinted silent-film print; the lantern's amber is the only warm note */}
				<AbsoluteFill style={{background: '#5E7590', mixBlendMode: 'color', opacity: 0.32}} />
			</AbsoluteFill>
			<Beams />
			<Fog y={0.62} opacity={0.5} speed={0.5} />
			<CandleLight x={lx} y={ly} size={0.32} strength={0.42} />
			{/* the walkers, on the cut-paper ground */}
			<svg width={1080} height={1920} style={{position: 'absolute'}}>
				<g transform={`translate(${hound.x} ${GROUND})`}><Hound phase={hound.phase} look={look} /></g>
				<g transform={`translate(${her.x} ${GROUND}) scale(1.18)`}><Woman phase={her.phase} /></g>
			</svg>
			<Ground x={(0.5 - cam) * 70} />
			<Fog y={0.82} opacity={0.35} speed={-0.8} />
			<FrontTrees x={(0.5 - cam) * 140} />
			{finish && <Finish mark={false} />}
		</AbsoluteFill>
	);
};
