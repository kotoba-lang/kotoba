from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6420_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of holding companies.

    This class includes the activities of holding companies, i.e. units that hold the assets (owning controlling-levels of equity) of a group of subsidiary corporations.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6420":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6420."}
    return await task_open_isic_classify_entity(**kwargs)
