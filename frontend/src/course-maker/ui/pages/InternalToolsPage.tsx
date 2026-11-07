import "../styles/internal-tools.css";
import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  parseLessonReference,
  type LessonReference,
  type LessonDiagnostics,
} from "../../application/internal-tools";
import { useApplication } from "../application-context";
import { ErrorNotice } from "../components";
import { Button } from "../primitives/Button";
import { formatElapsed, formatSpend, SpendDisclosure } from "../SpendDetails";

export function InternalToolsPage() {
  const tools = useApplication().internalTools;
  const [reference, setReference] = useState("");
  const [key, setKey] = useState("");
  const [validation, setValidation] = useState<Error | null>(null);
  const [result, setResult] = useState<LessonDiagnostics | null>(null);
  const inspection = useMutation({
    gcTime: 0,
    mutationFn: (request: {
      reference: LessonReference;
      key: string;
      refresh?: boolean;
    }) => {
      if (!tools)
        throw new Error("Internal tools require a server connection.");
      return tools.inspect(request.reference, request.key, request.refresh);
    },
    onSuccess: (value) => setResult(value),
    onError: () => setResult(null),
  });
  const { variables, isPending, mutate } = inspection;
  useEffect(() => {
    if (!result?.generationActive || isPending || !variables) return;
    const timer = window.setTimeout(
      () => mutate({ ...variables, refresh: false }),
      3000,
    );
    return () => window.clearTimeout(timer);
  }, [result, variables, isPending, mutate]);

  return (
    <div className="internal-tools-page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">Internal</span>
          <h1>Internal tools</h1>
          <p className="muted">Tools for the team.</p>
        </div>
      </header>
      <nav aria-label="Internal tools">
        <a href="#lesson-diagnostics">Lesson diagnostics</a>
      </nav>
      <section id="lesson-diagnostics" aria-labelledby="diagnostics-title">
        <h2 id="diagnostics-title">Lesson diagnostics</h2>
        <p className="muted">
          Look up AI spend and generation time for a lesson.
        </p>
        <form
          className="internal-lookup"
          onSubmit={(event) => {
            event.preventDefault();
            inspection.reset();
            setResult(null);
            try {
              const parsed = parseLessonReference(reference);
              if (!key.trim())
                throw new Error("Enter your internal access key.");
              setValidation(null);
              inspection.mutate({ reference: parsed, key });
            } catch (error) {
              setValidation(error as Error);
            }
          }}
        >
          <label>
            Internal access key
            <input
              type="password"
              autoComplete="off"
              value={key}
              onChange={(event) => {
                setKey(event.target.value);
                inspection.reset();
                setResult(null);
              }}
              disabled={isPending}
              required
            />
          </label>
          <label>
            Lesson URL or ID
            <input
              type="text"
              placeholder="https://…/lessons/lesson_…"
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              disabled={isPending}
              required
            />
          </label>
          <Button type="submit" disabled={isPending}>
            {isPending ? "Loading…" : "Inspect lesson"}
          </Button>
        </form>
        <ErrorNotice error={validation ?? inspection.error} />
        {result ? (
          <section
            className="internal-result"
            aria-label="Lesson diagnostics result"
          >
            <h3>{result.title}</h3>
            <p className="muted small">{result.lessonId}</p>
            <dl className="internal-metrics">
              <div>
                <dt>Total AI spend</dt>
                <dd>{formatSpend(result.spend.total)}</dd>
              </div>
              <div>
                <dt>Total generation time</dt>
                <dd>
                  {result.generationSeconds === null
                    ? "Unavailable"
                    : formatElapsed(result.generationSeconds)}
                  {result.generationActive ? " · In progress" : ""}
                </dd>
              </div>
            </dl>
            <p className="muted small">
              Recorded processing time across generations and updates. Parallel
              steps count once; idle gaps are excluded. Older lessons may have
              incomplete timing records.
            </p>
            <SpendDisclosure
              key={`${result.courseId}:${result.lessonId}`}
              spend={result.spend}
              lessonId={result.lessonId}
              defaultOpen
              pending={isPending}
              error={null}
              onRefresh={() => {
                if (variables)
                  inspection.mutate({ ...variables, refresh: true });
              }}
            />
          </section>
        ) : null}
      </section>
    </div>
  );
}
