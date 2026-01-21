import logging
import io
import os
import threading
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
from flask import Flask

# --- إعدادات Flask (لإبقاء البوت يعمل على Render) ---
app_server = Flask(__name__)

@app_server.route('/')
def home():
    return "Bot is running!"

def run_flask():
    # Render يعطينا منفذ (PORT) عبر متغيرات البيئة
    port = int(os.environ.get("PORT", 8080))
    app_server.run(host="0.0.0.0", port=port)

# --- إعدادات البوت ---
# سنقوم بجلب التوكن من متغيرات البيئة في Render للأمان
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# إعداد Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 أهلاً بك! أرسل لي أي صورة وسأعطيك الوصف (Prompt) الخاص بها."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not GOOGLE_API_KEY:
        await update.message.reply_text("⚠️ خطأ: لم يتم إعداد مفتاح Google API.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        img_byte_arr = io.BytesIO()
        await photo_file.download_to_memory(img_byte_arr)
        img_byte_arr.seek(0)
        
        image = Image.open(img_byte_arr)

        prompt_request = """
        Analyze this image and provide a highly detailed text-to-image prompt suitable for Stable Diffusion. 
        Format:
        **English Prompt:** [Prompt]
        **Arabic:** [Translation]
        """
        
        response = model.generate_content([prompt_request, image])
        await update.message.reply_text(response.text, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("حدث خطأ أثناء المعالجة.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found.")
        return

    # تشغيل سيرفر Flask في خيط منفصل (Thread)
    threading.Thread(target=run_flask).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
