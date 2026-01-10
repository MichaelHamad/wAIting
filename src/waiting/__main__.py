"""Main entry point for the Waiting CLI."""

import sys

from .cli import CLI


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for the Waiting CLI.

    Args:
        args: Command-line arguments. Defaults to sys.argv[1:]

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    args = args or sys.argv[1:]
    cli = CLI()

    # No args or help requested
    if not args or args[0] in ["--help", "-h", "help"]:
        return cli.show_help()

    command = args[0]

    if command == "enable":
        return cli.enable()
    elif command == "disable":
        return cli.disable()
    elif command == "status":
        return cli.status()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return cli.show_help()


if __name__ == "__main__":
    sys.exit(main())
