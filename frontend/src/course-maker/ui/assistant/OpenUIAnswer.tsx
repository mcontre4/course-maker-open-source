import { useMemo } from "react";
import type { SyntaxHighlighterProps } from "@assistant-ui/react-markdown";
import { createParser, Renderer } from "@openuidev/react-lang";
import { answerLibrary } from "./answer-library";

const parser = createParser(answerLibrary.toJSONSchema(), "Answer");

export default function OpenUIAnswer({ code }: SyntaxHighlighterProps) {
  const result = useMemo(() => {
    try {
      return parser.parse(code);
    } catch {
      return null;
    }
  }, [code]);
  if (
    !result?.root ||
    result.meta.errors.length ||
    result.meta.incomplete ||
    result.meta.unresolved.length ||
    result.queryStatements.length ||
    result.mutationStatements.length
  )
    return (
      <div className="agent-answer-fallback">
        <p>
          This answer could not be displayed. Ask your guide to explain it
          again.
        </p>
        <details>
          <summary>View original answer</summary>
          <pre>{code}</pre>
        </details>
      </div>
    );
  return <Renderer response={code} library={answerLibrary} />;
}
