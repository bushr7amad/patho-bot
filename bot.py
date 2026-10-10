bot.py
import json
import sqlite3
import uuid
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- ضع التوكن الذي نسخته من BotFather هنا ---
BOT_TOKEN = "8945939835:AAF2KhhwVNWmWtCQQriaF1j8kfdqkXgja60"
ADMIN_TELEGRAM_ID = 5683811825  # هويتك الشخصية مثبتة كمدير


def get_db():
    return sqlite3.connect("patho_subscribers.db")


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_subscribed INTEGER DEFAULT 0
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS activation_codes (
            code TEXT PRIMARY KEY,
            is_used INTEGER DEFAULT 0
        )"""
    )
    conn.commit()
    conn.close()


init_db()


def load_questions():
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, username, is_subscribed) VALUES (?, ?, 0)",
        (user.id, user.username),
    )
    conn.commit()
    conn.close()

    keyboard = [
        [
            InlineKeyboardButton(
                "🔬 بنك دورات التشريح المرضي الخاص", callback_data="open_exams"
            )
        ],
        [
            InlineKeyboardButton(
                "🔑 إدخال كود التفعيل", callback_data="enter_code"
            )
        ],
        [
            InlineKeyboardButton(
                "💬 للاشتراك عبر الإدارة", url="https://t.me/auramed2"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"مرحباً بك زميلنا {user.first_name} في بنك أتمتة **التشريح المرضي الخاص** — فريق AURA 🛡️\n\n"
        "اختر من القائمة أدناه للبدء بالحل واختبار معلوماتك:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_subscribed FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    is_sub = row[0] if row else 0
    conn.close()

    if query.data == "open_exams":
        if is_sub == 1:
            context.user_data["current_q_index"] = 0
            await send_next_question(query.message.chat_id, context)
        else:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔑 لدي كود تفعيل", callback_data="enter_code"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💬 شراء اشتراك جديد", url="https://t.me/auramed2"
                    )
                ],
            ]
            await query.edit_message_text(
                "⚠️ **هذا المحتوى مخصص للمشتركين فقط**\n\n"
                "للوصول إلى كامل بنوك الدورات والحلول والتعليلات السريرية، يرجى التواصل مع فريق AURA للتفعيل أو إدخال كود الاشتراك الخاص بك.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

    elif query.data == "enter_code":
        context.user_data["awaiting_code"] = True
        await query.edit_message_text(
            "🔑 أرسل كود التفعيل الخاص بك الآن كرسالة عادية:"
        )


async def send_next_question(chat_id, context: ContextTypes.DEFAULT_TYPE):
    questions = load_questions()
    idx = context.user_data.get("current_q_index", 0)

    if idx < len(questions):
        q = questions[idx]
        context.user_data["current_q_index"] = idx + 1

        await context.bot.send_poll(
            chat_id=chat_id,
            question=f"[{q['chapter']}] {q['question']}",
            options=q["options"],
            type="quiz",
            correct_option_id=q["correct_option_id"],
            explanation=q["explanation"],
            is_anonymous=False,
            protect_content=True,
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎉 أحسنت! أنهيت جميع أسئلة هذا القسم بنجاح. أرسل /start للعودة للقائمة.",
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get("awaiting_code"):
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT is_used FROM activation_codes WHERE code = ? AND is_used = 0",
            (text,),
        )
        found = c.fetchone()

        if found:
            c.execute(
                "UPDATE activation_codes SET is_used = 1 WHERE code = ?",
                (text,),
            )
            c.execute(
                "UPDATE users SET is_subscribed = 1 WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
            context.user_data["awaiting_code"] = False
            await update.message.reply_text(
                "✅ **تم تفعيل اشتراكك بنجاح!**\nاضغط /start للدخول والبدء بحل دورات التشريح المرضي.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "❌ كود التفعيل غير صحيح أو مستخدم مسبقاً. تأكد من الرمز وحاول ثانية."
            )
        conn.close()


async def create_code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    code = "PATHO-" + str(uuid.uuid4())[:6].upper()
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO activation_codes (code, is_used) VALUES (?, 0)", (code,)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"تم توليد كود اشتراك جديد:\n`{code}`", parse_mode="Markdown"
    )


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new_code", create_code_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )

     ```python
   import os
   import threading
   from flask import Flask

   server = Flask('')

   @server.route('/')
   def home():
       return 'Bot is alive!'

   def run_web():
       port = int(os.environ.get('PORT', 8080))
       server.run(host='0.0.0.0', port=port)

   threading.Thread(target=run_web).start()
   app.run_polling()
