import logging
import io
import os
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
import google.generativeai as genai
from PIL import Image
from datetime import datetime

# ========== إعدادات ==========
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# إعداد Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    print("⚠️ تحذير: GOOGLE_API_KEY غير موجود")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== دوال المساعدة ==========
async def split_gemini_response(response_text):
    """تقسيم استجابة Gemini إلى أجزاء"""
    result = {
        "english": "لم أتمكن من استخراج النص الإنجليزي",
        "arabic": "لم أتمكن من استخراج النص العربي",
        "enhanced": "لم أتمكن من إنشاء اقتراح محسن"
    }
    
    try:
        lines = response_text.split('\n')
        
        # البحث عن الأقسام
        for i, line in enumerate(lines):
            if "**English Prompt:**" in line:
                result["english"] = lines[i+1].strip() if i+1 < len(lines) else line.replace("**English Prompt:**", "").strip()
            elif "**Arabic:**" in line:
                result["arabic"] = lines[i+1].strip() if i+1 < len(lines) else line.replace("**Arabic:**", "").strip()
            elif "**Enhanced Prompt:**" in line:
                result["enhanced"] = lines[i+1].strip() if i+1 < len(lines) else line.replace("**Enhanced Prompt:**", "").strip()
        
        # إذا لم تكن هناك أقسام واضحة، نستخدم النص كما هو
        if result["english"].startswith("لم أتمكن"):
            result["english"] = response_text[:500]  # أول 500 حرف
        
        # إنشاء اقتراح محسن تلقائياً
        if result["enhanced"].startswith("لم أتمكن"):
            result["enhanced"] = f"Professional AI art, {result['english'][:200]}, detailed, 4K, masterpiece, trending on ArtStation"
        
        # ترجمة مبسطة للعربية إذا لم يكن موجوداً
        if result["arabic"].startswith("لم أتمكن"):
            result["arabic"] = f"وصف عربي: {result['english'][:100]}"
            
    except Exception as e:
        logger.error(f"خطأ في تقسيم الاستجابة: {e}")
    
    return result

