import type { Metadata } from "next";
import { WorkbookExplorer } from "@/components/workbook-explorer";
import sample from "@/data/sample-workbook.json";
import type { ParsedWorkbook } from "@/lib/workbook";

export const metadata: Metadata = {
  title: "Sample",
  description: "Browse the sanitised sermon-insights sample workbook in the browser.",
};

export default function ExplorePage() {
  return (
    <article className="page">
      <p className="kicker">Offline fixture</p>
      <h1>The sample workbook</h1>
      <p className="lede">
        Same five sheets the CLI writes. Search, filter, and follow the timestamped links. Rows
        that carry <span className="flag-pill">verify</span> are the ones the pipeline refused to
        treat as settled.
      </p>
      <WorkbookExplorer workbook={sample as ParsedWorkbook} source="sample" />
    </article>
  );
}
