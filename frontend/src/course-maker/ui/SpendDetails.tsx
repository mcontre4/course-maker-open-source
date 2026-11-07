import { useEffect, useEffectEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import { useLessonMutation } from "./lesson-context";
import type {
  CourseResponse,
  CourseSpendResponse,
  SpendTotalResponse,
} from "../application/dto";
import { useApplication, useCourseMutation } from "./application-context";
import { ErrorNotice } from "./components";

const empty: SpendTotalResponse = {
  knownUsd: "0",
  pendingCalls: 0,
  estimatedCalls: 0,
  calls: 0,
  inputTokens: 0,
  outputTokens: 0,
};
const stageLabels: Readonly<Record<string, string>> = {
  syllabus: "Course planning",
  thumbnail: "Thumbnail",
  style: "Style planning",
  lesson: "Lesson planning",
  script: "Scripting",
  storyboard: "Storyboarding",
  quiz: "Lesson quiz",
  interactive: "Lesson interactive",
  speech: "Narration",
  assets: "Asset generation",
  element_planning: "Visual element planning",
  element_generation: "Parallel element generation",
  animation: "Video / animation",
  visual_review: "Visual review",
  animation_repair: "Visual repair",
  render: "Rendering & verification",
  guide: "Guide",
};
const stageOrder = new Map(
  Object.keys(stageLabels).map((stage, index) => [stage, index]),
);

export function formatSpend(total: SpendTotalResponse): string {
  const dollars = Number(total.knownUsd);
  const value =
    dollars > 0 && dollars < 0.0001
      ? "<$0.0001"
      : new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: "USD",
          minimumFractionDigits: 2,
          maximumFractionDigits: dollars < 0.01 ? 4 : 2,
        }).format(dollars);
  return `${total.estimatedCalls ? "≈" : ""}${value}${total.pendingCalls ? " + pending" : ""}`;
}

export function formatElapsed(seconds: number): string {
  const rounded = Math.floor(seconds);
  if (rounded < 60) return `${rounded}s`;
  if (rounded < 3600) return `${Math.floor(rounded / 60)}m ${rounded % 60}s`;
  return `${Math.floor(rounded / 3600)}h ${Math.floor((rounded % 3600) / 60)}m`;
}

export function SpendDetails({
  course,
  lessonId,
}: {
  course: CourseResponse;
  lessonId?: string;
}) {
  const app = useApplication();
  const cache = useQueryClient();
  const refresh = useCourseMutation((id: string) =>
    cache.fetchQuery({
      queryKey: ["spend-refresh", "course", id],
      queryFn: () =>
        app.refreshSpend
          ? app.refreshSpend.execute(id)
          : app.getCourse.execute(id),
      staleTime: 1000,
      retry: false,
    }),
  );
  if (course.spend === undefined && !course.activeOperation) return null;
  return (
    <SpendDisclosure
      spend={course.spend ?? null}
      lessonId={lessonId}
      onRefresh={() => refresh.mutate(course.id)}
      pending={refresh.isPending}
      error={refresh.error}
    />
  );
}

export function StandaloneSpendDetails({
  lesson,
  expandWhileActive = true,
}: {
  lesson: StandaloneLessonResponse;
  expandWhileActive?: boolean;
}) {
  const app = useApplication().lessons;
  const cache = useQueryClient();
  const refresh = useLessonMutation(async () => {
    if (!app)
      throw new Error("Standalone lessons require a server connection.");
    return cache.fetchQuery({
      queryKey: ["spend-refresh", "lesson", lesson.id],
      queryFn: () =>
        app.refreshSpend
          ? app.refreshSpend.execute(lesson.id)
          : app.get.execute(lesson.id),
      staleTime: 1000,
      retry: false,
    });
  });
  if (lesson.spend === undefined && !lesson.activeOperation) return null;
  return (
    <SpendDisclosure
      spend={lesson.spend ?? null}
      lessonId={lesson.id}
      active={
        !!lesson.activeOperation ||
        lesson.spend?.steps?.some((step) => step.finishedAt === null)
      }
      expandWhileActive={expandWhileActive}
      onRefresh={() => refresh.mutate(undefined)}
      pending={refresh.isPending}
      error={refresh.error}
    />
  );
}

