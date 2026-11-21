import React from 'react';
import {AbsoluteFill, Img, interpolate, random, staticFile, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {Fog, CandleLight, Finish} from './fx';
import {Beams, FrontTrees, Ground, GROUND, INK} from './Nocturne';
import POSES from '../../public/concept/nocturne/poses.json';

/* Part I, beat 6 as stop motion (Luis, 2026-11-18: "stop motion poses"): Reiniger-style paper cutouts (AI-cut, four walk
   poses each) swapped on fours (7.5 poses/s) and moved in the same steps, like a figure shifted under the camera between
   exposures. The plate, mist, beams and grain stay smooth, as they would on a rostrum camera. */

const ON = 4; // frames per exposure

// One posed cutout, placed with its feet on the ground and its anchor (head for her, body for the hound) at x.
const Cutout = ({name, pose, x, height, style}) => {
	const p = POSES[name][pose];
	const k = height / p.h;
	return (
		<Img src={staticFile(`concept/nocturne/cut/${name}/${pose}.png`)}
			style={{position: 'absolute', left: x - p.ax * k, top: GROUND - height + 6, width: p.w * k, height, ...style}} />
	);
};

export const NocturnePoses = () => {
	const f = useCurrentFrame();
	const {durationInFrames: N} = useVideoConfig();
	const step = Math.floor(f / ON) * ON; // the figures only change on exposures
	const cam = interpolate(f, [0, N], [0, 1], {easing: Easing.inOut(Easing.quad)});
	const houndX = interpolate(step, [0, N], [-120, 860]);
	const herX = interpolate(step, [0, N], [-260, 520]);
	const hp = Math.floor(f / ON) % 4, mp = Math.floor(f / ON + 1) % 4;
	const herH = 660, houndH = 300;
	const m = POSES['margaret-lantern'][mp], k = herH / m.h;
	const lx = herX + (m.lx - m.ax) * k, ly = GROUND - herH + 6 + m.ly * k;
	const flick = 1 + 0.035 * Math.sin(f * 1.9) + 0.03 * (random(`fl${Math.floor(f / 2)}`) - 0.5);
	const rim = 'drop-shadow(0 0 3px rgba(205,215,230,0.55)) drop-shadow(0 0 14px rgba(205,215,230,0.25))';
	return (
		<AbsoluteFill style={{background: INK, filter: `brightness(${flick}) contrast(1.06)`}}>
			<AbsoluteFill style={{transform: `scale(${1.08 + 0.06 * cam}) translateX(${(0.5 - cam) * 30}px)`}}>
				<Img src={staticFile('concept/nocturne/forest-bw.jpg')} style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'grayscale(1) contrast(1.25)'}} />
				<AbsoluteFill style={{background: '#5E7590', mixBlendMode: 'color', opacity: 0.32}} />
			</AbsoluteFill>
			<Beams />
			<Fog y={0.62} opacity={0.5} speed={0.5} />
			<CandleLight x={lx / 1080} y={ly / 1920} size={0.3} strength={0.42} />
			{/* amber behind the lantern: it shows through the cut-out panes */}
			<div style={{position: 'absolute', left: lx - 34, top: ly - 46, width: 68, height: 92, borderRadius: '45%',
				background: 'radial-gradient(closest-side, #FFE2A0, #F0A040 60%, rgba(240,160,64,0))'}} />
			<Cutout name="hound" pose={hp} x={houndX} height={houndH} style={{filter: rim}} />
			<Cutout name="margaret-lantern" pose={mp} x={herX} height={herH} style={{filter: 'drop-shadow(0 0 3px rgba(205,215,230,0.35))'}} />
			<Ground x={(0.5 - cam) * 70} />
			<Fog y={0.82} opacity={0.35} speed={-0.8} />
			<FrontTrees x={(0.5 - cam) * 140} />
			<Finish mark={false} />
		</AbsoluteFill>
	);
};
