import asyncio
import logging
import os
import re
import uuid
from typing import Dict, Any

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ---- Load env ----
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing. Set it in environment or .env")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing. Set it in environment or .env")

# ---- Logging ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("ai-photo-bot")

# ---- OpenAI client (v1+) ----
try:
    from openai import OpenAI
    oai_client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    raise RuntimeError(f"Failed to initialize OpenAI client: {e}")

# ---- Simple in-memory session store ----
UserSessions: Dict[int, Dict[str, Any]] = {}

# ---- Helpers ----
def detect_language(text: str) -> str:
    """Detects Bangla vs English by Unicode range heuristic."""
    return "bangla" if re.search(r'[\u0980-\u09FF]', text or "") else "english"

async def delete_last_message_if_any(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    data = UserSessions.get(user_id) or {}
    last_msg_id = data.get("last_msg_id")
    chat_id = data.get("chat_id")
    if last_msg_id and chat_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_msg_id)
        except Exception as e:
            logger.debug(f"Could not delete previous message: {e}")

def variation_suffix() -> str:
    # Invisible variation anchor to force a fresh sample each time
    return f"\n\n# variation:{uuid.uuid4()}"

async def generate_image_url(prompt: str) -> str:
    """
    Uses OpenAI Images API (gpt-image-1) to generate an image URL.
    If URL is not returned, tries b64 and raises on failure.
    """
    try:
        resp = oai_client.images.generate(
            model="gpt-image-1",
            prompt=prompt + variation_suffix(),
            size="1024x1024",
            n=1
        )
        # Prefer URL if available
        if resp.data and getattr(resp.data[0], "url", None):
            return resp.data[0].url
        # Fallback to b64
        b64 = getattr(resp.data[0], "b64_json", None)
        if b64:
            import base64, tempfile
            raw = base64.b64decode(b64)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(raw)
            tmp.flush()
            tmp.close()
            # Telegram can upload local file path directly
            return tmp.name
        raise RuntimeError("OpenAI did not return URL or b64 image data.")
    except Exception as e:
        raise RuntimeError(str(e))

async def add_download_button(context: ContextTypes.DEFAULT_TYPE, msg: Message, script: str):
    """
    After sending a photo, retrieve Telegram's file URL and update buttons to include a Download link.
    """
    try:
        if not msg.photo:
            return  # If this wasn't a photo, nothing to do.
        # Largest size is last
        file_id = msg.photo[-1].file_id
        file = await context.bot.get_file(file_id)
        download_url = file.file_path  # e.g., https://api.telegram.org/file/bot<TOKEN>/<path>

        # Build keyboard: ENTIRE / GO (regenerate), plus download URL button
        keyboard = [
            [InlineKeyboardButton("ENTIRE", callback_data=f"regen|{script}")],
            [InlineKeyboardButton("GO", callback_data=f"regen|{script}")],
            [InlineKeyboardButton("⬇️ Download", url=download_url)]
        ]
        await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.debug(f"Failed to attach download button: {e}")

# ---- Handlers ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Greet in English, by name
    welcome_msg = f"👋 Welcome {user.first_name}!"
    await update.message.reply_text(welcome_msg)

    # Ask for script in Bangla
    ask_msg = "✍️ দয়া করে একটি স্ক্রিপ্ট লিখুন (বাংলা বা ইংরেজি) — আমি সেটি থেকে একটি ছবি বানিয়ে দেব।"
    await update.message.reply_text(ask_msg)

async def handle_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    script = (update.message.text or "").strip()
    UserSessions[user.id] = UserSessions.get(user.id, {})
    UserSessions[user.id]["chat_id"] = chat_id

    # Auto-vanish previous output (image or error)
    await delete_last_message_if_any(context, user.id)

    try:
        image_url_or_path = await generate_image_url(script)

        # Send first with regen buttons (we'll patch in the download link right after)
        keyboard = [
            [InlineKeyboardButton("ENTIRE", callback_data=f"regen|{script}")],
            [InlineKeyboardButton("GO", callback_data=f"regen|{script}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        sent = await update.message.reply_photo(
            photo=image_url_or_path,
            caption="",
            reply_markup=reply_markup
        )

        # Track the sent message id
        UserSessions[user.id]["last_msg_id"] = sent.message_id

        # Attach a download button once Telegram hosts the file
        await add_download_button(context, sent, script)

    except Exception as e:
        lang = detect_language(script)
        reason = str(e)
        if lang == "bangla":
            error_msg = f"❌ একটি ত্রুটি ঘটেছে!\nকারণ: {reason}"
        else:
            error_msg = f"❌ An error occurred!\nReason: {reason}"
        sent = await update.message.reply_text(error_msg)
        UserSessions[user.id]["last_msg_id"] = sent.message_id

async def on_regen_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    chat_id = query.message.chat_id
    UserSessions[user.id] = UserSessions.get(user.id, {})
    UserSessions[user.id]["chat_id"] = chat_id

    # Parse callback data: "regen|<script>"
    data = (query.data or "").split("|", 1)
    script = data[1] if len(data) == 2 else ""

    # Auto-vanish previous output
    await delete_last_message_if_any(context, user.id)

    try:
        image_url_or_path = await generate_image_url(script)

        keyboard = [
            [InlineKeyboardButton("ENTIRE", callback_data=f"regen|{script}")],
            [InlineKeyboardButton("GO", callback_data=f"regen|{script}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        sent = await query.message.reply_photo(
            photo=image_url_or_path,
            caption="",
            reply_markup=reply_markup
        )
        UserSessions[user.id]["last_msg_id"] = sent.message_id
        await add_download_button(context, sent, script)

    except Exception as e:
        lang = detect_language(script)
        reason = str(e)
        if lang == "bangla":
            error_msg = f"❌ একটি ত্রুটি ঘটেছে!\nকারণ: {reason}"
        else:
            error_msg = f"❌ An error occurred!\nReason: {reason}"
        sent = await query.message.reply_text(error_msg)
        UserSessions[user.id]["last_msg_id"] = sent.message_id

async def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_script))
    app.add_handler(CallbackQueryHandler(on_regen_button, pattern=r"^regen\\|"))
    logger.info("Bot started...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
