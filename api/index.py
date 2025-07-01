from flask import Flask, request, jsonify, abort, make_response
from datetime import datetime, timedelta, time
import os
import pytz
import json
from functools import wraps
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from .models import db, Member, Session, SessionMember
from sqlalchemy import text

app = Flask(__name__)

if os.environ.get("FLASK_ENV") != "production":
    from dotenv import load_dotenv
    load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SUPABASE_DB_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
SYDNEY = pytz.timezone("Australia/Sydney")
ADMIN_TOKEN = os.environ['ADMIN_TOKEN']

db.init_app(app)

# --- Auth with Cookies ---
def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get("admin_token")
        if token != ADMIN_TOKEN:
            abort(401)
        return f(*args, **kwargs)
    return wrapper

# --- Helper: Get default session time ---
def get_default_session_time():
    row = db.session.execute(
        text("SELECT value FROM settings WHERE key = 'default_session_time'")
    ).fetchone()
    if not row:
        return (16, 5)  # fallback default
    hour_str, minute_str = row[0].split(":")
    return int(hour_str), int(minute_str)

# --- Helper: Get active session ---
def get_active_session():
    session = (
        Session.query
        .order_by(Session.datetime.desc())
        .first()
    )
    return session

# --- Cookie validator ---
@app.route("/api/auth/check", methods=["GET"])
@require_admin
def check_auth():
    return jsonify({"authenticated": True})

# --- Login route ---
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if data.get("password") == ADMIN_TOKEN:
        resp = make_response(jsonify({"status": "success"}))
        resp.set_cookie("admin_token", ADMIN_TOKEN, httponly=True, max_age=86400)
        return resp
    return jsonify({"error": "unauthorized"}), 401

# --- Get or update members ---
@app.route("/api/members", methods=["GET", "POST"])
@require_admin
def edit_members():
    if request.method == "POST":
        data = request.json
        new_names = set(data.get("members", []))
        existing_members = Member.query.all()
        existing_names = set(m.name for m in existing_members)

        for name in new_names - existing_names:
            db.session.add(Member(name=name))

        for member in existing_members:
            if member.name not in new_names:
                in_use = SessionMember.query.filter_by(member_id=member.id).first()
                if not in_use:
                    db.session.delete(member)

        db.session.commit()
        return jsonify({"status": "updated"})

    members = Member.query.all()
    return jsonify([m.name for m in members])

# --- Get active session info ---
@app.route("/api/session", methods=["GET"])
def get_session():
    session = get_active_session()
    if not session:
        return jsonify({"error": "No active session"}), 404

    members = (
        db.session.query(Member.name)
        .join(SessionMember, Member.id == SessionMember.member_id)
        .filter(SessionMember.session_id == session.id)
        .all()
    )

    return jsonify({
        "id": session.id,
        "datetime": session.datetime.isoformat(),
        "members": [name for (name,) in members],
    })

# --- Remove member (check-in) ---
@app.route("/api/session/remove", methods=["POST"])
def remove_member_from_session():
    name = request.json.get("name")
    member = Member.query.filter_by(name=name).first()
    if not member:
        return jsonify({"error": "invalid member"}), 400

    session = get_active_session()
    if not session:
        return jsonify({"error": "No active session"}), 404

    now = datetime.now(SYDNEY)
    session_time = session.datetime.astimezone(SYDNEY)
    if now > session_time + timedelta(minutes=5):
        return jsonify({"error": "출석 시간이 마감되었습니다"}), 403

    db.session.query(SessionMember).filter_by(
        session_id=session.id,
        member_id=member.id
    ).delete()

    db.session.commit()
    return jsonify({"status": "removed"})

# --- Remove member (removing someone irrelevant to a session) ---
@app.route("/api/session/member", methods=["DELETE"])
@require_admin
def remove_member_from_active_session():
    data = request.json
    name = data.get("name")
    if not name:
        return jsonify({"error": "Missing member name"}), 400

    member = Member.query.filter_by(name=name).first()
    if not member:
        return jsonify({"error": "Invalid member"}), 400

    session = get_active_session()
    if not session:
        return jsonify({"error": "No active session"}), 404

    deleted = db.session.query(SessionMember).filter_by(
        session_id=session.id,
        member_id=member.id
    ).delete()

    if deleted == 0:
        return jsonify({"error": "Member not in session"}), 400

    db.session.commit()
    return jsonify({"status": "removed"})


# --- Set default session time and update all sessions ---
@app.route("/api/default-time", methods=["PUT"])
@require_admin
def set_default_time():
    data = request.json
    if "time" not in data:
        return jsonify({"error": "Missing 'time'"}), 400
    try:
        hour, minute = map(int, data["time"].split(":"))
        if not (0 <= hour <= 23) or not (0 <= minute <= 59):
            raise ValueError()
    except ValueError:
        return jsonify({"error": "Invalid time format, expected HH:MM"}), 400

    result = db.session.execute(
        text("UPDATE settings SET value = :v WHERE key = 'default_session_time'"),
        {"v": data["time"]}
    )
    if result.rowcount == 0:
        db.session.execute(
            text("INSERT INTO settings (key, value) VALUES ('default_session_time', :v)"),
            {"v": data["time"]}
        )

    sydney = pytz.timezone("Australia/Sydney")
    sessions = db.session.query(Session).all()
    for session in sessions:
        date_sydney = session.datetime.astimezone(sydney).date()
        dt_sydney = sydney.localize(datetime.combine(date_sydney, time(hour=hour, minute=minute)))
        dt_utc = dt_sydney.astimezone(pytz.utc)
        session.datetime = dt_utc

    db.session.commit()
    return jsonify({"message": "Default session time updated and all sessions updated"})

# --- Clean expired sessions and create new one if needed ---
@app.route("/api/clean", methods=["GET"])
def clean_expired_sessions():
    now = datetime.now(SYDNEY)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("ignite-late-record").sheet1
    records = sheet.get_all_records()
    names_col = [row["이름"] for row in records]

    cleaned = 0
    created = 0
    sessions = Session.query.all()
    expired_sessions = []

    for session in sessions:
        if now < session.datetime + timedelta(minutes=5):
            continue
        expired_sessions.append(session)
        late_members = [m.name for m in session.members]
        for member in late_members:
            if member in names_col:
                row_index = names_col.index(member) + 2
                count_cell = f"B{row_index}"
                prev = int(sheet.acell(count_cell).value)
                sheet.update(count_cell, str(prev + 1))
            else:
                sheet.append_row([member, "1"])
        db.session.delete(session)
        cleaned += 1

    if expired_sessions or not sessions:
        hour, minute = get_default_session_time()
        days_ahead = 6 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_sunday = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        all_members = Member.query.all()
        new_session = Session(datetime=next_sunday)
        new_session.members.extend(all_members)
        db.session.add(new_session)
        created = 1

    db.session.commit()
    return jsonify({"status": "cleaned", "sessions_deleted": cleaned, "sessions_created": created})
