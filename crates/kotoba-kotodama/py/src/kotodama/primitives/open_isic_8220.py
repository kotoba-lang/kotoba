from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8220_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of call centres

    This class includes inbound and outbound telephone activities for the purpose of providing information or selling goods and services.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8220":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8220."}
    return await task_open_isic_classify_entity(**kwargs)
