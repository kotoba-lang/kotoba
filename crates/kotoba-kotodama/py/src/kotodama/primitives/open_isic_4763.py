from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4763_classify(**kwargs: Any) -> dict[str, Any]:
    """Retail sale of sporting equipment in specialised stores.

    This class includes the retail sale of sporting goods in specialised stores.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4763":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4763."}
    return await task_open_isic_classify_entity(**kwargs)
