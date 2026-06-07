from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0721_classify(**kwargs: Any) -> dict[str, Any]:
    """Mining of uranium and thorium ores

    This class includes mining of ores chiefly valued for uranium and thorium content: pitchblende and other uranium ores, and thorium ores.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0721":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0721."}
    return await task_open_isic_classify_entity(**kwargs)
