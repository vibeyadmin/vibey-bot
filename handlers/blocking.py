from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_user


async def handle_blocked_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if user and user["is_blocked"]:
        await update.message.reply_text(
            "⛔ חשבונך חסום. שלח הודעה עם הסברך לערעור."
        )
