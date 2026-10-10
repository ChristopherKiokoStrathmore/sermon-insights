import type { Metadata } from "next";
import { OpenWorkbook } from "@/components/open-workbook";

export const metadata: Metadata = {
  title: "Workbook",
  description: "Open a sermon-insights workbook in the browser. The file is not uploaded.",
};

export default function WorkbookPage() {
  return (
    <article className="page">
      <p className="kicker">Your file, this browser</p>
      <h1>Open your workbook</h1>
      <p className="lede">
        Drop the <code>sermon_insights.xlsx</code> the CLI wrote. Charts and sheets are counted
        from that file alone. There is no account, no upload, and no copy left on a server.
      </p>
      <OpenWorkbook />
    </article>
  );
}
