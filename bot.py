import logging
import os
import threading
from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    PreCheckoutQueryHandler, filters
)
from handlers.registration import (
    start, get_gender, get_name, get_age, get_region, get_city,
    get_bio, get_photos, get_id_card, send_main_menu,
    GENDER, NAME, AGE, REGION, CITY, BIO, PHOTOS, ID_CARD
)
from handlers.matching import (
    show_next_profile, handle_like_dislike, handle_chat_consent,
    handle_like_message_text, handle_region_filter
)
from handlers.admin import admin_panel, handle_admin_callback, handle_appeal_message
from handlers.chat import handle_chat_message, handle_chat_callbacks
try:
    from flask import Flask as _Flask, request as _request, session as _session, redirect as _redirect
    from functools import wraps as _wraps
    FLASK_OK = True
except Exception:
    FLASK_OK = False

from database.db import (
    init_db, get_user, get_likes_status, REGIONS,
    add_report, add_bug_report, delete_user_self, track_premium_interest,
    get_user_settings, update_user_setting, add_user_message, get_unread_messages_count,
    set_admin_chat, get_admin_chat
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

WAITING_REPORT_REASON = {}
WAITING_REPORT_EVIDENCE = {}
WAITING_BUG = set()
WAITING_EDIT_BIO = set()
WAITING_EDIT_PHOTOS = set()  # set of user_ids adding photos
WAITING_DELETE_PHOTO = {}  # user_id -> list of file_ids to choose from


async def handle_menu_callbacks(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    settings = get_user_settings(user_id)
    lang = settings.get("language", "he")

    if data == "menu_back":
        await send_main_menu(context, user_id)
        return

    if data == "menu_browse":
        await show_next_profile(update, context)
        return

    if data == "menu_premium":
        track_premium_interest(user_id)
        if lang == "he":
            text = (
                "⭐ *FlirtZone Premium*\n\n"
                "✅ לייקים ללא הגבלה\n"
                "✅ הפרופיל מופיע ראשון\n"
                "✅ שלח הודעה עם כל לייק\n"
                "✅ בחר אזור / טווח קילומטרים\n"
                "✅ ראה מי לייקד אותך\n\n"
                "⏰ תוקף: 30 יום | ~50₪/חודש"
            )
        else:
            text = (
                "⭐ *FlirtZone Premium*\n\n"
                "✅ Unlimited likes\n"
                "✅ Profile shown first\n"
                "✅ Send message with every like\n"
                "✅ Choose region / distance\n"
                "✅ See who liked you\n\n"
                "⏰ Valid: 30 days | ~$15/month"
            )
        keyboard = [
            [InlineKeyboardButton("💰 רכישה | Purchase", callback_data="menu_premium_buy")],
            [InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]
        ]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_premium_buy":
        track_premium_interest(user_id)
        msg = (
            "🚧 *הפיצ'ר בפיתוח!*\n\n"
            "אנחנו עובדים על מערכת התשלומים.\n"
            "נשלח לך הודעה כשיהיה מוכן! 💌"
            if lang == "he" else
            "🚧 *Feature in development!*\n\n"
            "We're working on the payment system.\n"
            "We'll message you when it's ready! 💌"
        )
        kb = [[InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "menu_status":
        user = get_user(user_id)
        if not user:
            await query.message.reply_text("❌ לא נמצא חשבון")
            return
        likes = get_likes_status(user_id)
        if likes and likes["type"] == "premium":
            likes_text = "⭐ פרמיום - ללא הגבלה" if lang == "he" else "⭐ Premium - unlimited"
        elif likes:
            likes_text = f"❤️ {likes['daily_remaining']} לייקים היום + {likes['bonus_likes']} בונוס"
        else:
            likes_text = "?"
        region_name = REGIONS.get(user.get("region", ""), "")
        from database.db import get_user_photos as gup
        photos = gup(user_id)
        gender_emoji = "👩" if user["gender"] == "female" else "👨"
        premium_badge = "⭐ " if user.get("is_premium") else ""
        profile_text = (
            f"{gender_emoji} {premium_badge}*{user['name']}*, גיל {user['age']}\n"
            f"📍 {region_name} - {user.get('city', '')}\n\n"
            f"📝 {user.get('bio', '')}\n\n"
            f"🔢 {likes_text}"
        )
        kb = [[InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]]
        if photos:
            from telegram import InputMediaPhoto
            if len(photos) == 1:
                await query.message.reply_photo(
                    photo=photos[0], caption=profile_text,
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
                )
            else:
                media = [InputMediaPhoto(media=f) for f in photos[:5]]
                media[0] = InputMediaPhoto(media=photos[0], caption=profile_text, parse_mode="Markdown")
                await context.bot.send_media_group(chat_id=user_id, media=media)
                await query.message.reply_text("👆 הפרופיל שלך | _Your profile_",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await query.message.reply_text(profile_text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "menu_settings":
        await show_settings_menu(query.message, user_id, lang)
        return

    if data.startswith("settings_lang_"):
        new_lang = data.replace("settings_lang_", "")
        update_user_setting(user_id, "language", new_lang)
        lang = new_lang
        msg = "✅ השפה שונתה לעברית!" if new_lang == "he" else "✅ Language changed to English!"
        await query.message.reply_text(msg)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data.startswith("settings_age_"):
        val = int(data.replace("settings_age_", ""))
        update_user_setting(user_id, "show_age", val)
        msg = ("✅ הגיל שלך יוצג בפרופיל" if val else "✅ הגיל שלך יוסתר מהפרופיל") if lang == "he" else \
              ("✅ Your age will be shown" if val else "✅ Your age will be hidden")
        await query.message.reply_text(msg)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data.startswith("settings_notif_"):
        val = int(data.replace("settings_notif_", ""))
        update_user_setting(user_id, "notifications", val)
        msg = ("✅ התראות הופעלו" if val else "✅ התראות כובו") if lang == "he" else \
              ("✅ Notifications enabled" if val else "✅ Notifications disabled")
        await query.message.reply_text(msg)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data == "settings_edit_bio":
        WAITING_EDIT_BIO.add(user_id)
        msg = "✏️ *ערוך ביו*\n\nכתוב/י ביו חדש (עד 300 תווים):" if lang == "he" else "✏️ *Edit bio*\n\nWrite your new bio (max 300 chars):"
        kb = [[InlineKeyboardButton("❌ ביטול | Cancel", callback_data="settings_cancel_edit")]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "settings_edit_photos":
        from database.db import get_user_photos as gup
        photos = gup(user_id)
        msg_he = f"📸 *ערוך תמונות*\n\nיש לך {len(photos)} תמונות כרגע (מינימום 1, מקסימום 5)."
        msg_en = f"📸 *Edit photos*\n\nYou have {len(photos)} photos (min 1, max 5)."
        msg = msg_he if lang == "he" else msg_en
        kb = []
        if len(photos) < 5:
            add_label = "➕ הוסף תמונה" if lang == "he" else "➕ Add photo"
            kb.append([InlineKeyboardButton(add_label, callback_data="settings_add_photo")])
        if len(photos) > 1:
            del_label = "🗑 מחק תמונה" if lang == "he" else "🗑 Delete photo"
            kb.append([InlineKeyboardButton(del_label, callback_data="settings_delete_photo")])
        kb.append([InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_settings")])
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "settings_add_photo":
        WAITING_EDIT_PHOTOS.add(user_id)
        msg = "📸 שלח/י תמונה חדשה:" if lang == "he" else "📸 Send your new photo:"
        kb = [[InlineKeyboardButton("❌ ביטול | Cancel", callback_data="settings_cancel_edit")]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "settings_delete_photo":
        from database.db import get_user_photos as gup
        photos = gup(user_id)
        msg = "🗑 *בחר/י תמונה למחיקה:*\n\n" if lang == "he" else "🗑 *Choose photo to delete:*\n\n"
        kb = []
        for i, _ in enumerate(photos):
            kb.append([InlineKeyboardButton(f"תמונה {i+1} | Photo {i+1}", callback_data=f"settings_del_photo_{i}")])
        kb.append([InlineKeyboardButton("🔙 חזרה | Back", callback_data="settings_edit_photos")])
        # Send photos so user can see them
        for i, fid in enumerate(photos):
            await query.message.reply_photo(photo=fid, caption=f"תמונה {i+1} | Photo {i+1}")
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("settings_del_photo_"):
        idx = int(data.replace("settings_del_photo_", ""))
        from database.db import get_user_photos as gup, get_conn
        photos = gup(user_id)
        if len(photos) <= 1:
            msg = "❌ לא ניתן למחוק - חייבת להישאר לפחות תמונה אחת!" if lang == "he" else "❌ Cannot delete - must keep at least one photo!"
            await query.message.reply_text(msg)
            return
        file_to_del = photos[idx]
        conn = get_conn()
        conn.execute("DELETE FROM user_photos WHERE user_id = ? AND file_id = ?", (user_id, file_to_del))
        conn.commit()
        conn.close()
        msg = f"✅ תמונה {idx+1} נמחקה!" if lang == "he" else f"✅ Photo {idx+1} deleted!"
        await query.message.reply_text(msg)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data == "settings_cancel_edit":
        WAITING_EDIT_BIO.discard(user_id)
        WAITING_EDIT_PHOTOS.discard(user_id)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data == "menu_settings":
        await show_settings_menu(query.message, user_id, lang)
        return

    if data == "menu_report":
        msg = (
            "🚨 *דיווח על משתמש*\n\nשלח: `/report [ID]`\n\nאת ה-ID תוכל/י לבקש מהמשתמש ישירות."
            if lang == "he" else
            "🚨 *Report a user*\n\nSend: `/report [ID]`\n\nYou can ask the user for their ID directly."
        )
        kb = [[InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "menu_bug":
        WAITING_BUG.add(user_id)
        msg = "🐛 *דיווח תקלה*\n\nתאר/י את הבעיה:" if lang == "he" else "🐛 *Report a bug*\n\nDescribe the issue:"
        await query.message.reply_text(msg, parse_mode="Markdown")
        return

    if data == "menu_delete_disabled":  # disabled
        yes = "🗑 כן, מחק" if lang == "he" else "🗑 Yes, delete"
        no = "❌ ביטול" if lang == "he" else "❌ Cancel"
        msg = (
            "⚠️ *האם אתה בטוח?*\n\nהפרופיל יימחק. ניתן להירשם מחדש בעתיד."
            if lang == "he" else
            "⚠️ *Are you sure?*\n\nYour profile will be deleted. You can register again later."
        )
        keyboard = [[
            InlineKeyboardButton(yes, callback_data="confirm_delete"),
            InlineKeyboardButton(no, callback_data="cancel_delete")
        ]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return


async def show_settings_menu(message, user_id, lang):
    settings = get_user_settings(user_id)
    show_age = settings.get("show_age", 1)
    notif = settings.get("notifications", 1)

    if lang == "he":
        title = "⚙️ *הגדרות*"
        lang_label = "🌐 שפה: עברית ✅" if lang == "he" else "🌐 שפה: English ✅"
        age_label = f"👁 הצג גיל: {'כן ✅' if show_age else 'לא ❌'}"
        notif_label = f"🔔 התראות: {'פועל ✅' if notif else 'כבוי ❌'}"
    else:
        title = "⚙️ *Settings*"
        lang_label = "🌐 Language: English ✅"
        age_label = f"👁 Show age: {'Yes ✅' if show_age else 'No ❌'}"
        notif_label = f"🔔 Notifications: {'On ✅' if notif else 'Off ❌'}"

    edit_bio = "✏️ ערוך ביו" if lang == "he" else "✏️ Edit bio"
    edit_photos = "📸 ערוך תמונות" if lang == "he" else "📸 Edit photos"
    keyboard = [
        [InlineKeyboardButton("🇮🇱 עברית" + (" ✅" if lang == "he" else ""), callback_data="settings_lang_he"),
         InlineKeyboardButton("🇬🇧 English" + (" ✅" if lang == "en" else ""), callback_data="settings_lang_en")],
        [InlineKeyboardButton(age_label, callback_data=f"settings_age_{0 if show_age else 1}")],
        [InlineKeyboardButton(notif_label, callback_data=f"settings_notif_{0 if notif else 1}")],
        [InlineKeyboardButton(edit_bio, callback_data="settings_edit_bio"),
         InlineKeyboardButton(edit_photos, callback_data="settings_edit_photos")],
        [InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]
    ]
    await message.reply_text(
        f"{title}\n\n{lang_label}\n{age_label}\n{notif_label}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_delete_confirm(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = get_user_settings(user_id).get("language", "he")
    if query.data == "confirm_delete":
        delete_user_self(user_id)
        msg = (
            "🗑 *החשבון נמחק*\n\nתודה שהיית חלק מ-FlirtZone! 💋\nכדי להצטרף שוב: /start"
            if lang == "he" else
            "🗑 *Account deleted*\n\nThank you for being part of FlirtZone! 💋\nTo rejoin: /start"
        )
        await query.edit_message_text(msg, parse_mode="Markdown")
    else:
        await query.edit_message_text("✅ ביטול | Cancelled")


async def handle_message(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id

    # Edit bio
    if update.message.text and user_id in WAITING_EDIT_BIO:
        bio = update.message.text.strip()
        if len(bio) > 300:
            await update.message.reply_text("❌ עד 300 תווים | Max 300 chars")
            return
        WAITING_EDIT_BIO.discard(user_id)
        from database.db import get_conn
        conn = get_conn()
        conn.execute("UPDATE users SET bio = ? WHERE user_id = ?", (bio, user_id))
        conn.commit()
        conn.close()
        lang = get_user_settings(user_id).get("language", "he")
        msg = "✅ הביו עודכן!" if lang == "he" else "✅ Bio updated!"
        await update.message.reply_text(msg)
        await send_main_menu(context, user_id)
        return

    if update.message.text and user_id in WAITING_REPORT_REASON:
        target_id = WAITING_REPORT_REASON.pop(user_id)
        WAITING_REPORT_EVIDENCE[user_id] = {"target_id": target_id, "reason": update.message.text.strip()}
        await update.message.reply_text("📎 שלח/י תמונת הוכחה, או /skip אם אין")
        return

    if user_id in WAITING_REPORT_EVIDENCE:
        data = WAITING_REPORT_EVIDENCE.pop(user_id)
        evidence = update.message.photo[-1].file_id if update.message.photo else None
        add_report(user_id, data["target_id"], data["reason"], evidence)
        await update.message.reply_text("✅ *הדיווח התקבל!* ההנהלה תבדוק בהקדם.", parse_mode="Markdown")
        admin_id = int(os.environ.get("ADMIN_ID", "0"))
        if admin_id:
            from database.db import get_user as gu
            reporter = gu(user_id)
            reported = gu(data["target_id"])
            kb = [[
                InlineKeyboardButton("⏸ השעה", callback_data=f"suspend_{data['target_id']}"),
                InlineKeyboardButton("🚫 חסום", callback_data=f"block_{data['target_id']}")
            ], [
                InlineKeyboardButton("💬 מדווח", callback_data=f"msg_to_{user_id}"),
                InlineKeyboardButton("💬 מדוּוח", callback_data=f"msg_to_{data['target_id']}")
            ]]
            text = (f"🚨 *דיווח חדש*\n\n"
                    f"👤 מדווח: {reporter['name'] if reporter else user_id}\n"
                    f"👤 מדוּוח: {reported['name'] if reported else data['target_id']}\n"
                    f"📝 {data['reason']}")
            if evidence:
                try:
                    await context.bot.send_photo(chat_id=admin_id, photo=evidence,
                        caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
                    return
                except Exception:
                    pass
            await context.bot.send_message(chat_id=admin_id, text=text,
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if update.message.text and user_id in WAITING_BUG:
        WAITING_BUG.discard(user_id)
        add_bug_report(user_id, update.message.text.strip())
        await update.message.reply_text("✅ *תודה! הדיווח התקבל.*", parse_mode="Markdown")
        return

    if not update.message.text:
        return

    # ── Admin chat mode: if admin is in chat with a user, forward messages ──
    admin_id = int(os.environ.get("ADMIN_ID", "0"))
    if user_id == admin_id:
        # Admin sent a message - forward to user if in chat mode
        target_uid = get_admin_chat()
        if target_uid and update.message and update.message.text:
            try:
                await context.bot.send_message(
                    chat_id=target_uid,
                    text=f"📨 *הודעה מהנהלת FlirtZone:*\n\n{update.message.text}",
                    parse_mode="Markdown"
                )
                await update.message.reply_text("✅ נשלח!")
            except Exception as e:
                await update.message.reply_text(f"❌ לא ניתן לשלוח: {e}")
            return

    # ── User sent a message - if admin is in chat with this user, forward to admin ──
    target_admin = get_admin_chat()
    if target_admin and target_admin == user_id and update.message and update.message.text:
        user = get_user(user_id)
        name = user["name"] if user else user_id
        admin_id2 = int(os.environ.get("ADMIN_ID", "0"))
        from telegram import InlineKeyboardButton as IKB, InlineKeyboardMarkup as IKM
        kb = [[IKB("🔚 סיים שיחה", callback_data="admin_end_chat")]]
        await context.bot.send_message(
            chat_id=admin_id2,
            text=f"💬 *{name}:*\n\n{update.message.text}",
            parse_mode="Markdown",
            reply_markup=IKM(kb)
        )
        return

    # Forward message to admin inbox (if approved user, not in any other flow)
    user = get_user(user_id)
    if user and user.get("status") == "approved" and not user.get("is_blocked"):
        # Only save if not in any waiting state
        not_in_flow = (
            user_id not in WAITING_REPORT_REASON and
            user_id not in WAITING_REPORT_EVIDENCE and
            user_id not in WAITING_BUG and
            user_id not in WAITING_EDIT_BIO and
            user_id not in WAITING_EDIT_PHOTOS
        )
        # Will be saved after other handlers check - see bottom of function

    handled = await handle_chat_message(update, context)
    if handled:
        return
    handled = await handle_like_message_text(update, context)
    if handled:
        return
    await handle_appeal_message(update, context)

    # Save message to admin inbox if approved user
    user2 = get_user(user_id)
    if user2 and user2.get("status") == "approved" and not user2.get("is_blocked"):
        not_in_flow = (
            user_id not in WAITING_REPORT_REASON and
            user_id not in WAITING_REPORT_EVIDENCE and
            user_id not in WAITING_BUG and
            user_id not in WAITING_EDIT_BIO and
            user_id not in WAITING_EDIT_PHOTOS
        )
        if not_in_flow and update.message and update.message.text:
            add_user_message(user_id, update.message.text)
            # Forward immediately to admin
            admin_id = int(os.environ.get("ADMIN_ID", "0"))
            if admin_id:
                ge = "👩" if user2.get("gender") == "female" else "👨"
                name = user2.get("name") or user_id
                kb = [[
                    InlineKeyboardButton("💬 שוחח איתו", callback_data=f"admin_start_chat_{user_id}"),
                    InlineKeyboardButton("👁 פרופיל", callback_data=f"admin_view_user_{user_id}")
                ]]
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"💬 *הודעה מ{ge} {name}:*\n\n{update.message.text}\n\n🆔 `{user_id}`",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(kb)
                    )
                except Exception:
                    pass


async def handle_photo_message(update, context):
    user_id = update.effective_user.id
    if user_id in WAITING_REPORT_EVIDENCE:
        await handle_message(update, context)
        return
    if user_id in WAITING_EDIT_PHOTOS:
        WAITING_EDIT_PHOTOS.discard(user_id)
        from database.db import get_user_photos as gup, get_conn
        photos = gup(user_id)
        if len(photos) >= 5:
            await update.message.reply_text("❌ כבר יש 5 תמונות - המקסימום! מחק תמונה קודם.")
            return
        file_id = update.message.photo[-1].file_id
        conn = get_conn()
        pos = len(photos)
        conn.execute("INSERT INTO user_photos (user_id, file_id, position) VALUES (?, ?, ?)",
                     (user_id, file_id, pos))
        conn.commit()
        conn.close()
        lang = get_user_settings(user_id).get("language", "he")
        msg = f"✅ תמונה נוספה! יש לך עכשיו {pos+1} תמונות." if lang == "he" else f"✅ Photo added! You now have {pos+1} photos."
        await update.message.reply_text(msg)
        await send_main_menu(context, user_id)
        return
    await handle_chat_message(update, context)


async def pre_checkout(update, context):
    await update.pre_checkout_query.answer(ok=True)


async def report_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר")
        return
    args = context.args
    if not args:
        await update.message.reply_text("🚨 שלח: `/report [ID]`", parse_mode="Markdown")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID לא תקין")
        return
    if target_id == user_id:
        await update.message.reply_text("❌ לא ניתן לדווח על עצמך")
        return
    WAITING_REPORT_REASON[user_id] = target_id
    await update.message.reply_text("📝 מה סיבת הדיווח? תאר/י בקצרה:")


async def skip_command(update, context):
    user_id = update.effective_user.id
    if user_id in WAITING_REPORT_EVIDENCE:
        data = WAITING_REPORT_EVIDENCE.pop(user_id)
        add_report(user_id, data["target_id"], data["reason"], None)
        await update.message.reply_text("✅ הדיווח התקבל.")


async def bug_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר")
        return
    WAITING_BUG.add(user_id)
    await update.message.reply_text("🐛 תאר/י את הבעיה:")


async def delete_command(update, context):
    keyboard = [[
        InlineKeyboardButton("🗑 כן, מחק", callback_data="confirm_delete"),
        InlineKeyboardButton("❌ ביטול", callback_data="cancel_delete")
    ]]
    await update.message.reply_text(
        "⚠️ *מחיקת חשבון*\n\nהפרופיל יימחק. להמשיך?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def menu_command(update, context):
    user = get_user(update.effective_user.id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר | /start")
        return
    await send_main_menu(context, update.effective_user.id)



def _run_web_admin():
    """Run web admin in background - safe, won't affect bot if it fails."""
    try:
        import os as _os
        db_path = _os.environ.get("DB_PATH", "dating_bot.db")
        admin_pass = _os.environ.get("ADMIN_WEB_PASSWORD", "admin123")
        secret = _os.environ.get("WEB_SECRET_KEY", "flirtzonesecret")
        port = int(_os.environ.get("PORT", _os.environ.get("WEB_PORT", "5000")))

        if not FLASK_OK:
            return

        web = _Flask(__name__)
        web.secret_key = secret

        REGIONS = {"north": "צפון 🌿", "center": "מרכז 🏙", "south": "דרום 🌵"}

        def _conn():
            import sqlite3
            c = sqlite3.connect(db_path)
            c.row_factory = lambda cur, row: {col[0]: row[i] for i, col in enumerate(cur.description)} if cur.description else row
            return c

        def lr(f):
            @_wraps(f)
            def d(*a, **k):
                if not _session.get("ok"):
                    return _redirect("/login")
                return f(*a, **k)
            return d

        BASE = """<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box}
body{background:#080810;color:#fff;font-family:'Heebo',sans-serif;min-height:100vh}
body::before{content:'';position:fixed;top:0;left:0;width:100%;height:300px;background:radial-gradient(ellipse at 50% 0%,rgba(233,30,140,0.12) 0%,transparent 70%);pointer-events:none;z-index:0}
nav{background:rgba(255,255,255,0.02);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.06);position:sticky;top:0;z-index:100}
.ni{max-width:1400px;margin:0 auto;padding:0 32px;display:flex;align-items:center;justify-content:space-between;height:64px}
.nl{font-size:1.3rem;font-weight:900;text-decoration:none;color:#fff}
.na{display:flex;gap:4px}
.na a{color:rgba(255,255,255,0.5);text-decoration:none;padding:8px 14px;border-radius:8px;font-size:.85rem;transition:all .2s}
.na a:hover,.na a.active{background:rgba(233,30,140,0.15);color:#fff}
.container{max-width:1400px;margin:0 auto;padding:40px 32px;position:relative;z-index:1}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:40px}
.stat{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:24px;text-align:center}
.num{font-size:2.8rem;font-weight:900;line-height:1}
.lbl{color:rgba(255,255,255,0.4);font-size:.8rem;margin-top:6px}
.pink{color:#e91e8c}.green{color:#4caf50}.orange{color:#ff9800}.red{color:#f44336}.purple{color:#9c27b0}.blue{color:#2196f3}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}
.card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:16px;overflow:hidden;transition:all .2s}
.card:hover{border-color:rgba(233,30,140,0.3)}
.av{height:160px;background:linear-gradient(135deg,rgba(233,30,140,0.2),rgba(100,0,200,0.2));display:flex;align-items:center;justify-content:center;font-size:4rem}
.cb{padding:16px}
.cn{font-size:1.05rem;font-weight:700;margin-bottom:4px}
.cm{color:rgba(255,255,255,0.4);font-size:.8rem;margin-bottom:3px}
.bio{color:rgba(255,255,255,0.6);font-size:.82rem;margin-top:8px;line-height:1.5}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:600;margin:2px}
.bg{background:rgba(76,175,80,0.15);color:#4caf50;border:1px solid rgba(76,175,80,0.3)}
.bo{background:rgba(255,152,0,0.15);color:#ff9800;border:1px solid rgba(255,152,0,0.3)}
.br{background:rgba(244,67,54,0.15);color:#f44336;border:1px solid rgba(244,67,54,0.3)}
.bp{background:rgba(233,30,140,0.15);color:#e91e8c;border:1px solid rgba(233,30,140,0.3)}
code{background:rgba(255,255,255,0.07);padding:2px 8px;border-radius:6px;font-size:.78rem;font-family:monospace}
.fi{display:flex;gap:10px;margin-bottom:24px;flex-wrap:wrap;align-items:center}
.fi input{padding:10px 16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:10px;color:#fff;font-family:inherit;font-size:.9rem;outline:none;width:240px}
.fi input:focus{border-color:#e91e8c}
.fa{padding:9px 16px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:10px;color:rgba(255,255,255,0.5);text-decoration:none;font-size:.82rem;transition:all .2s}
.fa:hover,.fa.active{background:rgba(233,30,140,0.15);border-color:rgba(233,30,140,0.3);color:#fff}
.fb{padding:9px 16px;background:linear-gradient(135deg,#e91e8c,#9c27b0);border:none;border-radius:10px;color:#fff;cursor:pointer;font-family:inherit;font-size:.82rem}
table{width:100%;border-collapse:collapse}
th{padding:12px 16px;text-align:right;color:rgba(255,255,255,0.3);font-size:.8rem;border-bottom:1px solid rgba(255,255,255,0.06)}
td{padding:12px 16px;border-bottom:1px solid rgba(255,255,255,0.04);font-size:.85rem}
.mc{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:18px;margin-bottom:12px}
.mh{display:flex;justify-content:space-between;margin-bottom:8px}
.mt{color:rgba(255,255,255,0.7);line-height:1.6}
.pag{margin-top:28px;display:flex;gap:6px;justify-content:center}
.pag a{padding:8px 14px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:8px;color:rgba(255,255,255,0.5);text-decoration:none;font-size:.85rem}
.pag a.cur{background:rgba(233,30,140,0.2);border-color:#e91e8c;color:#fff}
</style></head><body>"""

        def nav(p):
            ps = {"home":"","users":"","pending":"","reports":"","messages":""}
            ps[p] = "active"
            return f"""{BASE}<nav><div class="ni">
<a href="/" class="nl">💋 FlirtZone Admin</a>
<div class="na">
<a href="/" class="{ps["home"]}">🏠 ראשי</a>
<a href="/users" class="{ps["users"]}">👥 משתמשים</a>
<a href="/pending" class="{ps["pending"]}">⏳ ממתינים</a>
<a href="/reports" class="{ps["reports"]}">🚨 דיווחים</a>
<a href="/messages" class="{ps["messages"]}">💬 הודעות</a>
<a href="/logout" style="color:rgba(255,100,100,0.5)">יציאה</a>
</div></div></nav><div class="container">"""

        @web.route("/login", methods=["GET","POST"])
        def wlogin():
            err = ""
            if _request.method == "POST":
                if _request.form.get("password") == admin_pass:
                    _session["ok"] = True
                    return _redirect("/")
                err = "סיסמה שגויה"
            return f"""{BASE}<div style="display:flex;align-items:center;justify-content:center;min-height:100vh">
<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(233,30,140,0.2);border-radius:24px;padding:56px 48px;width:380px;text-align:center">
<div style="font-size:3rem;margin-bottom:8px">💋</div>
<h1 style="font-size:2rem;font-weight:900;margin-bottom:4px">FlirtZone</h1>
<p style="color:rgba(255,255,255,0.4);margin-bottom:36px">פאנל ניהול</p>
<form method="POST">
<input type="password" name="password" placeholder="סיסמה" autofocus style="width:100%;padding:14px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:12px;color:#fff;font-size:1rem;margin-bottom:14px;outline:none;text-align:center;font-family:inherit">
<button style="width:100%;padding:14px;background:linear-gradient(135deg,#e91e8c,#9c27b0);border:none;border-radius:12px;color:#fff;font-size:1rem;font-weight:700;cursor:pointer;font-family:inherit">כניסה</button>
</form>
{f'<p style="color:#f66;font-size:.85rem;margin-top:12px">{err}</p>' if err else ''}
</div></div></body></html>"""

        @web.route("/photo/<file_id>")
        def photo_proxy(file_id):
            try:
                import urllib.request
                token = _os.environ.get("BOT_TOKEN", "")
                # Get file path from Telegram
                url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
                with urllib.request.urlopen(url) as r:
                    import json
                    data = json.loads(r.read())
                    file_path = data["result"]["file_path"]
                # Download file
                file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                with urllib.request.urlopen(file_url) as r:
                    img_data = r.read()
                from flask import Response
                return Response(img_data, mimetype="image/jpeg")
            except Exception:
                # Return empty 1x1 pixel if fails
                from flask import Response
                import base64
                px = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
                return Response(px, mimetype="image/png")

        @web.route("/logout")
        def wlogout():
            _session.clear()
            return _redirect("/login")

        @web.route("/")
        @lr
        def whome():
            c = _conn()
            try:
                total = c.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
                pending = c.execute("SELECT COUNT(*) as n FROM users WHERE status='pending'").fetchone()["n"]
                approved = c.execute("SELECT COUNT(*) as n FROM users WHERE status='approved'").fetchone()["n"]
                blocked = c.execute("SELECT COUNT(*) as n FROM users WHERE is_blocked=1").fetchone()["n"]
                matches = c.execute("SELECT COUNT(*) as n FROM matches").fetchone()["n"]
                try: reports = c.execute("SELECT COUNT(*) as n FROM reports WHERE status='pending'").fetchone()["n"]
                except: reports = 0
                try: msgs = c.execute("SELECT COUNT(*) as n FROM user_messages WHERE is_read=0").fetchone()["n"]
                except: msgs = 0
            except Exception as e:
                c.close()
                return f"שגיאה: {e}"
            c.close()
            return nav("home") + f"""
<div class="stats">
<div class="stat"><div class="num pink">{total}</div><div class="lbl">סה"כ משתמשים</div></div>
<div class="stat"><div class="num orange">{pending}</div><div class="lbl">ממתינים</div></div>
<div class="stat"><div class="num green">{approved}</div><div class="lbl">מאושרים</div></div>
<div class="stat"><div class="num red">{blocked}</div><div class="lbl">חסומים</div></div>
<div class="stat"><div class="num purple">{matches}</div><div class="lbl">התאמות</div></div>
<div class="stat"><div class="num blue">{reports}</div><div class="lbl">דיווחים</div></div>
<div class="stat"><div class="num pink">{msgs}</div><div class="lbl">הודעות חדשות</div></div>
</div>
<p style="font-size:1.3rem;font-weight:700;margin-bottom:20px">קישורים מהירים</p>
<div style="display:flex;gap:12px;flex-wrap:wrap">
<a href="/pending" class="fa active">⏳ ממתינים ({pending})</a>
<a href="/users" class="fa">👥 כל המשתמשים</a>
<a href="/reports" class="fa">🚨 דיווחים ({reports})</a>
<a href="/messages" class="fa">💬 הודעות ({msgs})</a>
</div></div></body></html>"""

        @web.route("/users")
        @lr
        def wusers():
            sf = _request.args.get("status","")
            s = _request.args.get("search","")
            pg = int(_request.args.get("page",1))
            pp = 12
            c = _conn()
            w, p = "WHERE 1=1", []
            if sf: w += " AND status=?"; p.append(sf)
            if s:
                try: uid=int(s); w += " AND user_id=?"; p.append(uid)
                except: w += " AND LOWER(name) LIKE LOWER(?)"; p.append(f"%{s}%")
            total = c.execute(f"SELECT COUNT(*) as n FROM users {w}", p).fetchone()["n"]
            ul = c.execute(f"SELECT * FROM users {w} ORDER BY created_at DESC LIMIT ? OFFSET ?", p+[pp,(pg-1)*pp]).fetchall()
            c.close()
            cards = ""
            for u in ul:
                ge = "👩" if u["gender"]=="female" else "👨"
                reg = REGIONS.get(u.get("region",""),"")
                un = f"@{u['username']}" if u.get("username") else "אין"
                sb = {"approved":'<span class="badge bg">✅ מאושר</span>',
                      "pending":'<span class="badge bo">⏳ ממתין</span>',
                      "rejected":'<span class="badge br">❌ נדחה</span>'}.get(u["status"],"")
                fl = ""
                if u.get("is_blocked"): fl += '<span class="badge br">🚫</span>'
                if u.get("is_premium"): fl += '<span class="badge bp">⭐</span>'
                bio = (u.get("bio") or "")[:70]
                _photos = _conn().execute("SELECT file_id FROM user_photos WHERE user_id=? ORDER BY position LIMIT 1",(u["user_id"],)).fetchone()
                _img = f'<img src="/photo/{_photos["file_id"]}" style="width:100%;height:100%;object-fit:cover">' if _photos else ge
                cards += f'''<div class="card"><div class="av" style="{'background:#111' if _photos else ''}">{_img}</div><div class="cb">
<div class="cn">{ge} {u["name"]}, {u["age"]}</div>
<div class="cm">📍 {reg} {u.get("city","")}</div>
<div class="cm">📱 {un} | <code>{u["user_id"]}</code></div>
<div style="margin-top:8px">{sb}{fl}</div>
<div class="bio">{bio}{"..." if len(u.get("bio") or "") > 70 else ""}</div>
</div></div>'''
            tp = max(1,(total+pp-1)//pp)
            pag = "".join([f'<a href="?page={i}&status={sf}&search={s}" class="{"cur" if i==pg else ""}">{i}</a>' for i in range(1,min(tp+1,11))])
            return nav("users") + f"""
<form method="GET" class="fi">
<input type="text" name="search" placeholder="🔍 שם או מזהה..." value="{s}">
<a href="/users" class="fa {"active" if not sf else ""}">הכל</a>
<a href="/users?status=approved" class="fa {"active" if sf=="approved" else ""}">✅ מאושרים</a>
<a href="/users?status=pending" class="fa {"active" if sf=="pending" else ""}">⏳ ממתינים</a>
<button type="submit" class="fb">חפש</button>
</form>
<p style="color:rgba(255,255,255,0.3);font-size:.85rem;margin-bottom:16px">נמצאו {total} משתמשים</p>
<div class="grid">{cards or '<p style="color:rgba(255,255,255,0.3)">אין משתמשים</p>'}</div>
<div class="pag">{pag}</div></div></body></html>"""

        @web.route("/pending")
        @lr
        def wpending():
            c = _conn()
            ul = c.execute("SELECT * FROM users WHERE status='pending' ORDER BY created_at DESC").fetchall()
            c.close()
            cards = ""
            for u in ul:
                ge = "👩" if u["gender"]=="female" else "👨"
                reg = REGIONS.get(u.get("region",""),"")
                un = f"@{u['username']}" if u.get("username") else "אין"
                _photos = _conn().execute("SELECT file_id FROM user_photos WHERE user_id=? ORDER BY position LIMIT 1",(u["user_id"],)).fetchone()
                _img = f'<img src="/photo/{_photos["file_id"]}" style="width:100%;height:100%;object-fit:cover">' if _photos else ge
                cards += f'''<div class="card"><div class="av" style="{'background:#111' if _photos else ''}">{_img}</div><div class="cb">
<div class="cn">{ge} {u["name"]}, {u["age"]}</div>
<div class="cm">📍 {reg} {u.get("city","")}</div>
<div class="cm">📱 {un} | <code>{u["user_id"]}</code></div>
<span class="badge bo">⏳ ממתין</span>
<div class="bio">{(u.get("bio") or "")[:70]}</div>
<div style="margin-top:10px;color:rgba(255,255,255,0.3);font-size:.75rem">לאישור/דחייה - השתמש בטלגרם</div>
</div></div>'''
            return nav("pending") + f"""
<p style="font-size:1.3rem;font-weight:700;margin-bottom:20px">⏳ ממתינים ({len(ul)})</p>
<div class="grid">{cards or '<p style="color:rgba(255,255,255,0.3)">אין ממתינים</p>'}</div>
</div></body></html>"""

        @web.route("/reports")
        @lr
        def wreports():
            c = _conn()
            try:
                reps = c.execute("""SELECT r.*,u1.name as rn,u2.name as dn,u2.age as da
                    FROM reports r LEFT JOIN users u1 ON r.reporter_id=u1.user_id
                    LEFT JOIN users u2 ON r.reported_id=u2.user_id
                    WHERE r.status='pending' ORDER BY r.created_at DESC""").fetchall()
            except: reps = []
            c.close()
            rows = "".join([f'''<tr><td>{r.get("rn","?")}</td>
<td>{r.get("dn","?")}, {r.get("da","?")} <code>{r["reported_id"]}</code></td>
<td>{r.get("reason","")}</td>
<td style="color:rgba(255,255,255,0.3)">{str(r.get("created_at",""))[:10]}</td></tr>''' for r in reps])
            return nav("reports") + f"""
<p style="font-size:1.3rem;font-weight:700;margin-bottom:20px">🚨 דיווחים ({len(reps)})</p>
{"<table><tr><th>מדווח</th><th>מדוּוח</th><th>סיבה</th><th>תאריך</th></tr>"+rows+"</table>" if reps else '<p style="color:rgba(255,255,255,0.3)">אין דיווחים</p>'}
<p style="color:rgba(255,255,255,0.3);font-size:.8rem;margin-top:20px">לטיפול - השתמש בפאנל הטלגרם</p>
</div></body></html>"""

        @web.route("/messages")
        @lr
        def wmessages():
            c = _conn()
            try:
                msgs = c.execute("""SELECT m.*,u.name,u.gender FROM user_messages m
                    LEFT JOIN users u ON m.from_user_id=u.user_id
                    WHERE m.admin_closed=0 ORDER BY m.created_at DESC LIMIT 50""").fetchall()
            except: msgs = []
            c.close()
            cards = ""
            for m in msgs:
                ge = "👩" if m.get("gender")=="female" else "👨"
                nm = m.get("name") or m["from_user_id"]
                unr = not m.get("is_read")
                cards += f'''<div class="mc" style="{"border-color:rgba(233,30,140,0.4)" if unr else ""}">
<div class="mh">
<span style="font-weight:700">{ge} {nm} <code>{m["from_user_id"]}</code> {"<span class='badge bp'>חדש</span>" if unr else ""}</span>
<span style="color:rgba(255,255,255,0.3);font-size:.8rem">{str(m.get("created_at",""))[:16]}</span>
</div>
<div class="mt">{m.get("message_text","")}</div>
</div>'''
            return nav("messages") + f"""
<p style="font-size:1.3rem;font-weight:700;margin-bottom:20px">💬 הודעות ({len(msgs)})</p>
{cards or '<p style="color:rgba(255,255,255,0.3)">אין הודעות</p>'}
<p style="color:rgba(255,255,255,0.3);font-size:.8rem;margin-top:20px">למענה - השתמש בפאנל הטלגרם</p>
</div></body></html>"""

        web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error(f"Web admin failed to start: {e}")


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    registration_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [CallbackQueryHandler(get_gender, pattern="^gender_")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            REGION: [CallbackQueryHandler(get_region, pattern="^region_")],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
            PHOTOS: [
                MessageHandler(filters.PHOTO, get_photos),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_photos),
                CommandHandler("done", get_photos)
            ],
            ID_CARD: [MessageHandler(filters.PHOTO | filters.Document.ALL, get_id_card)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(registration_conv)
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("browse", show_next_profile))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CommandHandler("bug", bug_command))
    app.add_handler(CommandHandler("delete", delete_command))

    app.add_handler(CallbackQueryHandler(handle_menu_callbacks, pattern="^(menu_|settings_)"))
    app.add_handler(CallbackQueryHandler(handle_delete_confirm, pattern="^(confirm|cancel)_delete$"))
    app.add_handler(CallbackQueryHandler(handle_like_dislike, pattern="^(like|dislike|like_msg)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_consent, pattern="^chat_(consent|decline)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_callbacks, pattern="^(end_chat|share_details)_"))
    app.add_handler(CallbackQueryHandler(handle_region_filter, pattern="^filter_region_"))
    app.add_handler(CallbackQueryHandler(handle_admin_callback,
        pattern="^(approve|reject|block|unblock|suspend|unsuspend|admin_|delete_id|view_id|appeal_|broadcast|gift|revoke|report_|bug_|msg_|noop)"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    async def error_handler(update, context):
        import traceback
        err = traceback.format_exc()
        logger.error(f"Exception: {context.error}\n{err}")
        admin_id = int(os.environ.get("ADMIN_ID", "0"))
        if admin_id:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🚨 שגיאה בבוט:\n`{str(context.error)[:500]}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    app.add_error_handler(error_handler)
    # Start web admin in background thread - safe, won't affect bot
    web_thread = threading.Thread(target=_run_web_admin, daemon=True)
    web_thread.start()
    logger.info("FlirtZone Bot + Web Admin started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
