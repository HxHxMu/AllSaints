import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../components';
import {DISPLAY, TEXT, ACCENT, loadFonts} from '../fonts';
import {Rain, Fog, CandleLight, Finish} from './fx';
import {Plate, Figure, IconStandIn, SkyStandIn, HutsStandIn, LeavesStandIn, RoomStandIn} from './layers';
import cfg from './venard.json';

loadFonts();

/* 30 s proof of concept for the long-form format: the icon opens into the story world, the story is told with
   parallax camera moves and effects (very little character motion), and the icon closes it. 16:9, no narration yet. */

export const VENARD_FRAMES = 900;
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'};
const ease = Easing.bezier(0.25, 0.1, 0.25, 1);
const art = (k) => (cfg.useArt && cfg.art[k] ? `${cfg.dir}/${cfg.art[k]}` : null); // missing art keeps its stand-in

const rise = (f, delay = 0, dur = 15) => {
	const t = interpolate(f, [delay, delay + dur], [0, 1], {...clamp, easing: ease});
	return {opacity: t, transform: `translateY(${(1 - t) * 12}px)`};
};
const fadeOut = (f, end, dur = 15) => interpolate(f, [end - dur, end], [1, 0], clamp);

// The icon on its board: gilt frame on soot, as if hanging in a dark chapel.
const IconPanel = ({zoom = 1, x = 0.5, glow = 0}) => {
	const {width: W, height: H} = useVideoConfig();
	const h = H * 0.82, w = h * 0.75;
	return (
		<div style={{position: 'absolute', left: W * x - w / 2, top: (H - h) / 2, width: w, height: h, transform: `scale(${zoom})`, transformOrigin: '50% 34%',
			boxShadow: `0 0 0 14px #3A2C1C, 0 0 0 18px ${C.gilt}, 0 30px 80px rgba(0,0,0,0.8), 0 0 ${120 + 80 * glow}px rgba(230,200,120,${0.12 + 0.2 * glow})`}}>
			{art('icon') ? <Img src={staticFile(art('icon'))} style={{width: '100%', height: '100%', objectFit: 'cover'}} /> : <IconStandIn />}
		</div>
	);
};

/* ---------- 1. Icon opens (0–7.5 s); the village shows through from 5 s ---------- */
const IconOpen = ({dur}) => {
	const f = useCurrentFrame();
	const zoom = interpolate(f, [0, dur], [1, 1.5], {...clamp, easing: Easing.in(Easing.cubic)});
	// the "step into the icon" reveal: a soft-edged hole opens from the saint's face, rimmed with gilt light
	const r = interpolate(f, [150, dur], [0, 95], {...clamp, easing: Easing.in(Easing.quad)});
	const mask = `radial-gradient(circle at 32% 40%, transparent ${r}%, black ${r + 10}%)`;
	return (
		<AbsoluteFill style={{WebkitMaskImage: f >= 150 ? mask : undefined, maskImage: f >= 150 ? mask : undefined}}>
			<AbsoluteFill style={{background: `radial-gradient(ellipse at 32% 45%, ${C.umber} 0%, ${C.soot} 70%)`}} />
			<IconPanel zoom={zoom} x={0.32} glow={interpolate(f, [100, 170], [0, 1], clamp)} />
			<CandleLight x={0.32} y={0.95} size={0.6} strength={0.22} />
			<div style={{position: 'absolute', left: '58%', top: '40%', width: '36%', opacity: fadeOut(f, 140, 20)}}>
				<div style={{width: 120, height: 2, background: C.martyr, marginBottom: 28, ...rise(f, 20)}} />
				<div style={{fontFamily: DISPLAY, fontWeight: 600, fontSize: 64, letterSpacing: '0.1em', lineHeight: 1.15, color: C.vellum, textTransform: 'uppercase', ...rise(f, 26)}}>
					{cfg.saint.name}
				</div>
				<div style={{fontFamily: TEXT, fontStyle: 'italic', fontSize: 38, color: C.giltLight, marginTop: 18, ...rise(f, 36)}}>{cfg.saint.dates}</div>
			</div>
		</AbsoluteFill>
	);
};

/* ---------- 2. Night village in the rain (5–16.5 s) ---------- */
const Village = ({dur}) => {
	const f = useCurrentFrame();
	const cam = interpolate(f, [0, dur], [0, 1], {...clamp, easing: Easing.bezier(0.3, 0, 0.6, 1)});
	const zoom = interpolate(f, [0, dur], [1.04, 1.0], clamp);
	const opacity = fadeOut(f, dur, 18);
	return (
		<AbsoluteFill style={{opacity, backgroundColor: C.soot, overflow: 'hidden'}}>
			<Plate file={art('villageSky')} Fallback={SkyStandIn} depth={0.25} cam={cam} zoom={zoom} />
			<Fog y={0.62} opacity={0.3} speed={0.5} />
			<Plate file={art('villageHuts')} Fallback={HutsStandIn} depth={0.7} cam={cam} zoom={zoom} />
			{/* lantern in the lit window rides with the huts plate */}
			<CandleLight x={0.53 + (0.5 - cam) * 0.7 * 0.1 * 2} y={0.62}size={0.22} strength={0.55} />
			<Rain count={170} />
			<Plate file={art('villageLeaves')} Fallback={LeavesStandIn} depth={1.6} cam={cam} zoom={zoom} />
			<div style={{position: 'absolute', left: 0, right: 0, bottom: 120, textAlign: 'center', fontFamily: DISPLAY, fontWeight: 600, fontSize: 34, letterSpacing: '0.24em', color: C.giltLight, textTransform: 'uppercase', textShadow: '0 2px 14px rgba(0,0,0,0.95)', opacity: fadeOut(f, 260, 20)}}>
				<span style={{display: 'inline-block', ...rise(f, 70, 20)}}>{cfg.saint.place}</span>
			</div>
		</AbsoluteFill>
	);
};

