from flask import Flask, request, jsonify, abort, make_response
from datetime import datetime, timedelta
import os
import pytz
import uuid
import json
from functools import wraps
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from .models import db, Member, Session, SessionMember

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

@app.route("/api/session", methods=["POST"])
@require_admin
def create_session():
    data = request.json
    dt_str = f"{data['date']}T{data['time']}:00"
    dt = datetime.fromisoformat(dt_str)
    dt = SYDNEY.localize(dt).astimezone(pytz.UTC) 
    session_id = str(uuid.uuid4())  # Generate UUID string manually

    session = Session(id=session_id, datetime=dt)
    db.session.add(session)
    db.session.flush()

    for name in data["members"]:
        member = Member.query.filter_by(name=name).first()
        if member:
            db.session.add(SessionMember(session_id=session.id, member_id=member.id))

    db.session.commit()
    return jsonify({"session_id": session_id})

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

    sessions = Session.query.all()
    for session in sessions:
        if now < session.datetime + timedelta(minutes=5):
            continue  # Skip if not yet expired

        late_members = [m.name for m in session.members]  # Assuming many-to-many relationship

        for member in late_members:
            if member in names_col:
                row_index = names_col.index(member) + 2
                count_cell = f"B{row_index}"
                prev = int(sheet.acell(count_cell).value)
                sheet.update(count_cell, str(prev + 1))
            else:
                sheet.append_row([member, "1"])

        # Delete session and links
        db.session.delete(session)
        cleaned += 1

    db.session.commit()
    return jsonify({"status": "cleaned", "sessions_deleted": cleaned})


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