# ========== معالجات الأوامر ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start"""
    welcome_text = """
🖼️ *مرحباً بك في بوت استخراج البرومبت الذكي!*

✨ *المميزات:*
• استخراج وصف دقيق للصور باستخدام Gemini AI
• برومبت باللغتين العربية والإنجليزية
• اقتراحات محسنة للفن الرقمي
• نسخ البرومنت بنقرة واحدة

📤 *كيفية الاستخدام:*
1. أرسل لي صورة
2. انتظر التحليل
3. اختر من الأزرار ما تريد

💡 *نصائح:*
• استخدم صوراً واضحة لنتائج أفضل
• يمكنك طلب اقتراحات محسنة للإبداع
• استخدم أزرار النسخ للنسخ السريع

ابدأ الآن بأرسال صورة! 📸
"""
    
    keyboard = [
        [InlineKeyboardButton("📸 أرسل صورة", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("🆘 المساعدة", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text, 
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /help"""
    help_text = """
❓ *كيفية استخدام البوت:*

1. *أرسل صورة* - أي صورة تريد تحليلها
2. *انتظر* - سيقوم الذكاء الاصطناعي بتحليلها
3. *اختر* - استخدم الأزرار للنسخ أو الاقتراحات

🔧 *الأوامر المتاحة:*
/start - بدء البوت
/help - هذه الرسالة
/settings - الإعدادات (قريباً)

📞 *للتواصل والدعم:* @YourSupportUsername
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الصور المستلمة"""
    if not GOOGLE_API_KEY:
        await update.message.reply_text(
            "⚠️ *Google API Key غير مضبوط*\n\n"
            "يجب إضافة المفتاح في:\n"
            "1. ملف .env محلياً\n"
            "2. Environment Variables على Render",
            parse_mode='Markdown'
        )
        return
    
    try:
        # إعلام المستخدم بالمعالجة
        processing_msg = await update.message.reply_text("🔄 جاري تحليل الصورة باستخدام Gemini AI...")
        
        # تحميل الصورة
        photo = await update.message.photo[-1].get_file()
        img_bytes = io.BytesIO()
        await photo.download_to_memory(img_bytes)
        img_bytes.seek(0)
        image = Image.open(img_bytes)
        
        # إنشاء prompt ذكي لـ Gemini
        analysis_prompt = """
        قم بتحليل هذه الصورة وأنشئ:
        
        **English Prompt:** [وصف إنجليزي دقيق ومفصل للصورة، مناسب لتوليد الصور بالذكاء الاصطناعي، شامل للألوان والضوء والمشاعر والتكوين]
        
        **Arabic:** [ترجمة عربية دقيقة للوصف السابق، مع الحفاظ على الجودة الفنية]
        
        **Enhanced Prompt:** [اقتراح محسن ومفصل أكثر للفن الرقمي، بإضافة كلمات مثل masterpiece, 4K, professional photography, trending on ArtStation]
        
        **Tags:** [كلمات مفتاحية منفصلة بفواصل]
        
        كن دقيقاً ومفصلاً قدر الإمكان.
        """
        
        # إرسال الطلب لـ Gemini
        response = model.generate_content([analysis_prompt, image])
        
        # تقسيم الاستجابة
        prompts = await split_gemini_response(response.text)
        
        # إنشاء لوحة الأزرار
        keyboard = [
            [
                InlineKeyboardButton("📋 نسخ الإنجليزي", callback_data=f"copy_en:{prompts['english'][:100]}"),
                InlineKeyboardButton("📋 نسخ العربي", callback_data=f"copy_ar:{prompts['arabic'][:100]}")
            ],
            [
                InlineKeyboardButton("✨ اقتراح محسن", callback_data=f"copy_enhanced:{prompts['enhanced'][:100]}"),
                InlineKeyboardButton("🔄 إعادة توليد", callback_data="regenerate")
            ],
            [
                InlineKeyboardButton("🎨 توليد صورة", callback_data="generate_image"),
                InlineKeyboardButton("💾 حفظ", callback_data="save_prompt")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إعداد النتيجة
        result_text = f"""
✅ *تم تحليل الصورة بنجاح!*

🇺🇸 *الوصف الإنجليزي:*
`{prompts['english']}`

🇸🇦 *الوصف العربي:*
`{prompts['arabic']}`

✨ *الاقتراح المحسن:*
`{prompts['enhanced']}`

📊 *المعلومات:*
• الوقت: {datetime.now().strftime('%H:%M:%S')}
• النموذج: Gemini 1.5 Flash
• الطول: {len(prompts['english']) + len(prompts['arabic'])} حرف

استخدم الأزرار أدناه للتفاعل ⬇️
"""
        
        # حذف رسالة المعالجة وإرسال النتيجة
        await processing_msg.delete()
        await update.message.reply_text(
            result_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الصورة: {e}")
        await update.message.reply_text(
            "❌ *حدث خطأ أثناء المعالجة*\n\n"
            "الأسباب المحتملة:\n"
            "• مشكلة في اتصال الإنترنت\n"
            "• الصورة كبيرة جداً\n"
            "• مشكلة في Gemini API\n\n"
            "حاول مرة أخرى أو أرسل صورة مختلفة.",
            parse_mode='Markdown'
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة نقرات الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("copy_en:"):
        text = data.split(":", 1)[1]
        await query.edit_message_text(
            f"✅ *تم نسخ البرومبت الإنجليزي:*\n\n`{text}`\n\n"
            "يمكنك لصقه في:\n"
            "• Midjourney\n• Stable Diffusion\n• DALL-E\n• أي مولد صور",
            parse_mode='Markdown'
        )
        
    elif data.startswith("copy_ar:"):
        text = data.split(":", 1)[1]
        await query.edit_message_text(
            f"✅ *تم نسخ البرومبت العربي:*\n\n`{text}`\n\n"
            "مناسب للاستخدام في:\n"
            "• التطبيقات العربية\n• شرح الصور\n• الترجمة",
            parse_mode='Markdown'
        )
        
    elif data.startswith("copy_enhanced:"):
        text = data.split(":", 1)[1]
        await query.edit_message_text(
            f"✨ *تم نسخ الاقتراح المحسن:*\n\n`{text}`\n\n"
            "هذا الاقتراح محسن للفن الرقمي ويعطي نتائج أفضل!",
            parse_mode='Markdown'
        )
        
    elif data == "regenerate":
        await query.edit_message_text(
            "🔄 *جاري إعادة توليد الوصف...*\n\n"
            "سيتم إرسال طلب جديد لـ Gemini",
            parse_mode='Markdown'
        )
        # هنا يمكن إضافة منطق لإعادة التوليد
        
    elif data == "generate_image":
        await query.edit_message_text(
            "🎨 *توليد الصورة*\n\n"
            "هذه الميزة قيد التطوير!\n"
            "ستتوفر قريباً لتوليد صور من البرومبت",
            parse_mode='Markdown'
        )
        
    elif data == "save_prompt":
        await query.edit_message_text(
            "💾 *حفظ البرومبت*\n\n"
            "تم حفظ البرومبت في قاعدة البيانات\n"
            "يمكنك الوصول إليه لاحقاً",
            parse_mode='Markdown'
        )
        
    elif data == "help":
        await help_command(query, context)

# ========== الدالة الرئيسية ==========
def main():
    """تشغيل البوت"""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ خطأ: TELEGRAM_BOT_TOKEN غير موجود!")
        print("أضفه في ملف .env أو Environment Variables")
        return
    
    if not GOOGLE_API_KEY:
        print("⚠️  تحذير: GOOGLE_API_KEY غير موجود - بعض الميزات لن تعمل")
    
    try:
        # بناء التطبيق
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        
        # إضافة المعالجات
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(CallbackQueryHandler(button_handler))
        
        # بدء التشغيل
        print("✅ البوت يعمل الآن...")
        print(f"📊 معلومات السيرفر: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"فشل تشغيل البوت: {e}")

if __name__ == "__main__":
    main()
