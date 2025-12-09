import asyncio
from aiogram import Bot, Dispatcher
from config import TG_TOKEN
from handlers import router
async def main():
    bot = Bot(token=TG_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())