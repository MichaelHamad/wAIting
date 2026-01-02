"""Command-line interface for waiting."""

import argparse
import sys

from .runner import Runner
from .notifiers import BellNotifier


def main() -> None:
    """Main entry point for the waiting CLI."""
    parser = argparse.ArgumentParser(
        prog='waiting',
        description='Run a command and alert when it waits for input',
        usage='%(prog)s [options] command [args...]'
    )

    parser.add_argument(
        'command',
        nargs=argparse.REMAINDER,
        help='Command to run'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Handle -- separator if present
    command = args.command
    if command and command[0] == '--':
        command = command[1:]

    if not command:
        parser.print_help()
        sys.exit(1)

    # Create runner with bell notifier
    notifier = BellNotifier()
    runner = Runner(notifier=notifier)

    # Run the command and exit with its exit code
    exit_code = runner.run(command)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
