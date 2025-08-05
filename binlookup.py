import asyncio
import aiohttp

bin_cache = {}

async def get_bin_details(bin_number):
    if bin_number in bin_cache:
        return bin_cache[bin_number]

    url = f"https://laksfr.pythonanywhere.com/bin/{bin_number}"
    
    async with aiohttp.ClientSession() as session:
        await asyncio.sleep(1)  # Prevent API from blocking due to rate limits
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                bank_name = data.get("bank", "Unknown Bank")
                card_type = data.get("type", "Unknown Type")
                brand = data.get("brand", "Unknown Brand")
                issuer = data.get("bank", "Unknown Issuer")
                country_name = data.get("country_name", "Unknown Country")
                country_flag = data.get("country_flag", "")
                level = data.get("level", "Unknown Level")
                
                details = (bank_name, card_type, brand, issuer, country_name, country_flag, level)
                bin_cache[bin_number] = details  # Cache the result
                return details

            elif response.status == 429:
                print("❌ Rate Limit Reached! Retrying after delay...")
                await asyncio.sleep(5)  # Wait 5 seconds and try again
                return await get_bin_details(bin_number)

            else:
                print("API Error:", response.status)
                return ("Unknown Bank", "Unknown Type", "Unknown Brand", "Unknown Issuer", "Unknown Country", "", "Unknown Level")
