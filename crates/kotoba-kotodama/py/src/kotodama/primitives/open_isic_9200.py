from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9200_classify(**kwargs: Any) -> dict[str, Any]:
    """Gambling and betting activities

    This class includes the operation of gambling facilities such as casinos, bingo halls, video gaming terminals and lotteries.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9200":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9200."}
    return await task_open_isic_classify_entity(**kwargs)
