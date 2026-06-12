from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0111_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of cereals (except rice), leguminous crops and oil seeds.

    This class includes all forms of growing of cereals, leguminous crops and oil seeds in open fields, including organic agriculture, the growing of genetically modified cereals, leguminous crops and oil seeds. Growing of these crops is often combined within agricultural units.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0111":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0111."}
    return await task_open_isic_classify_entity(**kwargs)
