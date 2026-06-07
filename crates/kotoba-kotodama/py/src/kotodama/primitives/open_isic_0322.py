from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0322_classify(**kwargs: Any) -> dict[str, Any]:
    """Freshwater aquaculture.

    This class includes freshwater culture aquaculture, including the cultivation of finfish, crustaceans, molluscs, other aquatic animals and plants in freshwater environments, as well as the production of freshwater ornamental fish.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0322":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0322."}
    return await task_open_isic_classify_entity(**kwargs)
