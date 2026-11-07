import type {
  Chapter,
  Course,
  CourseDetails,
  Lesson,
  Question,
} from "../domain/course";

export interface CourseRepository {
  list(): Promise<readonly Course[]>;
  getById(id: string): Promise<Course | null>;
  save(course: Course): Promise<void>;
}
export type GeneratedSyllabus = Readonly<{
  image: string;
  chapters: readonly Chapter[];
}>;
export interface SyllabusGenerator {
  generate(details: CourseDetails): Promise<GeneratedSyllabus>;
}
export interface QuizGenerator {
  generate(lesson: Lesson): Promise<readonly Question[]>;
}
export interface IdGenerator {
  next(): string;
}
