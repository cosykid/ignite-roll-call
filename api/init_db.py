from .models import db
from .index import app

with app.app_context():
    db.create_all()
