from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8422_classify(**kwargs: Any) -> dict[str, Any]:
    """Defence activities

    This class includes activities of the provision of military defence services.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8422":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8422."}
    return await task_open_isic_classify_entity(**kwargs)
