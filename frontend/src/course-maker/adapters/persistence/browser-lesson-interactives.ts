import type {
  InteractiveRef,
  LearnerInteractiveApplication,
  LessonInteractiveBackend,
} from "../../application/lesson-interactives";
import type { IdGenerator } from "../../application/ports";
import {
  LessonInteractiveError,
  interactiveBuildStages,
  interactiveLimits,
  learnerView,
  type LearnerInteractive,
  type LessonInteractive,
} from "../../domain/lesson-interactive";
import {
  sampleInteractiveDetails,
  sampleInteractiveHtml,
} from "../demo/sample-interactive";
import type { KeyValueStorage } from "./browser-course-repository";

const key = (lessonId: string) =>
  `course-maker:lesson-interactives:${lessonId}`;
const stageMilliseconds = 1500;

/**
 * Keeps interactives in this browser and acts out background builds until the
 * server can do both. A build finishes when it is next read after enough time
 * has passed, so a page reload never loses it. A request containing "#fail"
 * ends in a failed build, so that path can be tried by hand.
 */
export class BrowserLessonInteractives implements LessonInteractiveBackend {
  /** Only what could not be written to storage, which makes it the newest copy. */
  private readonly memory = new Map<string, readonly LessonInteractive[]>();
  constructor(
    private readonly storage: KeyValueStorage,
    private readonly ids: IdGenerator,
    private readonly now: () => Date,
  ) {}

  private read(lessonId: string): readonly LessonInteractive[] {
    const unsaved = this.memory.get(lessonId);
    if (unsaved) return unsaved;
    try {
      const raw = this.storage.getItem(key(lessonId));
      const items: unknown = raw ? JSON.parse(raw) : [];
      if (Array.isArray(items)) return items as readonly LessonInteractive[];
    } catch {
      /* Unreadable storage starts the lesson's list afresh. */
    }
    return [];
  }

  private write(lessonId: string, items: readonly LessonInteractive[]) {
    try {
      this.storage.setItem(key(lessonId), JSON.stringify(items));
      this.memory.delete(lessonId);
    } catch {
      // Kept for this session only.
      this.memory.set(lessonId, items);
    }
  }

  /** Moves any running builds along to where the clock says they should be. */
  private settled(lessonId: string): readonly LessonInteractive[] {
    const items = this.read(lessonId);
    const next = items.map((item) => this.advance(item));
    if (next.some((item, index) => item !== items[index]))
      this.write(lessonId, next);
    return next;
  }

  private advance(item: LessonInteractive): LessonInteractive {
    if (!item.build) return item;
    const elapsed = this.now().getTime() - Date.parse(item.build.startedAt);
    const stage = Math.floor(elapsed / stageMilliseconds);
    if (stage < interactiveBuildStages.length) {
      const name = interactiveBuildStages[stage];
      return name === item.build.stage
        ? item
        : { ...item, build: { ...item.build, stage: name } };
    }
    const { request } = item.build;
    if (request.includes("#fail"))
      return {
        ...item,
        build: null,
        failure: {
          request,
          message:
            "The build stopped before it finished. Nothing in your lesson changed.",
        },
      };
    const number = item.versions.length
      ? Math.max(...item.versions.map((version) => version.number)) + 1
      : 1;
    // A change builds on the version on screen, not on ones gone back from.
    const requests = [
      ...item.versions
        .filter((version) => version.number <= (item.currentVersion ?? 0))
        .map((version) => version.request),
      request,
    ];
    const first = item.versions.length === 0;
    return {
      ...item,
      ...(first ? sampleInteractiveDetails() : {}),
      versions: [
        ...item.versions,
        { number, request, createdAt: this.now().toISOString() },
      ],
      currentVersion: number,
      html: sampleInteractiveHtml(requests),
      build: null,
      failure: null,
      revision: item.revision + 1,
      updatedAt: this.now().toISOString(),
    };
  }

  private update(
    ref: InteractiveRef,
    change: (item: LessonInteractive) => LessonInteractive,
    expectedRevision?: number,
  ): LessonInteractive {
    const items = this.settled(ref.lessonId);
    const item = items.find((candidate) => candidate.id === ref.id);
    if (!item)
      throw new LessonInteractiveError("This interactive could not be found.");
    if (expectedRevision !== undefined && item.revision !== expectedRevision)
      throw new LessonInteractiveError(
        "This interactive changed in another tab. Reload and try again.",
      );
    const updated = {
      ...change(item),
      revision: item.revision + 1,
      updatedAt: this.now().toISOString(),
    };
    this.write(
      ref.lessonId,
      items.map((candidate) => (candidate.id === ref.id ? updated : candidate)),
    );
    return updated;
  }

