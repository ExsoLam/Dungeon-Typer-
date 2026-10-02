# Typing of the Dungeon

A Typing of the Dead inspired typing game. Monsters walk down a corridor towards you with a word attached; type the word to kill them before they reach you.

The whole game is one file, `typing_dungeon_v21.html`: engine, renderer, procedural sound, embedded art and the word lists. There is no build step and no dependencies.

## Play it

Open `typing_dungeon_v21.html` in a browser. Either double-click the file, drag it into a browser window, or serve the folder with anything static:

```sh
python3 -m http.server 8000   # then open http://localhost:8000/typing_dungeon_v21.html
```

Everything runs locally. The game makes no network requests and needs no server component.

- Keyboard required (it is a typing game). A wide window works best: the canvas is 960x540 and scales up to a 16:9 box.
- Sound is generated with Web Audio. Browsers only allow audio after a user gesture, so the first key press starts the audio context. F2 mutes and unmutes.
- Best score and the chosen mode are kept in `localStorage`, so they survive a reload.

## Controls

| Key | Action |
| --- | --- |
| Any letter, digit or space | Type the word on the targeted monster |
| Enter | Start from the title; advance the stage results; take a continue after dying; return to the title from the final screen |
| Tab or arrow keys | Switch mode on the title screen (strict / original) |
| Escape | Pause and unpause |
| F2 | Mute / unmute |

Targeting: the first letter you type locks onto the monster whose word starts with that letter, and that target is drawn above the others until it dies. Keys with no valid target are ignored, as in the original game. While a word is locked, every key goes to that monster.

## The bow

Every correct key looses an arrow. It leaves the bow at the bottom of the view and flies to the monster you are typing at; a wrong key or a key with no target throws nothing, because nothing is being aimed at.

The arrows are visual only. A hit still resolves the instant you type the last letter of a word, so ranks, timing and scores are unchanged by the bow, and leaderboard entries stay comparable with ones posted before it existed.

Prisoners are not shot at: typing a prisoner's word frees them, so no arrow is loosed.

## Modes

| Mode | Case | Spaces | Score multiplier |
| --- | --- | --- | --- |
| strict | counted | counted | 1.0 |
| original | ignored | ignored (typing a space does nothing) | 0.75 |

`original` follows the original game's forgiving rules and pays less for it. Mode is set on the title screen and remembered.

## How a run works

Three stages, one wave each:

1. **THE BONFIRE GATE**
2. **THE COURTYARD**
3. **THE CRYPT** (ends with the boss)

You start with 3 lives and 5 continues. A monster that reaches you costs a life; at zero lives the run ends and a continue resets you to 3 lives and costs 5 p. Each stage ends with a results parchment, and the run ends with a final score.

### The hidden progress counter (p)

`p` starts at 3 and is clamped to 0 to 15. It is not shown as a number, but it drives the word tier, which the HUD shows as a label such as `L040` (tier n uses the original game's `Z000L(n*10)` word list).

- +1 each time the accuracy accumulator fills (100 points of rank accuracy)
- +1 after 30 seconds without being hit
- -2 per hit taken
- -5 per continue

### Ranks and stage score

Each word is ranked A to E from your typing speed against that word's par value (par comes from the original game's word lists). Speed is measured from your first correct key to your last, divided by the word's value.

| Rank | Points | Ratio (seconds per value unit) |
| --- | --- | --- |
| A | 35 | 0.0325 or better |
| B | 20 | 0.043 or better |
| C | 15 | 0.050 or better |
| D | 10 | 0.058 or better |
| E | 5 | anything slower |

Stage score is the sum of:

- **Base**: 15 points per word killed
- **Rank points**: the table above
- **Accuracy**: `max(0, (floor(accuracy) - 90) * 100)`, where accuracy is correct keys over keys typed for that stage
- **Prisoner rescues**: 150 points each
- **Difficulty bonus**: `((1 + 0.1 * p) * mode multiplier - 1) * (rank points + base)`, so a higher tier and the strict mode both pay more

Final score is the three stage scores plus 100 per life remaining (the results screen still labels this bonus a placeholder).

## Enemies

| Enemy | Words needed | Behaviour |
| --- | --- | --- |
| Zombie | 1 | Basic walker |
| Rotter | 1 | Basic walker |
| Brute | 1 | Basic walker |
| Husk | 1 | Basic walker |
| Armored | 2 | The first word breaks the armour and the zombie staggers back; a second word finishes it |
| Axeman | 3 | Axes, then armour, then plain. A typo while it still has its axes gets an axe thrown at you, and a landed axe costs a life |
| Bat | 1 | Comes in threes alongside some zombies, flies above the lanes, and uses low tier words |
| Prisoner | 1 | Not a threat. Rescue it for 150 points before it reaches you, or it is lost (counted, no life lost) |
| ZOMBIE LORD | 3 | Boss at the end of the Crypt, one word per phase |

