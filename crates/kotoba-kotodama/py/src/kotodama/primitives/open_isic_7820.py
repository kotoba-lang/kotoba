from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7820_classify(**kwargs: Any) -> dict[str, Any]:
    """Temporary employment agency activities

    This class includes the supply of workers to client businesses for limited periods of time to temporarily replace or supplement the working force of the client.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7820":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7820."}
    return await task_open_isic_classify_entity(**kwargs)
