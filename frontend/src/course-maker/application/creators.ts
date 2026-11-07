export type Creator = Readonly<{
  id: string;
  name: string;
  picture: string | null;
}>;
export type PublishedLesson = Readonly<{
  id: string;
  title: string;
  minutes: number;
  image: string;
  videoUrl: string | null;
  courseId: string | null;
}>;
export type PublishedCourse = Readonly<{
  id: string;
  title: string;
  description: string;
  image: string;
  lessons: readonly PublishedLesson[];
}>;
export type CreatorPage = Readonly<{
  creator: Creator;
  lessons: readonly PublishedLesson[];
  courses: readonly PublishedCourse[];
}>;
export type Discovery = Readonly<{
  lessons: readonly PublishedLesson[];
  courses: readonly PublishedCourse[];
}>;
export interface Creators {
  discover(query?: string): Promise<Discovery>;
  own(): Promise<Creator>;
  save(profile: Pick<Creator, "name" | "picture">): Promise<Creator>;
  page(id: string): Promise<CreatorPage>;
  watch(
    id: string,
    courseId?: string,
  ): Promise<{ creator: Creator | null; lesson: PublishedLesson }>;
}
