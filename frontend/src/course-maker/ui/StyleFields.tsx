import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { StyleInput } from "../application/style";
import { useApplication } from "./application-context";
import { ErrorNotice } from "./components";

export const emptyStyle: StyleInput = {
  visualStyleId: "",
  reviewOutput: true,
  description: "",
  audience: "",
  voiceId: "",
  accent: "American",
  tone: "",
  pacing: "",
};

const visualStyles = [
  {
    id: "swiss-grid",
    name: "International Typographic Style",
    thumbnail: "/styles/swiss-grid.png",
    contactSheet: false,
    description:
      "Tight grotesk headlines, precise modular grids and red-black offset printing",
  },
  {
    id: "bauhaus",
    name: "Bauhaus Poster",
    thumbnail: "/styles/bauhaus.png",
    contactSheet: false,
    description:
      "Primary geometric forms, strict grids and lithographic ink on aged cream paper",
  },
  {
    id: "memphis",
    name: "Memphis Group",
    thumbnail: "/styles/memphis.png",
    contactSheet: false,
    description:
      "Clashing pastels and primaries, bold outlines, terrazzo patterns and bouncy cut-out motion",
  },
  {
    id: "risograph",
    name: "Risograph Zine",
    thumbnail: "/styles/risograph.png",
    contactSheet: false,
    description:
      "Fluorescent spot inks, misregistered plates and grainy textures on off-white paper",
  },
  {
    id: "gouache-poster",
    name: "Gouache Travel Poster",
    thumbnail: "/styles/gouache-poster.png",
    contactSheet: false,
    description:
      "Opaque matte colors, dry-brush edges and bold mid-century poster lettering",
  },
  {
    id: "soft-3d",
    name: "Soft 3D Clay",
    thumbnail: "/styles/soft-3d.png",
    contactSheet: false,
    description:
      "Puffy pastel clay forms, soft shadows and springy squash-and-stretch motion",
  },
  {
    id: "halftone-pop",
    name: "Halftone Pop Panel",
    thumbnail: "/styles/halftone-pop.png",
    contactSheet: false,
    description:
      "Bold comic panels, Ben-Day dots and punchy speech balloons on aged paper",
  },
  {
    id: "whiteboard",
    name: "Whiteboard Explainer",
    thumbnail: "/styles/whiteboard.png",
    contactSheet: false,
    description:
      "Hand-drawn marker diagrams, eraser ghosts and a glossy whiteboard",
  },
  {
    id: "tech-glow",
    name: "Tech Glow Explainer",
    thumbnail: "/styles/tech-glow.png",
    contactSheet: false,
    description:
      "Neon diagrams, gradient lettering and electric glows in deep indigo space",
  },
  {
    id: "flat-vector-science",
    name: "Flat-Vector Science",
    thumbnail: "/styles/flat-vector-science.png",
    contactSheet: true,
    description: "Colorful illustrations on a navy-to-violet backdrop",
  },
  {
    id: "watercolor-wash",
    name: "Watercolor Wash",
    thumbnail: "/styles/watercolor-wash.png",
    contactSheet: false,
    description:
      "Layered pigment, pencil sketches and brush lettering on textured paper",
  },
];

export function visualStyleName(id?: string) {
  return visualStyles.find((style) => style.id === id)?.name;
}

