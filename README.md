# Typing of the Dungeon

A Typing of the Dead inspired typing game. Monsters come at you with a word attached; type the word to kill them before they reach you.

The game is one file, `typing_dungeon_v48.html`: engine, renderer, sound effects, embedded art, stage photos, weapons and the word lists. Music is in `SOUNDS/`. There is no build step and no dependencies.

## Play it

**Online:** https://play.dtyper.workers.dev. Pick a name when the game opens and your full runs are saved to a leaderboard for each mode.

**Offline:** keep `typing_dungeon_v48.html` and the `SOUNDS` folder side by side and open the HTML in a browser: double-click it, drag it into a browser window, or serve the folder with anything static:

```sh
python3 -m http.server 8000   # then open http://localhost:8000/typing_dungeon_v48.html
```

Opened as a file or from a static server, the game runs fully offline with no network requests, and the name and leaderboard screens do not appear.

- Keyboard required (it is a typing game). A wide window works best: the canvas is 960x540 and scales up to a 16:9 box.
- Browsers only allow audio after a user gesture, so the first key press starts sound and music. F2 mutes and unmutes everything. Without `SOUNDS/` the game still runs, with sound effects but no music.
- Mode, difficulty, stage choice, weapon and best scores are kept in `localStorage`, so they survive a reload. Hosted play also keeps your player identity there; clearing browser storage loses it.

## Controls

| Key | Action |
| --- | --- |
| Any letter, digit or space | Type the word on the targeted monster |
| Enter | Start from the title; advance the stage results; confirm a weapon; take a continue after dying; return to the title from the final screen |
| Up / Down | Title screen: choose the mode, difficulty or stage row |
| Left / Right | Title screen: change the chosen row. Weapon picker: choose a weapon (also 1 to 5) |
| Tab | Title screen and leaderboard: switch mode (strict / original) |
| H | Title screen: how to play (the full rules card; any key returns) |
| N | Hosted game, title screen: change your player name |
| S | Hosted game, title or final screen: open the leaderboard |
| R | Hosted game, final screen: retry a score that failed to save |
| Escape | Pause and unpause (all sound stops while paused); leave the weapon picker before a single-stage run |
| F2 | Mute / unmute |

Targeting: the first letter you type locks onto the monster whose word starts with that letter, and that target is drawn above the others until it dies. Keys with no valid target are ignored, as in the original game. While a word is locked, every key goes to that monster.

## Modes and difficulty

| Mode | Case | Spaces | Score multiplier |
| --- | --- | --- | --- |
| strict | counted | counted | 1.0 |
| original | ignored | ignored (typing a space does nothing) | 0.75 |

| Difficulty | Spawn rate | Typing time | Bats | Score multiplier |
| --- | --- | --- | --- | --- |
| easy | -50% | +25% | fewest | 0.6 |
| normal | -25% | normal | fewer | 0.8 |
| hard | full | normal | most | 1.0 |

The stage row picks `ALL STAGES` (a full run) or a single stage for practice. Best scores are kept separately for each mode, difficulty and stage choice. Only full runs go on the hosted leaderboard.

## How a run works

Five stages, one wave each:

1. **THE SUPPLY CORRIDOR**
2. **THE CONTROL ROOM** (boss: THE GRENADIER)
3. **THE BONFIRE GATE**
4. **THE COURTYARD**
5. **THE CRYPT** (final boss: the ZOMBIE LORD)

The weapon picker opens after the Control Room, before stage 3. A single-stage run opens it before that stage.

You start with 3 lives and 5 continues. A monster that reaches you costs a life; at zero lives the run ends and a continue resets you to 3 lives and costs 5 p. Each stage ends with a results parchment, and the run ends with a final score.

### Word difficulty

Words come from the original game's word lists, tiers 1 to 16 (the HUD shows `L040` for tier 4). The tier comes from the enemy type and the hidden progress counter p. Each stage also sets a minimum, so the run ramps up:

| Stage | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| Minimum tier | none | 3 | 4 | 6 | 8 |

Bosses type sentences from tiers 14 to 16.

### The hidden progress counter (p)

