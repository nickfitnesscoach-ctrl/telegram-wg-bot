import os
from aiogram import BaseMiddleware
from aiogram.types import Message

ALLOWED = {int(x) for x in os.getenv("ALLOWED_USERS","").split(",") if x.strip().isdigit()}

class AllowOnly(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        if ALLOWED and event.from_user.id not in ALLOWED:
            return await event.answer("Доступ только для админа.")
        return await handler(event, data)