export function SpendDisclosure({
  spend,
  lessonId,
  onRefresh,
  pending,
  error,
  active = false,
  expandWhileActive = true,
  defaultOpen = false,
}: {
  defaultOpen?: boolean;
  spend: CourseSpendResponse | null;
  lessonId?: string;
  onRefresh: () => void;
  pending: boolean;
  error: unknown;
  active?: boolean;
  expandWhileActive?: boolean;
}) {
  const total = lessonId
    ? (spend?.lessons.find((l) => l.lessonId === lessonId)?.total ?? empty)
    : (spend?.total ?? empty);
  const charges =
    spend?.breakdown.filter((row) => !lessonId || row.lessonId === lessonId) ??
    [];
  const steps =
    spend?.steps?.filter((step) => !lessonId || step.lessonId === lessonId) ??
    [];
  const processing = steps.some((step) => step.finishedAt === null);
  // Ordinary lesson polling only reads the ledger. Retry provider billing too,
  // including after generation has finished, without polling forever on lost IDs.
  const pendingBilling = charges
    .filter(
      (row) => row.provider === "openrouter" && row.total.pendingCalls > 0,
    )
    .map(
      (row) =>
        `${row.lessonId}:${row.stage}:${row.model}:${row.total.pendingCalls}:${row.total.inputTokens}:${row.total.outputTokens}`,
    )
    .sort()
    .join("|");
  const refreshBilling = useEffectEvent(() => {
    if (!pending) onRefresh();
  });
  useEffect(() => {
    if (!pendingBilling) return;
    const delays = [5000, 10000, 20000, 40000, 60000];
    let attempt = 0;
    let timer: number;
    const schedule = () => {
      if (attempt >= delays.length) return;
      timer = window.setTimeout(() => {
        refreshBilling();
        attempt += 1;
        schedule();
      }, delays[attempt]);
    };
    schedule();
    return () => window.clearTimeout(timer);
  }, [pendingBilling]);
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!processing) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [processing]);
  const keys = new Map<string, { lessonId: string | null; stage: string }>();
  for (const row of [...charges, ...steps]) {
    keys.set(`${row.lessonId}:${row.stage}`, row);
  }
  const rows = [...keys.values()]
    .sort(
      (a, b) =>
        (stageOrder.get(a.stage) ?? stageOrder.size) -
        (stageOrder.get(b.stage) ?? stageOrder.size),
    )
    .map((key) => {
      const matches = charges.filter(
        (row) => row.lessonId === key.lessonId && row.stage === key.stage,
      );
      const timings = steps.filter(
        (step) => step.lessonId === key.lessonId && step.stage === key.stage,
      );
      const total = matches.reduce<SpendTotalResponse>(
        (sum, row) => ({
          knownUsd: String(Number(sum.knownUsd) + Number(row.total.knownUsd)),
          calls: sum.calls + row.total.calls,
          pendingCalls: sum.pendingCalls + row.total.pendingCalls,
          estimatedCalls: sum.estimatedCalls + row.total.estimatedCalls,
          inputTokens: sum.inputTokens + row.total.inputTokens,
          outputTokens: sum.outputTokens + row.total.outputTokens,
        }),
        empty,
      );
      return {
        ...key,
        total,
        engines: [
          ...new Set(
            timings.flatMap((step) =>
              step.backend === "codex"
                ? ["Codex CLI"]
                : step.backend === "direct"
                  ? ["Direct LLM"]
                  : [],
            ),
          ),
        ].join(", "),
        agents: [
          ...new Set(
            matches.map(
              (row) =>
                `${row.provider} · ${row.model.replace(/:+fast$/, ":fast")}`,
            ),
          ),
        ].join(", "),
        processing: timings.some((step) => step.finishedAt === null),
        seconds: timings.length
          ? timings.reduce(
              (sum, step) =>
                sum + Math.max(0, (step.finishedAt ?? now) - step.startedAt),
              0,
            )
          : null,
      };
    });
  return (
    <details
      className="spend-details"
      open={defaultOpen || (expandWhileActive && active) || undefined}
    >
      <summary>
        <span>{lessonId ? "Lesson AI spend" : "Course AI spend"}</span>
        <span className="spend-amount">
          {spend ? formatSpend(total) : "Unavailable"}
          {processing ? " + processing" : ""}
        </span>
      </summary>
      <div className="spend-body">
        <p className="muted small">
          Recorded spend so far, in USD. Active requests stay pending until the
          provider reports their cost. Cumulative across generations and
          updates; earlier usage may be excluded.
        </p>
        {!lessonId && spend ? (
          <p className="muted small">
            All lessons plus {formatSpend(spend.shared)} of course planning.
          </p>
        ) : null}
        {rows.length ? (
          <div className="spend-table-scroll">
            <table className="spend-table" aria-label="AI spend by step">
              <thead>
                <tr>
                  <th scope="col">Step</th>
                  <th scope="col">Agent</th>
                  <th scope="col">Time</th>
                  <th scope="col">Spend</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.lessonId}:${row.stage}`}>
                    <th scope="row">{stageLabels[row.stage] ?? row.stage}</th>
                    <td>
                      {[
                        "assets",
                        "element_planning",
                        "element_generation",
                        "animation",
                        "visual_review",
                        "animation_repair",
                      ].includes(row.stage) ? (
                        <>
                          {row.engines || (row.agents ? null : "—")}
                          {row.agents ? <small>{row.agents}</small> : null}
                        </>
                      ) : row.stage === "render" ? (
                        "Video renderer"
                      ) : (
                        row.agents || "—"
                      )}
                    </td>
                    <td>
                      {row.seconds === null ? "—" : formatElapsed(row.seconds)}
                    </td>
                    <td>
                      {row.total.calls || row.processing
                        ? formatSpend(row.total)
                        : "—"}
                      {row.processing ? " + processing" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted small">
            {spend
              ? "No model calls recorded yet."
              : "Spend could not be loaded. Retry to fetch it."}
          </p>
        )}
        {spend ? (
          <p className="muted small">
            {total.calls} calls ·{" "}
            {(total.inputTokens + total.outputTokens).toLocaleString("en-US")}{" "}
            tokens
            {Number(total.credits ?? 0) > 0
              ? ` · ${Number(total.credits).toLocaleString("en-US")} speech credits`
              : ""}
          </p>
        ) : null}
        {total.pendingCalls ? (
          <p className="muted small">
            Pending request costs are not included in the recorded amount.
            {charges.some(
              (row) =>
                row.provider === "elevenlabs" && row.total.pendingCalls > 0,
            )
              ? " Speech credits need an account USD rate before they can be included."
              : " Provider billing is refreshed automatically."}
          </p>
        ) : null}
        {total.estimatedCalls ? (
          <p className="muted small">
            ≈ Includes speech credits converted using your configured account
            rate.
          </p>
        ) : null}
        <button
          className="spend-refresh"
          disabled={pending}
          onClick={onRefresh}
        >
          {pending ? "Fetching spend…" : "Refresh spend"}
        </button>
        <ErrorNotice error={error} />
      </div>
    </details>
  );
}