`p` starts at 3 and is clamped to 0 to 15. It is not shown as a number, but it drives the word tier.

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

- **Base**: 15 points per word killed (blast kills give base points only, no rank)
- **Rank points**: the table above
- **Accuracy**: `max(0, (floor(accuracy) - 90) * 100)`, where accuracy is correct keys over keys typed for that stage
- **Prisoner rescues**: 150 points each
- **Difficulty bonus**: `((1 + 0.1 * p) * mode multiplier * difficulty multiplier - 1) * (rank points + base)`, so a higher tier, strict mode and hard difficulty all pay more

Final score is the stage scores plus 100 per life remaining (the results screen still labels this bonus a placeholder).

## Weapons

| Weapon | Feel |
| --- | --- |
| Service pistol | The original. Short, loud, with a pixel muzzle flash |
| Suppressed AR | Suppressor, rails, red dot and laser. Quiet thup, tiny flash, brass flying out |
| Ray gun | Red and chrome retro blaster. Glowing teal core, a bolt and ring, a zap |
| Double barrel | Two big flashes, a boom and rising smoke |
| Crossbow | A bolt streaks away with a string twang |

Every correct key fires the weapon, with recoil, a muzzle effect and a procedural shot. A wrong key or a key with no target fires nothing, and typing a prisoner's word frees them without a shot. Weapons are visual only: ranks, timing and scores are the same with every weapon.

## Enemies

| Enemy | Words needed | Behaviour |
| --- | --- | --- |
| Zombie, Rotter, Brute, Husk | 1 | Walkers |
| Armored | 2 | The first word breaks the armour, which clangs and scatters plates that clank on the floor; a second word finishes it |
| Axeman | 3 | Axes, then armour, then plain. A typo while it still has its axes gets an axe thrown at you, and a landed axe costs a life |
| Lobber | 1 | Walks at half speed. A typo while it is targeted makes it pull a pin and throw a grenade; finish its word while the grenade is in the air and it bursts harmlessly. Killed any other way, it drops its grenade, which goes off where it stood |
| Bat | 1 | Comes in threes alongside some zombies, flies above the lanes, and uses low tier words |
| Prisoner | 1 | Not a threat. Rescue it for 150 points before it reaches you, or it is lost |
| THE GRENADIER | 3 | Control Room boss. Throws on his own half-way through each walk, with a click-click-whistle cue a second before. Lock onto him before the throw and he holds the grenade until you typo or kill him; dead, he drops it |
| ZOMBIE LORD | 3 | Crypt boss. A typo greys him out for 1.5 s (your progress is kept) and he summons a Lobber or an Axeman |

**Grenades.** A landed grenade costs a life and sets you on fire. Finish your next target without a typo and the fire goes out; a typo while burning costs another life. A dropped grenade kills every monster near it except bosses and bats, and a monster you were typing when a blast kills it explodes too, so blasts chain.

## Sound

Sound effects (shots, hits, armour clangs, explosions, fire, the heartbeat when something is close) are synthesised with Web Audio. Music is in `SOUNDS/`:

| File | Plays |
| --- | --- |
| `STAGE 1.mp3`, `STAGE 2.mp3`, `STAGE 3.mp3` | During a stage, looped. The Supply Corridor, Control Room and Bonfire Gate use `STAGE 1`, the Courtyard `STAGE 2`, the Crypt `STAGE 3` |
| `STAGE END.mp3` | On each stage results screen and the mid-run weapon picker, looped |
| `FINAL RESULTS.mp3` | On the final score screen, once |

Music pauses with the game, drops to 40% on the game over screen, and fades out over half a second between tracks. A missing file is skipped silently.

## Leaderboard

The hosted game saves scores to a Cloudflare D1 database through a Worker (`server/worker.mjs`).

- The first time the hosted game opens it asks for a name (Esc plays as a guest). Press **N** on the title to change it and **S** on the title or final screen to open the leaderboard, which is drawn in the game itself.
- Each mode has its own all-time board, showing each player's best full run. Tied scores share a rank, and the top 100 are shown. Single-stage runs are not submitted.
- Identity is a random token kept in your browser, so there is no login and no cross-device recovery. Names can be changed and need not be unique.
- A failed save is queued in the browser and can be retried with R, including after a reload. Resubmitting the same run never creates a duplicate.
- Scores are reported by the client, so this is a casual leaderboard rather than a cheat-proof one.
- The boards show scoring version `v48-1`. Runs from the three-stage v21 game are kept in the database but not shown.

