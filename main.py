import logging
import io
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import google.generativeai as genai
from PIL import Image

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 أهلاً بك! أرسل لي أي صورة وسأعطيك الوصف (Prompt) الخاص بها."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not GOOGLE_API_KEY:
        await update.message.reply_text("⚠️ Google API key غير موجود.")
        return

    try:
        photo = await update.message.photo[-1].get_file()
        img_bytes = io.BytesIO()
        await photo.download_to_memory(img_bytes)
        img_bytes.seek(0)

        image = Image.open(img_bytes)

        prompt = """
        Analyze this image and provide a highly detailed text-to-image prompt.
        **English Prompt:** 
        **Arabic:** 
        """

        response = model.generate_content([prompt, image])
        await update.message.reply_text(response.text)

    except Exception as e:
        logging.error(e)
        await update.message.reply_text("حدث خطأ أثناء المعالجة.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