export function StyleFields({
  value,
  onChange,
  label = "Lesson style",
  disabled = false,
  currentVoiceName,
  recommendedVoiceId,
  embedded = false,
  prominentAudience = false,
  focus,
}: {
  value: StyleInput;
  onChange(value: StyleInput): void;
  label?: string;
  disabled?: boolean;
  currentVoiceName?: string;
  recommendedVoiceId?: string;
  embedded?: boolean;
  /** The caller renders the audience field prominently, so omit it here. */
  prominentAudience?: boolean;
  focus?: "voice" | "visuals";
}) {
  const id = useId();
  const app = useApplication();
  const [customize, setCustomize] = useState(false);
  const voices = useQuery({
    queryKey: ["voices"],
    queryFn: () => app.styles!.voices.execute(),
    enabled: (customize || embedded) && focus !== "visuals" && !!app.styles,
    staleTime: 300000,
    retry: false,
  });
  const accent = value.accent ?? "American";
  const voiceAccent = (labels: readonly string[]) =>
    labels
      .find((label) => label.toLowerCase().startsWith("accent:"))
      ?.split(":")
      .slice(1)
      .join(":")
      .trim();
  const available =
    voices.data?.filter(
      (voice) =>
        voiceAccent(voice.labels)?.toLowerCase() === accent.toLowerCase(),
    ) ?? [];
  const selected = available.find(
    (voice) => voice.id === (value.voiceId || recommendedVoiceId),
  );
  const accents = Array.from(
    new Set([
      "American",
      accent,
      ...(voices.data?.flatMap((voice) => {
        const item = voiceAccent(voice.labels);
        return item
          ? [item.charAt(0).toUpperCase() + item.slice(1).toLowerCase()]
          : [];
      }) ?? []),
    ]),
  ).sort();
  const tones = ["Warm", "Professional", "Calm", "Energetic", "Storytelling"];
  const [customTone, setCustomTone] = useState(false);
  const isCustomTone =
    customTone || (!!value.tone && !tones.includes(value.tone));
  const visualStylePicker = (
    <fieldset className="visual-style-picker" disabled={disabled}>
      <legend>{focus ? "Choose a look" : "Visual style (required)"}</legend>
      <p id={id + "-visual-help"} className="muted small">
        Choose a thumbnail to set the look of your video.
      </p>
      <div
        className="visual-style-gallery"
        role="group"
        aria-label="Visual styles"
        aria-describedby={id + "-visual-help"}
      >
        {visualStyles.map((style) => (
          <label className="visual-style-option" key={style.id}>
            <input
              type="radio"
              name={id + "-visual"}
              value={style.id}
              checked={value.visualStyleId === style.id}
              required
              onChange={() => onChange({ ...value, visualStyleId: style.id })}
            />
            <span className="visual-style-thumbnail" aria-hidden="true">
              <img
                className={
                  style.contactSheet ? "style-contact-sheet" : undefined
                }
                src={style.thumbnail}
                alt=""
                loading="lazy"
              />
            </span>
            <span className="visual-style-name">{style.name}</span>
            <span className="visual-style-description">
              {style.description}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
  const fields = (
    <fieldset className="style-fields" disabled={disabled}>
      <legend className="sr-only">{label}</legend>
      <section
        className="advanced-settings-section"
        aria-label="Style and pacing"
      >
        {!focus && <h3>Style and pacing</h3>}
        {embedded && focus !== "voice" && visualStylePicker}
        {focus !== "voice" && (
          <>
            <label htmlFor={id + "-description"}>
              {focus === "visuals"
                ? "Visual instructions"
                : "Teaching tone and preferences (optional)"}
            </label>
            <textarea
              id={id + "-description"}
              rows={2}
              maxLength={2000}
              value={value.description}
              onChange={(event) =>
                onChange({ ...value, description: event.target.value })
              }
              placeholder={
                focus === "visuals"
                  ? "e.g. Simple diagrams with labeled parts and gentle movement"
                  : "e.g. Curious and conversational, with concrete examples"
              }
            />
            <label className="review-output-choice" htmlFor={id + "-review"}>
              <input
                id={id + "-review"}
                type="checkbox"
                checked={value.reviewOutput !== false}
                onChange={(event) =>
                  onChange({ ...value, reviewOutput: event.target.checked })
                }
              />
              AI review before delivery
            </label>
            <p className="muted small">
              One visual review and, if needed, one repair pass before delivery.
              Turn off for faster generation if you prefer to review the video
              yourself.
            </p>
          </>
        )}
        {focus !== "visuals" && (
          <>
            <label htmlFor={id + "-pacing"}>Pacing</label>
            <select
              id={id + "-pacing"}
              value={value.pacing ?? ""}
              onChange={(event) =>
                onChange({ ...value, pacing: event.target.value })
              }
            >
              <option value="">Automatic — match topic and audience</option>
              {["Relaxed", "Natural", "Brisk"].map((pace) => (
                <option key={pace}>{pace}</option>
              ))}
            </select>
          </>
        )}
      </section>
      {!prominentAudience && !focus && (
        <section className="advanced-settings-section" aria-label="Audience">
          <h3>Audience</h3>
          <label htmlFor={id + "-audience"}>Who is this for?</label>
          <input
            id={id + "-audience"}
            maxLength={2000}
            value={value.audience}
            onChange={(event) =>
              onChange({ ...value, audience: event.target.value })
            }
            placeholder="e.g. Children aged 8–10, or professionals new to the topic"
          />
        </section>
      )}
      {focus !== "visuals" && (
        <section
          className="advanced-settings-section"
          aria-label="Voice and tone"
        >
          <h3>Voice and tone</h3>
          <label htmlFor={id + "-accent"}>Accent</label>
          <select
            id={id + "-accent"}
            value={accent}
            onChange={(event) =>
              onChange({ ...value, accent: event.target.value, voiceId: "" })
            }
          >
            {accents.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <p className="muted small">
            American is the default. Voices follow your selected accent.
          </p>
          <label htmlFor={id + "-tone"}>Tone</label>
          <select
            id={id + "-tone"}
            value={isCustomTone ? "custom" : (value.tone ?? "")}
            onChange={(event) => {
              setCustomTone(event.target.value === "custom");
              onChange({
                ...value,
                tone: event.target.value === "custom" ? "" : event.target.value,
              });
            }}
          >
            <option value="">Automatic — match topic and audience</option>
            {tones.map((tone) => (
              <option key={tone}>{tone}</option>
            ))}
            <option value="custom">Custom instruction</option>
          </select>
          {isCustomTone && (
            <>
              <label htmlFor={id + "-custom-tone"}>Custom tone</label>
              <input
                id={id + "-custom-tone"}
                maxLength={100}
                value={value.tone ?? ""}
                pattern={"[^\\[\\]\\r\\n]*"}
                placeholder="e.g. Reassuring and curious, with gentle emphasis"
                onChange={(event) =>
                  onChange({ ...value, tone: event.target.value })
                }
              />
            </>
          )}
          {app.styles && (
            <>
              <label htmlFor={id + "-voice"}>Narrator voice</label>
              <select
                id={id + "-voice"}
                value={value.voiceId}
                onChange={(event) =>
                  onChange({ ...value, voiceId: event.target.value })
                }
              >
                <option value="">Recommend a voice for this style</option>
                {value.voiceId &&
                  !available.some((voice) => voice.id === value.voiceId) && (
                    <option value={value.voiceId}>
                      {currentVoiceName || "Current narrator"}
                    </option>
                  )}
                {available.map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.name}
                  </option>
                ))}
              </select>
              {voices.isPending && (
                <p className="muted small" role="status">
                  Loading narrator voices…
                </p>
              )}
              <ErrorNotice error={voices.error} />
              {voices.isError && (
                <button type="button" onClick={() => void voices.refetch()}>
                  Retry voices
                </button>
              )}
              {voices.data?.some((voice) =>
                voice.labels.includes("catalog_permission_required"),
              ) && (
                <p role="status" className="muted small">
                  The ElevenLabs key needs voices_read permission to browse
                  narrators and verify their accents. Enable it to choose a
                  matching narrator.
                </p>
              )}
              {voices.isSuccess && available.length === 0 && (
                <p className="muted small">
                  No verified {accent} voices are available. Choose another
                  accent or check the ElevenLabs configuration.
                </p>
              )}
              {selected && (
                <div className="voice-preview">
                  <p className="small">
                    {selected.description || selected.labels.join(" · ")}
                  </p>
                  {selected.previewUrl ? (
                    <audio
                      key={selected.id}
                      controls
                      preload="none"
                      src={selected.previewUrl}
                      aria-label={`Preview ${selected.name}`}
                    />
                  ) : (
                    <p className="muted small">
                      No sample is available for this voice.
                    </p>
                  )}
                  <p className="muted small">
                    Voice sample only. Your lesson’s tone and pacing are applied
                    during generation.
                  </p>
                </div>
              )}
            </>
          )}
        </section>
      )}
    </fieldset>
  );
  return embedded ? (
    fields
  ) : (
    <>
      {visualStylePicker}
      <details
        className="advanced-settings"
        onToggle={(event) => setCustomize(event.currentTarget.open)}
      >
        <summary>
          {prominentAudience
            ? "Voice & delivery preferences"
            : "Advanced settings"}
        </summary>
        {fields}
      </details>
    </>
  );
}
