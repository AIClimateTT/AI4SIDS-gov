# Prompt testing and replay

How the corp capture prompt is versioned, tested and watched over time, and how to check a reported issue or a complaint of drift against the real chat it happened in.

## Why this exists

The capture clerk is a prompt (`corp_capture`) running on a model (gpt-oss-20b on `nim-prod`). Either can change: we edit the prompt, or the model is upgraded. When officers say "it used to get this right", we need to answer two questions with evidence instead of guesses:

1. **Did a change make things better or worse?** Score each prompt version on the same fixed test set, on the same model.
2. **What happened in this particular chat, and would another version have done better?** Replay the recorded chat against other versions.

Everything runs in prod, next to the real NIM, and is triggered from a laptop. Nobody needs a terminal on the server.

## The pieces

| Piece | Where | What it does |
|---|---|---|
| Prompt registry | `apps/backend/app/prompts/` | Each prompt is versioned part files plus `prompt.yaml` (version, changelog). `prompts.lock.json` holds the SHA-256 of every version; `history/vN.txt` freezes each version's exact text so it can be re-run later. |
| Turn records | `capture_turns` table | Every officer turn records the prompt id, version, hash and model it ran on, whether the reply had to be retried, and `interventions`: how many times each code guard had to correct the model. |
| Test set | `apps/backend/evals/corp_capture/cases.yaml` | Officer messages taken from UAT transcripts, with **checks** on what a correct capture contains. Kept in git, versioned with the prompts. |
| Stats | `prompts stats` | Per version, from recorded turns: unreadable replies, retries, guard corrections, officer edits right after a turn. Shows how a version behaves on real use. |
| Eval runner | `docker-compose.evals.yml` | A small authenticated service in prod. It runs the test set against NIM, replays recorded chats, and passes `/v1` through to NIM for one-off checks. |
| Replay | `app/prompts/replay.py` | Reads a chat from the staging or prod database (read-only) and runs its turns again with chosen versions. |

### Why the guards matter for tracking

The model's reply goes through code before it reaches the record: it drops numbers the officer never said, reverts dates the officer did not give, restores dropped rows, clears invented zero counts, keeps fields the officer set by hand, and flags false claims of a change. Each correction is counted on the turn. **A falling guard count for a version means the model is getting it right by itself.** A rising count on the same version over time means the model, or how officers write, has drifted.

## How it fits together

```
 laptop (task / CLI)
   │  HTTPS + Bearer EVAL_RUNNER_API_KEY
   ▼
 eval-runner (prod server, built from the staging branch)
   ├──► nim-prod:8000             model calls (one run at a time)
   ├──► postgres-staging   (RO)   testers' chats
   └──► postgres-prod      (RO)   officers' chats
```

- **One runner, not one per environment.** There is one NIM, and runs share its GPU with live traffic. A runner built from `staging` has the newest prompt versions and can still run every frozen earlier one, so it covers prod as well.
- **The test set needs no database.** Its cases come from git. Only replay reads the databases.
- **Staging** is where testers find problems. Their transcripts become cases.
- **Prod** is where `prompts stats`, and replays of officers' chats, show whether a version holds up on real use.

## Setup

### Dokploy: the eval-runner stack

1. Create an app from `docker-compose.evals.yml` on the **staging** branch. Watch paths: `apps/backend/**`, `docker-compose.evals.yml`.
2. Attach a domain to `eval-runner`, port `8090`, with HTTPS.
3. Set environment:

   | Variable | Value |
   |---|---|
   | `EVAL_RUNNER_API_KEY` | A long random secret (`openssl rand -hex 32`). Required: with no key the runner refuses everything. Never commit it. |
   | `EVAL_STAGING_DATABASE_URL` | `postgresql+psycopg://dmcu_replay:<pw>@postgres-staging:5432/dmcu_staging` |
   | `EVAL_PROD_DATABASE_URL` | `postgresql+psycopg://dmcu_replay:<pw>@postgres-prod:5432/dmcu` |

   Leave a database URL empty to not offer that source.
4. The stack joins `dmcu-app-network` (NIM, prod Postgres) and `dmcu-staging-network` (staging Postgres). Both infra stacks must be up first.

### A read-only database role

The runner already opens every connection with `default_transaction_read_only=on`. Give it a role that cannot write either, so the protection doesn't rest on one setting. Run this once per database (`psql` in the Postgres container):

