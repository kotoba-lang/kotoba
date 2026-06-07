from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1629_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other products of wood; manufacture of articles of cork, straw and plaiting materials

    This class includes the manufacture of other wood products and articles of cork, straw and plaiting materials not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1629":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1629."}
    return await task_open_isic_classify_entity(**kwargs)
