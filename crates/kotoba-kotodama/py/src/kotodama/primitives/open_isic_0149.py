from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0149_classify(**kwargs: Any) -> dict[str, Any]:
    """Raising of other animals.

    This class includes raising and breeding of other animals such as semi-domesticated or wild animals, bees, silkworms, pet animals (except fish), and other animals not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0149":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0149."}
    return await task_open_isic_classify_entity(**kwargs)
