import {continueRender, delayRender, staticFile} from 'remotion';

const FONTS = [
	['Cinzel', 'Cinzel-SemiBold.ttf', '600', 'normal'],
	['Cinzel', 'Cinzel-Regular.ttf', '400', 'normal'],
	['EB Garamond', 'EBGaramond-Medium.ttf', '500', 'normal'],
	['EB Garamond', 'EBGaramond-SemiBold.ttf', '600', 'normal'],
	['EB Garamond', 'EBGaramond-Italic.ttf', '400', 'italic'],
	['Cormorant Garamond', 'Cormorant-MediumItalic.ttf', '500', 'italic'],
];

let loaded = false;
export const loadFonts = () => {
	if (loaded || typeof document === 'undefined') return;
	loaded = true;
	const handle = delayRender('fonts');
	Promise.all(
		FONTS.map(([family, file, weight, style]) => {
			const f = new FontFace(family, `url(${staticFile('fonts/' + file)})`, {weight, style});
			return f.load().then((ff) => document.fonts.add(ff));
		})
	)
		.then(() => continueRender(handle))
		.catch((e) => {
			console.error(e);
			continueRender(handle);
		});
};

export const DISPLAY = 'Cinzel, serif';
export const TEXT = '"EB Garamond", serif';
export const ACCENT = '"Cormorant Garamond", serif';