Production is `https://play.dtyper.workers.dev`. Every code PR gets its own preview at `https://pr-N.dtyper.workers.dev` with a separate database, so test scores never reach the production board. Setup, deployment and the testing loop are in [docs/HOSTING.md](docs/HOSTING.md).

## Adding a stage

Stages are data. `tools/stage_mapper.py` lays one out on its background photo and saves it as JSON:

```sh
pip install pillow
python tools/stage_mapper.py
```

File > New stage from image, then:

- **Attack line**: drag the yellow line to where enemies stop and hit you, the three lane dots along it, and the height handle above the middle lane to the size of an enemy there. Keep the line above the HUD (about 81% of the image height) or enemies' feet are hidden when they reach you.
- **Zones** (key 2): click where an enemy appears, drag the square above it to its height, and add up to two waypoints (key 3). In the Zones tab set which lanes it walks to and how often it is picked. Mark one zone as the boss zone if the wave has a boss.
- **Masks** (key 4): outline foreground objects. An enemy is drawn behind a mask while its feet are above the mask's depth line, so a mask something should step out from behind needs its depth line below that spawn point.
- **Lights** (keys 5 and 6) and fog: flickering glows and flames.
- **Wave** tab: the enemy queue, the seconds between spawns, and the maximum on screen at once.

Ghost figures show every zone walking to each of its lanes at the size the game will draw them, hidden behind masks the same way the game does; Walk animates them. The Check tab lists problems such as zones that cannot spawn, horizons that disagree between zones, or a boss with no boss zone. File > Import stage from game HTML loads an existing stage for reference.

The JSON and the photo then go into the game file as a new stage (see `AGENTS.md`).

## Repo layout

```
typing_dungeon_v48.html                the game, single file
SOUNDS/                                music, loaded from beside the HTML
archive/                               older versions (v21, v31, v38, v47), kept for reference
tools/stage_mapper.py                  stage layout tool
web/og.jpg                             link preview image for Discord, Slack and the like
server/                                hosted score API (Cloudflare Worker) and D1 migrations
relay/                                 GitHub webhook relay that streams PR events to agents
scripts/, tests/                       host staging, the layout check and verification
docs/HOSTING.md                        hosting, database setup and the playback loop
.github/workflows/check-game.yml       checks on every PR
.github/workflows/host-game.yml        PR previews and production deploy on Cloudflare
```

## Working on the game

- Run `scripts/dev-setup.sh` once after cloning: it installs the shared git hooks and pruning. Work in a worktree per task and open PRs against `main` (AGENTS.md has the workflow).
- No build and no dependencies for the game itself. Checks live in `tests/` and `scripts/check-game.py` (see AGENTS.md for the commands). The game logic is deliberately DOM free (`G`, `tierFor`, `pickFrom`, `key`, `kill`, `update`), so it can be driven headlessly; the browser glue, including music and the score client, is at the bottom of the file behind a `typeof window` check.
- Art is embedded as base64 data URIs (the zombie sprite sheet, the Axeman and Lobber atlases, the pistol and weapon sprites, and the five stage photos), which is why the file is about 3.8 MB. Editing art means replacing those strings.
- Word lists and their par values are embedded in `WORDSET`, taken from the original game. They are not published anywhere else in the repo, so treat them as data for this game rather than something to extract.
- Weapons live in the effects layer: the list is `WEAPONS` (engine side, so the picker is testable), `WEAPON_AT` sets where the picker opens in a full run, sprites are `PISTOL_SRC` and `WIMG.*`, and recoil and muzzle effects are in `WSTYLE`. To add a weapon, add a `WEAPONS` entry, a sound, a sprite and a `WSTYLE` entry.

## Provenance

There is no licence file in this repo. The word lists and par values come from The Typing of the Dead (SEGA), and the art is embedded in the HTML. Check before reusing either outside this project.
