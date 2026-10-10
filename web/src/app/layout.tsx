import type { Metadata } from "next";
import { Fraunces, Public_Sans } from "next/font/google";
import Link from "next/link";
import { SiteNav } from "@/components/site-nav";
import { GITHUB_REPO } from "@/lib/site";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
  weight: ["500", "600", "700"],
});

const sans = Public_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: {
    default: "sermon-insights",
    template: "%s · sermon-insights",
  },
  description:
    "Read a sermon-insights workbook in the browser. Cataloguing, captions, and Whisper stay on your computer.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable}`}>
      <body>
        <a className="skip" href="#content">
          Skip to content
        </a>
        <header className="mast">
          <Link className="mark" href="/">
            <span className="mark-flag" aria-hidden="true" />
            sermon-insights
          </Link>
          <SiteNav />
        </header>
        <main id="content">{children}</main>
        <footer className="colophon">
          <p>
            Personal research on public videos. The package throttles, caches, and does not ship a
            church&apos;s livestreams.{" "}
            <a href={GITHUB_REPO}>Source on GitHub</a>.
          </p>
        </footer>
      </body>
    </html>
  );
}
