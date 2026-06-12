from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9602_classify(**kwargs: Any) -> dict[str, Any]:
    """Hairdressing and other beauty treatment

    This class includes the activities of hairdressers and beauty parlors.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9602":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9602."}
    return await task_open_isic_classify_entity(**kwargs)
