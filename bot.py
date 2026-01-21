import logging
import io
import os
import base64
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
from PIL import Image
from datetime import datetime
import requests

# ========== إعدادات ==========
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== دوال OpenAI ==========
async def analyze_image_with_openai(image_bytes):
    """تحليل الصورة باستخدام OpenAI GPT-4 Vision"""
    
    # تحويل الصورة إلى base64
    image_base64 = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Analyze this image and create:

1. **English Prompt**: Detailed description in English suitable for AI image generation
2. **Arabic Translation**: Accurate Arabic translation
3. **Enhanced Prompt**: Professional version with artistic keywords
4. **Keywords**: 5-10 keywords separated by commas

Format:
[EN]: [text]
[AR]: [text]
[ENHANCED]: [text]
[KEYWORDS]: [text]"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            logger.error(f"OpenAI API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return None

async def parse_openai_response(response_text):
    """تقسيم استجابة OpenAI إلى أجزاء"""
    result = {
        "english": "لم أتمكن من استخراج النص الإنجليزي",
        "arabic": "لم أتمكن من استخراج النص العربي",
        "enhanced": "لم أتمكن من إنشاء اقتراح محسن",
        "keywords": "صورة, فنية"
    }
    
    try:
        lines = response_text.split('\n')
        
        for line in lines:
            if line.startswith('[EN]:'):
                result["english"] = line.replace('[EN]:', '').strip()
            elif line.startswith('[AR]:'):
                result["arabic"] = line.replace('[AR]:', '').strip()
            elif line.startswith('[ENHANCED]:'):
                result["enhanced"] = line.replace('[ENHANCED]:', '').strip()
            elif line.startswith('[KEYWORDS]:'):
                result["keywords"] = line.replace('[KEYWORDS]:', '').strip()
        
        if result["english"].startswith("لم أتمكن"):
            result["english"] = response_text[:300]
            
    except Exception as e:
        logger.error(f"خطأ في تقسيم الاستجابة: {e}")
    
    return result

