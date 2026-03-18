import sqlite3
import os
from datetime import datetime, date, timedelta

DB_PATH = os.environ.get("DB_PATH", "dating_bot.db")

# Create directory if it doesn't exist
_db_dir = os.path.dirname(DB_PATH)
if _db_dir and not os.path.exists(_db_dir):
    os.makedirs(_db_dir, exist_ok=True)
FIRST_USERS_BONUS = 20
FIRST_USERS_COUNT = 20
FREE_DAILY_LIKES = 10
PREMIUM_PRICE_STARS = 1000

REGIONS = {
    "north": "צפון 🌿",
    "center": "מרכז 🏙",
    "south": "דרום 🌵"
}

RULES_TEXT = (
    "📋 *כללי FlirtZone*\n\n"
    "🇮🇱\n"
    "✅ שמור/י על שיח מכבד ונעים\n"
    "✅ תמונות אמיתיות ועדכניות בלבד\n"
    "❌ אסור להטריד, לאיים או לפגוע\n"
    "❌ אסור לשלוח תוכן פוגעני או בלתי הולם\n"
    "❌ אסור להתחזות לאדם אחר\n"
    "⚠️ הפרת הכללים תגרור השעיה או חסימה.\n\n"
    "🇬🇧\n"
    "✅ Be respectful and kind\n"
    "✅ Real and recent photos only\n"
    "❌ No harassment, threats or harm\n"
    "❌ No offensive or inappropriate content\n"
    "❌ No impersonation\n"
    "⚠️ Violations may result in suspension or ban."
)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: {
        col[0]: row[idx] for idx, col in enumerate(cursor.description)
    } if cursor.description else row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            gender TEXT,
            name TEXT,
            age INTEGER,
            region TEXT,
            city TEXT,
            bio TEXT,
            status TEXT DEFAULT 'pending',
            is_blocked INTEGER DEFAULT 0,
            is_suspended INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            premium_until TIMESTAMP,
            bonus_likes INTEGER DEFAULT 0,
            likes_used_today INTEGER DEFAULT 0,
            likes_reset_date TEXT,
            filter_region TEXT,
            id_card_file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS deleted_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            gender TEXT,
            name TEXT,
            age INTEGER,
            region TEXT,
            city TEXT,
            had_reports INTEGER DEFAULT 0,
            had_blocks INTEGER DEFAULT 0,
            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_id TEXT,
            position INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER,
            reported_id INTEGER,
            reason TEXT,
            evidence_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bug_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            description TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            to_user_id INTEGER,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(from_user_id, to_user_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER,
            user2_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            viewer_id INTEGER,
            viewed_id INTEGER,
            UNIQUE(viewer_id, viewed_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS active_chats (
            user_id INTEGER PRIMARY KEY,
            partner_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_consents (
            user_id INTEGER,
            partner_id INTEGER,
            PRIMARY KEY (user_id, partner_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'he',
            show_age INTEGER DEFAULT 1,
            notifications INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS share_consents (
            user_id INTEGER,
            partner_id INTEGER,
            PRIMARY KEY (user_id, partner_id)
        )
    """)
    # Migration - add missing columns to existing DB
    migrations = [
        "ALTER TABLE users ADD COLUMN is_suspended INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN filter_region TEXT",
        "ALTER TABLE users ADD COLUMN bonus_likes INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN likes_used_today INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN likes_reset_date TEXT",
        "ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN premium_until TIMESTAMP",
    ]
    for sql in migrations:
        try:
            c.execute(sql)
        except Exception:
            pass  # Column already exists

    conn.commit()
    conn.close()


def add_user(user_id, username, gender, name, age, region, city, bio, id_card_file_id, photos):
    conn = get_conn()
    # Check if returning user
    deleted = conn.execute("SELECT * FROM deleted_users WHERE user_id = ?", (user_id,)).fetchone()
    count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    bonus = FIRST_USERS_BONUS if count < FIRST_USERS_COUNT else 0
    conn.execute("""
        INSERT OR REPLACE INTO users
        (user_id, username, gender, name, age, region, city, bio, id_card_file_id, status, bonus_likes, filter_region)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (user_id, username, gender, name, age, region, city, bio, id_card_file_id, bonus, region))
    conn.execute("DELETE FROM user_photos WHERE user_id = ?", (user_id,))
    for i, file_id in enumerate(photos):
        conn.execute("INSERT INTO user_photos (user_id, file_id, position) VALUES (?, ?, ?)",
                     (user_id, file_id, i))
    conn.commit()
    conn.close()
    return bonus, deleted


def get_user(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def get_deleted_user_history(user_id):
    conn = get_conn()
    result = conn.execute("SELECT * FROM deleted_users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return result


def get_user_photos(user_id):
    conn = get_conn()
    photos = conn.execute(
        "SELECT file_id FROM user_photos WHERE user_id = ? ORDER BY position", (user_id,)
    ).fetchall()
    conn.close()
    return [p["file_id"] for p in photos]


def delete_user_self(user_id):
    """User deletes themselves - save skeleton record, remove everything else."""
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return

    had_reports = conn.execute(
        "SELECT COUNT(*) as c FROM reports WHERE reported_id = ?", (user_id,)
    ).fetchone()["c"]
    had_blocks = 1 if user["is_blocked"] else 0

    # Save skeleton
    conn.execute("""
        INSERT OR REPLACE INTO deleted_users
        (user_id, username, gender, name, age, region, city, had_reports, had_blocks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, user["username"], user["gender"], user["name"],
          user["age"], user["region"], user["city"], had_reports, had_blocks))

    # Delete everything else
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM user_photos WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM likes WHERE from_user_id = ? OR to_user_id = ?", (user_id, user_id))
    conn.execute("DELETE FROM seen WHERE viewer_id = ? OR viewed_id = ?", (user_id, user_id))
    conn.execute("DELETE FROM active_chats WHERE user_id = ? OR partner_id = ?", (user_id, user_id))
    conn.commit()
    conn.close()


def soft_delete_user(user_id):
    """Admin deletes user - marks as deleted, stays in DB for history."""
    conn = get_conn()
    conn.execute("UPDATE users SET status = 'deleted' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_pending_users():
    conn = get_conn()
    users = conn.execute("SELECT * FROM users WHERE status = 'pending'").fetchall()
    conn.close()
    return users


def approve_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET status = 'approved' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def reject_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET status = 'rejected' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def block_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def unblock_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_blocked = 0, is_suspended = 0, status = 'approved' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def suspend_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_suspended = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def unsuspend_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_suspended = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def delete_id_card(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET id_card_file_id = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def add_report(reporter_id, reported_id, reason, evidence_file_id=None):
    conn = get_conn()
    conn.execute("""
        INSERT INTO reports (reporter_id, reported_id, reason, evidence_file_id)
        VALUES (?, ?, ?, ?)
    """, (reporter_id, reported_id, reason, evidence_file_id))
    conn.commit()
    conn.close()


def get_pending_reports():
    conn = get_conn()
    reports = conn.execute("""
        SELECT r.*, 
               u1.name as reporter_name,
               u2.name as reported_name, u2.age as reported_age,
               u2.gender as reported_gender
        FROM reports r
        LEFT JOIN users u1 ON r.reporter_id = u1.user_id
        LEFT JOIN users u2 ON r.reported_id = u2.user_id
        WHERE r.status = 'pending'
        ORDER BY r.created_at DESC
    """).fetchall()
    conn.close()
    return reports


def resolve_report(report_id, status):
    conn = get_conn()
    conn.execute("UPDATE reports SET status = ? WHERE id = ?", (status, report_id))
    conn.commit()
    conn.close()


def add_bug_report(user_id, description):
    conn = get_conn()
    conn.execute("INSERT INTO bug_reports (user_id, description) VALUES (?, ?)",
                 (user_id, description))
    conn.commit()
    conn.close()


def get_open_bug_reports():
    conn = get_conn()
    bugs = conn.execute("""
        SELECT b.*, u.name FROM bug_reports b
        LEFT JOIN users u ON b.user_id = u.user_id
        WHERE b.status = 'open'
        ORDER BY b.created_at DESC
    """).fetchall()
    conn.close()
    return bugs


def set_premium(user_id, days=30):
    conn = get_conn()
    until = datetime.now() + timedelta(days=days)
    conn.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?",
                 (until.isoformat(), user_id))
    conn.commit()
    conn.close()
    return until


def revoke_premium(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def set_premium_all(days=30):
    from datetime import datetime, timedelta
    conn = get_conn()
    until = datetime.now() + timedelta(days=days)
    affected = conn.execute("SELECT COUNT(*) as c FROM users WHERE status='approved' AND is_blocked=0").fetchone()["c"]
    conn.execute("UPDATE users SET is_premium=1, premium_until=? WHERE status='approved' AND is_blocked=0",
                 (until.isoformat(),))
    conn.commit()
    conn.close()
    return affected, until


def set_filter_region(user_id, region):
    conn = get_conn()
    conn.execute("UPDATE users SET filter_region = ? WHERE user_id = ?", (region, user_id))
    conn.commit()
    conn.close()


def add_bonus_likes(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET bonus_likes = bonus_likes + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def add_bonus_likes_all(amount):
    conn = get_conn()
    conn.execute("UPDATE users SET bonus_likes = bonus_likes + ? WHERE status = 'approved' AND is_blocked = 0", (amount,))
    affected = conn.execute("SELECT COUNT(*) as c FROM users WHERE status = 'approved' AND is_blocked = 0").fetchone()["c"]
    conn.commit()
    conn.close()
    return affected


def check_and_use_like(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return False, 0
    today = date.today().isoformat()
    if user["is_premium"] and user["premium_until"]:
        if datetime.fromisoformat(user["premium_until"]) < datetime.now():
            conn.execute("UPDATE users SET is_premium = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if user["is_premium"]:
        conn.close()
        return True, -1
    if user["likes_reset_date"] != today:
        conn.execute("UPDATE users SET likes_used_today = 0, likes_reset_date = ? WHERE user_id = ?",
                     (today, user_id))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if user["bonus_likes"] > 0:
        conn.execute("UPDATE users SET bonus_likes = bonus_likes - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        remaining = user["bonus_likes"] - 1
        conn.close()
        return True, remaining
    if user["likes_used_today"] < FREE_DAILY_LIKES:
        conn.execute("UPDATE users SET likes_used_today = likes_used_today + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        remaining = FREE_DAILY_LIKES - user["likes_used_today"] - 1
        conn.close()
        return True, remaining
    conn.close()
    return False, 0


def get_likes_status(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return None
    today = date.today().isoformat()
    if user["is_premium"]:
        conn.close()
        return {"type": "premium", "remaining": -1}
    if user["likes_reset_date"] != today:
        daily_remaining = FREE_DAILY_LIKES
    else:
        daily_remaining = FREE_DAILY_LIKES - user["likes_used_today"]
    conn.close()
    return {"type": "free", "daily_remaining": max(0, daily_remaining), "bonus_likes": user["bonus_likes"]}


def get_next_profile(viewer_id, viewer_gender, filter_region=None):
    target_gender = "male" if viewer_gender == "female" else "female"
    conn = get_conn()
    region_filter = ""
    params = [target_gender, viewer_id, viewer_id]
    if filter_region:
        region_filter = "AND region = ?"
        params.append(filter_region)
    profile = conn.execute(f"""
        SELECT * FROM users
        WHERE gender = ? AND status = 'approved' AND is_blocked = 0
        AND is_suspended = 0 AND user_id != ?
        AND user_id NOT IN (SELECT viewed_id FROM seen WHERE viewer_id = ?)
        {region_filter}
        ORDER BY is_premium DESC, RANDOM()
        LIMIT 1
    """, params).fetchone()
    conn.close()
    return profile


def mark_seen(viewer_id, viewed_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO seen (viewer_id, viewed_id) VALUES (?, ?)", (viewer_id, viewed_id))
    conn.commit()
    conn.close()


def add_like(from_user_id, to_user_id, message=None):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO likes (from_user_id, to_user_id, message) VALUES (?, ?, ?)",
                 (from_user_id, to_user_id, message))
    conn.commit()
    conn.close()


def check_mutual_like(user1_id, user2_id):
    conn = get_conn()
    result = conn.execute("SELECT COUNT(*) as cnt FROM likes WHERE from_user_id = ? AND to_user_id = ?",
                          (user2_id, user1_id)).fetchone()
    conn.close()
    return result["cnt"] > 0


def save_match(user1_id, user2_id):
    conn = get_conn()
    conn.execute("INSERT INTO matches (user1_id, user2_id) VALUES (?, ?)", (user1_id, user2_id))
    conn.commit()
    conn.close()


def add_appeal(user_id, message):
    conn = get_conn()
    conn.execute("INSERT INTO appeals (user_id, message) VALUES (?, ?)", (user_id, message))
    conn.commit()
    conn.close()


def get_pending_appeals():
    conn = get_conn()
    appeals = conn.execute("""
        SELECT a.*, u.name, u.age FROM appeals a
        JOIN users u ON a.user_id = u.user_id
        WHERE a.status = 'pending'
    """).fetchall()
    conn.close()
    return appeals


def resolve_appeal(appeal_id, status):
    conn = get_conn()
    conn.execute("UPDATE appeals SET status = ? WHERE id = ?", (status, appeal_id))
    conn.commit()
    conn.close()


def get_all_approved_users():
    conn = get_conn()
    users = conn.execute("SELECT * FROM users WHERE status = 'approved' AND is_blocked = 0").fetchall()
    conn.close()
    return users


def get_user_settings(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"language": "he", "show_age": 1, "notifications": 1}


def update_user_setting(user_id, key, value):
    conn = get_conn()
    conn.execute("""
        INSERT INTO user_settings (user_id, language, show_age, notifications)
        VALUES (?, 'he', 1, 1)
        ON CONFLICT(user_id) DO NOTHING
    """, (user_id,))
    conn.execute(f"UPDATE user_settings SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()


def track_premium_interest(user_id):
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS premium_interest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO premium_interest (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()


def get_premium_interested_users():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS premium_interest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    results = conn.execute("""
        SELECT pi.user_id, pi.created_at, u.name, u.age, u.region, u.city, u.gender
        FROM premium_interest pi
        LEFT JOIN users u ON pi.user_id = u.user_id
        ORDER BY pi.created_at DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    return results


def get_all_users_detailed():
    conn = get_conn()
    users = conn.execute("""
        SELECT u.*,
               (SELECT COUNT(*) FROM reports WHERE reported_id = u.user_id) as report_count,
               (SELECT COUNT(*) FROM likes WHERE from_user_id = u.user_id) as likes_given,
               (SELECT COUNT(*) FROM likes WHERE to_user_id = u.user_id) as likes_received
        FROM users u
        ORDER BY u.created_at DESC
    """).fetchall()
    conn.close()
    return users


def get_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) as c FROM users WHERE status='pending'").fetchone()["c"]
    approved = conn.execute("SELECT COUNT(*) as c FROM users WHERE status='approved'").fetchone()["c"]
    blocked = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_blocked=1").fetchone()["c"]
    suspended = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_suspended=1").fetchone()["c"]
    matches = conn.execute("SELECT COUNT(*) as c FROM matches").fetchone()["c"]
    premium = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_premium=1").fetchone()["c"]
    reports = conn.execute("SELECT COUNT(*) as c FROM reports WHERE status='pending'").fetchone()["c"]
    bugs = conn.execute("SELECT COUNT(*) as c FROM bug_reports WHERE status='open'").fetchone()["c"]
    deleted = conn.execute("SELECT COUNT(*) as c FROM deleted_users").fetchone()["c"]
    try:
        interested = conn.execute("SELECT COUNT(*) as c FROM premium_interest").fetchone()["c"]
    except Exception:
        interested = 0
    conn.close()
    return {"total": total, "pending": pending, "approved": approved, "blocked": blocked,
            "suspended": suspended, "matches": matches, "premium": premium,
            "reports": reports, "bugs": bugs, "deleted": deleted, "premium_interest": interested}


def search_users(query):
    conn = get_conn()
    try:
        uid = int(query)
        users = conn.execute(
            "SELECT u.*, "
            "(SELECT COUNT(*) FROM reports WHERE reported_id = u.user_id) as report_count, "
            "(SELECT COUNT(*) FROM likes WHERE from_user_id = u.user_id) as likes_given, "
            "(SELECT COUNT(*) FROM likes WHERE to_user_id = u.user_id) as likes_received "
            "FROM users u WHERE u.user_id = ?",
            (uid,)
        ).fetchall()
    except ValueError:
        users = conn.execute(
            "SELECT u.*, "
            "(SELECT COUNT(*) FROM reports WHERE reported_id = u.user_id) as report_count, "
            "(SELECT COUNT(*) FROM likes WHERE from_user_id = u.user_id) as likes_given, "
            "(SELECT COUNT(*) FROM likes WHERE to_user_id = u.user_id) as likes_received "
            "FROM users u WHERE LOWER(u.name) LIKE LOWER(?)",
            (f"%{query}%",)
        ).fetchall()
    conn.close()
    return users


CREATE_MESSAGES_SQL = """
    CREATE TABLE IF NOT EXISTS user_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        message_text TEXT,
        message_type TEXT DEFAULT 'text',
        is_read INTEGER DEFAULT 0,
        admin_closed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


def _ensure_messages_table(conn):
    conn.execute(CREATE_MESSAGES_SQL)


def add_user_message(from_user_id, message_text, message_type="text"):
    conn = get_conn()
    _ensure_messages_table(conn)
    conn.execute(
        "INSERT INTO user_messages (from_user_id, message_text, message_type) VALUES (?, ?, ?)",
        (from_user_id, message_text, message_type)
    )
    conn.commit()
    conn.close()


def get_user_messages(unread_only=False):
    conn = get_conn()
    _ensure_messages_table(conn)
    where = "WHERE m.admin_closed = 0"
    if unread_only:
        where += " AND m.is_read = 0"
    msgs = conn.execute(
        f"SELECT m.*, u.name, u.age, u.gender FROM user_messages m "
        f"LEFT JOIN users u ON m.from_user_id = u.user_id "
        f"{where} ORDER BY m.created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return msgs


def mark_messages_read(user_id):
    conn = get_conn()
    _ensure_messages_table(conn)
    conn.execute("UPDATE user_messages SET is_read = 1 WHERE from_user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def close_user_conversation(user_id):
    conn = get_conn()
    _ensure_messages_table(conn)
    conn.execute("UPDATE user_messages SET admin_closed = 1 WHERE from_user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_unread_messages_count():
    conn = get_conn()
    try:
        _ensure_messages_table(conn)
        count = conn.execute(
            "SELECT COUNT(*) as c FROM user_messages WHERE is_read = 0 AND admin_closed = 0"
        ).fetchone()["c"]
    except Exception:
        count = 0
    conn.close()
    return count


ADMIN_CHAT_SQL = """
    CREATE TABLE IF NOT EXISTS admin_chat_session (
        id INTEGER PRIMARY KEY,
        target_user_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


def set_admin_chat(target_user_id):
    conn = get_conn()
    conn.execute(ADMIN_CHAT_SQL)
    conn.execute("DELETE FROM admin_chat_session")
    if target_user_id:
        conn.execute("INSERT INTO admin_chat_session (id, target_user_id) VALUES (1, ?)", (target_user_id,))
    conn.commit()
    conn.close()


def get_admin_chat():
    conn = get_conn()
    try:
        conn.execute(ADMIN_CHAT_SQL)
        row = conn.execute("SELECT target_user_id FROM admin_chat_session WHERE id=1").fetchone()
        conn.close()
        return row["target_user_id"] if row else None
    except Exception:
        conn.close()
        return None


INCOMPLETE_SQL = """
    CREATE TABLE IF NOT EXISTS incomplete_registrations (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        last_step TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


def track_registration_start(user_id, username, full_name):
    conn = get_conn()
    conn.execute(INCOMPLETE_SQL)
    conn.execute("""
        INSERT OR REPLACE INTO incomplete_registrations
        (user_id, username, full_name, last_step, updated_at)
        VALUES (?, ?, ?, 'start', CURRENT_TIMESTAMP)
    """, (user_id, username or "", full_name or ""))
    conn.commit()
    conn.close()


def update_registration_step(user_id, step):
    conn = get_conn()
    conn.execute(INCOMPLETE_SQL)
    conn.execute("""
        UPDATE incomplete_registrations
        SET last_step=?, updated_at=CURRENT_TIMESTAMP
        WHERE user_id=?
    """, (step, user_id))
    conn.commit()
    conn.close()


def remove_incomplete_registration(user_id):
    conn = get_conn()
    conn.execute(INCOMPLETE_SQL)
    conn.execute("DELETE FROM incomplete_registrations WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_incomplete_registrations():
    conn = get_conn()
    conn.execute(INCOMPLETE_SQL)
    rows = conn.execute("""
        SELECT i.* FROM incomplete_registrations i
        WHERE i.user_id NOT IN (SELECT user_id FROM users)
        ORDER BY i.updated_at DESC
    """).fetchall()
    conn.close()
    return rows
