# Typing of the Dungeon

A Typing of the Dead inspired typing game. Monsters walk down a corridor towards you with a word attached; type the word to kill them before they reach you.

The whole game is one file, `typing_dungeon_v21.html`: engine, renderer, procedural sound, embedded art and the word lists. There is no build step and no dependencies.

## Play it

**Online:** https://play.dtyper.workers.dev. Pick a name when the game opens and your runs are saved to a leaderboard for each mode.

**Offline:** open `typing_dungeon_v21.html` in a browser. Either double-click the file, drag it into a browser window, or serve the folder with anything static:

```sh
python3 -m http.server 8000   # then open http://localhost:8000/typing_dungeon_v21.html
```

Opened as a file or from a static server, the game runs fully offline with no network requests. The hosted version at https://play.dtyper.workers.dev also saves scores to a database (see [Leaderboard](#leaderboard)).

- Keyboard required (it is a typing game). A wide window works best: the canvas is 960x540 and scales up to a 16:9 box.
- Sound is generated with Web Audio. Browsers only allow audio after a user gesture, so the first key press starts the audio context. F2 mutes and unmutes.
- Best score and the chosen mode are kept in `localStorage`, so they survive a reload. Hosted play also keeps your player identity there; clearing browser storage loses it.
- Each correct key fires your pistol (see [The pistol](#the-pistol)).

## Controls

| Key | Action |
| --- | --- |
| Any letter, digit or space | Type the word on the targeted monster |
| Enter | Start from the title; advance the stage results; take a continue after dying; return to the title from the final screen |
| Tab or arrow keys | Switch mode on the title screen and the leaderboard (strict / original) |
| N | Hosted game, title screen: change your player name |
| S | Hosted game, title or final screen: open the leaderboard |
| R | Hosted game, final screen: retry a score that failed to save |
| Escape | Pause and unpause |
| F2 | Mute / unmute |

Targeting: the first letter you type locks onto the monster whose word starts with that letter, and that target is drawn above the others until it dies. Keys with no valid target are ignored, as in the original game. While a word is locked, every key goes to that monster.

## The pistol

A retro pistol sits at the bottom of the view. Every correct key fires it, with recoil, a muzzle flash and a procedural gunshot. A wrong key or a key with no target fires nothing, and typing a prisoner's word frees them without a shot.

The pistol is visual only. A hit still resolves the instant you type the last letter of a word, so ranks, timing and scores are unchanged by it, and leaderboard entries stay comparable with earlier ones.

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

The hosted game saves scores to a Cloudflare D1 database through a Worker (`server/worker.mjs`).

- The first time the hosted game opens it asks for a name on the title screen (Esc plays as a guest). Press **N** on the title to change it and **S** on the title or final screen to open the leaderboard, which is drawn in the game itself.
- Each mode has its own all-time board, showing each player's best run. Tied scores share a rank, and the top 100 are shown.
- Identity is a random token kept in your browser, so there is no login and no cross-device recovery. Names can be changed and need not be unique.
- A failed save is queued in the browser and can be retried with R, including after a reload. Resubmitting the same run never creates a duplicate.
- Scores are reported by the client, so this is a casual leaderboard rather than a cheat-proof one.
- Offline file play still works; the name and leaderboard screens simply do not appear.

Production is `https://play.dtyper.workers.dev`. Every code PR gets its own preview at `https://pr-N.dtyper.workers.dev` with a separate database, so test scores never reach the production board. Setup, deployment and the testing loop are in [HOSTING.md](HOSTING.md). The earlier GitHub issue pipeline has been retired, and its two scores were not imported, so the hosted boards started empty.

## Repo layout

```
typing_dungeon_v21.html                the game, single file
server/                                hosted score API (Cloudflare Worker) and D1 migrations
scripts/, tests/                       host staging and verification
HOSTING.md                             hosting, database setup and the playback loop
.github/workflows/check-game.yml       checks on every PR
.github/workflows/host-game.yml        PR previews and production deploy on Cloudflare
```

## Working on the game

- No build and no dependencies for the game itself. Checks live in `tests/` and `scripts/check-game.py` (see AGENTS.md for the commands). The game logic is deliberately DOM free (`G`, `tierFor`, `pickFrom`, `key`, `kill`, `update`), so it can be driven headlessly; the browser glue is at the bottom of the file behind a `typeof window` check.
- Art is embedded as base64 data URIs (the zombie sprite sheet, the Axeman atlas and the three stage photos), which is why the file is about 2 MB. Editing art means replacing those strings.
- Word lists and their par values are embedded in `WORDSET`, taken from the original game. They are not published anywhere else in the repo, so treat them as data for this game rather than something to extract.
- Sound is synthesised at runtime (Web Audio), so there are no audio files.
- The pistol lives in the effects layer (`shootPistol`, `drawPistol`, `PISTOL_VIEW`), fired from `hooks.hit` and drawn during the render pass. Effects are driven by hooks so the game logic stays DOM free and testable; put new visuals there rather than in `G`.

## Provenance

There is no licence file in this repo. The word lists and par values come from The Typing of the Dead (SEGA), and the art is embedded in the HTML. Check before reusing either outside this project.
