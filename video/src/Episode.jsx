import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {ArtScene, MapScene, TitleCard, CloseScene, Captions, Atmosphere, Credit, C, src} from './components';
import {loadFonts} from './fonts';

loadFonts();

export const OVERLAP = 18;

export const episodeDuration = (props, fps = 30) => Math.ceil(((props.voiceDuration || 58) + 0.8 + (props.outro || 3)) * fps);

export const Episode = (props) => {
	const {fps, durationInFrames} = useVideoConfig();
	const {scenes = [], words = [], saint = {}, voice, music, title} = props;
	const outroFrames = Math.round((props.outro || 3) * fps);
	const fr = (s) => Math.round(s * fps);
	const closeStart = scenes.find((s) => s.kind === 'close')?.start;
	const frame = useCurrentFrame();
	// the caption shade would mute the close prayer and outro, so lift it as the close scene begins
	const bottomShade = closeStart ? interpolate(frame, [fr(closeStart), fr(closeStart) + 18], [1, 0.25], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;

	return (
		<AbsoluteFill style={{backgroundColor: C.soot}}>
			{scenes.map((s, i) => {
				const from = fr(s.start);
				const next = scenes[i + 1];
				const dur = next ? fr(next.start) - from + OVERLAP : durationInFrames - from;
				return (
					<Sequence key={i} from={from} durationInFrames={Math.max(1, dur)} layout="none">
						<AbsoluteFill>
							{s.kind === 'art' && <ArtScene scene={s} durationInFrames={dur} />}
							{s.kind === 'map' && <MapScene scene={s} durationInFrames={dur} />}
							{s.kind === 'close' && <CloseScene scene={s} saint={saint} durationInFrames={dur} outroFrames={outroFrames} />}
						</AbsoluteFill>
					</Sequence>
				);
			})}

			<Atmosphere showMark bottomShade={bottomShade} />

			{scenes.map((s, i) =>
				s.kind === 'art' && s.credit ? (
					<Sequence key={'c' + i} from={fr(s.start)} durationInFrames={fr(Math.min(3.5, (scenes[i + 1]?.start ?? s.end) - s.start))} layout="none">
						<Credit text={s.credit} />
					</Sequence>
				) : null
			)}

			{title && (
				<Sequence from={fr(title.start)} durationInFrames={Math.max(1, fr(title.end - title.start))} layout="none">
					<TitleCard saint={saint} durationInFrames={fr(title.end - title.start)} />
				</Sequence>
			)}

			<Captions words={words} hideAfter={closeStart} />

			{voice && <Audio src={src(voice)} />}
			{music && (
				<Audio
					src={src(music)}
					loop
					volume={(f) => {
						const t = f / fps;
						const fadeIn = interpolate(t, [0, 1.5], [0, 1], {extrapolateRight: 'clamp'});
						const fadeOut = interpolate(f, [durationInFrames - fps * 1.5, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
						const lift = closeStart ? interpolate(t, [closeStart, closeStart + 2], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
						return (0.14 + 0.16 * lift) * fadeIn * fadeOut;
					}}
				/>
			)}
		</AbsoluteFill>
	);
};