## Leaderboard

Scores are submitted as GitHub issues and processed by a workflow into `scores.json`.

1. A `[SCORE]` issue is opened, titled `[SCORE] <mode> - <score> - <submission id>`, with the same values repeated in the body as `**Label:** value` lines (`**Name:**`, `**Mode:**`, `**Score:**`, `**Submission ID:**`, plus anything else the sender adds).
2. `.github/workflows/process-score.yml` runs on `issues: [opened]` and ignores any title that does not start with `[SCORE]`.
3. The issue is validated: the author must be in `ALLOWED_AUTHORS` (default: the repository owner), the mode must be in `ALLOWED_MODES`, the score must be within `MAX_SCORE`, the name and submission id must match their patterns, and the submission id must not already be on any board.
4. An accepted score is appended, sorted by score (descending, then date, then id), trimmed to `TOP_N` per mode, and written to `scores.json` with an `updated` timestamp. The workflow commits that file itself.
5. The issue is commented with the outcome (accepted plus rank, `not_top`, `duplicate`, or the rejection reason) and closed. Issues from other authors are ignored and left open, so nobody can bypass the sender by opening an issue by hand.

The game file in this repo does not submit scores itself: there is no `fetch` or `XMLHttpRequest` in it. The `[SCORE]` issues are created by the leaderboard Worker, which lives outside this repo.

Workflow settings, at the top of `.github/workflows/process-score.yml`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `ALLOWED_MODES` | `strict,original` | Modes accepted; empty accepts any mode name |
| `MAX_SCORE` | `1000000` | Sanity ceiling, not a rule |
| `TOP_N` | `100` | Entries kept per mode |
| `ALLOWED_AUTHORS` | `github.repository_owner` | Who may create score issues; empty accepts anyone (not recommended) |

`scores.json` looks like this:

```json
{
  "updated": "2026-10-02T04:05:03Z",
  "boards": {
    "strict": [
      {
        "name": "Brutus",
        "score": 7523,
        "id": "e720c04d-87d9-4685-a4d3-fdbf71dc7dc8",
        "date": "2026-10-02T03:54:19Z",
        "extra": { "ip": "...", "submitted": "2026-10-02T03:54:18.897Z" }
      }
    ]
  }
}
```

Any `**Label:** value` line beyond name, mode, score and submission id is stored on the entry under `extra` (up to 12 fields; keys are lowercased with non-alphanumeric characters replaced by underscores, values trimmed to 64 characters). New fields therefore need no workflow change. A missing or unreadable `scores.json` is not fatal: the workflow starts a fresh board.

## Repo layout

```
typing_dungeon_v21.html                the game, single file
scores.json                            leaderboard data, written by the workflow
.github/workflows/process-score.yml    turns [SCORE] issues into scores.json entries
```

## Working on the game

- No build, no dependencies and no tests. The game logic is deliberately DOM free (`G`, `tierFor`, `pickFrom`, `key`, `kill`, `update`), so it can be driven headlessly; the browser glue is at the bottom of the file behind a `typeof window` check.
- Art is embedded as base64 data URIs (the zombie sprite sheet, the Axeman atlas and the three stage photos), which is why the file is about 2 MB. Editing art means replacing those strings.
- Word lists and their par values are embedded in `WORDSET`, taken from the original game. They are not published anywhere else in the repo, so treat them as data for this game rather than something to extract.
- Sound is synthesised at runtime (Web Audio), so there are no audio files.
- The bow and its arrows live in the effects layer (`shootArrow`, `drawArrows`, `drawBow` and the `arrows` array), fired from `hooks.hit` and drawn during the render pass. Effects are driven by hooks so the game logic stays DOM free and testable; put new visuals there rather than in `G`.

## Provenance

There is no licence file in this repo. The word lists and par values come from The Typing of the Dead (SEGA), and the art is embedded in the HTML. Check before reusing either outside this project.
## Hosted game preview and database

The optional Cloudflare hosted version adds a player name, automatic score saving,
personal bests and an all-time board per mode. Open **Scores** on the title or final
screen. Your player identity stays in that browser. Failed saves can be retried.
Local file play works offline.

Each code PR gets its own live preview once Cloudflare is configured. Production
updates from merged `main`. Preview scores stay separate from production.
See [HOSTING.md](HOSTING.md) for setup, deployment and the playback testing loop.
The legacy issue pipeline remains active until the new production path is verified.
