import React from 'react';
import {AbsoluteFill, Img, interpolate, random, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C} from '../components';

/* Effects for the long-form 16:9 look: most of the motion comes from here, not from the characters. */

// Two-depth rain: far streaks are short, faint and slow; near streaks long and fast. Positions are seeded so every
// render is identical.
export const Rain = ({count = 140, angle = 12, opacity = 1}) => {
	const f = useCurrentFrame();
	const {width: W, height: H} = useVideoConfig();
	const drops = React.useMemo(() => Array.from({length: count}, (_, i) => {
		const near = random(`rd${i}`) > 0.7;
		return {x: random(`rx${i}`) * (W + 400) - 200, y0: random(`ry${i}`) * H, len: near ? 90 : 38, speed: near ? 62 : 34, w: near ? 2.2 : 1.2, a: near ? 0.32 : 0.16};
	}), [count, W, H]);
	const dx = Math.tan((angle * Math.PI) / 180);
	return (
		<svg width={W} height={H} style={{position: 'absolute', opacity}}>
			{drops.map((d, i) => {
				const y = ((d.y0 + f * d.speed) % (H + 200)) - 100;
				const x = d.x + y * dx;
				return <line key={i} x1={x} y1={y} x2={x + d.len * dx} y2={y + d.len} stroke={C.vellum} strokeOpacity={d.a} strokeWidth={d.w} strokeLinecap="round" />;
			})}
		</svg>
	);
};

// Slow drifting mist bands.
export const Fog = ({y = 0.7, opacity = 0.35, speed = 0.6}) => {
	const f = useCurrentFrame();
	const {width: W} = useVideoConfig();
	const off = (f * speed) % W;
	const band = (dx, top, a) => (
		<div style={{position: 'absolute', left: dx - W, top: `${top * 100}%`, width: W * 3, height: '26%', opacity: a,
			background: 'radial-gradient(ellipse 30% 50% at 20% 50%, rgba(154,145,131,0.5), transparent 70%), radial-gradient(ellipse 25% 45% at 55% 55%, rgba(154,145,131,0.4), transparent 70%), radial-gradient(ellipse 30% 50% at 85% 45%, rgba(154,145,131,0.45), transparent 70%)'}} />
	);
	return (
		<AbsoluteFill style={{opacity, filter: 'blur(18px)'}}>
			{band(off, y - 0.08, 0.7)}
			{band(-off * 0.6, y, 1)}
		</AbsoluteFill>
	);
};

// Candle / lantern light: a warm pool that breathes and flickers. x, y are fractions of the frame.
export const CandleLight = ({x = 0.5, y = 0.5, size = 0.45, strength = 0.5}) => {
	const f = useCurrentFrame();
	const fl = strength * (0.85 + 0.08 * Math.sin(f / 3.7) + 0.05 * Math.sin(f / 1.9 + 2) + 0.06 * (random(`cf${Math.floor(f / 2)}`) - 0.5));
	return (
		<AbsoluteFill style={{mixBlendMode: 'screen', background: `radial-gradient(circle at ${x * 100}% ${y * 100}%, rgba(240,170,80,${fl}) 0%, rgba(200,120,50,${fl * 0.35}) ${size * 45}%, rgba(0,0,0,0) ${size * 100}%)`}} />
	);
};

// Grain + vignette + watermark for 16:9 (the Shorts Atmosphere is tuned for 9:16 captions).
export const Finish = ({mark = true}) => {
	const f = useCurrentFrame();
	const seed = Math.floor(f / 2) % 12;
	return (
		<>
			<AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 50%, rgba(0,0,0,0.6) 100%)'}} />
			<AbsoluteFill style={{opacity: 0.09, mixBlendMode: 'overlay', backgroundImage: `url(${staticFile(`brand/grain${seed % 4}.png`)})`, backgroundSize: '512px 512px', backgroundPosition: `${(seed * 137) % 512}px ${(seed * 211) % 512}px`}} />
			{mark && <Img src={staticFile('brand/initials.svg')} style={{position: 'absolute', left: 56, top: 48, height: 40, opacity: 0.6}} />}
		</>
	);
};
