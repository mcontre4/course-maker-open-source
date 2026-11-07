import React, {useEffect, useLayoutEffect, useRef, useState} from 'react';
import createRive, {RiveCanvas, File as RiveFile} from '@rive-app/canvas-advanced';
import {cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

let runtime: Promise<RiveCanvas> | undefined;
const loadRuntime = () => runtime ??= createRive({locateFile: () => staticFile('rive/rive.wasm')});

/** Adapter-owned: local WASM, no CDN, no wall clock; a fresh artboard per sought frame. */
const RiveAsset: React.FC<{
  asset: string; animation: string; width: number; height: number;
  artboard?: string; startFrame?: number; playbackRate?: number; loopSeconds?: number;
}> = ({asset, animation, width, height, artboard: name, startFrame = 0, playbackRate = 1, loopSeconds}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [handle] = useState(() => delayRender('Loading local Rive illustration'));
  const [loaded, setLoaded] = useState<{api: RiveCanvas; file: RiveFile} | null>(null);
  useEffect(() => {
    let cancelled = false;
    let file: RiveFile | undefined;
    Promise.all([loadRuntime(), fetch(staticFile(`illustrations/${asset}.riv`)).then(r => {
      if (!r.ok) throw new Error('Missing local Rive asset');
      return r.arrayBuffer();
    })]).then(async ([api, bytes]) => {
      file = await api.load(new Uint8Array(bytes), undefined, false);
      if (cancelled) {file.unref(); return;}
      setLoaded({api, file});
    }).catch(cancelRender);
    return () => {cancelled = true; file?.unref(); continueRender(handle);};
  }, [asset, handle]);
  useLayoutEffect(() => {
    if (!loaded || !canvas.current) return;
    const {api, file} = loaded;
    const board = name ? file.artboardByName(name) : file.defaultArtboard();
    if (!board) {cancelRender(new Error('Missing Rive artboard')); return;}
    const timeline = board.animationByName(animation);
    if (!timeline) {board.delete(); cancelRender(new Error('Missing Rive animation')); return;}
    const instance = new api.LinearAnimationInstance(timeline, board);
    const seconds = Math.max(0, frame - startFrame) / fps * playbackRate;
    instance.time = loopSeconds ? seconds % loopSeconds : seconds;
    instance.apply(1);
    board.advance(0);
    const renderer = api.makeRenderer(canvas.current);
    renderer.clear();
    renderer.save();
    renderer.align(api.Fit.contain, api.Alignment.center,
      {minX: 0, minY: 0, maxX: width, maxY: height}, board.bounds);
    board.draw(renderer);
    renderer.restore();
    api.resolveAnimationFrame();
    continueRender(handle);
    return () => {renderer.delete(); instance.delete(); board.delete();};
  }, [loaded, frame, fps, width, height, name, animation, startFrame, playbackRate, loopSeconds, handle]);
  return <canvas ref={canvas} width={width} height={height} style={{width, height, display: 'block'}}/>;
};

// A changed asset needs a fresh loading gate and file lifetime before frame capture.
export const RiveIllustration: React.FC<React.ComponentProps<typeof RiveAsset>> = props =>
  <RiveAsset {...props} key={props.asset}/>;
