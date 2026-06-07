from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8110_classify(**kwargs: Any) -> dict[str, Any]:
    """Combined facilities support activities

    This class includes the provision of a combination of support services within a client's facilities, such as general interior cleaning, maintenance, trash collection, guard and security, mail routing, reception, laundry and related services.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8110":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8110."}
    return await task_open_isic_classify_entity(**kwargs)
