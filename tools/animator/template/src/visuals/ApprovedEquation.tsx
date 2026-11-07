import React from 'react';
import katex from 'katex';

/** Keep the approved original visibly readable alongside typeset mathematics. */
export const ApprovedEquation = ({latex, verbatim}: {latex: string; verbatim: string}) => (
  <div>
    <div style={{fontSize: 56}} dangerouslySetInnerHTML={{__html: katex.renderToString(latex, {
      throwOnError: true, trust: false, output: 'htmlAndMathml', displayMode: true,
    })}} />
    <div style={{fontSize: 28, lineHeight: 1.4, whiteSpace: 'pre-wrap'}}>{verbatim}</div>
  </div>
);
