from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2732_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other electronic and electric wires and cables.

    This class includes the manufacture of insulated wire and cable, made of steel, copper, aluminium, etc.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2732":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2732."}
    return await task_open_isic_classify_entity(**kwargs)
