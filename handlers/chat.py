from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user, get_conn


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward messages between matched users in protected chat."""
    user_id = update.effective_user.id
    
    # Check if user is in an active chat session
    partner_id = _get_active_chat_partner(user_id)
    if not partner_id:
        return False  # Not in a chat, let other handlers process
    
    partner = get_user(partner_id)
    if not partner:
        return False

    # Forward message anonymously
    keyboard = [[
        InlineKeyboardButton("🔚 סיים שיחה | End chat", callback_data=f"end_chat_{user_id}_{partner_id}"),
        InlineKeyboardButton("✅ שתף פרטים | Share details", callback_data=f"share_details_{user_id}_{partner_id}")
    ]]

    try:
        if update.message.text:
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"💬 *הודעה חדשה | New message:*\n\n{update.message.text}\n\n_השב כרגיל | Reply normally_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif update.message.photo:
            await context.bot.send_photo(
                chat_id=partner_id,
                photo=update.message.photo[-1].file_id,
                caption="📸 _שלח/ה תמונה | Sent a photo_",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        await update.message.reply_text(
            "✅ _ההודעה נשלחה | Message sent_",
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text(
            "❌ לא ניתן לשלוח הודעה כרגע | _Could not send message right now_"
        )
    
    return True


async def handle_chat_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_")

    # End chat
    if data.startswith("end_chat_"):
        user1_id = int(parts[2])
        user2_id = int(parts[3])
        _end_chat_session(user1_id, user2_id)

        await context.bot.send_message(
            chat_id=user1_id,
            text=(
                "🔚 *השיחה הסתיימה | Chat ended*\n\n"
                "🇮🇱 הפרטים של הצד השני לא נחשפו.\n"
                "המשך לגלוש! /browse\n\n"
                "🇬🇧 The other person's details were not revealed.\n"
                "Keep browsing! /browse"
            ),
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=user2_id,
            text=(
                "🔚 *השיחה הסתיימה | Chat ended*\n\n"
                "🇮🇱 הצד השני סיים את השיחה. הפרטים שלך לא נחשפו.\n"
                "המשך לגלוש! /browse\n\n"
                "🇬🇧 The other person ended the chat. Your details were not revealed.\n"
                "Keep browsing! /browse"
            ),
            parse_mode="Markdown"
        )

    # Share details
    elif data.startswith("share_details_"):
        requester_id = int(parts[2])
        partner_id = int(parts[3])
        _save_share_consent(requester_id, partner_id)

        if _check_both_share_consent(requester_id, partner_id):
            # Both want to share
            requester = get_user(requester_id)
            partner = get_user(partner_id)
            _end_chat_session(requester_id, partner_id)

            await context.bot.send_message(
                chat_id=requester_id,
                text=(
                    f"🎉 *שניכם רוצים להמשיך! | You both want to continue!*\n\n"
                    f"🇮🇱 צור קשר ישירות עם {partner['name']}:\n"
                    f"👤 @{partner['username'] or 'חפש לפי שם'}\n\n"
                    f"🇬🇧 Contact {partner['name']} directly:\n"
                    f"👤 @{partner['username'] or 'Search by name'}"
                ),
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=partner_id,
                text=(
                    f"🎉 *שניכם רוצים להמשיך! | You both want to continue!*\n\n"
                    f"🇮🇱 צור קשר ישירות עם {requester['name']}:\n"
                    f"👤 @{requester['username'] or 'חפש לפי שם'}\n\n"
                    f"🇬🇧 Contact {requester['name']} directly:\n"
                    f"👤 @{requester['username'] or 'Search by name'}"
                ),
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=requester_id,
                text=(
                    "⏳ *בחרת לשתף פרטים!*\n"
                    "_You want to share details!_\n\n"
                    "🇮🇱 נמתין לתשובה של הצד השני...\n"
                    "🇬🇧 Waiting for the other person..."
                ),
                parse_mode="Markdown"
            )


def start_chat_session(user1_id, user2_id):
    """Start a protected chat session between two users."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS active_chats (
            user_id INTEGER PRIMARY KEY,
            partner_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT OR REPLACE INTO active_chats (user_id, partner_id) VALUES (?, ?)",
                 (user1_id, user2_id))
    conn.execute("INSERT OR REPLACE INTO active_chats (user_id, partner_id) VALUES (?, ?)",
                 (user2_id, user1_id))
    conn.commit()
    conn.close()


def _get_active_chat_partner(user_id):
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS active_chats (
            user_id INTEGER PRIMARY KEY,
            partner_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    result = conn.execute(
        "SELECT partner_id FROM active_chats WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return result["partner_id"] if result else None


def _end_chat_session(user1_id, user2_id):
    conn = get_conn()
    conn.execute("DELETE FROM active_chats WHERE user_id IN (?, ?)", (user1_id, user2_id))
    conn.execute("DELETE FROM share_consents WHERE (user_id = ? AND partner_id = ?) OR (user_id = ? AND partner_id = ?)",
                 (user1_id, user2_id, user2_id, user1_id))
    conn.commit()
    conn.close()


def _save_share_consent(user_id, partner_id):
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS share_consents (
            user_id INTEGER,
            partner_id INTEGER,
            PRIMARY KEY (user_id, partner_id)
        )
    """)
    conn.execute("INSERT OR IGNORE INTO share_consents (user_id, partner_id) VALUES (?, ?)",
                 (user_id, partner_id))
    conn.commit()
    conn.close()


def _check_both_share_consent(user1_id, user2_id):
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS share_consents (
            user_id INTEGER,
            partner_id INTEGER,
            PRIMARY KEY (user_id, partner_id)
        )
    """)
    r1 = conn.execute(
        "SELECT 1 FROM share_consents WHERE user_id=? AND partner_id=?",
        (user1_id, user2_id)
    ).fetchone()
    r2 = conn.execute(
        "SELECT 1 FROM share_consents WHERE user_id=? AND partner_id=?",
        (user2_id, user1_id)
    ).fetchone()
    conn.close()
    return r1 is not None and r2 is not None
