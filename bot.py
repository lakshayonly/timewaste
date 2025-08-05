import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from main import router
from keep_alive import keep_alive

keep_alive()
# Configure logging
logging.basicConfig(level=logging.INFO)

# Bot token - Replace with your actual bot token
BOT_TOKEN = "8371210517:AAH0kU5o5iGFv02L2l8GC-dd3Pq6DHfsqgM"

async def main():
    """Main function to start the bot"""
    # Initialize Bot instance with default bot properties
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Initialize Dispatcher
    dp = Dispatcher()
    
    # Include the router from main.py
    dp.include_router(router)
    
    # Start polling
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
