from __future__ import annotations

import argparse
import os
from pathlib import Path

from .agent import LocalAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="PDflow local agent")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PD_FLOW_AGENT_PORT", "43219")))
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()
    agent = LocalAgent(
        repo_root=args.repo_root,
        host=args.host,
        port=args.port,
        auth_token=args.token,
        poll_seconds=args.poll_seconds,
    )
    server = agent.start()
    print(
        f"PD_FLOW_AGENT_READY port={server.server_address[1]} pid={os.getpid()}",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        agent.stop()


if __name__ == "__main__":
    main()
