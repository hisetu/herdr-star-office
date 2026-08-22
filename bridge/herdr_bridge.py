#!/usr/bin/env python3
"""herdr -> Star-Office bridge.

Polls `herdr agent list` and pushes each herdr agent's live lifecycle state
into a Star-Office-UI backend as a guest agent, so the pixel office shows your
running herdr agents (qa, dev1..3, ...) walking around in real time.

No third-party deps (stdlib only). Star-Office join auto-approves a valid key.

Env / flags:
  --office URL      Star-Office base URL      (default $OFFICE_URL or http://127.0.0.1:19000)
  --key KEY         join key                  (default $OFFICE_JOIN_KEY or ocj_example_team_01)
  --interval SEC    poll interval             (default 5)
  --all             also include unnamed pi panes (labelled by pane id)
  --workspace WID   only agents in this herdr workspace (default: all)
  --once            one push cycle then exit (for testing)
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from urllib.error import URLError, HTTPError

# herdr lifecycle -> Star-Office recognised state
STATE_MAP = {
    "working": "executing",
    "idle": "idle",
    "done": "idle",
    "blocked": "error",
    "unknown": "idle",
}


def herdr_agents(workspace=None):
    out = subprocess.run(["herdr", "agent", "list"], capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        raise RuntimeError(f"herdr agent list failed: {out.stderr.strip()}")
    data = json.loads(out.stdout)
    agents = data.get("result", {}).get("agents", [])
    if workspace:
        agents = [a for a in agents if a.get("workspace_id") == workspace]
    return agents


def post(url, payload, timeout=10):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return e.code, {}
    except URLError as e:
        return 0, {"ok": False, "msg": str(e)}


class Bridge:
    def __init__(self, office, key, include_all, workspace):
        self.office = office.rstrip("/")
        self.key = key
        self.include_all = include_all
        self.workspace = workspace
        self.joined = {}   # display_name -> agentId

    def display_name(self, a):
        return a.get("name") or f"pi:{a.get('pane_id')}"

    def wanted(self, a):
        if a.get("name"):
            return True
        return self.include_all

    def state_of(self, a):
        return STATE_MAP.get(a.get("agent_status", "unknown"), "idle")

    def detail_of(self, a):
        cwd = os.path.basename(a.get("cwd", "") or "") or a.get("cwd", "")
        star = " ★" if a.get("focused") else ""
        return f"{a.get('agent_status', '?')} · {cwd}{star}"

    def join(self, name, state, detail):
        st, resp = post(f"{self.office}/join-agent",
                        {"name": name, "joinKey": self.key, "state": state, "detail": detail})
        if resp.get("ok") and resp.get("agentId"):
            self.joined[name] = resp["agentId"]
            print(f"  joined {name} -> {resp['agentId']}")
            return True
        print(f"  join failed {name}: {st} {resp.get('msg')}")
        return False

    def push(self, name, state, detail):
        aid = self.joined.get(name)
        if not aid:
            return self.join(name, state, detail)
        st, resp = post(f"{self.office}/agent-push",
                        {"agentId": aid, "joinKey": self.key, "state": state, "detail": detail, "name": name})
        if resp.get("ok"):
            return True
        # removed / rejected -> drop and rejoin next cycle
        if st in (403, 404):
            self.joined.pop(name, None)
        else:
            print(f"  push failed {name}: {st} {resp.get('msg')}")
        return False

    def leave(self, name):
        aid = self.joined.pop(name, None)
        if aid:
            post(f"{self.office}/leave-agent", {"agentId": aid, "name": name})
            print(f"  left {name}")

    def cycle(self):
        agents = [a for a in herdr_agents(self.workspace) if self.wanted(a)]
        present = set()
        for a in agents:
            name = self.display_name(a)
            present.add(name)
            self.push(name, self.state_of(a), self.detail_of(a))
        # anyone we joined but is gone -> leave
        for gone in [n for n in self.joined if n not in present]:
            self.leave(gone)
        return len(present)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--office", default=os.environ.get("OFFICE_URL", "http://127.0.0.1:19000"))
    ap.add_argument("--key", default=os.environ.get("OFFICE_JOIN_KEY", "ocj_example_team_01"))
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--all", action="store_true", dest="include_all")
    ap.add_argument("--workspace", default=os.environ.get("HERDR_WORKSPACE_ID"))
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    b = Bridge(args.office, args.key, args.include_all, args.workspace)
    print(f"bridge -> {b.office} (key={b.key}, workspace={b.workspace or 'all'}, "
          f"{'all panes' if b.include_all else 'named only'})")
    if args.once:
        n = b.cycle()
        print(f"pushed {n} agent(s)")
        return
    try:
        while True:
            try:
                n = b.cycle()
                print(f"[{time.strftime('%H:%M:%S')}] pushed {n} agent(s)")
            except Exception as e:
                print(f"cycle error: {e}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopping; leaving agents...")
        for n in list(b.joined):
            b.leave(n)


if __name__ == "__main__":
    main()
