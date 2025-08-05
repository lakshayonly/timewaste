# Independent Telegram Bot for Card Checking with Mass Check Features
import time
import os
import asyncio
import aiofiles
import random
import aiohttp
from aiogram import Router, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from binlookup import *

router = Router()

# Global dictionary to track stop flags for users
stop_flags = {}

# Keywords that indicate approval
approved_keywords = [
    'Nice! New payment method added',
    'Payment method successfully added.',
    'invalid postal code',
    'invalid street address',
    'insufficient funds',
    'Status code 81724: Duplicate card exists in the vault.',
    'Card Issuer Declined Cvv',
    'Status code avs: Gateway Rejected: avs',
    'Insufficient Funds',
    'APPROVED'
]

def validate_card_format(card: str):
    """
    Validate card in the format "number|month|year|cvv".
    Returns (True, "") if valid, or (False, error_message) if invalid.
    """
    parts = card.split("|")
    if len(parts) != 4:
        return False, "❌ Provide card in <code>number|month|year|cvv</code> format."
    
    card_number, month, year, cvv = parts
    
    if not card_number.isdigit():
        return False, "❌ Card number must be numeric."
    if not (13 <= len(card_number) <= 19):
        return False, "❌ Card number length is invalid."
    if not month.isdigit() or not (1 <= int(month) <= 12):
        return False, "❌ Invalid month."
    if not year.isdigit() or len(year) != 4:
        return False, "❌ Year must be 4 digits."
    if not cvv.isdigit() or len(cvv) not in (3, 4):
        return False, "❌ Invalid CVV."
    
    return True, ""

async def check_single_card(card: str):
    """
    Check a single card using the B3 API
    Returns (success, response_text, is_approved)
    """
    url = "https://khudkab3-uf7j.onrender.com/b3"
    params = {"cc": card}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    response_text = result.get("response", "No response")
                    
                    # Check if card is approved
                    is_approved = any(keyword.lower() in response_text.lower() for keyword in approved_keywords)
                    
                    return True, response_text, is_approved
                else:
                    return False, f"API Error: {response.status}", False
    except Exception as e:
        return False, f"Network Error: {str(e)}", False

@router.message(Command("b3"))
async def b3_command(message: Message):
    now = time.time()

    # Get user input and accept both "|" separated or space-separated formats.
    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.reply(
            "<b>❌ Provide card in</b> <code>number|month|year|cvv</code> or <code>number month year cvv</code> format.",
            parse_mode="HTML"
        )
        return

    # Normalize input: replace pipes with spaces and split into parts
    card_parts = args[1].replace("|", " ").split()
    if len(card_parts) != 4:
        await message.reply(
            "<b>❌ Provide card in</b> <code>number|month|year|cvv</code> or <code>number month year cvv</code> format.",
            parse_mode="HTML"
        )
        return

    card_number, month, year, cvv = card_parts

    # Normalize year: if it is two digits, assume 20XX
    if len(year) == 2:
        year = "20" + year

    # Reassemble card string in the standard format
    card = f"{card_number}|{month}|{year}|{cvv}"

    # Validate card format
    is_valid, error_msg = validate_card_format(card)
    if not is_valid:
        await message.reply(error_msg, parse_mode="HTML")
        return

    # Send a "Processing..." message
    processing_message = await message.reply("<b>Processing your request...</b>", parse_mode="HTML")

    success, response_text, is_approved = await check_single_card(card)
    
    if success:
        # Extract BIN info from the card number (first 6 digits)
        bin_number = card_number[:6]
        bin_data = await get_bin_details(bin_number)
        bank_name, card_type, brand, issuer, country_name, country_flag, level = bin_data

        if is_approved or "APPROVED" in response_text:
            reply_text = f"""
𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅

𝗖𝗮𝗿𝗱: <code>{card}</code>
𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Braintree Auth  
𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {response_text}

𝗜𝗻𝗳𝗼: {brand} - {card_type} - {level}
𝐈𝐬𝐬𝐮𝐞𝐫: {issuer}
𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {country_name} {country_flag}

𝗧𝗶𝗺𝗲: {round(time.time() - now, 2)} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬
"""
        else:
            reason = response_text if "DECLINED" not in response_text else response_text.replace("DECLINED", "").strip()
            reply_text = f"""
𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌

𝗖𝗮𝗿𝗱: <code>{card}</code>
𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Braintree Auth  
𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {reason}

𝗜𝗻𝗳𝗼: {brand} - {card_type} - {level}
𝐈𝐬𝐬𝐮𝐞𝐫: {issuer}
𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {country_name} {country_flag}

𝗧𝗶𝗺𝗲: {round(time.time() - now, 2)} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬
"""

        # Edit the "Processing..." message with the result
        await processing_message.edit_text(reply_text, parse_mode="HTML")
    else:
        await processing_message.edit_text(
            f"⚠️ <b>Error:</b> {response_text}",
            parse_mode="HTML"
        )

