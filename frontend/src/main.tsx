import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { BrowserModelPreferences } from "./course-maker/adapters/persistence/browser-model-preferences";
import { withModelOverride } from "./course-maker/adapters/http/model-override";
import { BrowserGenerationPreferences } from "./course-maker/adapters/persistence/browser-generation-preferences";
import { BrowserProfileStore } from "./course-maker/adapters/persistence/browser-profile-store";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createCourseApplication,
  createApiCourseApplication,
  createInteractiveApplications,
  createDemoCreditsApplication,
} from "./course-maker/composition";
import { ApplicationContext } from "./course-maker/ui/application-context";
import "./course-maker/ui/course-maker.css";
import {
  HttpAuthentication,
  accountAuthenticationEnabled,
} from "./course-maker/adapters/http/authentication";
import { AuthenticationProvider } from "./course-maker/ui/authentication";

const root = createRoot(document.getElementById("root")!);

async function start() {
  const accountAuthEnabled =
    import.meta.env.VITE_DEMO_MODE === "true"
      ? false
      : await accountAuthenticationEnabled((url, init) =>
          window.fetch(url, init),
        );
  // Composition root: create browser capabilities only at the application edge.
  const modelPreferences = new BrowserModelPreferences({
    getItem: (key) => window.localStorage.getItem(key),
    setItem: (key, value) => window.localStorage.setItem(key, value),
  });
  const authentication = new HttpAuthentication((url, init) =>
    window.fetch(url, init),
  );
  const application = {
    modelPreferences,
    ...(import.meta.env.VITE_DEMO_MODE === "true"
      ? createInteractiveApplications(
          {
            getItem: (key) => window.localStorage.getItem(key),
            setItem: (key, value) => window.localStorage.setItem(key, value),
          },
          { next: () => crypto.randomUUID() },
          () => new Date(),
        )
      : {}),
    ...(import.meta.env.VITE_DEMO_MODE === "true"
      ? createDemoCreditsApplication(
          {
            getItem: (key) => window.localStorage.getItem(key),
            setItem: (key, value) => window.localStorage.setItem(key, value),
          },
          { next: () => "credit_" + crypto.randomUUID() },
          () => new Date(),
        )
      : {}),
    ...(import.meta.env.VITE_DEMO_MODE === "true"
      ? createCourseApplication(
          {
            getItem: (key) => window.localStorage.getItem(key),
            setItem: (key, value) => window.localStorage.setItem(key, value),
          },
          { next: () => "course_" + crypto.randomUUID() },
        )
      : createApiCourseApplication(
          withModelOverride(
            (url, init) =>
              accountAuthEnabled
                ? authentication.fetch(url, init)
                : window.fetch(url, init),
            modelPreferences,
          ),
        )),
    generationPreferences: new BrowserGenerationPreferences({
      getItem: (key) => window.localStorage.getItem(key),
      setItem: (key, value) => window.localStorage.setItem(key, value),
    }),
  };
  const profileStore = new BrowserProfileStore({
    getItem: (key) => window.localStorage.getItem(key),
    setItem: (key, value) => window.localStorage.setItem(key, value),
  });
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: false },
      mutations: { retry: false },
    },
  });

  root.render(
    <StrictMode>
      <ApplicationContext.Provider value={application}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            {!accountAuthEnabled ? (
              <App profileStore={profileStore} />
            ) : (
              <AuthenticationProvider
                client={authentication}
                navigateProvider={(url) => window.location.assign(url)}
              >
                <App profileStore={profileStore} />
              </AuthenticationProvider>
            )}
          </BrowserRouter>
        </QueryClientProvider>
      </ApplicationContext.Provider>
    </StrictMode>,
  );
}

void start().catch(() => {
  root.render(
    <div role="alert">
      <p>Couldn’t connect to the server. Please try again.</p>
      <button onClick={() => window.location.reload()}>Try again</button>
    </div>,
  );
});
