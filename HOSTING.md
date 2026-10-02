# Hosted game and score service

The browser game remains one HTML file, with no build step or dependencies.
The optional hosted service uses a Cloudflare Worker with static assets and D1.
Wrangler is deployment tooling only; it is not a browser dependency.

The Cloudflare account subdomain is `dtyper`. Production uses the `play` Worker
at `https://play.dtyper.workers.dev`; PR previews use
`https://pr-N.dtyper.workers.dev`. The game opens at `/`, and the original
`/typing_dungeon_v21.html` entry point remains available. Changing the hostname
creates a fresh browser identity because local storage belongs to each origin.

## Release and playback loop

1. Open a code PR. Its head commit deploys to its own `pr-N` Worker.
2. Open the deployment link on the PR or in the workflow summary. Check
   `/api/health` for the exact head SHA and `pr-N` scope before testing.
3. Play, save a score, reload and check the board. Use two browser profiles to test
   two players. Check strict and original separately. Test a submission retry.
4. Record the tested SHA and findings in the PR. Push fixes to that same PR; the
   stable preview URL updates after the new deployment completes.
5. Merge only after review and playback. A push to merged `main` deploys production.

PRs use a dedicated preview D1 database. Rows are additionally partitioned by PR
number, so different previews do not share players or scores. Production uses a
separate D1 database. Preview migrations must be additive while other PRs use it.
Do not drop or alter shared preview tables without coordinating an upgrade.
A single production URL cannot simultaneously represent multiple PRs: production
shows merged code; each PR has a separate live version.

The earlier GitHub Pages workflow has been removed. This Worker deployment serves the game and API together and is the only production publisher.

## One-time Cloudflare configuration

In the Cloudflare account, create two D1 databases:
`dungeon-typer-production` and `dungeon-typer-preview`.
Enable a Workers subdomain for the account. Record both D1 database IDs.

In GitHub Settings > Secrets and variables > Actions, add:

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `CLOUDFLARE_API_TOKEN` | Scoped Cloudflare deployment token |
| Variable | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |
| Variable | `D1_PRODUCTION_DATABASE_ID` | Production D1 database ID |
| Variable | `D1_PREVIEW_DATABASE_ID` | Different preview D1 database ID |

The token needs Workers Admin and D1 Edit on the selected account. Creating the
first Worker for each new PR requires the Workers product-level Admin role;
Editor is enough only for updating an existing Worker. Older dashboards may show
the legacy Account Workers Scripts Edit permission instead. See the current
[Workers permissions](https://developers.cloudflare.com/workers/authorization/workers/).
Do not put the token in a PR, game source or chat. Only same-repository PRs deploy
with secrets; fork PRs run checks. People allowed to push branches in this repo
must be trusted to use the deployment token. Use GitHub environment approvals if
that is not appropriate for all contributors.

The workflow deliberately fails with an actionable message until configuration
exists. It does not pretend a preview is live. New same-repository PR commits then
publish automatically. Existing PRs need a new commit or workflow rerun after
configuration. Protect main against direct pushes and require the check job plus
review in GitHub branch settings. Restrict the production environment to main.
These account settings are not created by merely adding a workflow file.

## Local development

From the repo root, with Node 22 and Python 3 installed:

```sh
python3 scripts/check-game.py
node tests/validation.mjs
python3 tests/database.py
node scripts/stage-host.mjs
npx --yes wrangler@4 d1 migrations apply DB --local --config .deploy/wrangler.json
npx --yes wrangler@4 dev --config .deploy/wrangler.json
```

Open the local URL reported by Wrangler. Opening the HTML as a local file keeps
normal offline gameplay and shows an offline message in the score panel.
Only the staged game, landing redirect and `SOUNDS/` are published. Source
files are not static assets. Do not host the repo root.

## Score behaviour and limits

A random browser token identifies a player. Only its SHA-256 hash is stored on the
server. Players may change their display name; identical names are permitted and
are separate players. Browser storage is needed to retain identity between visits.
Clearing it loses access to that identity. There is no cross-device login yet.

Each completed run gets a unique ID. Failed saves stay in a browser queue for
retry, including after reload. Repeating an identical submission does not create
a second run. Boards show each player's best per mode and scoring version. Rank
uses competition ranking: tied scores share a rank. The board displays at most
100 players; the database retains all accepted runs.

The Worker accepts same-origin JSON, validates fields and limits each player to
five new scores per minute. These checks do not prove a client-reported score was
achieved by playing. This is a casual leaderboard, not cheat-proof competition.
For a public launch with substantial traffic, add edge rate limits to player
creation and submission; per-player limits can be bypassed by making identities.

Version `v21-1` describes the current scoring rules. Change it in the Worker and
browser submission together if scoring changes; cosmetic changes keep it.
Weekly boards and run-history screens can query the retained runs but are not yet
exposed in this first release.

## Retired issue pipeline

The earlier GitHub issue workflow (`[SCORE]` issues turned into `scores.json`) has
been removed. Its two historical scores were deliberately not imported, so the
hosted boards started empty. They remain in git history.

## Preview cleanup

Closing a PR does not delete its Worker or test scores automatically in this first
release. The owner can delete `pr-N` in Cloudflare and remove rows
with `scope='pr-N'` from the preview database (runs first, then players). Never use
production for that cleanup. Preview Workers count towards the account's limits.

## PR watcher agreement

PR #10 proposes the agent watcher agreement separately. Agent scheduling belongs
to the agent host; GitHub workflows deploy and check commits, they do not wake a
local agent by themselves. A watcher should observe current SHA, comments, reviews,
checks, deployments and closure, stay quiet when unchanged, and stop on closure.