@router.message(Command("mchk"))
async def mchk_command(message: Message):
    """Mass check up to 10 cards"""
    user_id = message.from_user.id
    
    # Extract cards after command
    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.reply(
            "Please provide cards to check, one per line, like:\n"
            "<code>/mchk 4111111111111111|12|2025|123\n4222222222222222|11|2024|456</code>",
            parse_mode="HTML"
        )
        return
    
    cards_text = args[1].strip()
    cards = [line.strip() for line in cards_text.splitlines() if line.strip()]
    
    if len(cards) > 10:
        await message.reply("❌ You can check a maximum of 10 cards at once.", parse_mode="HTML")
        return
    
    if not cards:
        await message.reply("❌ No valid cards found to check.", parse_mode="HTML")
        return
    
    # Initialize stop flag
    stop_flags[user_id] = False
    
    processing_message = await message.reply("<b>Processing your cards... ⏳</b>", parse_mode="HTML")
    
    results = ""
    approved_count = 0
    declined_count = 0
    
    for i, card_line in enumerate(cards, 1):
        if stop_flags.get(user_id, False):
            results += "⚠️ <b>Checking stopped by user</b>\n\n"
            break
        
        try:
            # Normalize card format
            card_parts = card_line.replace("|", " ").split()
            if len(card_parts) != 4:
                results += f"❌ <b>Invalid format:</b> <code>{card_line}</code>\n\n"
                continue
            
            card_number, month, year, cvv = card_parts
            
            # Normalize year
            if len(year) == 2:
                year = "20" + year
            
            card = f"{card_number}|{month}|{year}|{cvv}"
            
            # Validate card
            is_valid, error_msg = validate_card_format(card)
            if not is_valid:
                results += f"❌ <b>Invalid card:</b> <code>{card_line}</code>\n{error_msg}\n\n"
                continue
            
            # Check card
            success, response_text, is_approved = await check_single_card(card)
            
            # Get BIN info
            bin_data = await get_bin_details(card_number[:6])
            bank_name, card_type, brand, issuer, country_name, country_flag, level = bin_data
            
            if success and is_approved:
                approved_count += 1
                status_text = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
            else:
                declined_count += 1
                status_text = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
            
            results += f"""
<b>{status_text}</b>

𝗖𝗮𝗿𝗱: <code>{card}</code>
𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Braintree Auth
𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {response_text if success else 'API Error'}

𝗜𝗻𝗳𝗼: {brand} - {card_type} - {level}
𝐈𝐬𝐬𝐮𝐞𝐫: {issuer}
𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {country_name} {country_flag}

"""
        except Exception as e:
            results += f"❌ <b>Error with card:</b> <code>{card_line}</code>\n<b>Reason:</b> {str(e)}\n\n"
        
        # Update progress
        progress_text = f"<b>Processing cards... ⏳ ({i}/{len(cards)})</b>\n\n{results}"
        try:
            await processing_message.edit_text(progress_text, parse_mode="HTML")
        except:
            pass  # Ignore message too long errors during progress updates
        
        await asyncio.sleep(1)  # Small delay between requests
    
    # Final summary
    summary = f"""
<b>✅ Mass Check Complete!</b>

<b>📊 Summary:</b>
• Total Checked: {len(cards)}
• Approved: {approved_count} ✅
• Declined: {declined_count} ❌

{results}
"""
    
    try:
        await processing_message.edit_text(summary, parse_mode="HTML")
    except:
        # If message is too long, send summary separately
        await processing_message.edit_text(
            f"<b>✅ Mass Check Complete!</b>\n\n"
            f"<b>📊 Summary:</b>\n"
            f"• Total Checked: {len(cards)}\n"
            f"• Approved: {approved_count} ✅\n"
            f"• Declined: {declined_count} ❌",
            parse_mode="HTML"
        )
        
        # Send detailed results in chunks if needed
        if results:
            chunk_size = 4000
            for i in range(0, len(results), chunk_size):
                chunk = results[i:i+chunk_size]
                await message.reply(chunk, parse_mode="HTML")

