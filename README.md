# idiom-fable-story-shorts

Turn idioms and fables into **10 × 30-second English storytelling videos** — one story per
video, told in **55–70 simple English words**, with a Chinese translation, a 3–5 word
vocabulary card, and social posts + hashtags for Douyin / Xiaohongshu / X / YouTube Shorts.

Output is a real `.md` file that must pass the bundled validator before delivery.

## What one topic is

```
one idiom  →  one story  →  55–70 English words  →  30-second animated video
```

The video does exactly one thing: **tells the story**. A child who watches it should be
able to retell "who did what, and how it ended" — and that is also how they learn what the
idiom means.

This is **not** a science explainer, and **not** a multi-episode breakdown of a single
idiom. Both were tried and both were wrong:

| ❌ Wrong | ✅ Right |
|---|---|
| Tell 狐假虎威, then explain tiger pupils and fox ears | Tell 狐假虎威 and stop |
| Split one idiom into 10 episodes | 10 topics = 10 different stories |
| Repeat the same story in several topics | Each topic is a different idiom / fable |

## When to use

Trigger when the request involves any of:

- 成语故事 / 寓言故事 的英语短视频、英语讲故事、英语启蒙故事
- 中英双语故事旁白与英语讲故事脚本
- 抖音 / 小红书 / YouTube Shorts / X 社媒文案与话题标签

Not for: plain idiom explanations, single-script requests, or video editing / voiceover production.

## The four-beat story

| Beat | Time | Words | Job |
|---|---|---|---|
| 起 Open | 0–5s | 10–15 | time + who + first action |
| 承 Build | 5–15s | 15–20 | what happens, the conflict appears |
| 转 Turn | 15–24s | 15–20 | the twist, the result |
| 合 Meaning | 24–30s | 8–12 | one line that states what the story means |

Beat 4 is a **meaning line**, not a plot summary. `The tiger was strong. The fox was clever.
Clever won that day.` — not `Then the fox walked away.`

## Quick start

```bash
python skills/idiom-fable-story-shorts/scripts/validate_script_doc.py \
  "成语寓言-20261019101530.md" \
  --name-prefix "成语寓言" --min 55 --max 70
```

Exit code `0` = no failures, `1` = at least one failure (with a repair list printed).
Warnings never affect the exit code.

| Flag | Default | Meaning |
|---|---|---|
| `--name-prefix` | `成语寓言` | Expected filename prefix (spec: `<prefix>-<YYYYMMDDHHmmss>.md`); pass the theme name for a custom theme |
| `--topics` | `10` | Required number of topic sections |
| `--min` / `--max` | `55` / `70` | **Hard** voiceover word-count band (30s ↔ word count) |
| `--loose-words` | off | Downgrade out-of-band word counts from FAIL to WARN |
| `--no-summary` | off | Skip the per-topic overview table |

## Results: PASS / WARN / FAIL

- **PASS** — check satisfied
- **WARN** — advisory only, does not block delivery. Raised for likely hard vocabulary,
  over-long titles, a title that omits its own story name, low-quality clickbait wording,
  or an extra section such as 「第三部分」
- **FAIL** — must be fixed

## What the validator checks

FAIL-level:

1. Filename matches `<prefix>-<YYYYMMDDHHmmss>.md` (**no platform segment**), timestamp parseable
2. Document contains 「第一部分」 and 「第二部分」
3. Exactly 10 topic sections, numbering contiguous
4. **No idiom / fable reused across topics**
5. Overview table has 10 data rows, none with an empty title
6. Per topic: all required fields present, both titles non-empty
7. English voiceover within 55–70 words (hard; `--loose-words` downgrades to WARN)
8. Declared word count matches the measured count
9. English voiceover contains no Chinese characters
10. Vocabulary card has 3–5 items
11. Chinese voiceover ≥30 hanzi; Chinese post 30–80 hanzi; English post 20–50 words
12. Chinese hashtags 5–8; English hashtags 3–6
13. Child-appeal rationale present and specific
14. No elided sections

WARN-level:

- Likely hard words (built-in list + any token ≥13 letters)
- Chinese title >26 hanzi / English title >14 words
- Title omits its own story name (hurts search, not an error)
- Low-quality clickbait wording in the title
- Document contains an extra section beyond Part 1 / Part 2

Word counting rule (fixed, so results are reproducible): strip Markdown marks, split on
whitespace, count every token containing a letter or digit. Numbers, abbreviations and
hyphenated words each count as one word.

## Files

| Path | Purpose |
|---|---|
| `SKILL.md` | Triggers, defaults, Step 0–7 workflow, hard rules, content red lines |
| `references/content-spec.md` | Full authoring spec: four-beat structure, vocabulary ceiling, accuracy, format & naming |
| `references/output-template.md` | Markdown skeleton — field markers are load-bearing for the validator |
| `references/story-bank.md` | 2 fully annotated sample scripts + 45 candidate stories with sources |
| `scripts/validate_script_doc.py` | Validator; standard library only |

## Requirements

- Python **3.10+** (standard library only — no third-party dependencies)
