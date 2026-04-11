from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import add_user, get_user, get_deleted_user_history, get_user_settings, track_registration_start, update_registration_step, remove_incomplete_registration, REGIONS, RULES_TEXT
import os

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
GENDER, NAME, AGE, REGION, CITY, BIO, PHOTOS, ID_CARD = range(8)
MAX_PHOTOS = 5

TEXTS = {
    "he": {
        "welcome_back": "ברוך הבא חזרה",
        "browse": "💋 גלוש בפרופילים",
        "status": "👤 הפרופיל שלי",
        "premium": "⭐ פרמיום",
        "settings": "⚙️ הגדרות",
        "report": "🚨 דיווח",
        "bug": "🐛 תקלה",
        "delete": "🗑 מחק חשבון",
        "menu_title": "תפריט ראשי",
    },
    "en": {
        "welcome_back": "Welcome back",
        "browse": "💋 Browse profiles",
        "status": "👤 My profile",
        "premium": "⭐ Premium",
        "settings": "⚙️ Settings",
        "report": "🚨 Report",
        "bug": "🐛 Bug",
        "delete": "🗑 Delete account",
        "menu_title": "Main Menu",
    }
}


def get_lang(user_id):
    s = get_user_settings(user_id)
    return s.get("language", "he")


def t(user_id, key):
    lang = get_lang(user_id)
    return TEXTS.get(lang, TEXTS["he"]).get(key, TEXTS["he"].get(key, key))