@router.message(Command("mtxt"))
async def mtxt_command(message: Message):
    """Mass check from text file"""
    user_id = message.from_user.id
    
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply(
            "❌ Please reply to a text file (.txt) containing cards to check.\n"
            "Format: one card per line as <code>number|month|year|cvv</code>",
            parse_mode="HTML"
        )
        return
    
    document = message.reply_to_message.document
    if not document.file_name.endswith(".txt"):
        await message.reply("❌ Please reply to a valid <code>.txt</code> file.", parse_mode="HTML")
        return
    
    # Download file
    file_path = f"downloads/{user_id}_{int(time.time())}.txt"
    os.makedirs("downloads", exist_ok=True)
    
    try:
        await message.reply_to_message.download(destination=file_path)
    except Exception as e:
        await message.reply(f"❌ Error downloading file: {str(e)}", parse_mode="HTML")
        return
    
    # Read cards from file
    try:
        async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
            content = await f.read()
            cards = [line.strip() for line in content.splitlines() if line.strip()]
    except Exception as e:
        await message.reply(f"❌ Error reading file: {str(e)}", parse_mode="HTML")
        if os.path.exists(file_path):
            os.remove(file_path)
        return
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
    
    if not cards:
        await message.reply("❌ No valid cards found in the file.", parse_mode="HTML")
        return
    
    if len(cards) > 1000:  # Reasonable limit
        await message.reply(f"❌ Too many cards. Maximum allowed: 1000. Found: {len(cards)}", parse_mode="HTML")
        return
    
    # Initialize tracking
    stop_flags[user_id] = False
    approved, declined, errors = [], [], []
    total_cards = len(cards)
    
    # Create progress keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Card: Waiting...", callback_data="none")],
        [InlineKeyboardButton(text="⏳ Response: Waiting...", callback_data="none")],
        [InlineKeyboardButton(text="✅ Approved: 0", callback_data="none")],
        [InlineKeyboardButton(text="❌ Declined: 0", callback_data="none")],
        [InlineKeyboardButton(text=f"📊 Total Cards: {total_cards}", callback_data="none")]
    ])
    
    progress_msg = await message.reply(f"Processing cards: 0/{total_cards}", reply_markup=keyboard)
    
    for index, card_line in enumerate(cards, 1):
        if stop_flags.get(user_id, False):
            break
        
        try:
            # Normalize and validate card
            card_parts = card_line.replace("|", " ").split()
            if len(card_parts) != 4:
                errors.append(f"{card_line} , response: Invalid format")
                continue
            
            card_number, month, year, cvv = card_parts
            
            # Normalize year
            if len(year) == 2:
                year = "20" + year
            
            card = f"{card_number}|{month}|{year}|{cvv}"
            
            # Update progress display
            keyboard.inline_keyboard[0][0].text = f"🔄 Card: {card_number[:6]}...{card_number[-4:]}"
            keyboard.inline_keyboard[1][0].text = f"⏳ Response: Checking..."
            keyboard.inline_keyboard[2][0].text = f"✅ Approved: {len(approved)}"
            keyboard.inline_keyboard[3][0].text = f"❌ Declined: {len(declined)}"
            
            try:
                await progress_msg.edit_text(f"Processing cards: {index-1}/{total_cards}", reply_markup=keyboard)
            except:
                pass
            
            # Validate card format
            is_valid, error_msg = validate_card_format(card)
            if not is_valid:
                errors.append(f"{card_line} , response: {error_msg}")
                continue
            
            # Check card
            success, response_text, is_approved = await check_single_card(card)
            
            if success:
                # Get BIN info
                bin_data = await get_bin_details(card_number[:6])
                bank_name, card_type, brand, issuer, country_name, country_flag, level = bin_data
                
                if is_approved:
                    approved.append(f"{card} , response: {response_text}")
                    
                    # Send individual approved card notification
                    notification = f"""
𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅

𝗖𝗮𝗿𝗱: <code>{card}</code>
𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Braintree Auth
𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {response_text}

𝗜𝗻𝗳𝗼: {brand} - {card_type} - {level}
𝐈𝐬𝐬𝐮𝐞𝐫: {issuer}
𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {country_name} {country_flag}
"""
                    await message.reply(notification, parse_mode="HTML")
                else:
                    declined.append(f"{card} , response: {response_text}")
                
                # Update response in keyboard
                short_response = (response_text[:37] + "...") if len(response_text) > 40 else response_text
                keyboard.inline_keyboard[1][0].text = f"{'✅' if is_approved else '❌'} Response: {short_response}"
            else:
                errors.append(f"{card} , response: {response_text}")
                keyboard.inline_keyboard[1][0].text = f"❌ Response: Error"
        
        except Exception as e:
            errors.append(f"{card_line} , response: Error: {str(e)}")
            keyboard.inline_keyboard[1][0].text = f"❌ Response: Exception"
        
        # Update final counts
        keyboard.inline_keyboard[2][0].text = f"✅ Approved: {len(approved)}"
        keyboard.inline_keyboard[3][0].text = f"❌ Declined: {len(declined)}"
        
        try:
            await progress_msg.edit_text(f"Processing cards: {index}/{total_cards}", reply_markup=keyboard)
        except:
            pass
        
        await asyncio.sleep(2)  # Delay between requests
    
    # Final update
    await progress_msg.edit_text("✅ Done Checking Cards!", reply_markup=keyboard)
    
    # Send summary
    total_checked = len(approved) + len(declined) + len(errors)
    summary_text = f"""
<b>✅ File Check Complete!</b>

<b>📊 Final Summary:</b>
• Total Checked: {total_checked}
• Approved: {len(approved)} 🟢
• Declined: {len(declined)} 🔴
• Errors: {len(errors)} ⚠️
"""
    
    await message.reply(summary_text, parse_mode="HTML")
    
    # Generate and send result files
    for name, lst in [("approved", approved), ("declined", declined), ("errors", errors)]:
        if lst:
            filename = f"{name}_{user_id}_{random.randint(100000, 999999)}.txt"
            try:
                async with aiofiles.open(filename, mode='w', encoding='utf-8') as f:
                    await f.write("\n".join(lst))
                
                with open(filename, 'rb') as doc:
                    await message.reply_document(
                        document=doc,
                        caption=f"<b>{name.title()} Cards ({len(lst)})</b>",
                        parse_mode="HTML"
                    )
                
                os.remove(filename)
            except Exception as e:
                await message.reply(f"❌ Error generating {name} file: {str(e)}", parse_mode="HTML")

@router.message(Command("stop"))
async def stop_command(message: Message):
    """Stop ongoing mass check"""
    user_id = message.from_user.id
    stop_flags[user_id] = True
    await message.reply("⚠️ <b>Stopping check...</b> Will halt after current card.", parse_mode="HTML")