# ========== معالجات الأوامر ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start"""
    welcome_text = """
🖼️ *مرحباً بك في بوت استخراج البرومبت مع GPT-4!*

✨ *المميزات:*
• استخراج وصف دقيق للصور باستخدام OpenAI GPT-4
• برومبت باللغتين العربية والإنجليزية
• اقتراحات محسنة للفن الرقمي
• نسخ البرومبت بنقرة واحدة

📤 *كيفية الاستخدام:*
1. أرسل لي صورة
2. انتظر التحليل
3. اختر من الأزرار ما تريد

ابدأ الآن بإرسال صورة! 📸
"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الصور المستلمة"""
    if not OPENAI_API_KEY:
        await update.message.reply_text("⚠️ OPENAI_API_KEY غير موجود")
        return
    
    try:
        processing_msg = await update.message.reply_text("🔄 جاري تحليل الصورة مع GPT-4...")
        
        # تحميل الصورة
        photo = await update.message.photo[-1].get_file()
        img_bytes = io.BytesIO()
        await photo.download_to_memory(img_bytes)
        img_bytes.seek(0)
        
        # تحليل الصورة باستخدام OpenAI
        response_text = await analyze_image_with_openai(img_bytes)
        
        if not response_text:
            await processing_msg.delete()
            await update.message.reply_text("❌ فشل في تحليل الصورة")
            return
        
        # تقسيم الاستجابة
        prompts = await parse_openai_response(response_text)
        
        # حفظ البيانات في context
        user_id = update.effective_user.id
        context.user_data[f'{user_id}_prompts'] = prompts
        
        # إنشاء أزرار
        keyboard = [
            [
                InlineKeyboardButton("📋 نسخ الإنجليزي", callback_data="copy_en"),
                InlineKeyboardButton("📋 نسخ العربي", callback_data="copy_ar")
            ],
            [
                InlineKeyboardButton("✨ اقتراح محسن", callback_data="copy_enhanced"),
                InlineKeyboardButton("🏷️ الكلمات المفتاحية", callback_data="copy_keywords")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إعداد النتيجة
        en_preview = prompts['english'][:150] + "..." if len(prompts['english']) > 150 else prompts['english']
        ar_preview = prompts['arabic'][:150] + "..." if len(prompts['arabic']) > 150 else prompts['arabic']
        
        result_text = f"""
✅ *تم تحليل الصورة مع GPT-4!*

🇺🇸 *الوصف الإنجليزي:*
`{en_preview}`

🇸🇦 *الوصف العربي:*
`{ar_preview}`

🏷️ *الكلمات المفتاحية:*
{prompts['keywords']}

_اضغط الأزرار أدناه للنسخ الكامل_ 👇
"""
        
        await processing_msg.delete()
        await update.message.reply_text(
            result_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء المعالجة: {str(e)}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة نقرات الأزرار"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    prompts = context.user_data.get(f'{user_id}_prompts', {})
    
    if not prompts:
        await query.edit_message_text("❌ انتهت صلاحية البيانات. أرسل صورة جديدة.")
        return
    
    data = query.data
    
    if data == "copy_en":
        text = prompts.get('english', 'غير متوفر')
        await query.edit_message_text(
            f"✅ *البرومبت الإنجليزي:*\n\n`{text}`",
            parse_mode='Markdown'
        )
        
    elif data == "copy_ar":
        text = prompts.get('arabic', 'غير متوفر')
        await query.edit_message_text(
            f"✅ *البرومبت العربي:*\n\n`{text}`",
            parse_mode='Markdown'
        )
        
    elif data == "copy_enhanced":
        text = prompts.get('enhanced', 'غير متوفر')
        await query.edit_message_text(
            f"✨ *الاقتراح المحسن:*\n\n`{text}`",
            parse_mode='Markdown'
        )
    
    elif data == "copy_keywords":
        text = prompts.get('keywords', 'غير متوفر')
        await query.edit_message_text(
            f"🏷️ *الكلمات المفتاحية:*\n\n`{text}`",
            parse_mode='Markdown'
        )

# ========== الدالة الرئيسية ==========
def main():
    """تشغيل البوت"""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN غير موجود!")
        return
    
    if not OPENAI_API_KEY:
        print("⚠️ OPENAI_API_KEY غير موجود")
    
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(CallbackQueryHandler(button_handler))
        
        print("✅ البوت يعمل الآن...")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"فشل تشغيل البوت: {e}")

if __name__ == "__main__":
    main()            if line.startswith('[EN]:'):
                result["english"] = line.replace('[EN]:', '').strip()
            elif line.startswith('[AR]:'):
                result["arabic"] = line.replace('[AR]:', '').strip()
            elif line.startswith('[ENHANCED]:'):
                result["enhanced"] = line.replace('[ENHANCED]:', '').strip()
            elif line.startswith('[KEYWORDS]:'):
                result["keywords"] = line.replace('[KEYWORDS]:', '').strip()
        
        if result["english"].startswith("لم أتمكن"):
            result["english"] = response_text[:300]
            
    except Exception as e:
        logger.error(f"خطأ في تقسيم الاستجابة: {e}")
    
    return result

# ========== معالجات الأوامر ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start"""
    welcome_text = """
🖼️ *مرحباً بك في بوت استخراج البرومبت مع GPT-4 Vision!*

✨ *المميزات:*
• استخراج وصف دقيق للصور باستخدام OpenAI GPT-4
• برومبت باللغتين العربية والإنجليزية
• اقتراحات محسنة للفن الرقمي
• نسخ البرومنت بنقرة واحدة

📤 *كيفية الاستخدام:*
1. أرسل لي صورة
2. انتظر التحليل
3. اختر من الأزرار ما تريد

ابدأ الآن بأرسال صورة! 📸
"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الصور المستلمة"""
    if not OPENAI_API_KEY:
        await update.message.reply_text("⚠️ OPENAI_API_KEY غير موجود")
        return
    
    try:
        processing_msg = await update.message.reply_text("🔄 جاري تحليل الصورة مع GPT-4...")
        
        # تحميل الصورة
        photo = await update.message.photo[-1].get_file()
        img_bytes = io.BytesIO()
        await photo.download_to_memory(img_bytes)
        img_bytes.seek(0)
        
        # تحليل الصورة باستخدام OpenAI
        response_text = await analyze_image_with_openai(img_bytes)
        
        if not response_text:
            await processing_msg.delete()
            await update.message.reply_text("❌ فشل في تحليل الصورة")
            return
        
        # تقسيم الاستجابة
        prompts = await parse_openai_response(response_text)
        
        # إنشاء أزرار
        keyboard = [
            [
                InlineKeyboardButton("📋 نسخ الإنجليزي", callback_data=f"copy_en:{prompts['english'][:50]}"),
                InlineKeyboardButton("📋 نسخ العربي", callback_data=f"copy_ar:{prompts['arabic'][:50]}")
            ],
            [
                InlineKeyboardButton("✨ اقتراح محسن", callback_data=f"copy_enhanced:{prompts['enhanced'][:50]}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إعداد النتيجة
        result_text = f"""
✅ *تم تحليل الصورة مع GPT-4 Vision!*

🇺🇸 *الوصف الإنجليزي:*
`{prompts['english']}`

🇸🇦 *الوصف العربي:*
`{prompts['arabic']}`

✨ *الاقتراح المحسن:*
`{prompts['enhanced']}`

🏷️ *الكلمات المفتاحية:*
{', '.join(prompts['keywords'].split(',')[:10])}
"""
        
        await processing_msg.delete()
        await update.message.reply_text(
            result_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء المعالجة")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة نقرات الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("copy_en:"):
        text = data.split(":", 1)[1]
        await query.edit_message_text(f"✅ تم نسخ البرومبت الإنجليزي:\n\n`{text}`")
        
    elif data.startswith("copy_ar:"):
        text = data.split(":", 1)[1]
        await query.edit_message_text(f"✅ تم نسخ البرومبت العربي:\n\n`{text}`")
        
    elif data.startswith("copy_enhanced:"):
        text = data.split(":", 1)[1]
        await query.edit_message_text(f"✨ تم نسخ الاقتراح المحسن:\n\n`{text}`")

# ========== الدالة الرئيسية ==========
def main():
    """تشغيل البوت"""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN غير موجود!")
        return
    
    if not OPENAI_API_KEY:
        print("⚠️ OPENAI_API_KEY غير موجود")
    
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(CallbackQueryHandler(button_handler))
        
        print("✅ البوت يعمل الآن...")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"فشل تشغيل البوت: {e}")

if __name__ == "__main__":
    main()
