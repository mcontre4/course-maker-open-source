import { normalizeLessonDetails } from "../application/standalone-lessons";
import { styleFixture } from "./style-fixture";
import { MemoryGenerationPreferences } from "./generation-preferences";
import type {
  CopyLessonRequest,
  CreateLessonRequest,
  SaveOutlineRequest,
  SaveScriptRequest,
  UpdateLessonRequest,
  ReviseLessonRequest,
  StandaloneLessonBackend,
  StandaloneLessonResponse,
  LessonStage,
} from "../application/standalone-lessons";

export class MemoryStandaloneBackend implements StandaloneLessonBackend {
  readonly generationPreferences = new MemoryGenerationPreferences();
  value: StandaloneLessonResponse | null = null;
  created: CreateLessonRequest[] = [];
  planned: ReviseLessonRequest[] = [];
  stages: LessonStage[] = [];
  advanced: (ReviseLessonRequest & { stage: LessonStage })[] = [];
  failPlan = false;
  infeasiblePlan = false;
  failGet = false;
  failOutline = false;
  savedOutlines: SaveOutlineRequest[] = [];
  savedScripts: SaveScriptRequest[] = [];
  failScript = false;
  copied: CopyLessonRequest[] = [];
  failCopy = false;
  copyGate: Promise<void> | null = null;
  async copy(request: CopyLessonRequest) {
    this.copied.push(request);
    await this.copyGate;
    if (this.failCopy) throw new Error("Could not copy lesson. Try again.");
    const old = await this.get();
    this.value = {
      ...old,
      id: "lesson_copy",
      revision: 0,
      turns: [],
      content: {
        ...old.content,
        id: "lesson_copy",
        title: request.title ?? `${old.content.title}-copy`,
      },
    };
    return this.value;
  }
  async saveScript(request: SaveScriptRequest) {
    if (this.failScript) throw new Error("Could not save script. Try again.");
    const old = await this.get();
    if (request.expectedRevision !== old.revision)
      throw new Error("Lesson changed; reload before continuing");
    this.savedScripts.push(request);
    this.value = {
      ...old,
      revision: old.revision + 1,
      playbackContent:
        old.content.animation || old.content.videoUrl
          ? old.content
          : old.playbackContent,
      content: {
        ...old.content,
        storyboard: {
          scenes: request.narrations.map((narrationText) => ({
            narrationText,
          })),
        },
        alignment: null,
        animation: null,
        videoUrl: null,
      },
    };
    return this.value;
  }
  async saveOutline(request: SaveOutlineRequest) {
    if (this.failOutline) throw new Error("Could not save outline. Try again.");
    const old = await this.get();
    if (request.expectedRevision !== old.revision)
      throw new Error("Lesson changed; reload before continuing");
    this.savedOutlines.push(request);
    this.value = {
      ...old,
      revision: old.revision + 1,
      approved: false,
      playbackContent:
        old.content.animation || old.content.videoUrl
          ? old.content
          : old.playbackContent,
      content: {
        ...old.content,
        plan: {
          ...request.outline,
          lessonId: old.id,
          sources: old.content.plan?.sources ?? [],
        },
        storyboard: null,
        alignment: null,
        animation: null,
        videoUrl: null,
      },
    };
    return this.value;
  }
  failUpdate = false;
  thumbnailOperation = "";
  planGate: Promise<void> | null = null;
  advanceGate: Promise<void> | null = null;
  failStage: LessonStage | null = null;
  async list() {
    return this.value ? [this.value] : [];
  }
  async get(): Promise<StandaloneLessonResponse> {
    if (this.failGet)
      throw new Error("Could not verify lesson status. Try again.");
    if (!this.value) throw new Error("Missing lesson");
    return { ...this.value, thumbnailOperation: this.thumbnailOperation };
  }
  async create(request: CreateLessonRequest) {
    const details = normalizeLessonDetails(request);
    this.created.push(request);
    this.value = {
      id: "lesson_one",
      ownerId: "user_one",
      flow: request.flow ?? "guided",
      description: details.description,
      approved: false,
      revision: 0,
      turns: [],
      content: {
        style: request.style ? styleFixture(request.style) : null,
        id: "lesson_one",
        title: details.title,
        topics: [details.title],
        minutes: request.minutes,
        image: "",
        videoUrl: null,
        quiz: [],
        plan: null,
        storyboard: null,
        alignment: null,
        animation: null,
      },
    };
    return this.value;
  }
  async update(request: UpdateLessonRequest) {
    if (this.failUpdate) throw new Error("Could not save draft. Try again.");
    const old = await this.get();
    if (request.expectedRevision !== old.revision)
      throw new Error("Lesson changed; reload before continuing");
    const details = normalizeLessonDetails(request);
    this.value = {
      ...old,
      description: details.description,
      flow: request.flow ?? old.flow,
      revision: old.revision + 1,
      approved: false,
      playbackContent:
        old.content.animation || old.content.videoUrl
          ? old.content
          : old.playbackContent,
      content: {
        ...old.content,
        style: request.style
          ? styleFixture(request.style, (old.content.style?.version ?? 0) + 1)
          : old.content.style,
        title: details.title,
        minutes: request.minutes,
        topics: [details.title],
        plan: null,
        storyboard: null,
        alignment: null,
        animation: null,
        videoUrl: null,
      },
    };
    return this.value;
  }
  async plan(request: ReviseLessonRequest) {
    this.planned.push(request);
    await this.planGate;
    if (this.failPlan)
      throw new Error("Your lesson guide is unavailable. Please retry.");
    const old = await this.get();
    const notes =
      this.planned.length > 1
        ? "Use water to illustrate shared electrons."
        : "Explore how atoms share electrons.";
    this.value = {
      ...old,
      revision: old.revision + 1,
      approved: false,
      turns: [...old.turns, { user: request.message ?? "", assistant: notes }],
      playbackContent:
        old.content.animation || old.content.videoUrl
          ? old.content
          : old.playbackContent,
      content: {
        ...old.content,
        storyboard: null,
        alignment: null,
        animation: null,
        videoUrl: null,
        plan: {
          lessonId: old.id,
          ...(this.infeasiblePlan
            ? {
                feasibilityStatus: "infeasible" as const,
                feasibilityExplanation:
                  "The required explanation needs more time.",
                recommendedVideoMinutes: old.content.minutes + 1,
                recommendedScopeAdjustment:
                  "Move one objective to another lesson.",
              }
            : {}),
          objectives: ["Understand chemical bonds"],
          assumedKnowledge: [],
          introducedKnowledge: ["Bonds"],
          requiredFacts: ["Atoms share electrons"],
          equations: [],
          misconceptions: [],
          scopeBoundaries: ["Keep it introductory"],
          sources: [
            {
              title: "Chemistry reference",
              url: "https://example.com/chemistry",
            },
          ],
          beats: [
            {
              title: "Atoms and bonds",
              purpose: "Explain bonding",
              teachingNotes: notes,
              concepts: [...old.content.topics],
              seconds:
                old.content.minutes * 60 + (this.infeasiblePlan ? 60 : 0),
              checkQuestion: "What is shared?",
              expectedAnswer: "Electrons",
            },
          ],
          examples: [
            {
              problem: "How does water bond?",
              steps: ["Share electrons"],
              result: "A water molecule",
            },
          ],
        },
      },
    };
    return this.value;
  }
  async advance(
    request: ReviseLessonRequest & { stage: LessonStage },
  ): Promise<StandaloneLessonResponse> {
    if (request.stage === "automatic") {
      const current = await this.plan(request);
      if (current.content.plan?.feasibilityStatus === "infeasible")
        return current;
      return this.advance({
        ...request,
        stage: "video",
        expectedRevision: current.revision,
      });
    }
    if (request.stage === "video" || request.stage === "script/generate") {
      let current = await this.get();
      const stages =
        request.stage === "video"
          ? (["approve", "storyboard", "speech", "animation"] as const)
          : (["approve", "storyboard"] as const);
      for (const stage of stages) {
        current = await this.advance({
          ...request,
          expectedRevision: current.revision,
          stage,
        });
      }
      return current;
    }
    this.stages.push(request.stage);
    this.advanced.push(request);
    await this.advanceGate;
    if (this.failStage === request.stage)
      throw new Error("Narration unavailable. Your script is saved.");
    const old = await this.get();
    this.value = {
      ...old,
      approved: true,
      revision: old.revision + 1,
      content: {
        ...old.content,
        storyboard:
          request.stage === "storyboard" && !old.content.storyboard
            ? { scenes: [{ narrationText: "Atoms share electrons." }] }
            : old.content.storyboard,
        alignment:
          request.stage === "speech"
            ? { durationSec: 180 }
            : old.content.alignment,
        animation:
          request.stage === "animation"
            ? {
                status: "animation_ready",
                projectKey: "saved/source",
                prepareElements: request.prepareElements ?? false,
              }
            : old.content.animation,
      },
    };
    return this.value;
  }
}
