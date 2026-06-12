from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2432_classify(**kwargs: Any) -> dict[str, Any]:
    """Casting of non-ferrous metals.

    This class includes the casting of non-ferrous metals and alloys.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2432":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2432."}
    return await task_open_isic_classify_entity(**kwargs)
