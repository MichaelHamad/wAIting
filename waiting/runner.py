"""PTY runner with transparent I/O passthrough."""

import atexit
import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios
import tty
from typing import List, Optional

from .detector import WaitDetector
from .events import ProcessExited
from .notifiers import BellNotifier


# I/O buffer size
BUFFER_SIZE = 4096

# Poll interval for detector checks (seconds)
POLL_INTERVAL = 0.1


class Runner:
    """PTY wrapper that runs a command and detects waiting states."""

    def __init__(self, notifier: Optional[BellNotifier] = None):
        self.notifier = notifier or BellNotifier()
        self.detector = WaitDetector()
        self.child_pid: Optional[int] = None
        self.master_fd: Optional[int] = None
        self.original_termios: Optional[list] = None
        self.original_winsize: Optional[bytes] = None

    def run(self, command: List[str]) -> int:
        """
        Run a command in a PTY and detect waiting states.

        Returns the exit code of the command.
        """
        if not command:
            print("waiting: missing command", file=sys.stderr)
            return 1

        # Save terminal state before we modify anything
        self._save_terminal_state()

        # Register cleanup handler
        atexit.register(self._restore_terminal_state)

        try:
            # Fork a PTY
            self.child_pid, self.master_fd = pty.fork()

            if self.child_pid == 0:
                # Child process - exec the command
                self._exec_child(command)
                # exec_child doesn't return on success

            # Parent process
            return self._run_parent()

        except Exception as e:
            print(f"waiting: {e}", file=sys.stderr)
            return 1
        finally:
            self._restore_terminal_state()
            atexit.unregister(self._restore_terminal_state)

    def _exec_child(self, command: List[str]) -> None:
        """Execute the command in the child process."""
        try:
            os.execvp(command[0], command)
        except FileNotFoundError:
            print(f"waiting: command not found: {command[0]}", file=sys.stderr)
            sys.exit(127)
        except PermissionError:
            print(f"waiting: permission denied: {command[0]}", file=sys.stderr)
            sys.exit(126)

    def _run_parent(self) -> int:
        """Run the parent process I/O loop."""
        # Set up signal handlers
        self._setup_signals()

        # Propagate initial window size to child
        self._propagate_winsize()

        # Set stdin to raw mode for transparent passthrough
        if sys.stdin.isatty():
            tty.setraw(sys.stdin.fileno())

        # Make master_fd non-blocking
        flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
        fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        exit_code = self._io_loop()

        return exit_code

    def _io_loop(self) -> int:
        """Main I/O multiplexing loop."""
        stdin_fd = sys.stdin.fileno()
        stdout_fd = sys.stdout.fileno()

        while True:
            # Check if child is still alive
            try:
                pid, status = os.waitpid(self.child_pid, os.WNOHANG)
                if pid != 0:
                    # Child exited
                    if os.WIFEXITED(status):
                        return os.WEXITSTATUS(status)
                    elif os.WIFSIGNALED(status):
                        return 128 + os.WTERMSIG(status)
                    return 1
            except ChildProcessError:
                return 1

            # Set up select with timeout for polling
            read_fds = [self.master_fd]
            if sys.stdin.isatty():
                read_fds.append(stdin_fd)

            try:
                readable, _, _ = select.select(read_fds, [], [], POLL_INTERVAL)
            except (select.error, InterruptedError):
                continue

            # Handle readable file descriptors
            for fd in readable:
                if fd == self.master_fd:
                    # Output from child
                    try:
                        data = os.read(self.master_fd, BUFFER_SIZE)
                        if data:
                            os.write(stdout_fd, data)
                            self.detector.record_output(data)
                        else:
                            # EOF - child closed PTY
                            continue
                    except OSError:
                        continue

                elif fd == stdin_fd:
                    # Input from user
                    try:
                        data = os.read(stdin_fd, BUFFER_SIZE)
                        if data:
                            os.write(self.master_fd, data)
                            self.detector.record_input()
                        else:
                            # EOF on stdin
                            continue
                    except OSError:
                        continue

            # Check detector and alert if needed
            if self.detector.check(self.master_fd):
                self.notifier.notify()

    def _setup_signals(self) -> None:
        """Set up signal handlers."""
        # Forward SIGINT to child
        def handle_sigint(signum, frame):
            if self.child_pid:
                os.kill(self.child_pid, signal.SIGINT)

        # Forward SIGTERM to child
        def handle_sigterm(signum, frame):
            if self.child_pid:
                os.kill(self.child_pid, signal.SIGTERM)
            self._restore_terminal_state()
            sys.exit(128 + signal.SIGTERM)

        # Handle window resize
        def handle_sigwinch(signum, frame):
            self._propagate_winsize()

        signal.signal(signal.SIGINT, handle_sigint)
        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGWINCH, handle_sigwinch)

    def _propagate_winsize(self) -> None:
        """Propagate terminal window size to the child PTY."""
        if not sys.stdin.isatty() or self.master_fd is None:
            return

        try:
            winsize = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b'\x00' * 8)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
        except (OSError, termios.error):
            pass

    def _save_terminal_state(self) -> None:
        """Save the current terminal state for later restoration."""
        if sys.stdin.isatty():
            try:
                self.original_termios = termios.tcgetattr(sys.stdin.fileno())
            except termios.error:
                pass

    def _restore_terminal_state(self) -> None:
        """Restore the terminal to its original state."""
        if self.original_termios and sys.stdin.isatty():
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH,
                                  self.original_termios)
            except termios.error:
                pass
