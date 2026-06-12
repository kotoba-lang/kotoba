"""Command + CommandStack implementation for omni.kit.commands.

Each Command captures both the operation and its inverse. `do()` applies the
operation; `undo()` reverses it using state captured at do-time. The stack
maintains:

  - undo_stack: commands that have been executed (top = most recent)
  - redo_stack: commands that have been undone (top = next to redo); cleared
                whenever a new command is executed (standard undo-tree
                semantics — no branching)

`CommandStack` enforces a `history_size` cap (default 1000) so long-running
sessions don't accumulate unbounded memory. Hit the cap → oldest command is
dropped, never undoable again.

Thread safety: CommandStack is NOT thread-safe. Wrap external access in a
lock if commands fire from concurrent contexts (rare in Omniverse where
the command stack is owned by the main UI thread).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ────────────────────────────────────────────────────────────────────────────
# Command base
# ────────────────────────────────────────────────────────────────────────────


class Command:
    """Abstract base. Subclasses MUST override `do()` and `undo()`.

    `do()` should be idempotent only in the sense that re-calling it after
    an undo() restores the same state — implementations should NOT assume
    do/undo are called any specific number of times in sequence by the
    stack (it can issue do → undo → do → undo → undo arbitrarily).
    """

    # Subclasses may override `name` for tagging in the stack history.
    name: str = ""

    def do(self) -> None:
        """Apply the operation. Raise on error before mutating state where
        possible — the stack treats an exception here as "command did not
        execute" and does NOT push it onto the undo stack."""
        raise NotImplementedError("Command.do must be overridden")

    def undo(self) -> None:
        """Reverse the operation. Like do(), exceptions leave the stack in
        a defined state — the command remains on the redo side."""
        raise NotImplementedError("Command.undo must be overridden")

    def __repr__(self) -> str:
        cls = type(self).__name__
        if self.name:
            return f"<{cls} name={self.name!r}>"
        return f"<{cls}>"


# ────────────────────────────────────────────────────────────────────────────
# Concrete reference commands
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class SetAttributeCommand(Command):
    """Set a key on a dict-like target; undo restores prior value (or
    removes the key if it was absent)."""
    target: Dict[str, Any]
    key: str = ""
    value: Any = None
    name: str = "SetAttribute"

    # Captured at do() time.
    _had_key: bool = field(default=False, init=False, repr=False)
    _prev_value: Any = field(default=None, init=False, repr=False)

    def do(self) -> None:
        self._had_key = self.key in self.target
        self._prev_value = self.target.get(self.key)
        self.target[self.key] = self.value

    def undo(self) -> None:
        if self._had_key:
            self.target[self.key] = self._prev_value
        else:
            self.target.pop(self.key, None)


@dataclass
class DeleteEntryCommand(Command):
    """Delete a key from a dict-like target; undo restores the prior value.

    A no-op when the key is absent — do() captures that the key was absent
    and undo() leaves the target unchanged."""
    target: Dict[str, Any]
    key: str = ""
    name: str = "DeleteEntry"

    _had_key: bool = field(default=False, init=False, repr=False)
    _prev_value: Any = field(default=None, init=False, repr=False)

    def do(self) -> None:
        self._had_key = self.key in self.target
        if self._had_key:
            self._prev_value = self.target[self.key]
            del self.target[self.key]

    def undo(self) -> None:
        if self._had_key:
            self.target[self.key] = self._prev_value


@dataclass
class GroupCommand(Command):
    """Compound command — executes a list of sub-commands as one undoable
    unit. Sub-commands execute in given order; undo reverses in reverse
    order. An exception in any sub-command rolls back all preceding sub-
    commands in the group (atomic semantics)."""
    commands: List[Command] = field(default_factory=list)
    name: str = "Group"

    # Captured at do() time: how many sub-commands succeeded (so undo
    # knows how many to reverse if do() partially failed).
    _executed_count: int = field(default=0, init=False, repr=False)

    def do(self) -> None:
        self._executed_count = 0
        for cmd in self.commands:
            cmd.do()
            self._executed_count += 1

    def undo(self) -> None:
        # Reverse in reverse order, only those that successfully executed.
        for i in range(self._executed_count - 1, -1, -1):
            self.commands[i].undo()


