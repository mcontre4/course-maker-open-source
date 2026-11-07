export type LearningActivityItem = Readonly<{
  itemId: string;
  lastOpenedAt: string;
}>;
export interface LearningActivityLog {
  recent(): Promise<readonly LearningActivityItem[]>;
  record(itemId: string): Promise<void>;
}
