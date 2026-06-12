from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5911_classify(**kwargs: Any) -> dict[str, Any]:
    """Motion picture, video and television programme production activities

    This class includes the production of motion pictures, videos, television programmes and TV commercials.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5911":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5911."}
    return await task_open_isic_classify_entity(**kwargs)
