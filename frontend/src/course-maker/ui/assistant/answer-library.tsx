import { createLibrary, defineComponent } from "@openuidev/react-lang";
import { z } from "zod";

const Explanation = defineComponent({
  name: "Explanation",
  description:
    "A short explanation under a descriptive heading. Plain text only.",
  props: z.object({ heading: z.string(), body: z.string() }),
  component: ({ props }) => (
    <section>
      <h4>{props.heading}</h4>
      <p>{props.body}</p>
    </section>
  ),
});

const Steps = defineComponent({
  name: "Steps",
  description: "An ordered sequence of concrete learning or editing steps.",
  props: z.object({ heading: z.string(), items: z.array(z.string()) }),
  component: ({ props }) => (
    <section>
      <h4>{props.heading}</h4>
      <ol>
        {props.items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ol>
    </section>
  ),
});

const Comparison = defineComponent({
  name: "Comparison",
  description: "A small comparison table. Each row has one cell per column.",
  props: z.object({
    heading: z.string(),
    columns: z.array(z.string()),
    rows: z.array(z.array(z.string())),
  }),
  component: ({ props }) => (
    <section>
      <h4>{props.heading}</h4>
      <div
        className="agent-table-scroll"
        tabIndex={0}
        role="region"
        aria-label={props.heading}
      >
        <table>
          <thead>
            <tr>
              {props.columns.map((column, index) => (
                <th key={index} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {props.rows.map((row, index) => (
              <tr key={index}>
                {row.map((cell, column) => (
                  <td key={column}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  ),
});

const Callout = defineComponent({
  name: "Callout",
  description: "One useful takeaway, caveat, or question for the learner.",
  props: z.object({ heading: z.string(), body: z.string() }),
  component: ({ props }) => (
    <aside className="agent-callout">
      <h4>{props.heading}</h4>
      <p>{props.body}</p>
    </aside>
  ),
});

const Answer = defineComponent({
  name: "Answer",
  description:
    "Root of a guide answer. Use a brief title, a direct summary, and only the sections needed.",
  props: z.object({
    title: z.string(),
    summary: z.string(),
    sections: z.array(
      z.union([Explanation.ref, Steps.ref, Comparison.ref, Callout.ref]),
    ),
  }),
  component: ({ props, renderNode }) => (
    <div className="agent-answer">
      <h3>{props.title}</h3>
      <p className="agent-answer-summary">{props.summary}</p>
      {props.sections.map((section, index) => (
        <div key={index}>{renderNode(section)}</div>
      ))}
    </div>
  ),
});

export const answerLibrary = createLibrary({
  root: "Answer",
  components: [Answer, Explanation, Steps, Comparison, Callout],
});

export const answerInstructions = `
Response presentation for every guide role (lesson, syllabus, storyboard, animation):
For substantive explanations, comparisons, and plans, render your final answer as one
fenced \`openui\` code block using the library below. Short acknowledgements and simple
questions may use Markdown. Never put tool calls or application commands in OpenUI.
Components are display-only; they do not change outlines, approve, or generate media.
Use plain text inside component strings. Do not include HTML, JavaScript, or URLs in
component strings. Keep answers concise; do not add sections merely for decoration.
Always explain actual tool failures accurately. The presentation rules do not change
authorization, memory, or outline-mutation rules. Historical replies may be Markdown.

${answerLibrary.prompt({ preamble: "The following syntax applies inside the fenced openui block.", toolCalls: false, bindings: false, builtinFunctions: false, examples: ['root = Answer("A clearer opening", "Start with a familiar example before naming the concept.", [Steps("Suggested sequence", ["Show the example", "Explain the idea", "Check understanding"]), Callout("Next step", "Would you like me to revise the outline?")])'] })}
`;