  private startBuild(request: string) {
    return {
      request,
      stage: interactiveBuildStages[0],
      startedAt: this.now().toISOString(),
    };
  }

  async list(lessonId: string) {
    return this.settled(lessonId);
  }

  async get(ref: InteractiveRef) {
    const item = this.settled(ref.lessonId).find(
      (candidate) => candidate.id === ref.id,
    );
    if (!item)
      throw new LessonInteractiveError("This interactive could not be found.");
    return item;
  }

  async create(request: { lessonId: string; brief: string }) {
    const items = this.settled(request.lessonId);
    if (items.length >= interactiveLimits.perLesson)
      throw new LessonInteractiveError(
        `A lesson can have up to ${interactiveLimits.perLesson} interactives.`,
      );
    const now = this.now().toISOString();
    const created: LessonInteractive = {
      id: "interactive_" + this.ids.next(),
      lessonId: request.lessonId,
      brief: request.brief,
      title: "New interactive",
      goal: "",
      prompts: [],
      versions: [],
      currentVersion: null,
      html: null,
      publishedVersion: null,
      publishedHtml: null,
      build: this.startBuild(request.brief),
      failure: null,
      revision: 0,
      createdAt: now,
      updatedAt: now,
    };
    this.write(request.lessonId, [...items, created]);
    return created;
  }

  async requestChange(
    request: InteractiveRef & { instruction: string; expectedRevision: number },
  ) {
    return this.update(
      request,
      (item) => {
        if (item.build)
          throw new LessonInteractiveError(
            "Wait for the current build to finish first.",
          );
        return {
          ...item,
          build: this.startBuild(request.instruction),
          failure: null,
        };
      },
      request.expectedRevision,
    );
  }

  async retryBuild(ref: InteractiveRef) {
    return this.update(ref, (item) => {
      if (item.build || !item.failure) return item;
      return {
        ...item,
        // A retry drops the marker, so the failed path can be tried by hand once.
        build: this.startBuild(
          item.failure.request.replace("#fail", "").trim(),
        ),
        failure: null,
      };
    });
  }

  async cancelBuild(ref: InteractiveRef) {
    return this.update(ref, (item) => {
      if (!item.build) return item;
      return {
        ...item,
        build: null,
        failure: {
          request: item.build.request,
          message: "You stopped this build. Your description is saved.",
        },
      };
    });
  }

  async saveDetails(
    request: InteractiveRef & {
      details: Pick<LessonInteractive, "title" | "goal" | "prompts">;
      expectedRevision: number;
    },
  ) {
    return this.update(
      request,
      (item) => ({ ...item, ...request.details }),
      request.expectedRevision,
    );
  }

  async restoreVersion(
    request: InteractiveRef & { version: number; expectedRevision: number },
  ) {
    return this.update(
      request,
      (item) => {
        const requests = item.versions
          .filter((version) => version.number <= request.version)
          .map((version) => version.request);
        return {
          ...item,
          currentVersion: request.version,
          html: sampleInteractiveHtml(requests),
          failure: null,
        };
      },
      request.expectedRevision,
    );
  }

  async setPublishedVersion(
    request: InteractiveRef & { version: number | null },
  ) {
    return this.update(request, (item) =>
      request.version === null
        ? { ...item, publishedVersion: null, publishedHtml: null }
        : {
            ...item,
            publishedVersion: request.version,
            publishedHtml:
              request.version === item.currentVersion
                ? item.html
                : item.publishedHtml,
          },
    );
  }

  async reorder(lessonId: string, orderedIds: readonly string[]) {
    const items = this.settled(lessonId);
    const place = (id: string) => {
      const at = orderedIds.indexOf(id);
      return at < 0 ? orderedIds.length : at;
    };
    const next = [...items].sort((a, b) => place(a.id) - place(b.id));
    this.write(lessonId, next);
    return next;
  }

  async remove(ref: InteractiveRef) {
    this.write(
      ref.lessonId,
      this.settled(ref.lessonId).filter((item) => item.id !== ref.id),
    );
  }

  /** The published view is what a learner would receive from the server. */
  learnerList(lessonId: string): readonly LearnerInteractive[] {
    return this.settled(lessonId)
      .map(learnerView)
      .filter((item): item is LearnerInteractive => !!item);
  }
}

export function browserLearnerInteractives(
  store: BrowserLessonInteractives,
): LearnerInteractiveApplication {
  return { list: async (lessonId) => store.learnerList(lessonId) };
}