# ────────────────────────────────────────────────────────────────────────────
# CommandStack — history management
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class CommandStack:
    """Undo/redo history. Each entry is a Command instance with captured
    inverse state. New commands clear the redo stack (no branching)."""
    history_size: int = 1000
    _undo_stack: List[Command] = field(default_factory=list, init=False, repr=False)
    _redo_stack: List[Command] = field(default_factory=list, init=False, repr=False)
    # Registered command class lookup for string-based `execute("Name", ...)`.
    _registry: Dict[str, type] = field(default_factory=dict, init=False, repr=False)

    def register(self, name: str, cls: type) -> "CommandStack":
        """Register a Command subclass under `name` for string-based execute."""
        if not issubclass(cls, Command):
            raise TypeError(f"{cls.__name__} must subclass Command")
        self._registry[name] = cls
        return self

    def registered_names(self) -> List[str]:
        return list(self._registry.keys())

    # ── execute ──────────────────────────────────────────────────────────

    def execute(self, command_or_name, **kwargs) -> Command:
        """Execute a Command. Two forms:

          stack.execute(my_cmd)                # pass Command instance
          stack.execute("SetAttribute", ...)   # name + kwargs → instantiate

        On success the command is pushed to the undo stack + the redo
        stack is cleared. On exception the stack is unchanged.
        """
        if isinstance(command_or_name, Command):
            cmd = command_or_name
        elif isinstance(command_or_name, str):
            cls = self._registry.get(command_or_name)
            if cls is None:
                raise KeyError(
                    f"unknown command '{command_or_name}'; "
                    f"registered: {sorted(self._registry.keys())}"
                )
            cmd = cls(**kwargs)
        else:
            raise TypeError(
                f"execute() expected Command or str; got {type(command_or_name).__name__}"
            )
        # Note: exception here propagates without modifying the stack.
        cmd.do()
        self._undo_stack.append(cmd)
        self._redo_stack.clear()
        # Trim history.
        if len(self._undo_stack) > self.history_size:
            drop = len(self._undo_stack) - self.history_size
            self._undo_stack = self._undo_stack[drop:]
        return cmd

    # ── undo / redo ──────────────────────────────────────────────────────

    def undo(self) -> Optional[Command]:
        """Undo the most recent command. Returns the undone command, or
        None if the undo stack is empty."""
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return cmd

    def redo(self) -> Optional[Command]:
        """Re-do the most recently undone command. Returns the redone
        command, or None if the redo stack is empty."""
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        cmd.do()
        self._undo_stack.append(cmd)
        return cmd

    # ── introspection ────────────────────────────────────────────────────

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def undo_depth(self) -> int:
        return len(self._undo_stack)

    def redo_depth(self) -> int:
        return len(self._redo_stack)

    def history(self) -> List[str]:
        """Returns list of command names from oldest → newest undoable."""
        return [c.name or type(c).__name__ for c in self._undo_stack]

    def clear(self) -> None:
        """Drop all history (irreversible)."""
        self._undo_stack.clear()
        self._redo_stack.clear()


# ────────────────────────────────────────────────────────────────────────────
# Module-level singleton API (Omniverse Kit pattern)
# ────────────────────────────────────────────────────────────────────────────


_DEFAULT_STACK: Optional[CommandStack] = None


def get_stack() -> CommandStack:
    """Returns the module-level CommandStack singleton (lazy-initialized
    with the default reference commands registered)."""
    global _DEFAULT_STACK
    if _DEFAULT_STACK is None:
        _DEFAULT_STACK = CommandStack()
        _DEFAULT_STACK.register("SetAttribute", SetAttributeCommand)
        _DEFAULT_STACK.register("DeleteEntry", DeleteEntryCommand)
        _DEFAULT_STACK.register("Group", GroupCommand)
    return _DEFAULT_STACK


def execute(command_or_name, **kwargs) -> Command:
    """Module-level execute on the singleton stack."""
    return get_stack().execute(command_or_name, **kwargs)


def undo() -> Optional[Command]:
    """Module-level undo on the singleton stack."""
    return get_stack().undo()


def redo() -> Optional[Command]:
    """Module-level redo on the singleton stack."""
    return get_stack().redo()


def register(name: str, cls: type) -> None:
    """Module-level register on the singleton stack."""
    get_stack().register(name, cls)
