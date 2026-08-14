# Prompt log - Step 7: the report draft

*Milestone: generate the Part B report draft in Word. `[YOUR WORDS]` marks where I
add my own words.*

## What I wanted

A report draft in `report/report.docx` following `report/OUTLINE.md` and the
writing rules: methodology with the equations written out and every symbol
defined, every exhibit inserted and referenced, numbers traced to the results/
CSVs, and `[YOUR INTERPRETATION]` stubs where the economic reasoning is mine.

## Prompt(s)

- "Run Step 7."

## What the assistant produced

- `scripts/build_report.py` - a reproducible builder that reads every number from
  the results/ artifacts (nothing hand-typed), lays out the seven sections with
  Word built-in styles, renders the eight methodology equations as images
  (matplotlib mathtext), embeds the six figures, builds the performance and
  fusion tables, and inserts 10 `[YOUR INTERPRETATION]` stubs + 2 `[NOTE]` markers.
- Added a small `results/tables/sentiment_stats.csv` so the coverage/level numbers
  in the report trace to a file.

## What was wrong or risky

- **mathtext is a LaTeX subset.** The first build crashed on `\textstyle` and I
  also had to swap `\text{}` for `\mathrm{}`. Fixed and re-rendered; spot-checked
  the max-Sharpe and fusion equations by eye - they render cleanly.
- **The equations are IMAGES, not Word native equations.** The word-reporting
  rule prefers Word's equation editor. For a draft the rendered images are correct
  and complete; the script docstring flags that they can be re-authored in Word's
  equation editor for the final. [YOUR WORDS: your call on native vs image equations.]
- **This is a DRAFT, and the interpretation is deliberately not written.** The 10
  `[YOUR INTERPRETATION]` stubs (in red) are the economic reasoning graded as
  yours - the funds' behaviour, why sentiment hurt, the three recommendations.
  Do not hand in with stubs unfilled.
- **The app section is a scaffold** pending Step 9 screenshots; **innovation
  sections come after Step 8**; references are empty (add verified sources only).

## What I changed and why

- Kept the builder reproducible so a re-run after any results change refreshes the
  numbers automatically.
- Left every economic judgement as a stub rather than writing it for you.

**Verification performed (this run):**

| Check | Result |
|---|---|
| report/report.docx built | 73 paragraphs, 2 tables, 14 inline images |
| structure | Title/Subtitle + 7 sections + abstract/refs/appendix, Heading styles |
| equations | 8 rendered (mathtext), visually confirmed |
| figures embedded | 6 of 6 |
| Table 1 / Table 2 numbers | match performance_metrics.csv / fusion_comparison.csv |
| interpretation stubs / notes | 10 / 2 |
| check_handin.py | 22 passed, report reminder cleared |

[YOUR WORDS: my plan for filling the interpretation stubs and finishing in Word.]

## Extension (2026-08-13/14): innovation + benchmark folded in

After Step 8 (all three extensions) and the benchmark were built, `build_report.py`
was extended in one pass:

- New Section 3.1 "Do the funds beat simply owning the market?" - the benchmark
  table and the measured min-variance-loses-to-1/N decomposition (holdings, crypto
  weight, effective N, the return-vs-vol trade), all read from the artifacts.
- New Section 6 "Innovation" with 6.1 shrinkage, 6.2 two-stage, 6.3 decay - each
  with its equation, before-vs-after table, two figures, and the measured result.
- Growth and Sharpe figures now carry the equal-weight market reference.
- Renumbered: 8 sections, 11 equations (fixed the earlier non-sequential numbers),
  12 figures, 6 tables, 14 [YOUR INTERPRETATION] stubs, 2 [NOTE] markers.

The whole report still rebuilds from `python scripts/build_report.py` with nothing
hand-typed. Still a DRAFT: the 14 stubs (the economic reasoning, graded as mine)
are unfilled, the app screenshots wait for Step 9, references are empty, and the
PDF is not exported until after the app. Do not hand in with stubs unfilled.

## Equations -> native Word objects (2026-08-14, Gianni's call)

Gianni asked for native Word equation boxes instead of rendered PNG images, for a
seamless, consistent report. `build_report.py` now converts each equation
LaTeX -> MathML (latex2mathml) -> OMML (mathml2omml) and inserts it as a native,
editable Word equation object. Added both libs to requirements-dev.txt (build
tooling only). One converter quirk: `\bar{}` produced malformed OMML, so the three
mean-bar accents use `\overline{}` instead (identical rendering). Verified: 11
native OMML equations, 0 equation images, figures still images, 6 tables. The
matplotlib equation renderer is gone.

[YOUR WORDS: my read before I fill the stubs in Word.]
