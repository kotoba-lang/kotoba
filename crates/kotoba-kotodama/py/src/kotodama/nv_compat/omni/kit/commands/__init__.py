"""omni.kit.commands — undoable Command stack mirror.

Mirrors `omni.kit.commands` (Omniverse Kit 105+). Classic Command pattern
with do()/undo() — each command captures the inverse operation at do-time
so undo can reverse it without consulting external state.

Standard usage:

    from kotodama.nv_compat.omni.kit.commands import (
        execute, undo, redo, register,
        SetAttributeCommand, DeleteEntryCommand, GroupCommand,
    )

    target = {"color": "red", "size": 10}
    execute("SetAttribute", target=target, key="color", value="blue")
    # target == {"color": "blue", "size": 10}
    undo()
    # target == {"color": "red", "size": 10}
    redo()
    # target == {"color": "blue", "size": 10}

    # Group compound ops as a single undo unit:
    execute("Group", commands=[
        SetAttributeCommand(target, key="color", value="green"),
        SetAttributeCommand(target, key="size", value=20),
    ])
    undo()  # both reverted in one step

`CommandStack` is also exposed for direct manipulation; `execute()` /
`undo()` / `redo()` operate on a module-level singleton that mirrors
Omniverse Kit's global stack.
"""

from .command import (
    Command,
    CommandStack,
    DeleteEntryCommand,
    GroupCommand,
    SetAttributeCommand,
    execute,
    get_stack,
    redo,
    register,
    undo,
)

__all__ = [
    "Command", "CommandStack",
    "SetAttributeCommand", "DeleteEntryCommand", "GroupCommand",
    "execute", "undo", "redo", "register", "get_stack",
]
