from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6110_classify(**kwargs: Any) -> dict[str, Any]:
    """Wired telecommunications activities.

    This class includes operating, maintaining or providing access to facilities for the transmission of voice, data, text, sound and video using wired telecommunications networks.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6110":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6110."}
    return await task_open_isic_classify_entity(**kwargs)
