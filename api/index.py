from flask import Flask, request, jsonify, abort, make_response
from datetime import datetime, timedelta
import os
import pytz
import json
from functools import wraps
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from .models import db, Member, Session, SessionMember
from sqlalchemy import text, func


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

def get_default_session_time():
    row = db.session.execute(
        text("SELECT value FROM settings WHERE key = 'default_session_time'")
    ).fetchone()
    if not row:
        return (16, 5)  # fallback default
    hour_str, minute_str = row[0].split(":")
    return int(hour_str), int(minute_str)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if data.get("password") == ADMIN_TOKEN:
        resp = make_response(jsonify({"status": "success"}))
        resp.set_cookie("admin_token", ADMIN_TOKEN, httponly=True, max_age=86400)
        return resp
    return jsonify({"error": "unauthorized"}), 401

@app.route("/api/members", methods=["GET", "POST"])
@require_admin
def edit_members():
    if request.method == "POST":
        data = request.json
        new_names = set(data.get("members", []))

        # Step 1: Get current members from DB
        existing_members = Member.query.all()
        existing_names = set(m.name for m in existing_members)

        # Step 2: Add any new members
        for name in new_names - existing_names:
            db.session.add(Member(name=name))

        # Step 3: Safely delete members not in the new list
        for member in existing_members:
            if member.name not in new_names:
                # Check if the member is still referenced
                in_use = SessionMember.query.filter_by(member_id=member.id).first()
                if not in_use:
                    db.session.delete(member)

        db.session.commit()
        return jsonify({"status": "updated"})

    # GET
    members = Member.query.all()
    return jsonify([m.name for m in members])

# @app.route("/api/session/<session_id>", methods=["PUT"])
# @require_admin
# def update_session_time(session_id):
#     data = request.json
#     if "time" not in data:
#         return jsonify({"error": "Missing 'time' in request body"}), 400

#     # Fetch existing session
#     session = Session.query.get(int(session_id))
#     if not session:
#         return jsonify({"error": "Session not found"}), 404

#     # Parse the new time
#     try:
#         hour, minute = map(int, data["time"].split(":"))
#     except ValueError:
#         return jsonify({"error": "Invalid time format, expected HH:MM"}), 400

#     # Replace the time part while keeping the date
#     old_dt = session.datetime.astimezone(SYDNEY)
#     new_dt = old_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

#     # Convert back to UTC for storage
#     new_dt_utc = new_dt.astimezone(pytz.UTC)
#     session.datetime = new_dt_utc

#     db.session.commit()
#     return jsonify({"message": "Session time updated successfully"})

from datetime import datetime, time
import pytz

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

    # Update or insert the default time in settings
    result = db.session.execute(
        text("UPDATE settings SET value = :v WHERE key = 'default_session_time'"),
        {"v": data["time"]}
    )
    if result.rowcount == 0:
        db.session.execute(
            text("INSERT INTO settings (key, value) VALUES ('default_session_time', :v)"),
            {"v": data["time"]}
        )

    # Load Sydney timezone
    sydney = pytz.timezone("Australia/Sydney")

    # Fetch all sessions
    sessions = db.session.query(Session).all()
    for session in sessions:
        # Convert datetime to Sydney timezone to get local date
        date_sydney = session.datetime.astimezone(sydney).date()
        # Combine date and user-input time as Sydney time
        dt_sydney = sydney.localize(datetime.combine(date_sydney, time(hour=hour, minute=minute)))
        # Convert to UTC
        dt_utc = dt_sydney.astimezone(pytz.utc)
        # Update session datetime
        session.datetime = dt_utc

    db.session.commit()

    return jsonify({"message": "Default session time updated and all sessions updated"})



@app.route("/api/sessions", methods=["GET"])
@require_admin
def get_sessions():
    sessions = Session.query.all()
    data = []
    for s in sessions:
        members = db.session.query(Member.name).join(SessionMember, Member.id == SessionMember.member_id).filter(SessionMember.session_id == s.id).all()
        data.append({
            "id": str(s.id),
            "datetime": s.datetime.isoformat(),
            "members": [m[0] for m in members]
        })
    return jsonify(data)

@app.route("/api/clean", methods=["GET"])
def clean_expired_sessions():
    now = datetime.now(pytz.timezone("Australia/Sydney"))

    # Setup Google Sheets
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
            continue  # Not expired
        expired_sessions.append(session)

        # Update lateness counts
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

    # If there were expired sessions, create a new session for the following Sunday
    if expired_sessions or not sessions:
        # Get configured default time
        hour, minute = get_default_session_time()

        # Compute next Sunday at that time
        days_ahead = 6 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_sunday = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        # Get all members
        all_members = Member.query.all()

        # Create the new session with all members
        new_session = Session(datetime=next_sunday)
        new_session.members.extend(all_members)

        db.session.add(new_session)
        created = 1


    db.session.commit()

    return jsonify({"status": "cleaned", "sessions_deleted": cleaned, "sessions_created": created})

@app.route("/api/<session_id>", methods=["GET"])
def get_session(session_id):
    session = Session.query.get(session_id)
    if not session:
        return jsonify({"error": "not found"}), 404

    members = (
        db.session.query(Member.name)
        .join(SessionMember, Member.id == SessionMember.member_id)
        .filter(SessionMember.session_id == session_id)
        .all()
    )

    return jsonify({
        "id": session.id,
        "datetime": session.datetime.isoformat(),
        "members": [name for (name,) in members],
    })

@app.route("/api/<session_id>/remove", methods=["POST"])
def remove_member_from_session(session_id):
    name = request.json.get("name")
    member = Member.query.filter_by(name=name).first()
    if not member:
        return jsonify({"error": "invalid member"}), 400

    session = Session.query.get(session_id)
    if not session:
        return jsonify({"error": "session not found"}), 404

    # ✅ Check if it's over 5 minutes past the session time
    now = datetime.now(pytz.timezone("Australia/Sydney"))
    session_time = session.datetime.astimezone(pytz.timezone("Australia/Sydney"))

    if now > session_time + timedelta(minutes=5):
        return jsonify({"error": "출석 시간이 마감되었습니다"}), 403

    db.session.query(SessionMember).filter_by(
        session_id=session_id,
        member_id=member.id
    ).delete()

    db.session.commit()
    return jsonify({"status": "removed"})