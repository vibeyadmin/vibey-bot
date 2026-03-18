import os
import sqlite3
import json
from datetime import datetime
from functools import wraps
from flask import Flask, request, session, redirect, jsonify, Response
import urllib.request

app = Flask(__name__)
app.secret_key = os.environ.get("WEB_SECRET_KEY", "vibey_secret_2024")

DB_PATH = os.environ.get("DB_PATH", "dating_bot.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_WEB_PASSWORD", "admin123")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

REGIONS = {
    "north": "צפון 🌿",
    "center": "מרכז 🏙",
    "south": "דרום 🌵"
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cur, row: {
        col[0]: row[i] for i, col in enumerate(cur.description)
    } if cur.description else row
    return conn


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def get_photo_url(file_id):
    if not file_id or not BOT_TOKEN:
        return None
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
            path = data["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"
    except Exception:
        return None


@app.route("/photo/<file_id>")
@login_required
def proxy_photo(file_id):
    try:
        url = get_photo_url(file_id)
        if not url:
            raise Exception("no url")
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read()
        return Response(data, mimetype="image/jpeg")
    except Exception:
        px = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        return Response(px, mimetype="image/png")


HTML_BASE = """<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vibey Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0a0a0f;
  --surface: #13131a;
  --surface2: #1c1c26;
  --border: rgba(255,255,255,0.07);
  --accent: #7c3aed;
  --accent2: #a855f7;
  --pink: #ec4899;
  --green: #22c55e;
  --orange: #f97316;
  --red: #ef4444;
  --blue: #3b82f6;
  --text: #f1f5f9;
  --muted: rgba(255,255,255,0.4);
  --radius: 14px;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:'Rubik',sans-serif; min-height:100vh; }

/* NAV */
nav {
  position:sticky; top:0; z-index:100;
  background:rgba(10,10,15,0.85);
  backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border);
  padding:0 32px; height:60px;
  display:flex; align-items:center; justify-content:space-between;
}
.nav-brand { font-size:1.3rem; font-weight:900; background:linear-gradient(135deg,#a855f7,#ec4899); -webkit-background-clip:text; -webkit-text-fill-color:transparent; text-decoration:none; }
.nav-links { display:flex; gap:4px; }
.nav-links a { color:var(--muted); text-decoration:none; padding:7px 14px; border-radius:9px; font-size:.85rem; font-weight:500; transition:all .2s; }
.nav-links a:hover, .nav-links a.active { background:rgba(124,58,237,0.15); color:var(--text); }
.nav-links a.danger { color:rgba(239,68,68,0.5); }
.nav-links a.danger:hover { background:rgba(239,68,68,0.1); color:#ef4444; }

/* LAYOUT */
.container { max-width:1400px; margin:0 auto; padding:36px 32px; }

/* STATS */
.stats-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:14px; margin-bottom:36px; }
.stat-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:22px 18px; text-align:center; transition:border-color .2s; }
.stat-card:hover { border-color:rgba(124,58,237,0.3); }
.stat-num { font-size:2.4rem; font-weight:900; line-height:1; }
.stat-label { color:var(--muted); font-size:.78rem; margin-top:6px; font-weight:500; }

/* SEARCH / FILTERS */
.toolbar { display:flex; gap:10px; margin-bottom:24px; flex-wrap:wrap; align-items:center; }
.toolbar input { padding:10px 16px; background:var(--surface); border:1px solid var(--border); border-radius:10px; color:var(--text); font-family:'Rubik',sans-serif; font-size:.9rem; outline:none; min-width:220px; transition:border-color .2s; }
.toolbar input:focus { border-color:var(--accent); }
.filter-btn { padding:9px 16px; border:1px solid var(--border); border-radius:10px; background:var(--surface); color:var(--muted); text-decoration:none; font-size:.82rem; font-weight:500; cursor:pointer; transition:all .2s; white-space:nowrap; }
.filter-btn:hover, .filter-btn.active { background:rgba(124,58,237,0.15); border-color:rgba(124,58,237,0.4); color:var(--text); }
.btn { padding:9px 18px; border:none; border-radius:10px; font-family:'Rubik',sans-serif; font-size:.85rem; font-weight:600; cursor:pointer; transition:all .2s; text-decoration:none; display:inline-flex; align-items:center; gap:6px; }
.btn-primary { background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#fff; }
.btn-primary:hover { opacity:.85; transform:translateY(-1px); }
.btn-danger { background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.3); }
.btn-danger:hover { background:rgba(239,68,68,0.25); }
.btn-success { background:rgba(34,197,94,0.15); color:#22c55e; border:1px solid rgba(34,197,94,0.3); }
.btn-success:hover { background:rgba(34,197,94,0.25); }
.btn-warning { background:rgba(249,115,22,0.15); color:#f97316; border:1px solid rgba(249,115,22,0.3); }
.btn-warning:hover { background:rgba(249,115,22,0.25); }
.btn-sm { padding:6px 12px; font-size:.78rem; }

/* USER GRID */
.users-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:18px; }
.user-card {
  background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  overflow:hidden; transition:all .2s; cursor:pointer;
}
.user-card:hover { border-color:rgba(124,58,237,0.35); transform:translateY(-2px); box-shadow:0 8px 30px rgba(0,0,0,0.3); }
.card-photo { height:180px; background:linear-gradient(135deg,rgba(124,58,237,0.2),rgba(236,72,153,0.2)); display:flex; align-items:center; justify-content:center; font-size:4rem; position:relative; overflow:hidden; }
.card-photo img { width:100%; height:100%; object-fit:cover; }
.card-photo .photo-count { position:absolute; bottom:8px; right:8px; background:rgba(0,0,0,0.7); color:#fff; font-size:.72rem; padding:3px 8px; border-radius:20px; }
.card-body { padding:16px; }
.card-name { font-size:1.05rem; font-weight:700; margin-bottom:4px; }
.card-meta { color:var(--muted); font-size:.82rem; margin-bottom:3px; }
.card-bio { color:rgba(255,255,255,0.6); font-size:.8rem; margin-top:8px; line-height:1.5; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.card-actions { display:flex; gap:6px; margin-top:12px; flex-wrap:wrap; }
.badges { display:flex; gap:4px; flex-wrap:wrap; margin-top:8px; }
.badge { display:inline-block; padding:3px 9px; border-radius:20px; font-size:.7rem; font-weight:600; }
.badge-green { background:rgba(34,197,94,0.15); color:#22c55e; border:1px solid rgba(34,197,94,0.25); }
.badge-orange { background:rgba(249,115,22,0.15); color:#f97316; border:1px solid rgba(249,115,22,0.25); }
.badge-red { background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.25); }
.badge-purple { background:rgba(168,85,247,0.15); color:#a855f7; border:1px solid rgba(168,85,247,0.25); }
.badge-blue { background:rgba(59,130,246,0.15); color:#3b82f6; border:1px solid rgba(59,130,246,0.25); }

/* MODAL */
.modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.8); z-index:1000; align-items:center; justify-content:center; padding:20px; }
.modal-overlay.open { display:flex; }
.modal { background:var(--surface); border:1px solid var(--border); border-radius:20px; width:100%; max-width:680px; max-height:90vh; overflow-y:auto; padding:32px; position:relative; }
.modal-close { position:absolute; top:16px; left:16px; background:none; border:none; color:var(--muted); font-size:1.4rem; cursor:pointer; padding:4px 8px; border-radius:8px; transition:all .2s; }
.modal-close:hover { background:var(--surface2); color:var(--text); }
.modal-photos { display:flex; gap:8px; margin-bottom:20px; overflow-x:auto; padding-bottom:4px; }
.modal-photos img { height:160px; width:auto; border-radius:10px; object-fit:cover; flex-shrink:0; }
.modal-title { font-size:1.6rem; font-weight:900; margin-bottom:6px; }
.modal-row { display:flex; gap:8px; align-items:center; margin-bottom:8px; color:var(--muted); font-size:.88rem; }
.modal-row strong { color:var(--text); }
.modal-bio { background:var(--surface2); border-radius:10px; padding:14px; margin:16px 0; font-size:.88rem; line-height:1.7; color:rgba(255,255,255,0.8); }
.modal-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:20px; padding-top:20px; border-top:1px solid var(--border); }
.divider { height:1px; background:var(--border); margin:16px 0; }
.info-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:16px; }
.info-item { background:var(--surface2); border-radius:10px; padding:12px 14px; }
.info-item .label { color:var(--muted); font-size:.75rem; margin-bottom:4px; }
.info-item .value { font-weight:600; font-size:.9rem; }

/* TABLE */
.table-wrap { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
table { width:100%; border-collapse:collapse; }
th { padding:12px 16px; text-align:right; color:var(--muted); font-size:.78rem; font-weight:600; border-bottom:1px solid var(--border); background:var(--surface2); }
td { padding:12px 16px; border-bottom:1px solid rgba(255,255,255,0.03); font-size:.85rem; }
tr:last-child td { border-bottom:none; }
tr:hover td { background:rgba(255,255,255,0.02); }

/* PAGINATION */
.pagination { display:flex; gap:6px; justify-content:center; margin-top:28px; }
.pagination a { padding:8px 14px; background:var(--surface); border:1px solid var(--border); border-radius:9px; color:var(--muted); text-decoration:none; font-size:.85rem; transition:all .2s; }
.pagination a.cur, .pagination a:hover { background:rgba(124,58,237,0.2); border-color:var(--accent); color:var(--text); }

/* SECTION TITLE */
.section-title { font-size:1.25rem; font-weight:700; margin-bottom:20px; display:flex; align-items:center; gap:10px; }
.count-badge { background:var(--surface2); color:var(--muted); padding:3px 10px; border-radius:20px; font-size:.78rem; font-weight:600; }

/* TOAST */
#toast { position:fixed; bottom:24px; left:50%; transform:translateX(-50%) translateY(100px); background:#22c55e; color:#fff; padding:12px 24px; border-radius:12px; font-weight:600; font-size:.9rem; z-index:9999; transition:transform .3s; box-shadow:0 4px 20px rgba(0,0,0,0.4); }
#toast.show { transform:translateX(-50%) translateY(0); }
#toast.error { background:#ef4444; }

/* EMPTY */
.empty { text-align:center; padding:60px 20px; color:var(--muted); }
.empty-icon { font-size:3rem; margin-bottom:12px; }

code { background:var(--surface2); padding:2px 8px; border-radius:6px; font-size:.8rem; font-family:monospace; color:#a855f7; }

/* ID CARD */
.id-card-img { max-width:100%; border-radius:10px; margin-top:10px; }
</style>
</head>
<body>
"""


def nav_html(active=""):
    pages = [
        ("home", "/", "🏠 ראשי"),
        ("users", "/users", "👥 משתמשים"),
        ("pending", "/pending", "⏳ ממתינים"),
        ("reports", "/reports", "🚨 דיווחים"),
        ("messages", "/messages", "💬 הודעות"),
    ]
    links = ""
    for key, href, label in pages:
        cls = "active" if active == key else ""
        links += f'<a href="{href}" class="{cls}">{label}</a>'
    links += '<a href="/logout" class="danger">יציאה</a>'
    return f"""
{HTML_BASE}
<nav>
  <a href="/" class="nav-brand">💜 Vibey Admin</a>
  <div class="nav-links">{links}</div>
</nav>
<div id="toast"></div>
<script>
function showToast(msg, type='success') {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = type === 'error' ? 'error show' : 'show';
  setTimeout(() => t.className = '', 3000);
}}
async function doAction(url, msg) {{
  try {{
    const r = await fetch(url, {{method:'POST'}});
    const d = await r.json();
    if(d.ok) {{ showToast(msg || d.msg || '✅ בוצע!'); setTimeout(()=>location.reload(), 1200); }}
    else showToast(d.msg || '❌ שגיאה', 'error');
  }} catch(e) {{ showToast('❌ שגיאה', 'error'); }}
}}
function openModal(id) {{ document.getElementById(id).classList.add('open'); }}
function closeModal(id) {{ document.getElementById(id).classList.remove('open'); }}
document.addEventListener('keydown', e => {{
  if(e.key==='Escape') document.querySelectorAll('.modal-overlay.open').forEach(m=>m.classList.remove('open'));
}});
</script>
<div class="container">
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        error = "סיסמה שגויה ❌"
    return f"""{HTML_BASE}
<div style="display:flex;align-items:center;justify-content:center;min-height:100vh">
<div style="background:var(--surface);border:1px solid rgba(124,58,237,0.3);border-radius:24px;padding:52px 44px;width:360px;text-align:center">
  <div style="font-size:2.8rem;margin-bottom:8px">💜</div>
  <h1 style="font-size:2rem;font-weight:900;margin-bottom:4px">Vibey</h1>
  <p style="color:var(--muted);margin-bottom:32px;font-size:.9rem">פאנל ניהול</p>
  <form method="POST">
    <input type="password" name="password" placeholder="סיסמה" autofocus
      style="width:100%;padding:13px;background:var(--surface2);border:1px solid var(--border);border-radius:11px;color:var(--text);font-size:1rem;margin-bottom:12px;outline:none;text-align:center;font-family:'Rubik',sans-serif;transition:border-color .2s"
      onfocus="this.style.borderColor='var(--accent)'" onblur="this.style.borderColor='var(--border)'">
    <button type="submit"
      style="width:100%;padding:13px;background:linear-gradient(135deg,#7c3aed,#a855f7);border:none;border-radius:11px;color:#fff;font-size:1rem;font-weight:700;cursor:pointer;font-family:'Rubik',sans-serif">
      כניסה
    </button>
  </form>
  {'<p style="color:#ef4444;font-size:.85rem;margin-top:12px">'+error+'</p>' if error else ''}
</div></div></body></html>"""


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def home():
    c = get_conn()
    try:
        total = c.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
        pending = c.execute("SELECT COUNT(*) as n FROM users WHERE status='pending'").fetchone()["n"]
        approved = c.execute("SELECT COUNT(*) as n FROM users WHERE status='approved'").fetchone()["n"]
        blocked = c.execute("SELECT COUNT(*) as n FROM users WHERE is_blocked=1").fetchone()["n"]
        suspended = c.execute("SELECT COUNT(*) as n FROM users WHERE is_suspended=1").fetchone()["n"]
        matches = c.execute("SELECT COUNT(*) as n FROM matches").fetchone()["n"]
        premium = c.execute("SELECT COUNT(*) as n FROM users WHERE is_premium=1").fetchone()["n"]
        try:
            reports = c.execute("SELECT COUNT(*) as n FROM reports WHERE status='pending'").fetchone()["n"]
        except Exception:
            reports = 0
        try:
            msgs = c.execute("SELECT COUNT(*) as n FROM user_messages WHERE is_read=0").fetchone()["n"]
        except Exception:
            msgs = 0
        try:
            bugs = c.execute("SELECT COUNT(*) as n FROM bug_reports WHERE status='open'").fetchone()["n"]
        except Exception:
            bugs = 0
    finally:
        c.close()

    stats = [
        (total, "סה\"כ משתמשים", "#a855f7"),
        (pending, "ממתינים לאישור", "#f97316"),
        (approved, "מאושרים", "#22c55e"),
        (blocked, "חסומים", "#ef4444"),
        (suspended, "מושעים", "#f97316"),
        (premium, "פרמיום ⭐", "#a855f7"),
        (matches, "התאמות 💕", "#ec4899"),
        (reports, "דיווחים 🚨", "#ef4444"),
        (msgs, "הודעות חדשות", "#3b82f6"),
        (bugs, "תקלות 🐛", "#f97316"),
    ]

    stats_html = "".join([
        f'<div class="stat-card"><div class="stat-num" style="color:{color}">{n}</div><div class="stat-label">{label}</div></div>'
        for n, label, color in stats
    ])

    quick = f"""
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px">
      <a href="/pending" class="filter-btn active">⏳ ממתינים ({pending})</a>
      <a href="/users" class="filter-btn">👥 כל המשתמשים</a>
      <a href="/reports" class="filter-btn">🚨 דיווחים ({reports})</a>
      <a href="/messages" class="filter-btn">💬 הודעות ({msgs})</a>
    </div>
    """

    return nav_html("home") + f"""
<div class="stats-grid">{stats_html}</div>
<div class="section-title">קישורים מהירים</div>
{quick}
</div></body></html>"""


def _build_user_modal(u, photos):
    uid = u["user_id"]
    gender_text = "👩 אישה" if u["gender"] == "female" else "👨 גבר"
    region = REGIONS.get(u.get("region", ""), u.get("region", "") or "")
    status_map = {"approved": ("✅ מאושר", "green"), "pending": ("⏳ ממתין", "orange"),
                  "rejected": ("❌ נדחה", "red"), "deleted": ("🗑 נמחק", "red")}
    status_label, status_color = status_map.get(u["status"], ("?", "blue"))
    username = f"@{u['username']}" if u.get("username") else "אין"

    flags = []
    if u.get("is_blocked"): flags.append('<span class="badge badge-red">🚫 חסום</span>')
    if u.get("is_suspended"): flags.append('<span class="badge badge-orange">⏸ מושעה</span>')
    if u.get("is_premium"): flags.append('<span class="badge badge-purple">⭐ פרמיום</span>')

    photos_html = ""
    if photos:
        for fid in photos[:5]:
            photos_html += f'<img src="/photo/{fid}" alt="photo">'
    else:
        photos_html = f'<div style="color:var(--muted);font-size:.85rem;padding:10px">אין תמונות</div>'

    id_card_html = ""
    if u.get("id_card_file_id"):
        id_card_html = f"""
        <div style="margin-top:16px">
          <div style="color:var(--muted);font-size:.8rem;margin-bottom:8px">🪪 תעודת זהות</div>
          <img src="/photo/{u['id_card_file_id']}" class="id-card-img" alt="ID">
          <div style="margin-top:8px">
            <button class="btn btn-danger btn-sm" onclick="doAction('/api/delete_id/{uid}','🗑 תז נמחק')">🗑 מחק תז</button>
          </div>
        </div>"""

    approve_btn = f'<button class="btn btn-success" onclick="doAction(\'/api/approve/{uid}\',\'✅ אושר!\')">✅ אשר</button>' if u["status"] == "pending" else ""
    reject_btn = f'<button class="btn btn-danger" onclick="doAction(\'/api/reject/{uid}\',\'❌ נדחה\')">❌ דחה</button>' if u["status"] == "pending" else ""
    block_btn = f'<button class="btn btn-danger" onclick="doAction(\'/api/block/{uid}\',\'🚫 חסום!\')">🚫 חסום</button>' if not u.get("is_blocked") else f'<button class="btn btn-success" onclick="doAction(\'/api/unblock/{uid}\',\'✅ שוחרר!\')">🔓 שחרר</button>'
    suspend_btn = f'<button class="btn btn-warning" onclick="doAction(\'/api/suspend/{uid}\',\'⏸ הושעה\')">⏸ השעה</button>' if not u.get("is_suspended") else f'<button class="btn btn-success" onclick="doAction(\'/api/unsuspend/{uid}\',\'▶️ שוחרר\')">▶️ שחרר השעיה</button>'

    gift_html = f"""
    <div style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">
      <div style="font-size:.85rem;color:var(--muted);margin-bottom:10px">🎁 הענק מתנה</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <input type="number" id="likes_amount_{uid}" placeholder="מס׳ לייקים" min="1" max="999"
          style="width:130px;padding:8px 12px;background:var(--surface2);border:1px solid var(--border);border-radius:9px;color:var(--text);font-family:'Rubik',sans-serif;font-size:.85rem;outline:none">
        <button class="btn btn-primary btn-sm" onclick="giftLikes({uid})">❤️ הענק לייקים</button>
        <input type="number" id="premium_days_{uid}" placeholder="ימי פרמיום" min="1" max="365"
          style="width:130px;padding:8px 12px;background:var(--surface2);border:1px solid var(--border);border-radius:9px;color:var(--text);font-family:'Rubik',sans-serif;font-size:.85rem;outline:none">
        <button class="btn btn-primary btn-sm" onclick="giftPremium({uid})">⭐ הענק פרמיום</button>
      </div>
    </div>"""

    return f"""
<div class="modal-overlay" id="modal_{uid}">
  <div class="modal">
    <button class="modal-close" onclick="closeModal('modal_{uid}')">✕</button>
    <div class="modal-photos">{photos_html}</div>
    <div class="modal-title">{gender_text} {u['name']}, {u['age']}</div>
    <div class="badges">
      <span class="badge badge-{status_color}">{status_label}</span>
      {''.join(flags)}
    </div>
    <div class="divider"></div>
    <div class="info-grid">
      <div class="info-item"><div class="label">📍 אזור ועיר</div><div class="value">{region} — {u.get('city','')}</div></div>
      <div class="info-item"><div class="label">👤 טלגרם</div><div class="value">{username}</div></div>
      <div class="info-item"><div class="label">🆔 מזהה</div><div class="value"><code>{uid}</code></div></div>
      <div class="info-item"><div class="label">📅 הצטרף</div><div class="value">{str(u.get('created_at',''))[:10]}</div></div>
    </div>
    <div class="modal-bio">📝 {u.get('bio','') or 'אין תיאור'}</div>
    {id_card_html}
    {gift_html}
    <div class="modal-actions">
      {approve_btn}{reject_btn}{block_btn}{suspend_btn}
      <button class="btn btn-danger btn-sm" onclick="if(confirm('למחוק?'))doAction('/api/delete/{uid}','🗑 נמחק')">🗑 מחק</button>
    </div>
  </div>
</div>"""


def _build_user_card(u, photos):
    uid = u["user_id"]
    gender_emoji = "👩" if u["gender"] == "female" else "👨"
    region = REGIONS.get(u.get("region", ""), "")
    username = f"@{u['username']}" if u.get("username") else "אין שם משתמש"

    status_map = {"approved": ("badge-green", "✅ מאושר"), "pending": ("badge-orange", "⏳ ממתין"),
                  "rejected": ("badge-red", "❌ נדחה"), "deleted": ("badge-red", "🗑 נמחק")}
    sc, sl = status_map.get(u["status"], ("badge-blue", "?"))

    flags = f'<span class="badge {sc}">{sl}</span>'
    if u.get("is_blocked"): flags += '<span class="badge badge-red">🚫</span>'
    if u.get("is_suspended"): flags += '<span class="badge badge-orange">⏸</span>'
    if u.get("is_premium"): flags += '<span class="badge badge-purple">⭐</span>'

    photo_html = f'<img src="/photo/{photos[0]}" alt="">' if photos else gender_emoji
    count_html = f'<div class="photo-count">📸 {len(photos)}</div>' if len(photos) > 1 else ""
    bio = (u.get("bio") or "")[:80]

    return f"""
<div class="user-card" onclick="openModal('modal_{uid}')">
  <div class="card-photo" style="{'background:#111' if photos else ''}">
    {photo_html}{count_html}
  </div>
  <div class="card-body">
    <div class="card-name">{gender_emoji} {u['name']}, {u['age']}</div>
    <div class="card-meta">📍 {region} — {u.get('city','')}</div>
    <div class="card-meta">📱 {username} | <code>{uid}</code></div>
    <div class="badges">{flags}</div>
    <div class="card-bio">{bio}{'...' if len(u.get('bio') or '') > 80 else ''}</div>
  </div>
</div>
{_build_user_modal(u, photos)}"""


@app.route("/users")
@login_required
def users():
    sf = request.args.get("status", "")
    s = request.args.get("search", "")
    pg = int(request.args.get("page", 1))
    pp = 12

    c = get_conn()
    w, p = "WHERE 1=1", []
    if sf:
        w += " AND status=?"; p.append(sf)
    if s:
        try:
            uid = int(s); w += " AND user_id=?"; p.append(uid)
        except Exception:
            w += " AND (LOWER(name) LIKE LOWER(?) OR username LIKE ?)"; p.extend([f"%{s}%", f"%{s}%"])

    total = c.execute(f"SELECT COUNT(*) as n FROM users {w}", p).fetchone()["n"]
    ul = c.execute(f"SELECT * FROM users {w} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                   p + [pp, (pg - 1) * pp]).fetchall()

    cards = ""
    for u in ul:
        photos = [r["file_id"] for r in
                  c.execute("SELECT file_id FROM user_photos WHERE user_id=? ORDER BY position", (u["user_id"],)).fetchall()]
        cards += _build_user_card(u, photos)

    c.close()

    tp = max(1, (total + pp - 1) // pp)
    pag = "".join([
        f'<a href="?page={i}&status={sf}&search={s}" class="{"cur" if i == pg else ""}">{i}</a>'
        for i in range(max(1, pg - 4), min(tp + 1, pg + 5))
    ])

    filters = f"""
    <form method="GET" class="toolbar">
      <input type="text" name="search" placeholder="🔍 שם, @username או ID..." value="{s}">
      <a href="/users" class="filter-btn {'active' if not sf else ''}">הכל ({total})</a>
      <a href="/users?status=approved" class="filter-btn {'active' if sf=='approved' else ''}">✅ מאושרים</a>
      <a href="/users?status=pending" class="filter-btn {'active' if sf=='pending' else ''}">⏳ ממתינים</a>
      <a href="/users?status=rejected" class="filter-btn {'active' if sf=='rejected' else ''}">❌ נדחו</a>
      <button type="submit" class="btn btn-primary">חפש</button>
    </form>"""

    gift_all_html = """
    <div style="margin-bottom:24px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px">
      <div style="font-weight:700;margin-bottom:14px">🎁 מתנות לכולם</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <input type="number" id="all_likes" placeholder="כמה לייקים?" min="1"
          style="width:150px;padding:9px 13px;background:var(--surface2);border:1px solid var(--border);border-radius:9px;color:var(--text);font-family:'Rubik',sans-serif;font-size:.85rem;outline:none">
        <button class="btn btn-primary" onclick="giftAllLikes()">❤️ לייקים לכולם</button>
        <input type="number" id="all_premium_days" placeholder="כמה ימים?" min="1" value="30"
          style="width:150px;padding:9px 13px;background:var(--surface2);border:1px solid var(--border);border-radius:9px;color:var(--text);font-family:'Rubik',sans-serif;font-size:.85rem;outline:none">
        <button class="btn btn-primary" onclick="giftAllPremium()">⭐ פרמיום לכולם</button>
      </div>
    </div>"""

    return nav_html("users") + f"""
{gift_all_html}
{filters}
<div class="section-title">משתמשים <span class="count-badge">{total}</span></div>
<div class="users-grid">{cards or '<div class="empty"><div class="empty-icon">🔍</div><div>לא נמצאו משתמשים</div></div>'}</div>
<div class="pagination">{pag}</div>
<script>
async function giftLikes(uid) {{
  const n = document.getElementById('likes_amount_'+uid).value;
  if(!n) return showToast('הזן מספר לייקים', 'error');
  await doAction('/api/gift_likes/'+uid+'/'+n, '🎁 '+n+' לייקים הוענקו!');
}}
async function giftPremium(uid) {{
  const d = document.getElementById('premium_days_'+uid).value || 30;
  await doAction('/api/gift_premium/'+uid+'/'+d, '⭐ פרמיום הוענק ל-'+d+' ימים!');
}}
async function giftAllLikes() {{
  const n = document.getElementById('all_likes').value;
  if(!n) return showToast('הזן מספר', 'error');
  if(!confirm('לתת '+n+' לייקים לכל המשתמשים?')) return;
  await doAction('/api/gift_likes_all/'+n, '🎁 לייקים הוענקו לכולם!');
}}
async function giftAllPremium() {{
  const d = document.getElementById('all_premium_days').value || 30;
  if(!confirm('לתת פרמיום ל-'+d+' ימים לכולם?')) return;
  await doAction('/api/gift_premium_all/'+d, '⭐ פרמיום הוענק לכולם!');
}}
</script>
</div></body></html>"""


@app.route("/pending")
@login_required
def pending():
    c = get_conn()
    ul = c.execute("SELECT * FROM users WHERE status='pending' ORDER BY created_at DESC").fetchall()
    cards = ""
    for u in ul:
        photos = [r["file_id"] for r in
                  c.execute("SELECT file_id FROM user_photos WHERE user_id=? ORDER BY position", (u["user_id"],)).fetchall()]
        cards += _build_user_card(u, photos)
    c.close()

    return nav_html("pending") + f"""
<div class="section-title">ממתינים לאישור <span class="count-badge">{len(ul)}</span></div>
<div class="users-grid">{cards or '<div class="empty"><div class="empty-icon">✅</div><div>אין ממתינים!</div></div>'}</div>
</div></body></html>"""


@app.route("/reports")
@login_required
def reports():
    c = get_conn()
    try:
        reps = c.execute("""
            SELECT r.*, u1.name as rn, u2.name as dn, u2.age as da
            FROM reports r
            LEFT JOIN users u1 ON r.reporter_id=u1.user_id
            LEFT JOIN users u2 ON r.reported_id=u2.user_id
            WHERE r.status='pending' ORDER BY r.created_at DESC
        """).fetchall()
    except Exception:
        reps = []
    c.close()

    rows = ""
    for r in reps:
        rows += f"""<tr>
          <td>{r.get('rn','?')}</td>
          <td><strong>{r.get('dn','?')}</strong>, {r.get('da','?')} <code>{r['reported_id']}</code></td>
          <td>{r.get('reason','')}</td>
          <td style="color:var(--muted)">{str(r.get('created_at',''))[:10]}</td>
          <td>
            <button class="btn btn-warning btn-sm" onclick="doAction('/api/suspend/{r['reported_id']}','⏸ הושעה')">⏸ השעה</button>
            <button class="btn btn-danger btn-sm" onclick="doAction('/api/block/{r['reported_id']}','🚫 חסום')">🚫 חסום</button>
          </td>
        </tr>"""

    table = f"""<div class="table-wrap"><table>
      <tr><th>מדווח</th><th>מדוּוח</th><th>סיבה</th><th>תאריך</th><th>פעולות</th></tr>
      {rows}
    </table></div>""" if reps else '<div class="empty"><div class="empty-icon">✅</div><div>אין דיווחים פתוחים</div></div>'

    return nav_html("reports") + f"""
<div class="section-title">דיווחים <span class="count-badge">{len(reps)}</span></div>
{table}
</div></body></html>"""


@app.route("/messages")
@login_required
def messages():
    c = get_conn()
    try:
        msgs = c.execute("""
            SELECT m.*, u.name, u.gender FROM user_messages m
            LEFT JOIN users u ON m.from_user_id=u.user_id
            WHERE m.admin_closed=0 ORDER BY m.created_at DESC LIMIT 50
        """).fetchall()
    except Exception:
        msgs = []
    c.close()

    cards = ""
    for m in msgs:
        ge = "👩" if m.get("gender") == "female" else "👨"
        nm = m.get("name") or m["from_user_id"]
        unread = not m.get("is_read")
        border = "border-color:rgba(124,58,237,0.4)" if unread else ""
        new_badge = '<span class="badge badge-purple">חדש</span>' if unread else ""
        cards += f"""
        <div style="background:var(--surface);border:1px solid var(--border);{border};border-radius:var(--radius);padding:18px;margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <span style="font-weight:700">{ge} {nm} <code>{m['from_user_id']}</code> {new_badge}</span>
            <span style="color:var(--muted);font-size:.8rem">{str(m.get('created_at',''))[:16]}</span>
          </div>
          <div style="color:rgba(255,255,255,0.8);line-height:1.7">{m.get('message_text','')}</div>
        </div>"""

    return nav_html("messages") + f"""
<div class="section-title">הודעות <span class="count-badge">{len(msgs)}</span></div>
{cards or '<div class="empty"><div class="empty-icon">💬</div><div>אין הודעות</div></div>'}
</div></body></html>"""


# ── API ACTIONS ──

def api_ok(msg="בוצע!"):
    return jsonify({"ok": True, "msg": msg})

def api_err(msg="שגיאה"):
    return jsonify({"ok": False, "msg": msg})


@app.route("/api/approve/<int:uid>", methods=["POST"])
@login_required
def api_approve(uid):
    c = get_conn()
    c.execute("UPDATE users SET status='approved' WHERE user_id=?", (uid,))
    c.commit(); c.close()
    return api_ok("✅ אושר!")

@app.route("/api/reject/<int:uid>", methods=["POST"])
@login_required
def api_reject(uid):
    c = get_conn()
    c.execute("UPDATE users SET status='rejected' WHERE user_id=?", (uid,))
    c.commit(); c.close()
    return api_ok("❌ נדחה")

@app.route("/api/block/<int:uid>", methods=["POST"])
@login_required
def api_block(uid):
    c = get_conn()
    c.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (uid,))
    c.commit(); c.close()
    return api_ok("🚫 חסום!")

@app.route("/api/unblock/<int:uid>", methods=["POST"])
@login_required
def api_unblock(uid):
    c = get_conn()
    c.execute("UPDATE users SET is_blocked=0, is_suspended=0, status='approved' WHERE user_id=?", (uid,))
    c.commit(); c.close()
    return api_ok("🔓 שוחרר!")

@app.route("/api/suspend/<int:uid>", methods=["POST"])
@login_required
def api_suspend(uid):
    c = get_conn()
    c.execute("UPDATE users SET is_suspended=1 WHERE user_id=?", (uid,))
    c.commit(); c.close()
    return api_ok("⏸ הושעה")

@app.route("/api/unsuspend/<int:uid>", methods=["POST"])
@login_required
def api_unsuspend(uid):
    c = get_conn()
    c.execute("UPDATE users SET is_suspended=0 WHERE user_id=?", (uid,))
    c.commit(); c.close()
    return api_ok("▶️ שוחרר מהשעיה")

@app.route("/api/delete/<int:uid>", methods=["POST"])
@login_required
def api_delete(uid):
    c = get_conn()
    c.execute("UPDATE users SET status='deleted' WHERE user_id=?", (uid,))
    c.commit(); c.close()
    return api_ok("🗑 נמחק")

@app.route("/api/delete_id/<int:uid>", methods=["POST"])
@login_required
def api_delete_id(uid):
    c = get_conn()
    c.execute("UPDATE users SET id_card_file_id=NULL WHERE user_id=?", (uid,))
    c.commit(); c.close()
    return api_ok("🗑 תז נמחק")

@app.route("/api/gift_likes/<int:uid>/<int:amount>", methods=["POST"])
@login_required
def api_gift_likes(uid, amount):
    c = get_conn()
    c.execute("UPDATE users SET bonus_likes=bonus_likes+? WHERE user_id=?", (amount, uid))
    c.commit(); c.close()
    return api_ok(f"🎁 {amount} לייקים הוענקו!")

@app.route("/api/gift_premium/<int:uid>/<int:days>", methods=["POST"])
@login_required
def api_gift_premium(uid, days):
    from datetime import timedelta
    until = datetime.now() + timedelta(days=days)
    c = get_conn()
    c.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (until.isoformat(), uid))
    c.commit(); c.close()
    return api_ok(f"⭐ פרמיום ל-{days} ימים!")

@app.route("/api/gift_likes_all/<int:amount>", methods=["POST"])
@login_required
def api_gift_likes_all(amount):
    c = get_conn()
    c.execute("UPDATE users SET bonus_likes=bonus_likes+? WHERE status='approved' AND is_blocked=0", (amount,))
    affected = c.execute("SELECT COUNT(*) as n FROM users WHERE status='approved' AND is_blocked=0").fetchone()["n"]
    c.commit(); c.close()
    return api_ok(f"🎁 {amount} לייקים ל-{affected} משתמשים!")

@app.route("/api/gift_premium_all/<int:days>", methods=["POST"])
@login_required
def api_gift_premium_all(days):
    from datetime import timedelta
    until = datetime.now() + timedelta(days=days)
    c = get_conn()
    affected = c.execute("SELECT COUNT(*) as n FROM users WHERE status='approved' AND is_blocked=0").fetchone()["n"]
    c.execute("UPDATE users SET is_premium=1, premium_until=? WHERE status='approved' AND is_blocked=0", (until.isoformat(),))
    c.commit(); c.close()
    return api_ok(f"⭐ פרמיום ל-{days} ימים ל-{affected} משתמשים!")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("WEB_PORT", 5000)))
    app.run(host="0.0.0.0", port=port, debug=False)
