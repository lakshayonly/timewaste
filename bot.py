import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.filters import Command
from main import router
from keep_alive import keep_alive

keep_alive()
# Configure logging
logging.basicConfig(level=logging.INFO)

# Bot token - Replace with your actual bot token
BOT_TOKEN = "8371210517:AAH0kU5o5iGFv02L2l8GC-dd3Pq6DHfsqgM"

@router.message(Command("start"))
async def start_command(message: Message):
    """Welcome message for new users"""
    user_first_name = message.from_user.first_name or "User"
    
    start_text = f"""
🎉 <b>Welcome to B3 Checker Bot, {user_first_name}!</b> 🎉

🔥 <b>Premium Card Checking System</b> 🔥
⚡ <b>Powered by Braintree Gateway</b> ⚡

🚀 <b>What can I do?</b>
• 💳 Check single cards instantly
• 🔢 Mass check up to 20 cards
• 📁 Process text files (up to 1000 cards)
• 🧠 Auto-extract cards from any text
• 📊 Real-time progress tracking

<b>🔰 Ready to start checking? Use /cmds for full command list!</b>
"""
    await message.reply(start_text, parse_mode="HTML")

@router.message(Command("cmds"))
async def cmds_command(message: Message):
    """Display all available commands"""
    cmds_text = """
🤖 <b>B3 Checker Bot - Command List</b> 🤖

🔥 <b>Main Commands:</b>
┣ 💳 <code>/chk</code> - Single card checker
┣ 🔢 <code>/mchk</code> - Mass check (up to 20 cards)
┣ 📁 <code>/mtxt</code> - File checker (up to 1000 cards)
┣ ⏹️ <code>/stop</code> - Stop ongoing checks
┗ ❓ <code>/help</code> - Detailed help guide

⚡ <b>Quick Commands:</b>
┣ 🆔 <code>/b3</code> - Alias for /chk
┣ 📋 <code>/start</code> - Welcome message  
┗ 📚 <code>/cmds</code> - This command list

🎯 <b>Usage Examples:</b>

<b>1️⃣ Single Check:</b>
<code>/chk 4111111111111111|12|2025|123</code>

<b>2️⃣ Mass Check:</b>
<code>/mchk 
4111111111111111|12|2025|123
5500000000000004|01|2024|999</code>

<b>3️⃣ Reply Method:</b>
• Reply to any message containing cards
• Use <code>/chk</code> or <code>/mchk</code>

<b>4️⃣ File Method:</b>
• Upload a .txt file with cards
• Reply with <code>/mtxt</code>

🏆 <b>Premium Features:</b>
🔰 <b>Gateway:</b> Braintree Auth
⚡ <b>Speed:</b> Ultra-fast processing
🛡️ <b>Reliability:</b> 99.9% uptime

<b>🎉 Ready to check some cards? Start with /chk!</b>
"""
    await message.reply(cmds_text, parse_mode="HTML")

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
