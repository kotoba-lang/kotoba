from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4753_classify(**kwargs: Any) -> dict[str, Any]:
    """Retail sale of carpets, rugs, wall and floor coverings in specialised stores.

    This class includes the retail sale of floor coverings and wall coverings in specialised stores.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4753":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4753."}
    return await task_open_isic_classify_entity(**kwargs)
