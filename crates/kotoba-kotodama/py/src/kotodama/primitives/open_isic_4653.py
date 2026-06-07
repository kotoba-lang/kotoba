from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4653_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of agricultural machinery, equipment and supplies

    This class includes the wholesale of agricultural machinery, equipment and supplies.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4653":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4653."}
    return await task_open_isic_classify_entity(**kwargs)
