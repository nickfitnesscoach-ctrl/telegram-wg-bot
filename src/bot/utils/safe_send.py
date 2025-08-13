import asyncio, logging
from aiogram.exceptions import RetryAfter, TelegramNetworkError

async def safe_send(callable_, *args, **kwargs):
    delay = 2
    for attempt in range(5):
        try:
            return await callable_(*args, **kwargs)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramNetworkError:
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
        except Exception:
            logging.exception("send failed")
            if attempt == 4:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
