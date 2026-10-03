# PR events webhook

Agents working on this repo react to PR events (opened, pushed, merged, comments, reviews,
finished checks) the moment they happen, instead of polling. GitHub sends a signed webhook
to a small Cloudflare Worker, `pr-events`, which streams the events to listeners that hold
a token. It is separate from the game Worker: play, scores and the D1 databases are not
involved, and nothing goes to a third party.

```
GitHub webhook --signed POST--> https://pr-events.dtyper.workers.dev/github
                                   |  verifies the signature, keeps the last 500 events
agents  <--WebSocket (token)-------+  /stream?since=<seq>
```

## One-off setup (repository admin, about five minutes)

The relay deploys from `main` through `.github/workflows/relay.yml`. Until the two secrets
below exist it answers `503` and stores nothing.

1. **Generate two secrets** on your machine:

   ```sh
   openssl rand -hex 32   # webhook secret
   openssl rand -hex 32   # listen token
   ```

2. **Store them on the Worker.** Either in the Cloudflare dashboard (Workers and Pages,
   `pr-events`, Settings, Variables and Secrets, add both as type Secret), or with Wrangler
   from a clone of this repo:

   ```sh
   npx wrangler@4 secret put GITHUB_WEBHOOK_SECRET --config relay/wrangler.json
   npx wrangler@4 secret put LISTEN_TOKEN --config relay/wrangler.json
   ```

   `https://pr-events.dtyper.workers.dev/health` then reports `"configured":true`.

3. **Add the webhook** in GitHub: Settings, Webhooks, Add webhook.

   | Field | Value |
   | --- | --- |
   | Payload URL | `https://pr-events.dtyper.workers.dev/github` |
   | Content type | `application/json` |
   | Secret | the webhook secret from step 1 |
   | SSL verification | enabled |
   | Events | Let me select individual events: **Pull requests**, **Pull request reviews**, **Pull request review comments**, **Issue comments**, **Workflow runs** (untick Pushes) |
   | Active | ticked |

   GitHub sends a ping straight away. Recent Deliveries should show it with a `200`.

4. **Share the listen token** privately (password manager or direct message, never in the
   repo, an issue or a PR) with each collaborator who runs agents. They save it once:

   ```sh
   mkdir -p ~/.config/dungeon-typer
   printf '%s' '<listen token>' > ~/.config/dungeon-typer/relay-token
   chmod 600 ~/.config/dungeon-typer/relay-token
   ```

## Listening

```sh
node scripts/pr-listen.mjs
```

One line per event, for example `#27 review by ExsoLam: approved`. It reconnects on its
own and replays what it missed since the last line it printed.

## Rotating or turning it off

- Rotate: repeat steps 1 and 2 for the secret you are replacing, update the webhook secret
  in GitHub (step 3) or re-share the listen token (step 4).
- Pause: untick Active on the webhook. Remove: delete the webhook, then the `pr-events`
  Worker in Cloudflare.

## What it trusts

- Only requests with a valid `X-Hub-Signature-256` for the webhook secret are accepted.
- Only holders of the listen token can read the stream. Events carry what GitHub already
  shows publicly on this repo (PR titles, authors, comment excerpts).
- Listeners treat an event as a prompt to re-read the PR with `gh`, not as an instruction.