```sql
CREATE ROLE dmcu_replay LOGIN PASSWORD '<pw>';
GRANT CONNECT ON DATABASE dmcu_staging TO dmcu_replay;   -- or dmcu on prod
GRANT USAGE ON SCHEMA public TO dmcu_replay;
GRANT SELECT ON capture_sessions, capture_turns TO dmcu_replay;
```

Replay reads only those two tables.

### Laptop

In `apps/backend/.env` (git-ignored):

```
EVAL_RUNNER_URL=https://<your eval domain>
EVAL_RUNNER_API_KEY=<same key>
```

Check: `task remote:info` prints the deployed prompt versions and model.

## Workflows

### 1. Change the prompt

1. Edit the part files in `app/prompts/corp_capture/` (`identity.txt`, `rules.txt`, `example.txt`).
2. **Try the draft before committing:** `uv run python -m app.cli prompts remote-eval --draft --repeat 1`. This sends your working copy to the runner as an uncommitted draft. It's scored on the deployed test set and shows up as `corp_capture@draft-<hash>`.
3. When it looks right:
   1. Bump `version` in `prompt.yaml`.
   2. Add a changelog entry: why, and what evidence prompted the change.
   3. Run `uv run python -m app.cli prompts lock`.

   `task prompts:check` and the tests fail until all three are done, and a locked version can never be edited in place.
4. Push to `staging`. The runner redeploys with the new version.
5. Score both versions on NIM:
   ```
   task remote:eval VERSION=2 REPEAT=3
   task remote:eval REPEAT=3
   ```
   Then `uv run python -m app.cli prompts compare <v2 result> <v3 result>` (both results are saved in `evals/corp_capture/results/`).
6. Test by hand on staging, then merge to `main`. Prod sessions pin the prompt they started on, so a deploy never changes a chat that's already underway.
7. Afterwards, `prompts stats` on prod shows whether the new version's guard corrections and officer edits actually went down.

`--repeat 3` matters: the model varies from run to run, and a check that passes 2 of 3 times is a weak rule, not a pass.

### 2. Investigate a reported issue or drift

When an officer or tester says "it got this wrong":

1. **Find the chat**:
   ```
   task remote:sessions SOURCE=prod CORP=arima SINCE=2026-11-18
   ```
   Each row shows the session id, last change (local time), corporation, draft or filed, number of officer turns, incident and log counts, the prompt versions it ran on, and the first message.
2. **See its turns**:
   ```
   task remote:session ID=42 SOURCE=prod
   ```
   Each turn shows its sequence number, time, kind (officer turn, edit, import…), prompt version and guard corrections.
3. **Replay it**:
   ```
   task remote:replay ID=42 SOURCE=prod                  # the current version
   task remote:replay ID=42 SOURCE=prod VERSIONS="1 2"   # several versions
   task remote:replay ID=42 SOURCE=prod DRAFT=1          # plus your uncommitted fix
   task remote:replay ID=42 SOURCE=prod MODE=chained     # whole chat from the start
   ```
   To replay only some turns, use the CLI: `uv run python -m app.cli prompts remote-replay 42 --source prod --turn 5 --turn 7`.
4. **Read the result** (see below) and decide:
   - **Same mistake on every version, including the one it ran on:** a prompt or guard problem. Fix it, and try the fix with `DRAFT=1` on the same chat.
   - **Recorded turn was wrong, but the same version gets it right now:** the model is inconsistent on this input. Write a case and use `--repeat 3` to see how often it fails.
   - **An older version gets it right, the newer one doesn't:** a regression from the version bump. Read the changelog entry between them.
   - **Recorded turn was right, replay is wrong on the same version:** model drift. Check `remote:info` for a model change.
5. **Make it permanent:** write the turn up as a case (next section), so every future version is scored on it.

### 3. Turn a chat into a test case

A replay has no pass or fail, because nothing in the database says what the right capture was. A case adds that. Add it to `evals/corp_capture/cases.yaml`:

```yaml
  - id: arima-tarpaulin-size-not-quantity
    source: prod session 42 turn 5, 2026-11-18
    today: 2026-11-18
    prior: {}            # the working set before the turn, if it matters
    history: []          # earlier chat messages, if it matters
    message: Requesting 3 16x20 tarpaulins for LP 12 Example Road.
    checks:
      - {kind: row, rows: logs, where: {item: tarpaulin}, expect: {quantity: 3}}
      - {kind: none, rows: logs, where: {quantity: 16}}
```

