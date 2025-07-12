import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
import aiohttp
import datetime
import logging

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Load user locations
if os.path.exists("locations.json"):
    with open("locations.json", "r") as f:
        user_locations = json.load(f)
else:
    user_locations = {}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Helper: save locations
def save_locations():
    with open("locations.json", "w") as f:
        json.dump(user_locations, f, indent=2)

# Helper: warnings based on description
def weather_warning(desc: str):
    desc = desc.lower()
    if "rain" in desc or "drizzle" in desc:
        return "☔ Bring an umbrella!"
    if "storm" in desc or "thunder" in desc:
        return "⚡ Thunderstorm alert! Stay safe."
    if "snow" in desc:
        return "❄️ Snowfall ahead, dress warm."
    if "extreme" in desc or "tornado" in desc or "hurricane" in desc:
        return "🚨 Severe weather warning!"
    if "clear" in desc:
        return "😎 Clear skies today! Enjoy."
    return ""

# Helper: format unix timestamp to readable time with timezone offset
def format_time(timestamp, timezone_offset):
    dt = datetime.datetime.utcfromtimestamp(timestamp + timezone_offset)
    return dt.strftime('%Y-%m-%d %H:%M')

# Fetch geocode (lat, lon) from city name
async def get_coordinates(city):
    async with aiohttp.ClientSession() as session:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
        async with session.get(url) as resp:
            data = await resp.json()
            if not data:
                return None
            return data[0]["lat"], data[0]["lon"]

# Fetch current weather data
async def fetch_weather(lat, lon):
    async with aiohttp.ClientSession() as session:
        url = f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&exclude=minutely,alerts&appid={OPENWEATHER_API_KEY}&units=metric"
        async with session.get(url) as resp:
            return await resp.json()

@bot.event
async def on_ready():
    print(f"🌦️ Logged in as {bot.user.name}")

@bot.command(name="setlocation")
async def set_location(ctx, *, city: str = None):
    if not city:
        await ctx.send("Usage: `!setlocation [city]`")
        return

    user_locations[str(ctx.author.id)] = city
    save_locations()
    await ctx.send(f"📍 Location set to **{city}**.")

@bot.command(name="weather")
async def weather(ctx, timeframe="now", *, city_override: str = None):
    user_id = str(ctx.author.id)
    city = city_override or user_locations.get(user_id)

    if not city:
        await ctx.send("❌ No location set. Use `!setlocation [city]` or add a city to the command like `!weather now Toronto`.")
        return

    coords = await get_coordinates(city)
    if not coords:
        await ctx.send(f"❌ Could not find location: **{city}**")
        return
    lat, lon = coords

    data = await fetch_weather(lat, lon)
    if "current" not in data:
        await ctx.send("⚠️ Failed to retrieve weather data. Try again later.")
        return

    timezone_offset = data.get("timezone_offset", 0)

    if timeframe.lower() == "now":
        current = data["current"]
        desc = current["weather"][0]["description"].capitalize()
        temp = current["temp"]
        feels_like = current["feels_like"]
        humidity = current["humidity"]
        wind_speed = current["wind_speed"]
        time_str = format_time(current["dt"], timezone_offset)
        warning = weather_warning(desc)

        msg = (
            f"🌤️ **Current weather in {city}:**\n"
            f"Time: {time_str}\n"
            f"Temperature: {temp}°C (Feels like {feels_like}°C)\n"
            f"Condition: {desc} {warning}\n"
            f"Humidity: {humidity}%\n"
            f"Wind Speed: {wind_speed} m/s"
        )
        await ctx.send(msg)

    elif timeframe.lower() == "hourly":
        hourly = data.get("hourly", [])
        if not hourly:
            await ctx.send("⚠️ No hourly data available.")
            return
        msg = f"⏰ **Hourly forecast for {city} (next 12 hours):**\n"
        for hour_data in hourly[:12]:
            time_str = format_time(hour_data["dt"], timezone_offset)
            temp = hour_data["temp"]
            desc = hour_data["weather"][0]["description"].capitalize()
            warning = weather_warning(desc)
            msg += f"{time_str}: {temp}°C, {desc} {warning}\n"
        await ctx.send(msg)

    elif timeframe.lower() == "daily":
        daily = data.get("daily", [])
        if not daily:
            await ctx.send("⚠️ No daily forecast data available.")
            return
        msg = f"📅 **7-day forecast for {city}:**\n"
        for day_data in daily[:7]:
            time_str = format_time(day_data["dt"], timezone_offset)
            desc = day_data["weather"][0]["description"].capitalize()
            temp_min = day_data["temp"]["min"]
            temp_max = day_data["temp"]["max"]
            warning = weather_warning(desc)
            msg += f"{time_str}: {temp_min}°C - {temp_max}°C, {desc} {warning}\n"
        await ctx.send(msg)

    else:
        await ctx.send("❌ Invalid timeframe! Use `now`, `hourly`, or `daily`.")

bot.run(DISCORD_TOKEN)
