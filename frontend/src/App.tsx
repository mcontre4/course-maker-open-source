import { InternalToolsPage } from "./course-maker/ui/pages/InternalToolsPage";
import { COURSE_CREATION_ENABLED } from "./course-maker/ui/feature-flags";
import { CreateLessonPage } from "./course-maker/ui/pages/CreateLessonPage";
import { StandaloneLessonPage } from "./course-maker/ui/pages/StandaloneLessonPage";
import { PreparePage } from "./course-maker/ui/pages/PreparePage";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout, LinkButton } from "./course-maker/ui/components";
import { HomePage } from "./course-maker/ui/pages/HomePage";
import { CreateCoursePage } from "./course-maker/ui/pages/CreateCoursePage";
import { SyllabusPage } from "./course-maker/ui/pages/SyllabusPage";
import { LessonPage } from "./course-maker/ui/pages/LessonPage";

import { ProfileProvider } from "./course-maker/ui/profile-context";
import type { ProfileStore } from "./course-maker/application/profile";
import { SettingsPage } from "./course-maker/ui/pages/SettingsPage";
import { CreditsPage } from "./course-maker/ui/pages/CreditsPage";
import { LibraryPage } from "./course-maker/ui/pages/LibraryPage";
import { ExplorePage } from "./course-maker/ui/pages/ExplorePage";
import { ExploreTopicPage } from "./course-maker/ui/pages/ExploreTopicPage";

import { CreatorProfilePage } from "./course-maker/ui/pages/CreatorProfilePage";
import { PublicLessonPage } from "./course-maker/ui/pages/PublicLessonPage";
import { AuthenticationGate } from "./course-maker/ui/authentication";
import { AuthenticationPage } from "./course-maker/ui/pages/AuthenticationPage";
import {
  CourseInteractiveStudioPage,
  StandaloneInteractiveStudioPage,
} from "./course-maker/ui/pages/InteractiveStudioPage";

export default function App({ profileStore }: { profileStore?: ProfileStore }) {
  return (
    <ProfileProvider store={profileStore}>
      <Layout>
        <AuthenticationGate>
          <Routes>
            <Route
              path="/login"
              element={<AuthenticationPage key="login" mode="login" />}
            />
            <Route
              path="/signup"
              element={<AuthenticationPage key="signup" mode="signup" />}
            />
            <Route
              path="/forgot-password"
              element={
                <AuthenticationPage key="forgot" mode="forgot-password" />
              }
            />
            <Route
              path="/verify-email"
              element={<AuthenticationPage key="verify" mode="verify-email" />}
            />
            <Route
              path="/reset-password"
              element={<AuthenticationPage key="reset" mode="reset-password" />}
            />
            <Route
              path="/creators/:creatorId"
              element={<CreatorProfilePage />}
            />
            <Route
              path="/watch/lessons/:lessonId"
              element={<PublicLessonPage />}
            />
            <Route path="/" element={<HomePage />} />
            <Route path="/explore" element={<ExplorePage />} />
            <Route path="/explore/:topicSlug" element={<ExploreTopicPage />} />
            <Route path="/lessons/new" element={<CreateLessonPage />} />
            <Route
              path="/lessons/:lessonId/edit"
              element={<CreateLessonPage />}
            />
            <Route
              path="/lessons/:lessonId"
              element={<StandaloneLessonPage />}
            />
            <Route
              path="/lessons/:lessonId/interactives/:interactiveId"
              element={<StandaloneInteractiveStudioPage />}
            />
            <Route path="/internal/tools" element={<InternalToolsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/credits" element={<CreditsPage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route
              path="/my-courses"
              element={<Navigate to="/library" replace />}
            />
            <Route path="/workspace" element={<LibraryPage workspace />} />
            {COURSE_CREATION_ENABLED ? (
              <>
                <Route path="/courses/new" element={<CreateCoursePage />} />
                <Route
                  path="/courses/:courseId/edit"
                  element={<CreateCoursePage />}
                />
                <Route
                  path="/courses/:courseId/syllabus"
                  element={<SyllabusPage />}
                />
                <Route
                  path="/courses/:courseId/prepare"
                  element={<PreparePage />}
                />
                <Route
                  path="/courses/:courseId/lessons/:lessonId"
                  element={<LessonPage />}
                />
                <Route
                  path="/courses/:courseId/lessons/:lessonId/interactives/:interactiveId"
                  element={<CourseInteractiveStudioPage />}
                />
              </>
            ) : null}
            <Route
              path="*"
              element={
                <div className="status-panel">
                  <h1>We couldn’t find that page.</h1>
                  <LinkButton to="/">Back to my learning</LinkButton>
                </div>
              }
            />
          </Routes>
        </AuthenticationGate>
      </Layout>
    </ProfileProvider>
  );
}