async def send_main_menu(context, chat_id):
    lang = get_lang(chat_id)
    tx = TEXTS.get(lang, TEXTS["he"])
    keyboard = [
        [InlineKeyboardButton(tx["browse"], callback_data="menu_browse")],
        [InlineKeyboardButton(tx["status"], callback_data="menu_status"),
         InlineKeyboardButton(tx["premium"], callback_data="menu_premium")],
        [InlineKeyboardButton(tx["settings"], callback_data="menu_settings"),
         InlineKeyboardButton(tx["report"], callback_data="menu_report")],
        [InlineKeyboardButton(tx["bug"], callback_data="menu_bug")]
    ]
    title = "💋 *FlirtZone*"
    subtitle = "בחר/י פעולה:" if lang == "he" else "Choose an action:"
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"{title} | *{tx['menu_title']}*\n\n{subtitle}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = get_user(user_id)

    if existing:
        if existing["is_blocked"]:
            await update.message.reply_text(
                "⛔ *חשבונך חסום | Your account is blocked*\n\n"
                "שלח הודעה אם חושב שזו טעות.\n_Send a message if you think this is a mistake._",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        if existing.get("is_suspended"):
            await update.message.reply_text(
                "⏸ *חשבונך מושעה | Suspended*\n\n"
                "עקב דיווח. ההנהלה תיצור קשר.\n_Due to a report. Admin will contact you._",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        if existing["status"] == "pending":
            await update.message.reply_text(
                "⏳ *פרופילך ממתין לאישור | Pending approval*\n\n"
                "🇮🇱 תקבל הודעה כאן ברגע שיאושר.\n"
                "🇬🇧 You'll get a message here once approved.\n\n"
                "🙏 תודה על הסבלנות!",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        if existing["status"] == "approved":
            lang = get_lang(user_id)
            name = existing["name"]
            greeting = f"ברוך הבא חזרה, {name}! 💋" if lang == "he" else f"Welcome back, {name}! 💋"
            await update.message.reply_text(f"*{greeting}*", parse_mode="Markdown")
            await send_main_menu(context, user_id)
            return ConversationHandler.END

    # Track this as incomplete registration
    track_registration_start(
        update.effective_user.id,
        update.effective_user.username,
        update.effective_user.full_name
    )

    # Notify admin immediately
    import os
    admin_id = int(os.environ.get("ADMIN_ID", "0"))
    if admin_id:
        un = f"@{update.effective_user.username}" if update.effective_user.username else "אין שם משתמש"
        full = update.effective_user.full_name or ""
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"👋 *משתמש/ת חדש/ה התחיל/ה להירשם ל-FlirtZone!*\n\n👤 {full}\n📱 {un}\n🆔 `{update.effective_user.id}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # New registration
    keyboard = [
        [InlineKeyboardButton("👩 אישה / Woman", callback_data="gender_female")],
        [InlineKeyboardButton("👨 גבר / Man", callback_data="gender_male")]
    ]
    await update.message.reply_text(
        "💋 *ברוכים הבאים ל-FlirtZone!*\n"
        "_Welcome to FlirtZone!_\n\n"
        "🇮🇱 בוט היכרויות לקשר קליל ולא מחייב לבני/בנות 18+.\n\n"
        "🇬🇧 A casual, no-strings-attached dating platform open to all adults (18+).\n\n"
        "בחר/י מגדר | *Select your gender:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GENDER


async def _notify_admin_step(context, step_text, update, extra=""):
    """שלח עדכון לאדמין על כל שלב בהרשמה."""
    if not ADMIN_ID:
        return
    try:
        un = f"@{update.effective_user.username}" if update.effective_user.username else "אין שם משתמש"
        full = update.effective_user.full_name or ""
        uid = update.effective_user.id
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📝 *עדכון הרשמה בזמן אמת*\n\n"
                f"👤 {full} | {un}\n"
                f"🆔 `{uid}`\n\n"
                f"✏️ שלב: *{step_text}*"
                + (f"\n{extra}" if extra else "")
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gender = query.data.replace("gender_", "")
    context.user_data["gender"] = gender
    context.user_data["photos"] = []

    gender_text = "👩 אישה" if gender == "female" else "👨 גבר"
    await _notify_admin_step(context, f"בחר/ה מגדר: {gender_text}", update)

    await query.edit_message_text(
        "מה שמך? | *What's your name?*\n_(שם פרטי בלבד | First name only)_",
        parse_mode="Markdown"
    )
    update_registration_step(update.effective_user.id, 'name')
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 30:
        await update.message.reply_text("❌ שם לא תקין | _Invalid name (2-30 chars)_")
        return NAME
    context.user_data["name"] = name

    await _notify_admin_step(context, f"הזין/ה שם: *{name}*", update)

    await update.message.reply_text(
        f"שלום {name}! 👋\n\nמה גילך? | *How old are you?*\n_(מספר בלבד | numbers only)_",
        parse_mode="Markdown"
    )
    update_registration_step(update.effective_user.id, 'age')
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ מספר בלבד | _Numbers only_")
        return AGE

    if age < 18:
        await _notify_admin_step(context, f"❌ נדחה - גיל {age} (מתחת ל-18)", update)
        await update.message.reply_text(
            "❌ *הבוט מיועד למבוגרים מעל גיל 18 בלבד.*\n_This platform is for adults 18+ only._",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    context.user_data["age"] = age
    await _notify_admin_step(context, f"הזין/ה גיל: *{age}*", update)

    keyboard = [
        [InlineKeyboardButton("🌿 צפון / North", callback_data="region_north")],
        [InlineKeyboardButton("🏙 מרכז / Center", callback_data="region_center")],
        [InlineKeyboardButton("🌵 דרום / South", callback_data="region_south")]
    ]
    await update.message.reply_text(
        "📍 *באיזה אזור אתה/את?* | _Which region?_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    update_registration_step(update.effective_user.id, 'region')
    return REGION


async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region = query.data.replace("region_", "")
    context.user_data["region"] = region
    region_name = REGIONS.get(region, region)

    await _notify_admin_step(context, f"בחר/ה אזור: *{region_name}*", update)

    await query.edit_message_text(
        f"✅ {region_name}\n\nבאיזו עיר? | *Which city?*",
        parse_mode="Markdown"
    )
    update_registration_step(update.effective_user.id, 'city')
    return CITY


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    context.user_data["city"] = city

    # שלח סיכום נתוני הפרופיל עד כה
    data = context.user_data
    gender_text = "👩 אישה" if data.get("gender") == "female" else "👨 גבר"
    region_name = REGIONS.get(data.get("region", ""), data.get("region", ""))
    extra = (
        f"📊 *נתונים עד כה:*\n"
        f"• מגדר: {gender_text}\n"
        f"• שם: {data.get('name', '?')}\n"
        f"• גיל: {data.get('age', '?')}\n"
        f"• אזור: {region_name}\n"
        f"• עיר: {city}"
    )
    await _notify_admin_step(context, f"הזין/ה עיר: *{city}*", update, extra=extra)

    await update.message.reply_text(
        "📝 *ספר/י על עצמך | Tell us about yourself*\n\n"
        "🇮🇱 מה אתה/את מחפש/ת, תחביבים - עד 300 תווים\n"
        "🇬🇧 What you're looking for, hobbies - max 300 chars",
        parse_mode="Markdown"
    )
    update_registration_step(update.effective_user.id, 'bio')
    return BIO


async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bio = update.message.text.strip()
    if len(bio) > 300:
        await update.message.reply_text("❌ עד 300 תווים | _Max 300 chars_")
        return BIO
    context.user_data["bio"] = bio
    context.user_data["photos"] = []

    await _notify_admin_step(context, "הזין/ה ביו", update, extra=f"📝 _{bio}_")

    await update.message.reply_text(
        "📸 *שלח/י תמונות פרופיל | Send profile photos*\n\n"
        "🇮🇱 שלח/י עד 5 תמונות אחת אחת. כשסיימת שלח /done\n"
        "🇬🇧 Send up to 5 photos one by one. When done send /done\n\n"
        "_(התמונה הראשונה = תמונה ראשית)_",
        parse_mode="Markdown"
    )
    update_registration_step(update.effective_user.id, 'photos')
    return PHOTOS


async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.get("photos", [])

    if update.message.text and update.message.text.strip() in ["/done", "done"]:
        if len(photos) == 0:
            await update.message.reply_text("❌ שלח/י לפחות תמונה אחת | _Send at least one photo_")
            return PHOTOS
        await _ask_for_id(update)
        return ID_CARD

    if not update.message.photo:
        await update.message.reply_text("❌ שלח/י תמונה או /done לסיום")
        return PHOTOS

    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"✅ מקסימום {MAX_PHOTOS} תמונות! שלח /done להמשך")
        return PHOTOS

    photo_file_id = update.message.photo[-1].file_id
    photos.append(photo_file_id)
    context.user_data["photos"] = photos
    remaining = MAX_PHOTOS - len(photos)

    # שלח את התמונה לאדמין מיידית
    if ADMIN_ID:
        try:
            data = context.user_data
            un = f"@{update.effective_user.username}" if update.effective_user.username else "אין שם משתמש"
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo_file_id,
                caption=(
                    f"📸 *תמונה #{len(photos)} מ-{data.get('name', '?')}*\n"
                    f"👤 {update.effective_user.full_name or ''} | {un}\n"
                    f"🆔 `{update.effective_user.id}`"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    if remaining > 0:
        await update.message.reply_text(
            f"✅ תמונה {len(photos)} התקבלה! עוד {remaining} אפשריות, או /done לסיום"
        )
    else:
        await update.message.reply_text(f"✅ {MAX_PHOTOS} תמונות - מקסימום! שלח /done להמשך")
    return PHOTOS


async def _ask_for_id(update):
    await update.message.reply_text(
        "🪪 *שלח/י צילום תעודת זהות | Send your ID card*\n\n"
        "🇮🇱 *למה?* לאימות גיל ושם בלבד - כדי להבטיח קהילה בטוחה.\n"
        "🔒 נגיש אך ורק להנהלה ונמחק לאחר האימות.\n\n"
        "🇬🇧 *Why?* Age and name verification only.\n"
        "🔒 Only accessible to admin and deleted after verification.",
        parse_mode="Markdown"
    )


async def get_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        await update.message.reply_text("❌ שלח/י תמונה של התז | _Send a photo of your ID_")
        return ID_CARD

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("❌ שלח/י תמונה | _Send a photo_")
        return ID_CARD

    data = context.user_data
    bonus, returning = add_user(
        user_id=update.effective_user.id,
        username=update.effective_user.username or "",
        gender=data["gender"],
        name=data["name"],
        age=data["age"],
        region=data["region"],
        city=data["city"],
        bio=data["bio"],
        id_card_file_id=file_id,
        photos=data.get("photos", [])
    )

    bonus_msg = ""
    if bonus > 0:
        bonus_msg = f"\n\n🎁 *אתה בין 20 הנרשמים הראשונים! קיבלת {bonus} לייקים מתנה!* 🎉"

    await update.message.reply_text(
        "✅ *ההרשמה התקבלה! | Registration received!*\n\n"
        "🇮🇱 פרופילך ממתין לאישור. תקבל הודעה כאן כשיאושר. 🙏\n"
        "🇬🇧 Pending approval. You'll get a message here when approved. 🙏"
        + bonus_msg,
        parse_mode="Markdown"
    )

    if ADMIN_ID:
        photos_list = data.get("photos", [])
        gender_text = "👩 אישה" if data["gender"] == "female" else "👨 גבר"
        region_name = REGIONS.get(data["region"], data["region"])

        returning_flag = ""
        if returning:
            returning_flag = (
                f"\n\n⚠️ *משתמש חוזר!*\n"
                f"דיווחים קודמים: {returning['had_reports']} | חסימות: {returning['had_blocks']}"
            )

        keyboard = [[
            InlineKeyboardButton("✅ אשר", callback_data=f"approve_{update.effective_user.id}"),
            InlineKeyboardButton("❌ דחה", callback_data=f"reject_{update.effective_user.id}")
        ], [
            InlineKeyboardButton("🚫 חסום", callback_data=f"block_{update.effective_user.id}"),
            InlineKeyboardButton("🪪 תז", callback_data=f"view_id_{update.effective_user.id}")
        ]]

        tg_username = f"@{update.effective_user.username}" if update.effective_user.username else "אין שם משתמש"
        tg_name = update.effective_user.full_name or ""
        caption = (
            f"📋 *בקשת הרשמה - FlirtZone*\n\n"
            f"👤 {data['name']}, גיל {data['age']}\n"
            f"📍 {region_name} - {data['city']} | {gender_text}\n"
            f"📝 {data['bio']}\n"
            f"🆔 `{update.effective_user.id}`\n"
            f"📱 טלגרם: {tg_username} | {tg_name}"
            + returning_flag
        )

        try:
            if photos_list:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID, photo=photos_list[0],
                    caption=caption, parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                for p in photos_list[1:]:
                    await context.bot.send_photo(chat_id=ADMIN_ID, photo=p,
                                                 caption=f"📸 תמונה נוספת - {data['name']}")
            else:
                await context.bot.send_message(
                    chat_id=ADMIN_ID, text=caption, parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Admin notify failed: {e}")

    remove_incomplete_registration(update.effective_user.id)
    return ConversationHandler.END
