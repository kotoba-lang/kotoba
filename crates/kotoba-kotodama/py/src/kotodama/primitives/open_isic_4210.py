from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4210_classify(**kwargs: Any) -> dict[str, Any]:
    """Construction of roads and motorways.

    This class includes the construction of motorways, streets, roads and other vehicular and pedestrian ways.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4210":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4210."}
    return await task_open_isic_classify_entity(**kwargs)