// A whole painted scene (no separate layers), emerging from the dark with feathered edges. Oil-painting art can't be
// generated on a clean green screen, so these scenes move by push-in and light rather than parallax.
const Painting = ({file, clip, zoom, candle}) => {
	const {width: W, height: H} = useVideoConfig();
	const fade = 'radial-gradient(ellipse 50% 50% at 50% 50%, black 62%, transparent 100%)';
	return (
		<div style={{position: 'absolute', left: W * 0.12, top: H * 0.02, width: W * 0.76, height: H * 0.96, transform: `scale(${zoom})`, transformOrigin: '48% 38%', WebkitMaskImage: fade, maskImage: fade}}>
			{clip ? (
				// image-to-video of the same painting: it supplies the small life (flame, writing hand), Remotion the camera
				<OffthreadVideo src={staticFile(clip)} muted playbackRate={0.96} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
			) : (
				<Img src={staticFile(file)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
			)}
			{candle && <CandleLight x={candle.x} y={candle.y} size={0.35} strength={0.35} />}
		</div>
	);
};

/* ---------- 3. The cage, a letter by candlelight (16–26.5 s) ---------- */
const Cage = ({dur}) => {
	const f = useCurrentFrame();
	const zoom = interpolate(f, [0, dur], [1.0, 1.09], {...clamp, easing: ease});
	const cam = interpolate(f, [0, dur], [0.35, 0.6], clamp);
	const fadeIn = interpolate(f, [0, 18], [0, 1], clamp);
	const textOut = fadeOut(f, dur - 6, 18);
	return (
		<AbsoluteFill style={{opacity: fadeIn, backgroundColor: C.soot, overflow: 'hidden'}}>
			{art('cageScene') ? (
				<Painting file={art('cageScene')} clip={art('cageClip')} zoom={zoom} candle={cfg.candle} />
			) : (
				<>
					<Plate file={art('cageRoom')} Fallback={RoomStandIn} depth={0.3} cam={cam} zoom={zoom} travel={0.06} origin="45% 55%" />
					<Figure file={art('cageFigure')} blinkFile={art('cageFigureBlink')} depth={1} cam={cam} zoom={zoom} travel={0.06} />
					<CandleLight x={0.55} y={0.66} size={0.5} strength={0.5} />
				</>
			)}
			<AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(13,11,9,0) 55%, rgba(13,11,9,0.85) 100%)'}} />
			<div style={{position: 'absolute', left: 220, right: 220, bottom: 100, textAlign: 'center', opacity: textOut}}>
				<div style={{fontFamily: ACCENT, fontStyle: 'italic', fontWeight: 500, fontSize: 46, lineHeight: 1.3, color: C.vellum, textShadow: '0 3px 18px rgba(0,0,0,0.95)', ...rise(f, 50, 24)}}>
					“{cfg.quote.text}”
				</div>
				<div style={{fontFamily: TEXT, fontStyle: 'italic', fontSize: 28, color: C.ash, marginTop: 18, ...rise(f, 80, 20)}}>{cfg.quote.source}</div>
			</div>
		</AbsoluteFill>
	);
};

/* ---------- 4. Back to the icon (25.9–30 s) ---------- */
const IconClose = ({dur}) => {
	const f = useCurrentFrame();
	const opacity = interpolate(f, [0, 18], [0, 1], clamp);
	const zoom = interpolate(f, [0, dur], [1.12, 1.0], {...clamp, easing: ease});
	return (
		<AbsoluteFill style={{opacity, background: `radial-gradient(ellipse at 50% 45%, ${C.umber} 0%, ${C.soot} 70%)`}}>
			<IconPanel zoom={zoom} x={0.32} glow={0.6} />
			<CandleLight x={0.32} y={0.95} size={0.6} strength={0.22} />
			{/* beside the icon, as in the opening, so the words never cover the saint's face */}
			<div style={{position: 'absolute', left: '58%', top: '38%', width: '36%'}}>
				<div style={{fontFamily: ACCENT, fontStyle: 'italic', fontWeight: 500, fontSize: 76, lineHeight: 1.15, color: C.vellum, textShadow: '0 3px 26px rgba(0,0,0,0.95)', ...rise(f, 14, 24)}}>
					{cfg.saint.name}, pray for us.
				</div>
				<div style={{width: 120, height: 2, background: C.gilt, marginTop: 36, ...rise(f, 26, 20)}} />
			</div>
		</AbsoluteFill>
	);
};

const SCENES = [
	{C: IconOpen, from: 0, to: 225},
	{C: Village, from: 150, to: 495},
	{C: Cage, from: 477, to: 795},
	{C: IconClose, from: 777, to: VENARD_FRAMES},
];

export const Venard = () => {
	const {fps} = useVideoConfig();
	return (
		<AbsoluteFill style={{backgroundColor: C.soot}}>
			{/* the village is drawn first so the icon (on top) can open onto it */}
			{[1, 0, 2, 3].map((i) => {
				const {C: Scene, from, to} = SCENES[i];
				return (
					<Sequence key={i} from={from} durationInFrames={to - from} layout="none">
						<Scene dur={to - from} />
					</Sequence>
				);
			})}
			<Finish />
			{cfg.music && (
				<Audio src={staticFile(cfg.music)} volume={(f) => interpolate(f, [0, fps, VENARD_FRAMES - 2 * fps, VENARD_FRAMES], [0, 0.8, 0.8, 0], clamp)} />
			)}
		</AbsoluteFill>
	);
};
