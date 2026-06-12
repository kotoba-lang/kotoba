from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9700_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of households as employers of domestic personnel

    This class includes the activities of households as employers of domestic personnel such as maids, cooks, waiters, valets, butlers, laundresses, gardeners, gate keepers, stable keepers, chauffeurs, caretakers, governesses, babysitters, tutors, secretaries, etc.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9700":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9700."}
    return await task_open_isic_classify_entity(**kwargs)
