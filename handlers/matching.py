from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, InputMediaPhoto
from telegram.ext import ContextTypes
from database.db import (
    get_user, get_user_photos, get_next_profile, mark_seen,
    add_like, check_mutual_like, save_match, get_conn,
    check_and_use_like, get_likes_status, set_filter_region,
    PREMIUM_PRICE_STARS, REGIONS
)
from handlers.chat import start_chat_session

WAITING_LIKE_MESSAGE = {}


async def show_next_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        if update.message:
            await update.message.reply_text("❌ השתמש ב /start להרשמה | _Use /start to register_")
        return
    if user["is_blocked"]:
        if update.message:
            await update.message.reply_text("⛔ חשבונך חסום | _Your account is blocked_")
        return
    if user["status"] != "approved":
        if update.message:
            await update.message.reply_text("⏳ פרופילך ממתין לאישור | _Pending approval_")
        return

    filter_region = user["filter_region"]
    profile = get_next_profile(user_id, user["gender"], filter_region)

    if not profile:
        # Try without region filter as fallback
        profile = get_next_profile(user_id, user["gender"], None)
        if not profile:
            msg = "😔 *אין פרופילים כרגע* | _No profiles right now_\n\nחזור מאוחר יותר! | _Come back later!_"
            if update.message:
                await update.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
            return
        else:
            # Notify that showing profiles from other regions
            if update.message:
                await update.message.reply_text(
                    "ℹ️ _אין פרופילים באזורך כרגע - מציג מאזורים אחרים_\n"
                    "_No profiles in your region - showing from other regions_",
                    parse_mode="Markdown"
                )

    mark_seen(user_id, profile["user_id"])
    await _send_profile_card(context, user_id, profile, user["is_premium"])


