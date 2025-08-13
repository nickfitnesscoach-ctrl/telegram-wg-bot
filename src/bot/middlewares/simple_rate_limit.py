import time
from aiogram import BaseMiddleware
from aiogram.types import Message

class RateLimit(BaseMiddleware):
    def __init__(self, per_user_per_min: int = 10):
        self.per_user_per_min = per_user_per_min
        self.bucket = {}

    async def __call__(self, handler, event: Message, data):
        now = time.monotonic()
        arr = self.bucket.setdefault(event.from_user.id, [])
        while arr and now - arr[0] > 60:
            arr.pop(0)
        if len(arr) >= self.per_user_per_min:
            return await event.answer("Слишком часто. Попробуй позже.")
        arr.append(now)
        return await handler(event, data)
