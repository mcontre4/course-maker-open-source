# Illustrated lesson source handoff

Read ../inputs/*.json and ../hyperframes.json as approved data. The legacy filename
is canonical timing metadata, not a HyperFrames runtime.

The adapter owns src/Root.tsx, src/index.ts, src/timeline.json, src/remotion-env.d.ts,
src/toolkit.css, src/visuals/ApprovedEquation.tsx, src/visuals/RiveIllustration.tsx,
package.json, package-lock.json, tsconfig.json, remotion.config.ts, types/, vendor/,
public/audio/, public/skia/, public/rive/, public/fonts/ and public/illustrations/.
Preserve all these files byte for byte. The scaffold places scenes and unchanged
narration at canonical offsets and holds the last visual through inter-scene silence.

Implement default-exported scenes in src/scenes/<scene_id>.tsx. Source may import
React, Remotion, shapes/paths/rough-notation, local RemotionUI primitives, React Flow,
Rough.js, D3, KaTeX, Lucide, Skia, Three, layout-utils and Lottie. No dependency installs.
Use RiveIllustration from ../visuals/RiveIllustration for generated illustrations;
asset ID, named animation and timing controls are in public/illustrations/manifest.json.
Read public/illustrations/design-system.json for concrete visual tokens. Rive artwork
and editable RML sources are generated per lesson; no stock-art catalog is used.
The trusted helper loads local WASM, disables asset CDN and evaluates absolute frame
positions. Do not use the CDN-loading @remotion/rive component directly.

Inter fonts, KaTeX fonts, CanvasKit and Rive WASM are local. All rendering is offline.
Use Remotion frame primitives, never browser timers or mutable animation state.
Rough.js needs stable seeds. D3 is geometry, not timers. Disable React Flow
interactions/animations and provide explicit node dimensions, positions and viewport.
Skia native animation hooks are unsupported. Every frame must render independently.

Use ApprovedEquation with latex and the exact original equation in verbatim.
Read local cue frames from timeline.json. Write scene-manifest.json preserving every
original field and add visual_event/target per cue; attach literal data-cue-id attributes.
Write IMPLEMENTATION.md. Run node /opt/animator/validate-project.mjs /workspace/remotion.

Preview tools are installed. Render representative frames outside remotion/ with
node /opt/animator/verify-remotion.mjs /workspace/remotion /workspace/preview,
then inspect actual images. The platform separately renders and independently
reviews all scenes, cue changes and seeking before accepting the animation.
Never upload, publish or deploy. Review MP4s belong outside the immutable source tree.
