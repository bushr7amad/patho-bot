import os
import json
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ContextTypes
)

# --- إعدادات البوت والقناة ---
BOT_TOKEN = "8945939835:AAF2KhhwVNwmWtCQQriaF1j8kfdqkxGj"
CHANNEL_ID = -1004453592408

def load_questions():
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading questions: {e}")
        return []

async def is_user_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except Exception as e:
        print(f"Error checking membership: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    # التحقق من وجود الطالب في القناة
    subscribed = await is_user_subscribed(context.bot, user_id)

    if subscribed:
        keyboard = [
            [InlineKeyboardButton("بدء بنك أسئلة الهضمية 🔬", callback_data="start_quiz")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"أهلاً بك يا دكتور {user_name} في بوت التشريح المرضي الخاص (AURA) ✨\n\n"
            "تم التحقق من اشتراكك بنجاح. اضغط على الزر أدناه لبدء حل الأسئلة:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"مرحباً بك {user_name} 🩺\n\n"
            "⚠️ هذا البوت مخصص للمشتركين فقط.\n"
            "يرجى التواصل مع إدارة AURA للاشتراك وإضافتك للقناة لتفعيل البوت تلقائياً."
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    subscribed = await is_user_subscribed(context.bot, user_id)
    if not subscribed:
        await query.message.reply_text("⚠️ غير مسموح بالوصول: يرجى التأكد من الاشتراك في القناة الخاصة.")
        return

    if query.data == "start_quiz":
        context.user_data["current_q_index"] = 0
        await send_next_question(query.message.chat_id, context)

async def send_next_question(chat_id, context: ContextTypes.DEFAULT_TYPE):
    questions = load_questions()
    idx = context.user_data.get("current_q_index", 0)

    if idx < len(questions):
        q = questions[idx]
        context.user_data["current_q_index"] = idx + 1
        sent_poll = await context.bot.send_poll(
            chat_id=chat_id,
            question=f"[{idx + 1}/{len(questions)}] {q['question']}",
            options=q["options"],
            type="quiz",
            correct_option_id=q["correct_option_id"],
            explanation=q["explanation"],
            is_anonymous=False,
            protect_content=True
        )
        # حفظ معرف السؤال لتتبعه وإرسال السؤال التالي بعد الإجابة
        context.bot_data[sent_poll.poll.id] = chat_id
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎉 أحسنت! أنهيت جميع أسئلة هذا القسم بنجاح.\nأرسل /start في أي وقت للمراجعة من جديد."
        )

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    chat_id = context.bot_data.get(poll_id)
    if chat_id:
        # إرسال السؤال التالي بمجرد أن يختار الطالب الإجابة
        await send_next_question(chat_id, context)

# --- سيرفر الويب الوهمي لإبقاء Render نشطاً مجاناً ---
server = Flask("")

@server.route("/")
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()

# --- تشغيل البوت ---
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(PollAnswerHandler(handle_poll_answer))
app.run_polling()

