from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5913_classify(**kwargs: Any) -> dict[str, Any]:
    """Motion picture, video and television programme distribution activities

    This class includes the distribution of motion pictures, videotapes, DVDs and similar productions to motion picture theatres, television networks and television stations.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5913":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5913."}
    return await task_open_isic_classify_entity(**kwargs)
