from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4921_classify(**kwargs: Any) -> dict[str, Any]:
    """Urban and suburban passenger land transport.

    This class includes the transport of passengers within urban and suburban areas.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4921":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4921."}
    return await task_open_isic_classify_entity(**kwargs)
