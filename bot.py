import os
import json
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PollAnswerHandler,
    ContextTypes,
    filters
)

BOT_TOKEN = "8945939835:AAF2KhhwVNWmWtCQQriaF1j8kfdqkXgja60"
ADMIN_ID = 5683811825

def load_data(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_data(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_questions():
    return load_data("questions.json", [])

def get_codes_data():
    return load_data("codes.json", {"unused_codes": [], "used_by": {}})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name

    codes_data = get_codes_data()

    if user_id in codes_data.get("used_by", {}) or int(user_id) == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("بدء بنك أسئلة الهضمية 🔬", callback_data="start_quiz")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"أهلاً بك يا دكتور {user_name} في بوت التشريح المرضي الخاص (AURA) ✨\n\n"
            "اشتراكك مفعّل. اضغط أدناه للبدء:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"مرحباً بك دكتور {user_name} 🩺\n\n"
            "🔒 هذا البوت مخصص للمشتركين فقط.\n"
            "يرجى إرسال كود التفعيل الخاص بك هنا لتفعيل حسابك:"
        )

async def check_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    codes_data = get_codes_data()

    if user_id in codes_data.get("used_by", {}) or int(user_id) == ADMIN_ID:
        await update.message.reply_text("حسابك مفعّل بالفعل! أرسل /start لبدء الاختبار.")
        return

    unused = codes_data.get("unused_codes", [])

    if text in unused:
        unused.remove(text)
        codes_data["used_by"][user_id] = text
        save_data("codes.json", codes_data)

        keyboard = [
            [InlineKeyboardButton("بدء بنك أسئلة الهضمية 🔬", callback_data="start_quiz")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "✅ تم التحقق من الكود وتفعيل اشتراكك بنجاح!\nاضغط أدناه للبدء:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ هذا الكود غير صالح أو تم استخدامه مسبقاً.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    codes_data = get_codes_data()

    if user_id not in codes_data.get("used_by", {}) and int(user_id) != ADMIN_ID:
        await query.message.reply_text("⚠️ اشتراكك غير مفعّل.")
        return

    if query.data == "start_quiz":
        context.user_data["current_q_index"] = 0
        await send_next_question(query.message.chat_id, context)

async def send_next_question(chat_id, context: ContextTypes.DEFAULT_TYPE):
    questions = get_questions()
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
        context.bot_data[sent_poll.poll.id] = chat_id
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎉 مبروك! أنهيت الأسئلة بنجاح. أرسل /start للمراجعة مجدداً."
        )

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    chat_id = context.bot_data.get(poll_id)
    if chat_id:
        await send_next_question(chat_id, context)

web_app = Flask(__name__)

@web_app.route("/")
def index():
    return "Bot is alive!"

def start_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    flask_thread = Thread(target=start_flask, daemon=True)
    flask_thread.start()

    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(PollAnswerHandler(handle_poll_answer))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_code))

    bot_app.run_polling(drop_pending_updates=True)
