from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    get_pending_users, approve_user, reject_user,
    block_user, unblock_user, suspend_user, unsuspend_user,
    delete_id_card, get_user, get_stats, add_appeal,
    get_pending_appeals, resolve_appeal,
    set_premium, revoke_premium, add_bonus_likes, add_bonus_likes_all,
    get_all_approved_users, get_pending_reports, resolve_report,
    get_open_bug_reports, get_user_photos, get_all_users_detailed,
    get_premium_interested_users, soft_delete_user, set_premium_all, search_users,
    get_user_messages, mark_messages_read, close_user_conversation, get_unread_messages_count,
    set_admin_chat, get_admin_chat, get_incomplete_registrations,
    RULES_TEXT, REGIONS
)
import os

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
WAITING_BROADCAST = {}
WAITING_GIFT_AMOUNT = {}
WAITING_REJECT_REASON = {}
WAITING_MESSAGE_USER = {}
WAITING_SEARCH = set()


def is_admin(user_id):
    return user_id == ADMIN_ID


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ אין לך הרשאה.")
        return
    stats = get_stats()
    keyboard = [
        [InlineKeyboardButton(f"📋 ממתינים ({stats['pending']})", callback_data="admin_pending"),
         InlineKeyboardButton(f"👥 כל המשתמשים ({stats['total']})", callback_data="admin_users_0")],
        [InlineKeyboardButton("👀 עזבו באמצע", callback_data="admin_incomplete"),
         InlineKeyboardButton("🔍 חפש משתמש", callback_data="admin_search"),
         InlineKeyboardButton("💬 הודעות משתמשים", callback_data="admin_messages")],
        [InlineKeyboardButton(f"🚨 דיווחים ({stats['reports']})", callback_data="admin_reports"),
         InlineKeyboardButton(f"🐛 תקלות ({stats['bugs']})", callback_data="admin_bugs")],
        [InlineKeyboardButton(f"💰 עניין בפרמיום ({stats.get('premium_interest',0)})", callback_data="admin_premium_interest"),
         InlineKeyboardButton("⚠️ ערעורים", callback_data="appeal_list_appeals")],
        [InlineKeyboardButton("📢 שלח לכולם", callback_data="broadcast_all"),
         InlineKeyboardButton("💬 שוחח עם משתמש", callback_data="msg_user")],
        [InlineKeyboardButton("🎁 לייקים לכולם", callback_data="gift_likes_all"),
         InlineKeyboardButton("🎁 לייקים למשתמש", callback_data="gift_likes_user")],
        [InlineKeyboardButton("⭐ פרמיום לכולם", callback_data="gift_premium_all"),
         InlineKeyboardButton("⭐ תן פרמיום", callback_data="gift_premium_user")],
        [InlineKeyboardButton("❌ הסר פרמיום", callback_data="revoke_premium_user")],
        [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="appeal_stats")]
    ]
    await update.message.reply_text(
        f"🛡️ *פאנל ניהול Vibey*\n\n"
        f"👥 סה\"כ: {stats['total']} | ⏳ ממתינים: {stats['pending']}\n"
        f"✅ מאושרים: {stats['approved']} | 🚫 חסומים: {stats['blocked']}\n"
        f"⏸ מושעים: {stats['suspended']} | ⭐ פרמיום: {stats['premium']}\n"
        f"💕 מאצ'ים: {stats['matches']} | 🗑 נמחקו: {stats['deleted']}\n"
        f"🚨 דיווחים: {stats['reports']} | 💰 עניין בפרמיום: {stats.get('premium_interest',0)}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def _user_card_text(user, report_count=0, likes_given=0, likes_received=0):
    gender_text = "👩 אישה" if user["gender"] == "female" else "👨 גבר"
    region_name = REGIONS.get(user["region"], user["region"] or "")
    status_emoji = {"approved": "✅", "pending": "⏳", "rejected": "❌", "deleted": "🗑"}.get(user["status"], "❓")
    flags = []
    if user["is_blocked"]: flags.append("🚫 חסום")
    if user.get("is_suspended"): flags.append("⏸ מושעה")
    if user["is_premium"]: flags.append("⭐ פרמיום")
    flags_str = " | ".join(flags) if flags else "רגיל"
    username = f"@{user['username']}" if user.get('username') else "אין"
    return (
        f"{status_emoji} *{user['name']}*, גיל {user['age']}\n"
        f"{gender_text} | 📍 {region_name} - {user['city']}\n"
        f"🏷 {flags_str}\n"
        f"📝 {user['bio']}\n"
        f"📱 טלגרם: {username}\n"
        f"❤️ נתן: {likes_given} | קיבל: {likes_received} | 🚨 דיווחים: {report_count}\n"
        f"🆔 `{user['user_id']}`\n"
        f"📅 {str(user['created_at'])[:10] if user['created_at'] else '?'}"
    )


def _user_keyboard(uid, user):
    rows = []
    if user["status"] == "pending":
        rows.append([
            InlineKeyboardButton("✅ אשר", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("❌ דחה", callback_data=f"reject_{uid}")
        ])
    row2 = []
    if user["is_blocked"]:
        row2.append(InlineKeyboardButton("🔓 שחרר חסימה", callback_data=f"unblock_{uid}"))
    else:
        row2.append(InlineKeyboardButton("🚫 חסום", callback_data=f"block_{uid}"))
    if user.get("is_suspended"):
        row2.append(InlineKeyboardButton("▶️ שחרר השעיה", callback_data=f"unsuspend_{uid}"))
    else:
        row2.append(InlineKeyboardButton("⏸ השעה", callback_data=f"suspend_{uid}"))
    rows.append(row2)
    rows.append([
        InlineKeyboardButton("💬 שלח הודעה", callback_data=f"msg_to_{uid}"),
        InlineKeyboardButton("🗑 מחק", callback_data=f"admin_delete_{uid}")
    ])
    rows.append([InlineKeyboardButton("🪪 צפה בתז", callback_data=f"view_id_{uid}")])
    return rows


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    data = query.data

    if data == "noop":
        return

    # ── Messages ──
    if data == "admin_messages":
        msgs = get_user_messages()
        if not msgs:
            await context.bot.send_message(chat_id=ADMIN_ID, text="📭 אין הודעות מהמשתמשים.")
            return
        unread = [m for m in msgs if not m["is_read"]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💬 *הודעות מהמשתמשים*\n\n{len(msgs)} הודעות | {len(unread)} לא נקראו",
            parse_mode="Markdown"
        )
        for m in msgs[:10]:
            ge = "👩" if m.get("gender") == "female" else "👨"
            name = m.get("name") or m["from_user_id"]
            kb = [[
                InlineKeyboardButton("👁 פרופיל", callback_data=f"admin_view_user_{m['from_user_id']}"),
                InlineKeyboardButton("💬 שוחח איתו", callback_data=f"admin_start_chat_{m['from_user_id']}"),
            ], [
                InlineKeyboardButton("📨 שלח הודעה", callback_data=f"msg_to_{m['from_user_id']}"),
                InlineKeyboardButton("🔚 סגור", callback_data=f"msg_close_{m['from_user_id']}")
            ]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"{ge} *{name}* | 🆔 `{m['from_user_id']}`\n\n{m['message_text']}\n\n_{str(m['created_at'])[:16]}_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            mark_messages_read(m["from_user_id"])
        return

    if data.startswith("admin_start_chat_"):
        uid = int(data.replace("admin_start_chat_", ""))
        user = get_user(uid)
        name = user["name"] if user else uid
        set_admin_chat(uid)
        kb = [[InlineKeyboardButton("🔚 סיים שיחה", callback_data="admin_end_chat")]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💬 *התחלת שיחה עם {name}*\n\nכל הודעה שתשלח כעת תועבר אליו/ה ישירות.\nלסיום לחץ 'סיים שיחה'.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await context.bot.send_message(
            chat_id=uid,
            text="💬 *הנהלת Vibey פתחה איתך שיחה*\n\nתוכל/י לשלוח הודעה ולקבל תשובה.",
            parse_mode="Markdown"
        )
        return

    if data == "admin_end_chat":
        uid = get_admin_chat()
        set_admin_chat(None)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await context.bot.send_message(chat_id=ADMIN_ID, text="✅ השיחה הסתיימה.")
        if uid:
            user = get_user(uid)
            name = user["name"] if user else uid
            await context.bot.send_message(
                chat_id=uid,
                text="✅ השיחה עם ההנהלה הסתיימה.",
                parse_mode="Markdown"
            )
        return

    if data.startswith("admin_view_user_"):
        uid = int(data.replace("admin_view_user_", ""))
        user = get_user(uid)
        if not user:
            await context.bot.send_message(chat_id=ADMIN_ID, text="❌ משתמש לא נמצא")
            return
        text = _user_card_text(user, 0, 0, 0)
        kb = _user_keyboard(uid, user)
        photos = get_user_photos(uid)
        if photos:
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photos[0],
                caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text=text,
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("msg_close_"):
        uid = int(data.replace("msg_close_", ""))
        close_user_conversation(uid)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await context.bot.send_message(chat_id=ADMIN_ID, text="✅ השיחה נסגרה.")
        return

    # ── Incomplete registrations ──
    if data == "admin_incomplete":
        incomplete = get_incomplete_registrations()
        if not incomplete:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין משתמשים שעזבו באמצע.")
            return
        text = f"👀 *{len(incomplete)} עזבו באמצע ההרשמה:*\n\n"
        steps_he = {"start":"התחיל","name":"שם","age":"גיל","region":"אזור","city":"עיר","bio":"ביו","photos":"תמונות","id_card":"תעודת זהות"}
        for r in incomplete[:20]:
            un = f"@{r['username']}" if r.get("username") else "אין שם משתמש"
            step = steps_he.get(r.get("last_step",""), r.get("last_step",""))
            text += f"• {un} | עצר ב: {step} | 🆔 `{r['user_id']}`\n"
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="Markdown")
        return

    # ── Search ──
    if data == "admin_search":
        WAITING_SEARCH.add(ADMIN_ID)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="🔍 *חיפוש משתמש*\n\nכתוב שם (חלקי או מלא) או ID:",
            parse_mode="Markdown"
        )
        return

    # ── All users paginated ──
    if data.startswith("admin_users_"):
        page = int(data.replace("admin_users_", ""))
        users = get_all_users_detailed()
        page_size = 5
        total_pages = max(1, (len(users) + page_size - 1) // page_size)
        chunk = users[page * page_size:(page + 1) * page_size]
        if not chunk:
            await context.bot.send_message(chat_id=ADMIN_ID, text="❌ אין משתמשים.")
            return
        for u in chunk:
            text = _user_card_text(u, u["report_count"], u["likes_given"], u["likes_received"])
            kb = _user_keyboard(u["user_id"], u)
            photos = get_user_photos(u["user_id"])
            try:
                if photos:
                    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photos[0],
                                                  caption=text, parse_mode="Markdown",
                                                  reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await context.bot.send_message(chat_id=ADMIN_ID, text=text,
                                                   parse_mode="Markdown",
                                                   reply_markup=InlineKeyboardMarkup(kb))
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error sending user card: {e}")
                await context.bot.send_message(chat_id=ADMIN_ID,
                    text=f"⚠️ שגיאה בטעינת כרטיס משתמש {u['user_id']}: {e}")
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("◀️", callback_data=f"admin_users_{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page + 1 < total_pages: nav.append(InlineKeyboardButton("▶️", callback_data=f"admin_users_{page+1}"))
        await context.bot.send_message(chat_id=ADMIN_ID,
                                       text=f"עמוד {page+1}/{total_pages} | {len(users)} משתמשים",
                                       reply_markup=InlineKeyboardMarkup([nav]))
        return

    # ── Premium interest ──
    if data == "admin_premium_interest":
        interested = get_premium_interested_users()
        if not interested:
            await context.bot.send_message(chat_id=ADMIN_ID, text="📊 עדיין אין התעניינות בפרמיום.")
            return
        text = f"💰 *{len(interested)} התעניינו בפרמיום:*\n\n"
        for r in interested:
            g = "👩" if r["gender"] == "female" else "👨"
            reg = REGIONS.get(r["region"], "") if r["region"] else ""
            text += f"{g} {r['name'] or '?'}, {r['age'] or '?'} | {reg} | 🆔 `{r['user_id']}`\n"
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="Markdown")
        return

    # ── Approve ──
    if data.startswith("approve_"):
        uid = int(data.replace("approve_", ""))
        approve_user(uid)
        user = get_user(uid)
        try:
            if query.message.caption:
                await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n✅ אושר", parse_mode="Markdown")
            else:
                await query.edit_message_text((query.message.text or "") + "\n\n✅ אושר", parse_mode="Markdown")
        except Exception:
            pass
        bonus_msg = f"\n\n🎁 יש לך {user['bonus_likes']} לייקים בונוס!" if user and user["bonus_likes"] > 0 else ""
        await context.bot.send_message(
            chat_id=uid,
            text="✅ *פרופילך אושר! Your profile is approved!*\n\n💋 ברוך הבא ל-Vibey!\n\n" + RULES_TEXT + bonus_msg,
            parse_mode="Markdown"
        )
        await _send_main_menu(context, uid)
        return

    # ── Reject ──
    if data.startswith("reject_") and "confirm" not in data:
        uid = int(data.replace("reject_", ""))
        WAITING_REJECT_REASON[ADMIN_ID] = uid
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✍️ סיבת דחייה (או 'דלג'):")
        return

    # ── Block ──
    if data.startswith("block_") and len(data.split("_")) == 2:
        uid = int(data.split("_")[1])
        block_user(uid)
        try:
            if query.message.caption:
                await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n🚫 חסום", parse_mode="Markdown")
        except Exception:
            pass
        await context.bot.send_message(chat_id=uid,
            text="⛔ *חשבונך חסום | Blocked*\n\nשלח הודעה אם חושב שזו טעות.",
            parse_mode="Markdown")
        return

    # ── Unblock ──
    if data.startswith("unblock_"):
        uid = int(data.replace("unblock_", ""))
        unblock_user(uid)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ משתמש {uid} שוחרר.")
        await context.bot.send_message(chat_id=uid, text="✅ *החסימה הוסרה!*\n\nתוכל/י להמשיך.", parse_mode="Markdown")
        await _send_main_menu(context, uid)
        return

    # ── Suspend ──
    if data.startswith("suspend_"):
        uid = int(data.replace("suspend_", ""))
        suspend_user(uid)
        try:
            if query.message.caption:
                await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n⏸ מושעה", parse_mode="Markdown")
        except Exception:
            pass
        await context.bot.send_message(chat_id=uid,
            text="⏸ *חשבונך הושעה | Suspended*\n\nעקב דיווח. ההנהלה תיצור קשר.",
            parse_mode="Markdown")
        return

    # ── Unsuspend ──
    if data.startswith("unsuspend_"):
        uid = int(data.replace("unsuspend_", ""))
        unsuspend_user(uid)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ משתמש {uid} שוחרר מהשעיה.")
        await context.bot.send_message(chat_id=uid, text="✅ *ההשעיה הוסרה!*", parse_mode="Markdown")
        await _send_main_menu(context, uid)
        return

    # ── Admin delete ──
    if data.startswith("admin_delete_") and "confirm" not in data:
        uid = int(data.replace("admin_delete_", ""))
        keyboard = [[
            InlineKeyboardButton("✅ כן, מחק", callback_data=f"admin_delete_confirm_{uid}"),
            InlineKeyboardButton("❌ ביטול", callback_data="noop")
        ]]
        await context.bot.send_message(chat_id=ADMIN_ID,
            text=f"⚠️ למחוק משתמש `{uid}`?", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("admin_delete_confirm_"):
        uid = int(data.replace("admin_delete_confirm_", ""))
        soft_delete_user(uid)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ משתמש {uid} נמחק.")
        try:
            await context.bot.send_message(chat_id=uid,
                text="ℹ️ חשבונך הוסר מהפלטפורמה על ידי ההנהלה.", parse_mode="Markdown")
        except Exception:
            pass
        return

    # ── View / Delete ID ──
    if data.startswith("view_id_"):
        uid = int(data.replace("view_id_", ""))
        user = get_user(uid)
        if user and user["id_card_file_id"]:
            kb = [[InlineKeyboardButton("🗑 מחק תז", callback_data=f"delete_id_{uid}")]]
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=user["id_card_file_id"],
                caption=f"🪪 תז של {user['name']} | `{uid}`", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb))
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text="❌ תז לא נמצא.")
        return

    if data.startswith("delete_id_"):
        uid = int(data.replace("delete_id_", ""))
        delete_id_card(uid)
        await query.edit_message_caption(caption="🗑 תז נמחק.")
        return

    # ── Pending ──
    if data == "admin_pending":
        pending = get_pending_users()
        if not pending:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין ממתינים!")
            return
        for u in pending[:5]:
            kb = _user_keyboard(u["user_id"], u)
            region_name = REGIONS.get(u["region"], u["region"] or "")
            photos = get_user_photos(u["user_id"])
            caption = (f"📋 *ממתין*\n\n👤 {u['name']}, {u['age']}\n"
                       f"📍 {region_name} - {u['city']}\n📝 {u['bio']}\n🆔 `{u['user_id']}`")
            if photos:
                await context.bot.send_photo(chat_id=ADMIN_ID, photo=photos[0], caption=caption,
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
            else:
                await context.bot.send_message(chat_id=ADMIN_ID, text=caption,
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ── Reports ──
    if data == "admin_reports":
        reports = get_pending_reports()
        if not reports:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין דיווחים!")
            return
        for r in reports[:5]:
            kb = [[
                InlineKeyboardButton("⏸ השעה", callback_data=f"suspend_{r['reported_id']}"),
                InlineKeyboardButton("🚫 חסום", callback_data=f"block_{r['reported_id']}")
            ], [
                InlineKeyboardButton("💬 מדווח", callback_data=f"msg_to_{r['reporter_id']}"),
                InlineKeyboardButton("💬 מדוּוח", callback_data=f"msg_to_{r['reported_id']}")
            ], [InlineKeyboardButton("✅ סגור", callback_data=f"report_close_{r['id']}")]]
            text = (f"🚨 *דיווח*\n\n👤 מדווח: {r['reporter_name'] or r['reporter_id']}\n"
                    f"👤 מדוּוח: {r['reported_name'] or r['reported_id']}, {r['reported_age'] or '?'}\n"
                    f"📝 {r['reason']}\n🆔 `{r['reported_id']}`")
            if r["evidence_file_id"]:
                try:
                    await context.bot.send_photo(chat_id=ADMIN_ID, photo=r["evidence_file_id"],
                        caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
                    continue
                except Exception:
                    pass
            await context.bot.send_message(chat_id=ADMIN_ID, text=text,
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("report_close_"):
        rid = int(data.replace("report_close_", ""))
        if rid > 0:
            resolve_report(rid, "closed")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    # ── Bugs ──
    if data == "admin_bugs":
        bugs = get_open_bug_reports()
        if not bugs:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין תקלות!")
            return
        for b in bugs[:5]:
            kb = [[InlineKeyboardButton("✅ טופל", callback_data=f"bug_close_{b['id']}"),
                   InlineKeyboardButton("💬 השב", callback_data=f"msg_to_{b['user_id']}")]]
            await context.bot.send_message(chat_id=ADMIN_ID,
                text=f"🐛 *תקלה*\n\n👤 {b['name'] or b['user_id']} | 🆔 `{b['user_id']}`\n\n📝 {b['description']}",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("bug_close_"):
        bid = int(data.replace("bug_close_", ""))
        from database.db import get_conn
        conn = get_conn()
        conn.execute("UPDATE bug_reports SET status='closed' WHERE id=?", (bid,))
        conn.commit()
        conn.close()
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    # ── Appeals ──
    if data == "appeal_list_appeals":
        appeals = get_pending_appeals()
        if not appeals:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין ערעורים!")
            return
        for ap in appeals:
            kb = [[InlineKeyboardButton("✅ שחרר", callback_data=f"unblock_{ap['user_id']}"),
                   InlineKeyboardButton("❌ דחה", callback_data=f"appeal_reject_{ap['id']}")]]
            await context.bot.send_message(chat_id=ADMIN_ID,
                text=f"⚠️ *ערעור*\n\n👤 {ap['name']}, {ap['age']}\n🆔 `{ap['user_id']}`\n\n💬 {ap['message']}",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("appeal_reject_"):
        aid = int(data.replace("appeal_reject_", ""))
        resolve_appeal(aid, "rejected")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    # ── Stats ──
    if data == "appeal_stats":
        stats = get_stats()
        await context.bot.send_message(chat_id=ADMIN_ID,
            text=(f"📊 *סטטיסטיקות*\n\n"
                  f"👥 סה\"כ: {stats['total']}\n✅ מאושרים: {stats['approved']}\n"
                  f"⏳ ממתינים: {stats['pending']}\n🚫 חסומים: {stats['blocked']}\n"
                  f"⏸ מושעים: {stats['suspended']}\n⭐ פרמיום: {stats['premium']}\n"
                  f"💕 מאצ'ים: {stats['matches']}\n🗑 נמחקו: {stats['deleted']}\n"
                  f"💰 עניין בפרמיום: {stats.get('premium_interest',0)}"),
            parse_mode="Markdown")
        return

    # ── Broadcast ──
    if data == "broadcast_all":
        WAITING_BROADCAST[ADMIN_ID] = "all"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב הודעה לכולם:")
        return

    # ── Msg user ──
    if data == "msg_user":
        WAITING_MESSAGE_USER[ADMIN_ID] = "ask_id"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-ID:")
        return

    if data.startswith("msg_to_"):
        uid = int(data.replace("msg_to_", ""))
        WAITING_MESSAGE_USER[ADMIN_ID] = f"send_{uid}"
        user = get_user(uid)
        name = user["name"] if user else uid
        await context.bot.send_message(chat_id=ADMIN_ID,
            text=f"✍️ הודעה ל-*{name}* (`{uid}`):", parse_mode="Markdown")
        return

    # ── Gifts ──
    if data == "gift_likes_all":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "all_likes"
        await context.bot.send_message(chat_id=ADMIN_ID, text="🎁 כמה לייקים לכולם?")
        return
    if data == "gift_likes_user":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_user_likes"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ ID של המשתמש:")
        return
    if data == "gift_premium_all":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_premium_all_days"
        await context.bot.send_message(chat_id=ADMIN_ID, text="⭐ כמה ימים פרמיום לכולם? (ברירת מחדל: 30)")
        return

    if data == "gift_premium_user":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_user_premium"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ ID של המשתמש:")
        return
    if data == "revoke_premium_user":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_revoke_premium"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ ID של המשתמש:")
        return


async def _send_main_menu(context, chat_id):
    keyboard = [
        [InlineKeyboardButton("💋 גלוש בפרופילים | Browse", callback_data="menu_browse")],
        [InlineKeyboardButton("⭐ פרמיום | Premium", callback_data="menu_premium"),
         InlineKeyboardButton("👤 הסטטוס שלי | Status", callback_data="menu_status")],
        [InlineKeyboardButton("🚨 דווח | Report", callback_data="menu_report"),
         InlineKeyboardButton("🐛 תקלה | Bug", callback_data="menu_bug")],
        [InlineKeyboardButton("🗑 מחק חשבון | Delete", callback_data="menu_delete")]
    ]
    await context.bot.send_message(chat_id=chat_id,
        text="💋 *Vibey - תפריט ראשי | Main Menu*\n\nבחר/י פעולה:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_appeal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text if update.message and update.message.text else ""

    if is_admin(user_id):
        # Search
        if user_id in WAITING_SEARCH:
            WAITING_SEARCH.discard(user_id)
            results = search_users(message_text.strip())
            if not results:
                await update.message.reply_text("❌ לא נמצאו משתמשים.")
                return
            await update.message.reply_text(f"🔍 נמצאו {len(results)} משתמשים:")
            for u in results[:10]:
                text = _user_card_text(u, u["report_count"], u["likes_given"], u["likes_received"])
                kb = _user_keyboard(u["user_id"], u)
                photos = get_user_photos(u["user_id"])
                try:
                    if photos:
                        await context.bot.send_photo(chat_id=ADMIN_ID, photo=photos[0],
                            caption=text, parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(kb))
                    else:
                        await context.bot.send_message(chat_id=ADMIN_ID, text=text,
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(kb))
                except Exception as e:
                    await context.bot.send_message(chat_id=ADMIN_ID,
                        text=f"⚠️ שגיאה: {e}")
            return

        if user_id in WAITING_REJECT_REASON:
            target_id = WAITING_REJECT_REASON.pop(user_id)
            reject_user(target_id)
            reason = "" if message_text.strip() == "דלג" else f"\n\nסיבה: {message_text}"
            await context.bot.send_message(chat_id=target_id,
                text=f"❌ *בקשתך נדחתה*{reason}\n\nניתן לנסות שוב: /start", parse_mode="Markdown")
            await update.message.reply_text("✅ נדחה.")
            return

        if user_id in WAITING_MESSAGE_USER:
            state = WAITING_MESSAGE_USER.get(user_id)
            if state == "ask_id":
                WAITING_MESSAGE_USER[user_id] = f"send_{message_text.strip()}"
                await update.message.reply_text("✍️ כתוב את ההודעה:")
                return
            elif state and state.startswith("send_"):
                target_id = int(state.replace("send_", ""))
                WAITING_MESSAGE_USER.pop(user_id)
                try:
                    await context.bot.send_message(chat_id=target_id,
                        text=f"📨 *הודעה מהנהלת Vibey:*\n\n{message_text}", parse_mode="Markdown")
                    await update.message.reply_text("✅ נשלח!")
                except Exception:
                    await update.message.reply_text("❌ לא ניתן לשלוח.")
                return

        if user_id in WAITING_BROADCAST:
            state = WAITING_BROADCAST.get(user_id)
            if state == "all":
                WAITING_BROADCAST.pop(user_id)
                users = get_all_approved_users()
                sent, failed = 0, 0
                for u in users:
                    try:
                        await context.bot.send_message(chat_id=u["user_id"], text=message_text)
                        sent += 1
                    except Exception:
                        failed += 1
                await update.message.reply_text(f"✅ נשלח ל-{sent}. נכשל: {failed}")
                return

        if user_id in WAITING_GIFT_AMOUNT:
            state = WAITING_GIFT_AMOUNT.get(user_id)
            if state == "all_likes":
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    amount = int(message_text.strip())
                    affected = add_bonus_likes_all(amount)
                    users = get_all_approved_users()
                    for u in users:
                        try:
                            await context.bot.send_message(chat_id=u["user_id"],
                                text=f"🎁 *מתנה! קיבלת {amount} לייקים!* 🎉", parse_mode="Markdown")
                        except Exception:
                            pass
                    await update.message.reply_text(f"✅ {amount} לייקים ל-{affected} משתמשים!")
                except ValueError:
                    await update.message.reply_text("❌ מספר לא תקין")
                return
            elif state == "ask_user_likes":
                WAITING_GIFT_AMOUNT[user_id] = f"user_likes_{message_text.strip()}"
                await update.message.reply_text("✍️ כמה לייקים?")
                return
            elif state and state.startswith("user_likes_"):
                target_id = int(state.replace("user_likes_", ""))
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    amount = int(message_text.strip())
                    add_bonus_likes(target_id, amount)
                    await context.bot.send_message(chat_id=target_id,
                        text=f"🎁 *קיבלת {amount} לייקים בונוס!* 🎉", parse_mode="Markdown")
                    await update.message.reply_text(f"✅ ניתנו {amount} לייקים!")
                except Exception as e:
                    await update.message.reply_text(f"❌ שגיאה: {e}")
                return
            elif state == "ask_premium_all_days":
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    days = int(message_text.strip()) if message_text.strip().isdigit() else 30
                    affected, until = set_premium_all(days)
                    users = get_all_approved_users()
                    for u in users:
                        try:
                            await context.bot.send_message(
                                chat_id=u["user_id"],
                                text=f"⭐ *מתנה מהנהלת Vibey!*\n\nקיבלת פרמיום חינם ל-{days} ימים! 🎉\n\n✅ לייקים ללא הגבלה\n✅ הפרופיל מופיע ראשון\n\n⏰ עד: {until.strftime('%d/%m/%Y')}",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                    await update.message.reply_text(f"✅ פרמיום ל-{days} ימים ניתן ל-{affected} משתמשים!")
                except Exception as e:
                    await update.message.reply_text(f"❌ שגיאה: {e}")
                return

            elif state == "ask_user_premium":
                WAITING_GIFT_AMOUNT[user_id] = f"user_premium_{message_text.strip()}"
                await update.message.reply_text("✍️ כמה ימים? (ברירת מחדל: 30)")
                return
            elif state and state.startswith("user_premium_"):
                target_id = int(state.replace("user_premium_", ""))
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    days = int(message_text.strip()) if message_text.strip().isdigit() else 30
                    until = set_premium(target_id, days)
                    await context.bot.send_message(chat_id=target_id,
                        text=f"⭐ *קיבלת פרמיום!*\n\n✅ לייקים ללא הגבלה\n✅ הפרופיל מופיע ראשון\n\n⏰ עד: {until.strftime('%d/%m/%Y')}",
                        parse_mode="Markdown")
                    await update.message.reply_text(f"✅ פרמיום ניתן ל-{days} ימים!")
                except Exception as e:
                    await update.message.reply_text(f"❌ שגיאה: {e}")
                return
            elif state == "ask_revoke_premium":
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    target_id = int(message_text.strip())
                    revoke_premium(target_id)
                    await update.message.reply_text("✅ פרמיום הוסר.")
                except Exception:
                    await update.message.reply_text("❌ ID לא תקין")
                return

    # Blocked user appeal
    user = get_user(user_id)
    if user and user["is_blocked"]:
        add_appeal(user_id, message_text)
        await update.message.reply_text("📨 הערעור התקבל.\n_Your appeal has been received._", parse_mode="Markdown")
        if ADMIN_ID:
            kb = [[InlineKeyboardButton("✅ שחרר", callback_data=f"unblock_{user_id}"),
                   InlineKeyboardButton("❌ דחה", callback_data=f"block_{user_id}")]]
            await context.bot.send_message(chat_id=ADMIN_ID,
                text=f"⚠️ *ערעור*\n\n👤 {user['name']}\n🆔 `{user_id}`\n\n💬 {message_text}",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
