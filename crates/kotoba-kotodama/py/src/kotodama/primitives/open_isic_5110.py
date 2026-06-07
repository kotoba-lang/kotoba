from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5110_classify(**kwargs: Any) -> dict[str, Any]:
    """Passenger air transport

    This class includes the transport of passengers by air.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5110":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5110."}
    return await task_open_isic_classify_entity(**kwargs)
