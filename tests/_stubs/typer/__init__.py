"""Minimal Typer-compatible interface for the test environment.

Only the behaviour exercised by the repository's test-suite is implemented.  It
supports defining commands with ``Option`` and ``Argument`` parameters, invoking
commands programmatically and rendering help output through the standard
:mod:`argparse` machinery.  The goal is to remain dependency free while keeping a
familiar API for the rest of the project.
"""

from __future__ import annotations

import argparse
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import (Any, Callable, Dict, Iterable, List, Optional, Sequence,
                    Tuple, Union, get_args, get_origin, get_type_hints)


class Exit(Exception):
    """Signal an early exit from a command."""

    def __init__(self, code: int = 0):
        super().__init__(code)
        self.code = int(code)


class Option:
    """Descriptor used in command function signatures."""

    def __init__(self, default: Any, *param_decls: str, help: str = ""):
        self.default = default
        self.param_decls = [decl for decl in param_decls if isinstance(decl, str)]
        self.help = help


class Argument:
    """Descriptor representing a positional argument."""

    def __init__(self, default: Any = ..., *, help: str = ""):
        self.default = default
        self.help = help


@dataclass
class _Parameter:
    name: str
    annotation: Any
    default: Any
    help: str
    kind: str  # "argument" or "option"
    is_path: bool = False

    def convert(self, value: Any) -> Any:
        if self.is_path and value is not None and not isinstance(value, Path):
            return Path(value)
        return value


def _resolve_type(annotation: Any) -> Tuple[Callable[[str], Any], bool]:
    if annotation is inspect._empty:
        return str, False

    origin = get_origin(annotation)
    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if args:
            return _resolve_type(args[0])
        return str, False
    if origin is Tuple:
        args = get_args(annotation)
        if args:
            return _resolve_type(args[0])
    if origin is list or origin is Iterable:
        args = get_args(annotation)
        if args:
            return _resolve_type(args[0])

    if annotation is Path:
        return str, True
    if annotation in (int, float, str):
        return annotation, False
    if annotation is bool:
        return bool, False
    return str, False


def _expand_param_decls(param_decls: Sequence[str], fallback: str) -> List[str]:
    if not param_decls:
        return [fallback]
    expanded: List[str] = []
    for decl in param_decls:
        if "/" in decl and decl.startswith("--"):
            expanded.extend(part for part in decl.split("/") if part)
        else:
            expanded.append(decl)
    return expanded


class Command:
    def __init__(self, func: Callable[..., Any], name: str):
        self.func = func
        self.name = name
        description = (inspect.getdoc(func) or "").strip()
        self.summary = description.splitlines()[0] if description else ""
        self.parser = argparse.ArgumentParser(prog=name, description=description)
        self.parameters: List[_Parameter] = []
        self._build_parser()

    def _build_parser(self) -> None:
        signature = inspect.signature(self.func)
        type_hints = get_type_hints(self.func)
        for parameter in signature.parameters.values():
            default = parameter.default
            annotation = type_hints.get(parameter.name, parameter.annotation)

            if isinstance(default, Option):
                self._add_option(parameter.name, annotation, default)
            elif isinstance(default, Argument):
                self._add_argument(parameter.name, annotation, default)
            else:
                self._add_argument(parameter.name, annotation, Argument(default))

    # Argument / option helpers -------------------------------------------------
    def _add_argument(self, name: str, annotation: Any, arg: Argument) -> None:
        converter, is_path = _resolve_type(annotation)
        required = arg.default is ... or arg.default is inspect._empty
        default_value = None if required else arg.default
        param = _Parameter(
            name, annotation, default_value, arg.help, "argument", is_path
        )
        self.parameters.append(param)

        kwargs: Dict[str, Any] = {"help": arg.help}
        if converter is not str or is_path:
            kwargs["type"] = str if is_path else converter
        if required:
            self.parser.add_argument(name, **kwargs)
        else:
            kwargs["nargs"] = "?"
            kwargs["default"] = arg.default
            self.parser.add_argument(name, **kwargs)

    def _add_option(self, name: str, annotation: Any, opt: Option) -> None:
        converter, is_path = _resolve_type(annotation)
        option_names = _expand_param_decls(
            opt.param_decls, f"--{name.replace('_', '-')}"
        )
        is_bool_option = (
            converter is bool
            or isinstance(opt.default, bool)
            or any("/" in decl for decl in opt.param_decls)
        )

        param = _Parameter(name, annotation, opt.default, opt.help, "option", is_path)
        self.parameters.append(param)

        kwargs: Dict[str, Any] = {"dest": name}
        if not is_bool_option:
            if converter is not str or is_path:
                kwargs["type"] = str if is_path else converter
            kwargs["default"] = opt.default
            if opt.help:
                kwargs["help"] = opt.help
            self.parser.add_argument(*option_names, **kwargs)
            return

        # Boolean flags
        default_value = opt.default
        true_flag, *rest = option_names
        self.parser.add_argument(
            true_flag,
            action="store_true",
            default=default_value,
            help=opt.help,
            dest=name,
        )
        if rest:
            false_flag = rest[0]
            self.parser.add_argument(false_flag, action="store_false", dest=name)

    # Invocation ----------------------------------------------------------------
    def invoke(self, argv: Sequence[str]) -> int:
        try:
            namespace = self.parser.parse_args(list(argv))
        except SystemExit as exc:
            return int(exc.code or 0)

        kwargs: Dict[str, Any] = {}
        for param in self.parameters:
            value = getattr(namespace, param.name, param.default)
            kwargs[param.name] = param.convert(value)

        try:
            result = self.func(**kwargs)
        except Exit as exc:
            return exc.code
        return int(result) if isinstance(result, int) else 0


class Typer:
    def __init__(self, help: str = ""):
        self.help = help
        self._commands: Dict[str, Command] = {}

    def command(
        self, name: Optional[str] = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            command_name = name or func.__name__.replace("_", "-")
            self._commands[command_name] = Command(func, command_name)
            return func

        return decorator

    # Execution helpers --------------------------------------------------------
    def _main(self, argv: Optional[Sequence[str]] = None) -> int:
        args = list(argv or [])
        if not args:
            self._print_global_help()
            return 0
        if args[0] in {"-h", "--help"}:
            self._print_global_help()
            return 0
        command = self._commands.get(args[0])
        if command is None:
            print(f"Error: Unknown command '{args[0]}'")
            return 2
        return command.invoke(args[1:])

    def _print_global_help(self) -> None:
        if self.help:
            print(self.help)
        if self._commands:
            print("\nCommands:")
            for name in sorted(self._commands):
                summary = self._commands[name].summary
                if summary:
                    print(f"  {name:15s} {summary}")
                else:
                    print(f"  {name}")

    def __call__(self, argv: Optional[Sequence[str]] = None) -> None:
        exit_code = self._main(argv or sys.argv[1:])
        raise SystemExit(exit_code)


__all__ = [
    "Argument",
    "Exit",
    "Option",
    "Typer",
]
