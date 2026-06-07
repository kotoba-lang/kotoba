from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0892_classify(**kwargs: Any) -> dict[str, Any]:
    """Extraction of peat

    This class includes extraction and agglomeration of peat.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0892":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0892."}
    return await task_open_isic_classify_entity(**kwargs)
