from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2710_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of electric motors, generators, transformers and electricity distribution and control apparatus.

    This class includes the manufacture of electric motors, generators, transformers and electricity distribution and control apparatus.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2710":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2710."}
    return await task_open_isic_classify_entity(**kwargs)
