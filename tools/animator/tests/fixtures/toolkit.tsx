import React, {useLayoutEffect} from 'react';
import {useCurrentFrame} from 'remotion';
import {Rect} from '@remotion/shapes';
import {getLength} from '@remotion/paths';
import {Underline} from '@remotion/rough-notation';
import {ThreeCanvas} from '@remotion/three';
import {SkiaCanvas} from '@remotion/skia';
import {Circle as SkiaCircle} from '@shopify/react-native-skia';
import {ReactFlow, MarkerType, Position} from '@xyflow/react';
import rough from 'roughjs';
import {scaleLinear} from 'd3';
import {Circle} from 'lucide-react';
import {ArrowAnnotate} from '../remotion/primitives/arrow-annotate';
import {PathDraw} from '../remotion/primitives/path-draw';
import {ShapeMorph} from '../remotion/primitives/shape-morph';
import {ConnectorLines} from '../remotion/primitives/connector-lines';
import {ApprovedEquation} from '../visuals/ApprovedEquation';
const generator = rough.generator();
const sketch = generator.toPaths(generator.rectangle(30, 30, 200, 100, {seed: 42, stroke: '#387cff', fill: '#d7e7ff'}));
const scale = scaleLinear().domain([0, 90]).range([0, 220]);
const panel: React.CSSProperties = {background: '#fff', padding: 32, height: 350, position: 'relative', overflow: 'hidden'};
export default () => {
  const frame = useCurrentFrame();
  useLayoutEffect(() => {
    const ids = Array.from(document.querySelectorAll('filter[id^="path-draw-glow-"],mask[id^="connector-lines-"]')).map(element => element.id);
    if (new Set(ids).size !== ids.length) throw new Error('RemotionUI SVG ids must be unique per instance');
  }, [frame]);
  return <div data-cue-id="c1" style={{width: 1920, height: 1080, background: '#edf2f8', color: '#172a48', fontFamily: 'sans-serif', padding: 60, boxSizing: 'border-box'}}>
    <h1 style={{fontSize: 48}}>Offline visual toolkit</h1>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24}}>
      <section style={panel}><h2>KaTeX</h2><ApprovedEquation latex="F=ma" verbatim="F = ma"/></section>
      <section style={panel}><h2>RemotionUI + shapes</h2><div style={{display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap'}}><Rect width={80} height={60} fill="#387cff"/><ShapeMorph size={80} shapes={['circle', 'square']} durationInFrames={90}/><ArrowAnnotate width={220} height={110} durationInFrames={30}/><PathDraw d="M10 80Q80 5 150 80" width={160} height={100} durationInFrames={30}/><PathDraw d="M0 0L50 50" width={60} height={60} durationInFrames={30}/><ConnectorLines width={130} height={80} durationInFrames={30} dashed/><ConnectorLines width={130} height={80} durationInFrames={30} dashed/></div></section>
      <section style={panel}><h2>Skia / CanvasKit</h2><SkiaCanvas width={320} height={240}><SkiaCircle cx={160} cy={120} r={50 + frame / 3} color="#387cff"/></SkiaCanvas></section>
      <section style={panel}><h2>React Flow</h2><div style={{width: 440, height: 240}}><ReactFlow
        nodes={[{id: 'a', position: {x: 20, y: 60}, initialWidth: 140, initialHeight: 50, sourcePosition: Position.Right, targetPosition: Position.Left, style: {width: 140, height: 50, fontSize: 28}, data: {label: 'Cause'}}, {id: 'b', position: {x: 260, y: 60}, initialWidth: 140, initialHeight: 50, sourcePosition: Position.Right, targetPosition: Position.Left, style: {width: 140, height: 50, fontSize: 28}, data: {label: 'Effect'}}]}
        edges={[{id: 'ab', source: 'a', target: 'b', animated: false, style: {strokeWidth: 3, stroke: '#387cff'}, markerEnd: {type: MarkerType.ArrowClosed}}]}
        fitView={false} viewport={{x: 0, y: 0, zoom: 1}} nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} panOnDrag={false} zoomOnScroll={false} zoomOnDoubleClick={false}/></div></section>
      <section style={panel}><h2>Rough.js + notation</h2><Underline progress={Math.min(frame / 30, 1)} seed={42} strokeWidth={3} color="#e8a93c" style={{fontSize: 28}}>Frame-driven emphasis</Underline><svg width={320} height={170}>{sketch.map((p, i) => <path key={i} d={p.d} fill={p.fill} stroke={p.stroke} strokeWidth={p.strokeWidth}/>)}</svg></section>
      <section style={panel}><h2>D3 + SVG + Lucide</h2><svg width={320} height={150}><path d="M20 120H300" stroke="#172a48"/><rect x={40} y={120 - scale(frame) / 2} width={80} height={scale(frame) / 2} fill="#387cff"/></svg><Circle size={48}/><ThreeCanvas width={120} height={120} camera={{position: [0, 0, 4], fov: 45}} style={{position: 'absolute', right: 20, top: 80}}><ambientLight intensity={1}/><directionalLight position={[2, 3, 4]} intensity={3}/><mesh rotation={[0.3, frame / 60, 0]}><boxGeometry args={[1.5, 1.5, 1.5]}/><meshStandardMaterial color="#e8b86d"/></mesh></ThreeCanvas><p>Path length: {getLength('M0 0L100 0')}</p></section>
    </div>
  </div>;
};
