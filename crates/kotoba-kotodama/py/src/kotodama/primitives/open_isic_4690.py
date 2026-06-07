from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4690_classify(**kwargs: Any) -> dict[str, Any]:
    """Non-specialised wholesale trade

    This class includes the wholesale of a variety of goods without any particular specialisation.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4690":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4690."}
    return await task_open_isic_classify_entity(**kwargs)
