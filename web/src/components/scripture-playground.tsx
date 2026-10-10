"use client";

import { useMemo, useState } from "react";
import exodus from "@/data/exodus-snippet.json";
import { displayRef, findText } from "@/lib/scripture/match";

export function ScripturePlayground() {
  const [text, setText] = useState("");
  const hits = useMemo(() => (text.trim() ? findText(text) : []), [text]);

  return (
    <div className="playground">
      <label className="scripture-label" htmlFor="transcript">
        Transcript text
      </label>
      <textarea
        id="transcript"
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={10}
        placeholder="Zaburi sura ya ishirini na tatu mstari wa kwanza"
        spellCheck={false}
      />
      <div className="playground-actions">
        <button type="button" className="button" onClick={() => setText(exodus.text)}>
          Load the Exodus 17 fixture
        </button>
        <button type="button" className="button quiet" onClick={() => setText("")}>
          Clear
        </button>
      </div>
      <p className="result-count">
        {text.trim()
          ? `${hits.length} reference${hits.length === 1 ? "" : "s"} in this text`
          : "Paste a line, or load the fixture. Nothing is sent anywhere."}
      </p>
      {text.trim() && hits.length === 0 ? (
        <p className="empty">
          No reference matched. A bare name such as Mark, John, or Mwanzo, with no chapter, is
          skipped on purpose.
        </p>
      ) : null}
      <ol className="hits">
        {hits.map((hit, index) => (
          <li key={`${hit.ref}-${hit.span}-${index}`} className={hit.conf === "low" ? "verify-row" : undefined}>
            <div className="hit-top">
              <span className="hit-ref">{displayRef(hit.ref, hit.conf)}</span>
              <span className={`conf conf-${hit.conf}`}>{hit.conf}</span>
              {hit.conf === "low" ? <span className="flag-pill">verify</span> : null}
            </div>
            <p className="hit-span">“{hit.span}”</p>
            {hit.why ? <p className="hit-why">{hit.why}</p> : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
