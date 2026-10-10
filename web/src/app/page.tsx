import Link from "next/link";
import sample from "@/data/sample-workbook.json";
import { COLAB_NOTEBOOK, GITHUB_REPO } from "@/lib/site";

const STAGES = [
  ["catalog", "yt-dlp --flat-playlist on the channel’s /videos and /streams. Public videos only."],
  ["captions", "youtube-transcript-api, then yt-dlp auto-subs. No YouTube Data API key."],
  ["transcribe", "faster-whisper only where captions are missing. Audio is fetched on your machine."],
  ["detect", "A long speech run, pulled toward “tufungue biblia” and “tuombe”."],
  ["scripture", "Kiswahili and English book names, normalised to English, with a confidence."],
  ["songs", "Lyric phrases against a local cache. One phrase in one window stays (verify)."],
  ["topics", "A keyword seed, or BERTopic once you install the extra and have enough sermons."],
  ["export", "Five sheets: Sermons, Scripture, Worship Songs, Song List, Topics & Verses."],
];

export default function HomePage() {
  const sermons = sample.sermons.length;
  const scriptures = sample.scripture.length;
  const worship = sample.worshipSongs.length;

  return (
    <article className="essay">
      <p className="kicker">A reading room, not a crawler</p>
      <h1>The channel is not processed here.</h1>
      <p className="lede">
        sermon-insights is a Python package. Point it at a church YouTube channel on your own
        computer and it writes a workbook: the sermon window, the verses that were actually spoken,
        a few lines copied from the transcript, a broad theme, and the worship songs the lyrics
        support. This website only lets you read that workbook, and try the scripture matcher in
        the browser.
      </p>
      <p className="where">
        yt-dlp and Whisper do not run on Vercel. YouTube blocks many cloud IP ranges, including
        the machines that would host a “just paste a channel” button. There is no such button.
      </p>
      <p className="actions">
        <Link className="button" href="/explore">
          Browse the sample
        </Link>
        <Link className="button quiet" href="/workbook">
          Open a workbook
        </Link>
        <Link className="button quiet" href="/scripture">
          Try a verse
        </Link>
      </p>

      <section>
        <h2>What the package actually does</h2>
        <p>
          Kiswahili first, English mixed in. Book names live in YAML, one file per language, so
          another language is data rather than a rewrite. Weak matches stay visible and are marked{" "}
          <span className="flag-pill">verify</span>. The summary is an extract, not a translation
          and not a paragraph a model wrote. The theme column says whether it came from the keyword
          seed or from BERTopic.
        </p>
        <ol className="stages">
          {STAGES.map(([name, text], index) => (
            <li key={name}>
              <span className="stage-index">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3>{name}</h3>
                <p>{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2>Run it</h2>
        <pre>
          <code>{`python -m pip install -e ".[dev]"
sermon run --channel @handle --since 2025-01-01`}</code>
        </pre>
        <p>
          Copy <code>config/sermon.example.yaml</code> if you want sleeps, the Whisper model, and
          the cache directory in a file. <code>sermon run --config samples/offline/config.yaml</code>{" "}
          walks the synthetic fixture with the network off. That fixture is what the{" "}
          <Link href="/explore">sample</Link> shows: {sermons} sermon, {scriptures} scripture rows,{" "}
          {worship} worship segments. Those counts are the rows in the file, not a corpus.
        </p>
      </section>

      <section>
        <h2>When the captions are missing</h2>
        <p>
          YouTube blocks Colab, so the GPU notebook never calls yt-dlp. Fetch the audio locally,
          transcode it, put sermons and worship in a Drive folder you choose, and open{" "}
          <a href={COLAB_NOTEBOOK}>notebooks/colab_transcribe.ipynb</a>. On a T4 it uses
          faster-whisper <code>medium</code>, <code>float16</code>, language <code>sw</code>.
          Singing turns the VAD off. Copy the JSON it writes back into your cache and continue with{" "}
          <code>sermon detect</code>. The notebook has no Drive file ids.
        </p>
      </section>

      <section>
        <h2>Public videos, slowly</h2>
        <p>
          The tool is for personal research on videos that are already public. It drops private and
          deleted entries, waits between requests, and does not download a file it already has. Do
          not republish full transcripts, and do not present the workbook as the church’s own notes.
          Automated downloading can sit outside YouTube’s Terms of Service even when a video is
          public. Read the current terms, prefer captions over a full audio download, and stop if a
          creator asks you to.
        </p>
        <p>
          The package and this site are on{" "}
          <a href={GITHUB_REPO}>ChristopherKiokoStrathmore/sermon-insights</a>. Chris Nguu maintains
          them.
        </p>
      </section>
    </article>
  );
}
