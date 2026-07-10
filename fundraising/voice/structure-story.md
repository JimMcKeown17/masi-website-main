# Structure: child/youth story issue (the default newsletter)

> Part of the Editorial Layer (ADR 0009). Read by both shells alongside `voice_guide.md`.
> This file says WHAT the issue looks like; the voice guide says HOW it sounds.

## Shape: one story, told properly

One named child, youth, or graduate carries the whole issue. Do not run two or three
parallel profiles; they read samey and assembled. Depth beats breadth.

Order of the body (the lead photo, logo, bottom donate button, and social footer are
added around the body automatically; never write them):

1. **Greeting** in the house register ("Dear Masi Friends & Family," or similar).
2. **Hook** straight into the child: one or two sentences. The donor "you" must appear
   within the first ~150 words.
3. **The arc**: where the child started, what happened (the sessions, the coach by first
   name), where they are now. Ground every progress claim in the source story.
4. **The coach's voice**: one quote as a blockquote. Quotes are powerful; when the
   source has a good one, prefer letting it carry the moment over writing the same
   thing ourselves. Trim long quotes to the best one or two sentences (verbatim
   excerpt, magazine practice). Quote and surrounding copy must not repeat each other.
5. **Mid-email ask (longer issues only)**: a short issue (one story, a handful of
   paragraphs) gets NO marker; the single bottom button is enough. Only when the issue
   runs long (roughly 450+ words or multiple sections) emit `<!--MID_CTA-->` on its own
   line here, after the arc resolves. Never more than one marker.
6. **Broaden**: the child is not alone. This is where a programme stat belongs, woven as
   a sentence (see below). Then gratitude that credits the reader for the real outcome.
7. **Close**: sincere thanks, sign-off per the voice guide, then a **P.S.** that
   reinforces the same monthly-donor ask.

## Stats in a story issue

- At most one or two stats, chosen from the supplied catalog only, never from memory.
- For a donor audience, prefer story-adjacent numbers: scale ("one of 19,444 children
  learning with Masinyusane this year") and programme-level gains. Avoid financial,
  operational, or methodology-heavy numbers; they belong in funder-facing artifacts.
- A stat is one sentence inside the broadening paragraph, never a list or a table.

## Charts (from the chart library only)

One good chart can outpunch a paragraph of numbers. If the chart library
(`chart-library.json` in this folder) has an entry relevant to the story's programme,
embed AT MOST ONE in the broadening section: the entry's exact `image_url` full-width
like a photo, followed by its exact `caption` as a small gray line. Never build,
screenshot, or restyle a new chart for an issue; only curated library entries are
email-safe and fact-checked.

## Extra photos

If a non-lead story photo is supplied, embed it inline under the paragraph it belongs to
(the exact img markup is given in the composition contract). Never embed the lead photo;
it already sits above the body.

## Named variant: feature plus mini-cards (not the default)

Kept for occasional use when explicitly requested: one full story as above, followed by
two very short named vignettes (two or three sentences each, no quotes, no stats). Only
use when the issue must show breadth; the default is the single story.
