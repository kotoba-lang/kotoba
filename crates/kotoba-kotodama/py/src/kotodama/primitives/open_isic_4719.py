from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4719_classify(**kwargs: Any) -> dict[str, Any]:
    """Other retail sale in non-specialised stores.

    This class includes the retail sale of a variety of goods in non-specialised stores where food does not predominate.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4719":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4719."}
    return await task_open_isic_classify_entity(**kwargs)
