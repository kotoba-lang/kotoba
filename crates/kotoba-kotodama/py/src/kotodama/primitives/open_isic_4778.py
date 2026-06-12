from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4778_classify(**kwargs: Any) -> dict[str, Any]:
    """Other retail sale of new goods in specialised stores.

    This class includes the retail sale of new goods in specialised stores not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4778":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4778."}
    return await task_open_isic_classify_entity(**kwargs)
