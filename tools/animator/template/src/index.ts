import {LoadSkia} from '@shopify/react-native-skia/src/web';
import {cancelRender, registerRoot, staticFile} from 'remotion';
import 'katex/dist/katex.min.css';
import '@xyflow/react/dist/style.css';
import './toolkit.css';
import '@fontsource/inter/400.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';

// Initialize local CanvasKit before evaluating any scene that imports Skia.
LoadSkia({locateFile: (name: string) => staticFile(`skia/${name}`)})
  .then(async () => {
    const {Root} = await import('./Root');
    registerRoot(Root);
  })
  .catch(cancelRender);
