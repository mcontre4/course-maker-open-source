from dataclasses import dataclass

from app.courses.domain.errors import CourseError


@dataclass(frozen=True)
class VisualStyle:
    id: str = "flat-vector-science"
    version: int = 1

    def __post_init__(self) -> None:
        if (
            self.id
            not in (
                "flat-vector-science",
                "watercolor-wash",
                "tech-glow",
                "whiteboard",
                "halftone-pop",
                "risograph",
                "gouache-poster",
                "soft-3d",
                "memphis",
                "bauhaus",
                "swiss-grid",
            )
            or self.version != 1
        ):
            raise CourseError("Choose an available visual style and version")

    def direction(self) -> str:
        if self.id == "swiss-grid":
            return (
                "International Typographic Style v1 (Art & Design Movements): a "
                "1960s Zürich-school poster on a strict 12-column grid, enormous "
                "flush-left Inter headlines with tight tracking, precise information "
                "blocks and asymmetric concentric arc segments over a red disc. "
                "Use red, black and off-white only. Rules draw out, arc segments "
                "decelerate onto 22.5-degree modules, headline lines rise through "
                "baseline masks and the hook shrinks into a running header. Change "
                "pages with column-by-column wipes, show cause with hairline rules "
                "and solid arrowheads, count in Inter 800 and slam a red block behind "
                "the key result. Preserve offset ink dropouts, dot gain, paper fibres "
                "and grain; illustrate the lesson accurately rather than copying "
                "the AI topic, pictograms or illustrative statistics."
            )
        if self.id == "bauhaus":
            return (
                "Bauhaus Poster v1 (Art & Design Movements): primary red, yellow and "
                "blue plus black on aged cream stock, strict grids, circles, squares, "
                "semicircles and triangles, constructed geometric lettering and "
                "Space Grotesk labels/counters with Syne accents. Track one long "
                "Bayer-style information-design sheet and pull back for the takeaway. "
                "Grid rules draw out, geometric subjects stamp and snap into place, "
                "bar-and-triangle arrows grow, tags drop onto what they name and a "
                "red ring emphasizes the key moment. Preserve separate lithographic "
                "plates, knockouts, misregistration, ink mottle, aged paper, fold wear "
                "and grain. Draw accurate lesson-specific subjects rather than copying "
                "the reference's robot, pets or AI topic."
            )
        if self.id == "memphis":
            return (
                "Memphis Group v1 (Art & Design Movements): early-80s Memphis Milano "
                "maximalism, pastel grounds clashing with bold primaries, thick black "
                "outlines and hard offset shadows. Squiggles, zigzags, dot grids, "
                "terrazzo chips and confetti surround Rubik Mono One headlines and "
                "Fredoka sticker labels. Cut-out cel motion steps at 12 fps with springy "
                "overshoot, squash-and-stretch and off-beat bobs. Change scenes with "
                "striped polka-dot band swipes; use fat outlined arrows, popping "
                "sticker counters and spinning starbursts for emphasis. Preserve the "
                "reference patterns and full grain pass; draw accurate lesson-specific "
                "subjects rather than copying the AI computer or pet examples."
            )
        if self.id == "risograph":
            return (
                "Risograph Zine v1 (Print): fluorescent pink, blue and yellow spot inks "
                "multiplied on off-white stock, misregistered plates, patchy solids, "
                "dotted tints and roller streaks. Archivo Black headlines and Space Mono "
                "labels; big two-plate counters, dotted blue flow arrows and pink "
                "scribbled emphasis. Scene changes re-register each drum pass in turn; "
                "ink boils at 8 fps. Preserve the reference's full ink/paper compositor. "
                "Draw accurate lesson-specific subjects rather than copying the AI example."
            )
        if self.id == "gouache-poster":
            return (
                "Gouache Travel Poster v1 (Painterly): mid-century hand-painted posters "
                "with six opaque matte colours, receding flat layers, dry-brush edges, "
                "chalky pigment and board grain. Bebas Neue headlines and Oswald labels; "
                "parallax layers, flat poster arrows, repainted numbers in a lettering "
                "band and orange starbursts. Sweep a fresh cream coat for scene changes. "
                "Preserve the reference painter and finishing passes. Illustrate the "
                "lesson accurately rather than copying the AI or power-station example."
            )
        if self.id == "soft-3d":
            return (
                "Soft 3D Clay v1 (Dimensional): pastel matte-clay forms with rounded "
                "extrusions, core shadows, bounce-light rims, glossy highlights and "
                "blurry contact shadows on a seamless lavender sweep. Fredoka lettering, "
                "squishy label pills, butter-yellow number badges and puffy tube arrows. "
                "Springy squash-and-stretch and continuous camera dollies across a wide "
                "set with parallax depth of field. Preserve the reference shading and "
                "grain at full strength; use accurate lesson-specific subjects."
            )
        if self.id == "halftone-pop":
            return (
                "Halftone Pop Panel v1 (Print): bold comic panels with fat tapering "
                "black brush outlines, mechanical red/blue Ben-Day dots, primary yellow, "
                "Bangers lettering, caption boxes, speech balloons and explosion counters. "
                "Read a continuous comic strip panel by panel, pulling back to reveal "
                "gutters; use yellow comic arrows, emphatic bursts and purposeful shake. "
                "Use separate colour/key plates with the reference's misregistration, "
                "aged paper and fibre-grain finishing. Preserve lesson accuracy and "
                "invent appropriate subjects rather than copying the robot/AI example."
            )
        if self.id == "whiteboard":
            return (
                "Whiteboard Explainer v1 (Hand-Drawn): dry-erase marker on a glossy "
                "whiteboard, streaky chisel-tip strokes with pooled edges, wobbly "
                "double-traced boxes and arrows, erased ghost residue and ceiling-light "
                "sheen. Permanent Marker titles/numbers and Kalam labels draw on "
                "letter by letter. Follow the marker across one continuous board; "
                "use felt-eraser wipes leaving residue for meaningful scene changes. "
                "Use the bundled executable reference and full gloss/grain passes. "
                "Draw accurate lesson-specific subjects rather than copying the AI example."
            )
        if self.id == "tech-glow":
            return (
                "Tech Glow Explainer v1: deep navy-to-indigo space, drifting electric "
                "glows, perspective grids, gradient-stroked icon tiles, neon-bordered "
                "dark cards and node diagrams with light pulses along connectors. "
                "Inter labels and gradient Space Grotesk headlines and counters; "
                "smooth overshoot builds, continuous camera pushes and light-speed "
                "transitions. Use the bundled executable reference and full bloom "
                "and vignette finishing passes. Illustrate the lesson accurately; "
                "do not carry over the example's AI topic unless appropriate."
            )
        if self.id == "watercolor-wash":
            return (
                "Watercolor Wash v1 (Painterly): transparent layered pigment on cold-press "
                "paper, ragged pooled edges, wet-in-wet bleeds, cauliflower blooms, "
                "granulation, untouched paper highlights and faint pencil sketches. "
                "Caveat brush lettering, loaded round-brush arrows, alizarin emphasis "
                "circles, flooding washes and continuous sketchbook camera pans. "
                "Use the bundled executable style reference and its finishing passes. "
                "Draw subjects appropriate to the lesson and preserve scientific accuracy."
            )
        return (
            "Flat-Vector Science v1: navy-to-violet gradients, original rounded vector "
            "illustrations, rich gradients, crescent shadows, rim highlights, radial glows, "
            "seeded grain, Nunito/Fredoka lettering, dotted arrows and smooth eased motion. "
            "Use the bundled executable style reference. Draw subjects appropriate to the "
            "lesson; space decoration must not misrepresent geography or science."
        )
