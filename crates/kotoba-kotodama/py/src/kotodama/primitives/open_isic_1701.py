from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1701_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of pulp, paper and paperboard

    This class includes the manufacture of pulp by separating cellulose fibres from wood or other fibrous materials, and the manufacture of paper and paperboard.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1701":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1701."}
    return await task_open_isic_classify_entity(**kwargs)