- **Replace real names, house numbers and phone numbers with made-up ones.** Cases live in git; real officer data doesn't belong there.
- **Check properties, not exact wording.** Check kinds: `row`, `count`, `every`, `none`, `field`, `asks`, `parsed`, `any`. Value specs are described at the top of `app/prompts/evals.py`.
- **Try a case before committing it:** put it in a file and run `uv run python -m app.cli prompts remote-eval --inline my-case.yaml --repeat 3`.
- **Commit and push.** From then on, every eval run includes the case.

### 4. Watch prod over time

`uv run python -m app.cli prompts stats` (with the prod `DATABASE_URL`) groups real officer turns by prompt version and model:
- unreadable replies
- retries
- turns the guards had to correct, by guard
- officer edits right after a turn

Turns from before the registry existed are grouped as "before registry".

## Reading a replay

```
corp_capture@2: 3/8 turns differ from recorded, 0 unreadable, 0 failed; corrections: dates_reverted 1

--- turn 5 (2026-11-18): Requesting 3 16x20 tarpaulins ...
  recorded (corp_capture@2): Added a request for 16 tarpaulins.
    added log 3: ...
  corp_capture@2: Added a request for 3 tarpaulins (16x20).
    asks: ...
    corrections: {'invented_numbers': 1}
    vs recorded:
      log 3.quantity: 16 → 3
  corp_capture@3:
    ...
    vs corp_capture@2:
      ...
```

- **`recorded`**: what happened at the time, with the changes that turn made.
- **`vs recorded`**: how the replay's capture differs from the recorded one. "same" means identical.
- **`vs corp_capture@N`**: when several versions run, how each later version differs from the first.
- **`corrections`**: what the guards had to fix in this replay's model output.
- **Recorded mode** (the default): every turn starts from the recorded state, so one bad turn doesn't affect later ones.
- **Chained mode**: replays the chat as the officer would have experienced it on that version, start to finish. Differences add up from turn to turn, which is the point.
- **Row ids**: a different row id on an otherwise identical row shows as removed plus added. Read the two together.

## Rules

- **One run at a time.** Evals and replays share the production GPU with officers. A second run gets `409` until the first finishes. A replay is capped at 60 model calls; pick turns or fewer versions for long chats.
- **Real data stays out of git.** Replay results contain real officer messages. They're kept on the runner's volume (`dmcu-evals_results`), and the CLI saves its copy in `apps/backend/evals/replays/`, which is git-ignored. Test cases use made-up details.
- **The key is personal.** Every route except `/health` needs `EVAL_RUNNER_API_KEY` as a Bearer token. The key is never forwarded to NIM. To rotate it, change it in Dokploy and in your `.env`.
- **Read-only.** The runner never writes to either database, by connection setting and by role.
- **Locked versions are frozen.** If a version's text changes, `prompts check` fails. Make a new version instead.

## Reference

### Task commands

| Command | Does |
|---|---|
| `task remote:info` | Deployed prompt versions and model |
| `task remote:eval [VERSION=n] [REPEAT=n]` | Score a version on the test set; saves to `evals/corp_capture/results/` |
| `task remote:runs` | Recent evals and replays |
| `task remote:sessions [SOURCE=] [CORP=] [SINCE=]` | Chats that can be replayed |
| `task remote:session ID= [SOURCE=]` | One chat's turns |
| `task remote:replay ID= [SOURCE=] [VERSIONS="1 2"] [DRAFT=1] [MODE=chained]` | Replay a chat; saves to `evals/replays/` |
| `task prompts:check` | Fail if a prompt changed without a version bump |

The CLI underneath is `uv run python -m app.cli prompts <command> --help`. It also has `remote-result <id>` to fetch a finished run, and the local `eval`, `compare`, `stats`, `show`, `lock` and `list` commands.

### Runner API

All routes except `/health` need `Authorization: Bearer <key>`.

| Route | |
|---|---|
| `GET /health` | Liveness, no auth |
| `GET /info` | Prompt versions, hashes, model |
| `POST /evals` | `{prompt_id, version, draft_text, repeat (1–5), cases, inline_cases}` → `202 {id}` |
| `GET /evals` | Recent runs (evals and replays) |
| `GET /evals/{id}` | Progress while running, then the result and readable `summary_lines` |
| `GET /evals/compare?a=&b=` | Differences between two eval results |
| `GET /sources` | Which databases are configured |
| `GET /sessions?source=&corp=&since=&status=&limit=` | Chats, newest first, dated in local time |
| `GET /sessions/{id}?source=` | One chat's turns |
| `POST /replays` | `{source, session_id, prompt_id, versions, draft_text, mode, turns}` → `202 {id}`; fetch it with `GET /evals/{id}` |
| `/v1/...` | OpenAI-style passthrough to NIM |
