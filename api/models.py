from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import TIMESTAMP

db = SQLAlchemy()

class Member(db.Model):
    __tablename__ = 'members'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, unique=True, nullable=False)

class Session(db.Model):
    __tablename__ = 'sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # <-- auto increment
    datetime = db.Column(TIMESTAMP(timezone=True), nullable=False)
    members = db.relationship(
        "Member",
        secondary="session_members",
        backref="sessions",
        passive_deletes=True
    )

class SessionMember(db.Model):
    __tablename__ = 'session_members'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey('sessions.id', ondelete="CASCADE")
    )
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'))
