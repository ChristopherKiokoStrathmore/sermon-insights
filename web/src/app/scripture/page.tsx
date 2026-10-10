import type { Metadata } from "next";
import { ScripturePlayground } from "@/components/scripture-playground";

export const metadata: Metadata = {
  title: "Scripture",
  description: "Kiswahili and English scripture references, normalised in the browser.",
};

export default function ScripturePage() {
  return (
    <article className="page">
      <p className="kicker">Same rules as the package</p>
      <h1>Scripture, in the browser</h1>
      <p className="lede">
        Paste Kiswahili or English. Book names come from the same YAML as{" "}
        <code>sermon_insights.scripture</code>, compiled into this page. A high match means the
        words lined up. It does not mean a person checked the pulpit Bible, and it does not call a
        model or a Bible API.
      </p>
      <ScripturePlayground />
    </article>
  );
}
