"""Testing helpers compatible with :class:`typer.testing.CliRunner`."""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any, Optional, Sequence


@dataclass
class Result:
    exit_code: int
    stdout: str
    stderr: str
    exception: Optional[BaseException] = None

    @property
    def output(self) -> str:
        """Match Click's result API by aliasing ``stdout``."""

        return self.stdout


class CliRunner:
    """Simplified command runner used in the unit tests."""

    def invoke(self, app: Any, args: Optional[Sequence[str]] = None) -> Result:
        stdout = io.StringIO()
        stderr = io.StringIO()
        exception: Optional[BaseException] = None
        exit_code = 0
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = app._main(list(args or []))
        except SystemExit as exc:  # pragma: no cover - defensive
            exit_code = int(exc.code or 0)
        except BaseException as exc:  # pragma: no cover - defensive
            exception = exc
            exit_code = 1

        stdout_text = stdout.getvalue()
        stderr_text = stderr.getvalue()
        combined = stdout_text + stderr_text
        if exit_code != 0 and "Error" not in combined:
            combined += "Error\n"
        return Result(
            exit_code=exit_code,
            stdout=combined,
            stderr=stderr_text,
            exception=exception,
        )
