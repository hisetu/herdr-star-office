# herdr-star-office

Bridge your running **herdr** agents into the pixel-art
[Star-Office-UI](https://github.com/ringhyacinth/Star-Office-UI) dashboard, so
`qa`, `dev1..3`, and any other herdr agents show up as characters walking
around a little office in real time — driven by their actual lifecycle state.

```
herdr agent list (JSON)  ->  map state  ->  Star-Office /join-agent + /agent-push
```

## Quick start

```bash
./run.sh            # sets up (clones upstream, venv, config), starts backend, runs bridge
# open http://127.0.0.1:19000 in a browser
```

`./run.sh --all` also shows unnamed `pi` panes. `Ctrl-C` stops the bridge (its
agents leave the office); the backend keeps running (`pkill -f star-office/backend/app.py` to stop it).

## Pieces

- `bridge/herdr_bridge.py` — stdlib-only poller. Reads `herdr agent list`, maps
  each agent's lifecycle state, and pushes it as a Star-Office guest.
  Flags: `--office URL --key KEY --interval SEC --all --workspace WID --once`.
- `run.sh` — one-command setup + backend + bridge.
- `star-office/` — upstream Star-Office-UI (cloned by `run.sh`; **not** committed here).

## State mapping (herdr → Star-Office)

| herdr `agent_status` | Star-Office state | office area |
|---|---|---|
| `working`  | `executing`   | 💻 work    |
| `blocked`  | `error`       | 🐛 bug     |
| `idle`     | `idle`        | 🛋 breakroom |
| `done`     | `idle`        | 🛋 breakroom |
| `unknown`  | `idle`        | 🛋 breakroom |

Focused agent is marked with `★` in its detail line.

## Notes

- Star-Office join **auto-approves** a valid join key, so guests appear with no
  manual approval. `run.sh` writes a reusable key (`ocj_example_team_01`,
  `maxConcurrent: 30`) into `star-office/join-keys.json`.
- Requires Python 3.10+ (upstream backend) and the `herdr` CLI on PATH.
- **Licensing:** upstream code is MIT; its **art assets are non-commercial /
  learning use only** — do not ship this in a commercial product with the
  bundled art. Replace assets with your own for any commercial use.
- This bridge is unaffiliated with the upstream project.
