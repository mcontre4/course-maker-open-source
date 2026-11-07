import type { GenerationMode } from "./generation-mode";

export type GuideRole = "lesson" | "syllabus" | "storyboard" | "animation";
export type GuideTurn = Readonly<{
  id: string;
  revision: number;
  user: string;
  assistant: string;
}>;
export type GuideChat = Readonly<{
  id: string;
  resourceId: string;
  guide: GuideRole;
  title: string;
  revision: number;
  turns: readonly GuideTurn[];
  hasMore: boolean;
}>;
export type GuideMemory = Readonly<{
  id: string;
  scope: "user" | "lesson";
  key: string;
  content: string;
  sourceMessageId: string;
  revision: number;
}>;
export type OutlineVersion = Readonly<{
  revision: number;
  outlineJson: string;
  description: string;
  sourceMessageId: string;
  createdAt: string;
}>;
export interface Guides {
  list(resourceId: string, guide: GuideRole): Promise<readonly GuideChat[]>;
  create(
    resourceId: string,
    guide: GuideRole,
    title: string,
  ): Promise<GuideChat>;
  get(id: string, before?: number): Promise<GuideChat>;
  send(
    request: Readonly<{
      threadId: string;
      message: string;
      requestId: string;
      expectedRevision: number;
      generationMode: GenerationMode;
    }>,
  ): Promise<GuideChat>;
  memories(resourceId: string): Promise<readonly GuideMemory[]>;
  changeMemory(
    resourceId: string,
    memory: GuideMemory,
    content: string | null,
  ): Promise<void>;
  versions(
    resourceId: string,
    before?: number,
  ): Promise<readonly OutlineVersion[]>;
}
