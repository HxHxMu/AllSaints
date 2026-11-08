import React from 'react';
import {Composition, Still} from 'remotion';
import {Episode, episodeDuration} from './Episode';
import {Cover} from './Cover';
import sample from './sample.json';

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
		<Still id="Cover" component={Cover} width={1080} height={1920} defaultProps={sample} />
	</>
);
