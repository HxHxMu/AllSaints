import React from 'react';
import {Composition, Still} from 'remotion';
import {Episode, episodeDuration} from './Episode';
import {Cover} from './Cover';
import sample from './sample.json';
import {Venard, VENARD_FRAMES} from './concept/Venard';

export const Root = () => (
	<>
		<Composition
			id="Episode"
			component={Episode}
			width={1080}
			height={1920}
			fps={30}
			durationInFrames={episodeDuration(sample)}
			defaultProps={sample}
			calculateMetadata={({props}) => ({durationInFrames: episodeDuration(props)})}
		/>
		<Composition id="ConceptVenard" component={Venard} width={1920} height={1080} fps={30} durationInFrames={VENARD_FRAMES} />
		<Still id="Cover" component={Cover} width={1080} height={1920} defaultProps={sample} />
	</>
);
