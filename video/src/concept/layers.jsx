import React from 'react';
import {Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../components';

/* Parallax plates. Each plate is real art (a PNG from public/<dir>/, transparent where it should show the plate behind)
   or, until that art exists, a flat ink-and-gilt SVG stand-in so the camera and effects can be judged. */

const INK = '#050403';
const ink = {stroke: INK, strokeWidth: 6, strokeLinejoin: 'round'};

// A plate overscanned by `over` so the camera can truck across it. cam runs 0..1; depth scales how far it travels
// (far plates < 1 < near plates), which is where the depth comes from.
export const Plate = ({file, Fallback, depth = 1, cam = 0, zoom = 1, travel = 0.1, over = 1.3, origin = '50% 50%', style}) => {
	const {width: W, height: H} = useVideoConfig();
	const w = W * over, h = H * over;
	const x = (W - w) / 2 + (0.5 - cam) * depth * travel * W * 2;
	return (
		<div style={{position: 'absolute', left: x, top: (H - h) / 2, width: w, height: h, transform: `scale(${zoom})`, transformOrigin: origin, ...style}}>
			{file ? <Img src={staticFile(file)} style={{width: '100%', height: '100%', objectFit: 'cover'}} /> : <Fallback />}
		</div>
	);
};

const Svg = ({children, vb = '0 0 2400 1350'}) => (
	<svg viewBox={vb} preserveAspectRatio="xMidYMid slice" width="100%" height="100%">{children}</svg>
);

/* ---------- Stand-ins ---------- */

export const IconStandIn = () => (
	<Svg vb="0 0 900 1200">
		<defs>
			<linearGradient id="leaf" x1="0" y1="0" x2="1" y2="1">
				<stop offset="0" stopColor="#E6C878" /><stop offset="0.5" stopColor="#C9A44C" /><stop offset="1" stopColor="#9C7A2E" />
			</linearGradient>
		</defs>
		<rect width="900" height="1200" fill="url(#leaf)" />
		<rect x="28" y="28" width="844" height="1144" fill="none" stroke={C.martyr} strokeWidth="10" />
		<circle cx="450" cy="400" r="210" fill="#D8B860" stroke={INK} strokeWidth="5" />
		<circle cx="450" cy="400" r="186" fill="none" stroke={C.martyr} strokeWidth="3" />
		<path d="M190 1172 C210 860 300 700 450 690 C600 700 690 860 710 1172 Z" fill={INK} {...ink} />
		<path d="M300 1172 C320 900 380 760 450 750 C520 760 580 900 600 1172 Z" fill="#2A241C" />
		<ellipse cx="450" cy="430" rx="118" ry="146" fill="#B98A5E" {...ink} />
		<path d="M332 410 C340 300 400 268 450 268 C500 268 560 300 568 410 C540 350 500 330 450 330 C400 330 360 350 332 410 Z" fill="#2A1C12" {...ink} />
		<path d="M395 430 q22 -14 44 0 M461 430 q22 -14 44 0" fill="none" stroke={INK} strokeWidth="5" />
		<path d="M430 520 q20 10 40 0" fill="none" stroke={INK} strokeWidth="4" />
		<path d="M380 840 L520 840 L520 1000 L380 1000 Z" fill={C.vellum} {...ink} />
		<path d="M450 860 v120 M410 900 h80" stroke={C.martyr} strokeWidth="8" />
	</Svg>
);

export const SkyStandIn = () => (
	<Svg>
		<defs>
			<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0" stopColor="#0A1424" /><stop offset="0.7" stopColor={C.lapis} /><stop offset="1" stopColor="#2E4A6E" />
			</linearGradient>
			<radialGradient id="moon"><stop offset="0" stopColor="rgba(239,230,210,0.5)" /><stop offset="1" stopColor="rgba(239,230,210,0)" /></radialGradient>
		</defs>
		<rect width="2400" height="1350" fill="url(#sky)" />
		<circle cx="1700" cy="300" r="260" fill="url(#moon)" />
		<circle cx="1700" cy="300" r="70" fill={C.vellum} {...ink} />
		<path d="M0 900 C300 700 520 760 760 820 C1000 640 1260 700 1500 800 C1760 660 2050 720 2400 840 L2400 1350 L0 1350 Z" fill="#14233A" {...ink} />
		<path d="M0 1040 C400 920 800 1000 1200 960 C1600 920 2000 1000 2400 960 L2400 1350 L0 1350 Z" fill="#101A2A" />
	</Svg>
);

const Hut = ({x, s = 1, lit}) => (
	<g transform={`translate(${x} 0) scale(${s})`}>
		{[0, 120, 240, 360].map((p) => <rect key={p} x={p + 20} y="880" width="16" height="230" fill={C.umber} {...ink} />)}
		<rect x="0" y="720" width="420" height="170" fill="#2A2018" {...ink} />
		<path d="M-60 740 L210 520 L480 740 Z" fill="#3A2C1C" {...ink} />
		<path d="M-20 720 L210 560 M440 720 L210 560" stroke={INK} strokeWidth="3" />
		<rect x="160" y="760" width="90" height="80" fill={lit ? C.giltLight : '#120E0A'} {...ink} />
	</g>
);

export const HutsStandIn = () => (
	<Svg>
		<rect x="0" y="1090" width="2400" height="260" fill="#0E0C0A" {...ink} />
		<Hut x={260} s={0.9} />
		<Hut x={1050} lit />
		<Hut x={1800} s={0.8} />
		{[700, 1580, 2250].map((x) => (
			<g key={x}>
				<path d={`M${x} 1100 C${x + 10} 900 ${x - 10} 760 ${x + 20} 560`} stroke="#1E1912" strokeWidth="22" fill="none" />
				<path d={`M${x + 20} 560 c-120 20 -200 80 -240 140 M${x + 20} 560 c120 10 210 60 250 130 M${x + 20} 560 c-40 -80 -120 -120 -200 -130 M${x + 20} 560 c60 -70 140 -100 220 -100`} stroke="#1E1912" strokeWidth="30" fill="none" strokeLinecap="round" />
			</g>
		))}
	</Svg>
);

export const LeavesStandIn = () => (
	<Svg>
		<path d="M0 1350 L0 300 C120 420 260 700 300 1350 Z" fill={INK} />
		<path d="M0 700 C200 640 420 700 560 860 C380 820 200 820 0 900 Z" fill={INK} />
		<path d="M2400 1350 L2400 200 C2240 360 2100 760 2080 1350 Z" fill={INK} />
		<path d="M2400 560 C2180 520 1960 600 1840 760 C2040 720 2240 740 2400 800 Z" fill={INK} />
		<path d="M900 1350 C980 1240 1120 1210 1260 1260 C1360 1300 1400 1350 1400 1350 Z" fill={INK} />
	</Svg>
);

export const RoomStandIn = () => (
	<Svg>
		<rect width="2400" height="1350" fill="#120E0A" />
		<rect x="1500" y="260" width="520" height="760" fill="#14233A" {...ink} />
		<circle cx="1820" cy="420" r="40" fill={C.vellum} opacity="0.7" />
		{[200, 1400, 2140].map((x) => <rect key={x} x={x} y="0" width="70" height="1350" fill="#2A2018" {...ink} />)}
		<rect x="0" y="120" width="2400" height="60" fill="#2A2018" {...ink} />
		<rect x="0" y="1060" width="2400" height="290" fill="#1C1712" {...ink} />
	</Svg>
);

export const FigureStandIn = () => (
	<Svg>
		{/* seated priest writing, inside a bamboo cage */}
		<path d="M820 1080 C820 900 880 790 1000 770 C1100 760 1180 830 1200 1000 L1220 1080 Z" fill="#1A1612" {...ink} />
		<ellipse cx="1010" cy="680" rx="78" ry="96" fill="#B98A5E" {...ink} />
		<path d="M932 660 C940 590 980 570 1012 570 C1050 570 1086 590 1090 660 C1060 620 1040 612 1012 612 C984 612 956 624 932 660 Z" fill="#2A1C12" {...ink} />
		<path d="M1060 940 L1260 900 L1290 960 L1080 1000 Z" fill={C.vellum} {...ink} />
		<path d="M1150 860 C1190 890 1220 910 1240 930" stroke="#B98A5E" strokeWidth="26" strokeLinecap="round" fill="none" />
		<rect x="1340" y="940" width="24" height="70" fill={C.vellum} {...ink} />
		<path d="M1352 900 q14 22 0 40 q-14 -18 0 -40 Z" fill={C.giltLight} />
		<rect x="640" y="380" width="900" height="30" fill="#5A4628" {...ink} />
		<rect x="640" y="1060" width="900" height="30" fill="#5A4628" {...ink} />
		{Array.from({length: 10}, (_, i) => <rect key={i} x={650 + i * 96} y="380" width="20" height="710" fill="#6B5430" {...ink} />)}
	</Svg>
);

/* ---------- Minimal puppetry: breathing, and a blink when a closed-eyes frame exists ---------- */
const BLINKS = [40, 150, 230]; // frames (within the scene) where a 4-frame blink starts

export const Figure = ({file, blinkFile, cam, depth, zoom, travel}) => {
	const f = useCurrentFrame();
	const breathe = 1 + 0.006 * Math.sin(f / 24);
	const blinking = blinkFile && BLINKS.some((b) => f >= b && f < b + 4);
	return (
		<div style={{position: 'absolute', inset: 0, transform: `scaleY(${breathe})`, transformOrigin: '50% 80%'}}>
			<Plate file={blinking ? blinkFile : file} Fallback={FigureStandIn} depth={depth} cam={cam} zoom={zoom} travel={travel} origin="45% 55%" />
		</div>
	);
};
