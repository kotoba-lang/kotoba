from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6010_classify(**kwargs: Any) -> dict[str, Any]:
    """Radio broadcasting.

    This class includes the broadcasting of audio content to the public.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6010":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6010."}
    return await task_open_isic_classify_entity(**kwargs)
