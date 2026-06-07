from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4911_classify(**kwargs: Any) -> dict[str, Any]:
    """Passenger rail transport, interurban.

    This class includes the carriage of passengers on railways between cities and other urban areas.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4911":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4911."}
    return await task_open_isic_classify_entity(**kwargs)