async def _send_profile_card(context, chat_id, profile, is_premium=False):
    photos = get_user_photos(profile["user_id"])
    gender_emoji = "👩" if profile["gender"] == "female" else "👨"
    premium_badge = "⭐ " if profile["is_premium"] else ""
    region_name = REGIONS.get(profile["region"], "")

    caption = (
        f"{gender_emoji} {premium_badge}*{profile['name']}*, גיל {profile['age']}\n"
        f"📍 {region_name} - {profile['city']}\n\n"
        f"📝 {profile['bio']}"
    )

    buttons = [
        InlineKeyboardButton("❤️ כן / Yes", callback_data=f"like_{profile['user_id']}"),
        InlineKeyboardButton("❌ לא / No", callback_data=f"dislike_{profile['user_id']}")
    ]
    if is_premium:
        keyboard = [buttons, [
            InlineKeyboardButton("💌 שלח הודעה עם לייק | Message with like",
                                 callback_data=f"like_msg_{profile['user_id']}")
        ]]
    else:
        keyboard = [buttons]

    if len(photos) > 1:
        # Send as media group first, then send caption with buttons
        media = [InputMediaPhoto(media=f) for f in photos[:5]]
        media[0] = InputMediaPhoto(media=photos[0], caption=caption, parse_mode="Markdown")
        await context.bot.send_media_group(chat_id=chat_id, media=media)
        await context.bot.send_message(
            chat_id=chat_id,
            text="👆 בחר/י | _Choose:_",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif photos:
        await context.bot.send_photo(
            chat_id=chat_id, photo=photos[0], caption=caption,
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id, text=caption,
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_like_dislike(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    if data.startswith("like_msg_"):
        target_id = int(data.replace("like_msg_", ""))
        WAITING_LIKE_MESSAGE[user_id] = target_id
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "💌 *כתוב/י הודעה קצרה לשלוח עם הלייק*\n"
            "_Write a short message to send with your like (max 200 chars):_",
            parse_mode="Markdown"
        )
        return

    action, target_id = data.split("_", 1)
    target_id = int(target_id)

    user = get_user(user_id)
    if not user or user["is_blocked"] or user["status"] != "approved":
        return

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "like":
        await _process_like(update, context, user_id, target_id, user, query)
    else:
        await query.message.reply_text("👋 עוברים הלאה | _Moving on..._")
        await _show_next_auto(context, user_id, user["gender"], user["is_premium"], user["filter_region"])


async def handle_like_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in WAITING_LIKE_MESSAGE:
        return False
    target_id = WAITING_LIKE_MESSAGE.pop(user_id)
    message = update.message.text.strip()[:200]
    user = get_user(user_id)
    if not user:
        return True
    await _process_like(update, context, user_id, target_id, user, None, message=message)
    return True


async def _process_like(update, context, user_id, target_id, user, query, message=None):
    can_like, remaining = check_and_use_like(user_id)

    if not can_like:
        keyboard = [[InlineKeyboardButton("⭐ שדרג לפרמיום | Upgrade", callback_data="buy_premium")]]
        text = (
            "❌ *נגמרו הלייקים להיום! | No more likes today!*\n\n"
            "🇮🇱 יש לך 10 לייקים חינמיים ביום.\n"
            "🇬🇧 You have 10 free likes per day.\n\n"
            "שדרג לפרמיום ללייקים ללא הגבלה! | _Upgrade for unlimited likes!_"
        )
        target = query.message if query else update.message
        await target.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    add_like(user_id, target_id, message)

    if message:
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"💌 *{user['name']} שלח/ה לך הודעה עם לייק!*\n\n"
                    f"_{message}_\n\n"
                    f"_Browse to see their profile: /browse_"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    if remaining == -1:
        likes_text = "⭐ _פרמיום - ללא הגבלה_"
    elif remaining == 0:
        likes_text = "⚠️ _נגמרו הלייקים להיום_"
    else:
        likes_text = f"❤️ נשארו {remaining} לייקים היום | _{remaining} likes left today_"

    reply_text = f"❤️ לייקת! | _Liked!_\n\n{likes_text}"
    target = query.message if query else update.message
    await target.reply_text(reply_text, parse_mode="Markdown")

    if check_mutual_like(user_id, target_id):
        save_match(user_id, target_id)
        target_user = get_user(target_id)
        target_photos = get_user_photos(target_id)
        user_photos = get_user_photos(user_id)

        keyboard = [[
            InlineKeyboardButton("💬 כן! | Yes!", callback_data=f"chat_consent_{user_id}_{target_id}"),
            InlineKeyboardButton("❌ לא | No", callback_data=f"chat_decline_{user_id}_{target_id}")
        ]]

        match_text_user = (
            f"🎉 *יש התאמה! It's a Match!*\n\n"
            f"את/ה ו-*{target_user['name']}* אהבתם אחד את השני! 🎉\n"
            f"רוצה להתחיל שיחה מוגנת? הפרטים שלך לא יחשפו.\n\n"
            f"_You and *{target_user['name']}* liked each other! Protected chat?_"
        )
        match_text_target = (
            f"🎉 *יש התאמה! It's a Match!*\n\n"
            f"את/ה ו-*{user['name']}* אהבתם אחד את השני! 🎉\n"
            f"רוצה להתחיל שיחה מוגנת? הפרטים שלך לא יחשפו.\n\n"
            f"_You and *{user['name']}* liked each other! Protected chat?_"
        )

        if target_photos:
            await context.bot.send_photo(chat_id=user_id, photo=target_photos[0],
                                         caption=match_text_user, parse_mode="Markdown",
                                         reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=user_id, text=match_text_user,
                                           parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

        if user_photos:
            await context.bot.send_photo(chat_id=target_id, photo=user_photos[0],
                                         caption=match_text_target, parse_mode="Markdown",
                                         reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=target_id, text=match_text_target,
                                           parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    await _show_next_auto(context, user_id, user["gender"], user["is_premium"], user["filter_region"])


async def _show_next_auto(context, user_id, gender, is_premium, filter_region=None):
    profile = get_next_profile(user_id, gender, filter_region)
    if not profile and filter_region:
        profile = get_next_profile(user_id, gender, None)
    if profile:
        mark_seen(user_id, profile["user_id"])
        await _send_profile_card(context, user_id, profile, is_premium)


async def handle_premium_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        chat_id = update.effective_user.id
    else:
        chat_id = update.effective_user.id

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="Vibey Premium ⭐",
        description=(
            "✅ לייקים ללא הגבלה\n"
            "✅ הפרופיל מופיע ראשון\n"
            "✅ שלח הודעה עם כל לייק\n"
            "✅ בחר אזור / טווח קילומטרים\n"
            "✅ ראה מי לייקד אותך\n\n"
            "תוקף: 30 יום | Valid: 30 days"
        ),
        payload="premium_monthly",
        currency="XTR",
        prices=[LabeledPrice("Vibey Premium - חודש", PREMIUM_PRICE_STARS)]
    )


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db import set_premium
    user_id = update.effective_user.id
    until = set_premium(user_id)
    await update.message.reply_text(
        "🎉 *תשלום התקבל! Payment received!*\n\n"
        "⭐ *ברוך הבא לפרמיום! Welcome to Premium!*\n\n"
        "הפיצ'רים הבאים נפתחו לך:\n"
        "✅ לייקים ללא הגבלה\n"
        "✅ הפרופיל שלך מופיע ראשון\n"
        "✅ שלח הודעה עם כל לייק\n"
        "✅ בחר אזור / טווח קילומטרים\n"
        "✅ ראה מי לייקד אותך\n\n"
        f"⏰ תוקף עד: {until.strftime('%d/%m/%Y')}\n\n"
        "השתמש ב /browse! | _Start browsing!_",
        parse_mode="Markdown"
    )


async def handle_region_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user or not user["is_premium"]:
        await query.message.reply_text("⭐ פיצ'ר זה זמין לפרמיום בלבד | _Premium only feature_")
        return

    region = query.data.replace("filter_region_", "")
    if region == "all":
        set_filter_region(user_id, None)
        await query.edit_message_text("✅ מציג פרופילים מכל הארץ | _Showing profiles from all regions_")
    else:
        set_filter_region(user_id, region)
        region_name = REGIONS.get(region, region)
        await query.edit_message_text(f"✅ מציג פרופילים מ{region_name} | _Showing profiles from {region_name}_")


async def handle_chat_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("chat_consent_"):
        rest = data.replace("chat_consent_", "")
        ids = rest.split("_")
        requester_id, partner_id = int(ids[0]), int(ids[1])
        action = "consent"
    elif data.startswith("chat_decline_"):
        rest = data.replace("chat_decline_", "")
        ids = rest.split("_")
        requester_id, partner_id = int(ids[0]), int(ids[1])
        action = "decline"
    else:
        return

    user = get_user(requester_id)
    partner = get_user(partner_id)
    if not user or not partner:
        return

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "consent":
        _save_chat_consent(requester_id, partner_id)
        if _check_both_consented(requester_id, partner_id):
            start_chat_session(requester_id, partner_id)
            for uid, puid in [(requester_id, partner_id), (partner_id, requester_id)]:
                p = get_user(puid)
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"💬 *שיחה מוגנת התחילה! Protected chat started!*\n\n"
                        f"🇮🇱 אתה מדבר עם *{p['name']}*. הפרטים שלך לא נחשפים.\n"
                        f"כתוב/י כרגיל ואני אעביר.\n\n"
                        f"🇬🇧 Chatting with *{p['name']}*. Your details are hidden.\n"
                        f"Just type and I'll forward."
                    ),
                    parse_mode="Markdown"
                )
        else:
            await context.bot.send_message(
                chat_id=requester_id,
                text="⏳ ממתין לתשובה של הצד השני...\n_Waiting for the other person..._",
                parse_mode="Markdown"
            )
    else:
        await context.bot.send_message(
            chat_id=requester_id,
            text="👋 בחרת לא לדבר הפעם. /browse\n_You chose not to chat._",
            parse_mode="Markdown"
        )


def _save_chat_consent(user_id, partner_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO chat_consents (user_id, partner_id) VALUES (?, ?)", (user_id, partner_id))
    conn.commit()
    conn.close()


def _check_both_consented(user1_id, user2_id):
    conn = get_conn()
    r1 = conn.execute("SELECT 1 FROM chat_consents WHERE user_id=? AND partner_id=?", (user1_id, user2_id)).fetchone()
    r2 = conn.execute("SELECT 1 FROM chat_consents WHERE user_id=? AND partner_id=?", (user2_id, user1_id)).fetchone()
    conn.close()
    return r1 is not None and r2 is not None
