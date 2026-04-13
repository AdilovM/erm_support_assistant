"""Entry point for the Tirithel desktop agent.

Usage:
    python -m tirithel.agent                    # Start with system tray
    python -m tirithel.agent --cli              # Start in CLI mode
    python -m tirithel.agent --api-url http://server:8000
"""

import argparse
import logging
import sys

from tirithel.agent.agent import TirithelAgent
from tirithel.agent.tray import TrayApp


def main():
    parser = argparse.ArgumentParser(
        description="Tirithel Desktop Agent - captures support sessions"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Tirithel API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Screenshot capture interval in seconds (default: 3.0)",
    )
    parser.add_argument(
        "--profile-id",
        default=None,
        help="Software profile ID to tag sessions with",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in CLI mode instead of system tray",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    agent = TirithelAgent(
        api_url=args.api_url,
        capture_interval=args.interval,
        profile_id=args.profile_id,
    )

    tray = TrayApp(agent)

    if args.cli:
        tray._run_cli_mode()
    else:
        tray.run()


if __name__ == "__main__":
    main()
