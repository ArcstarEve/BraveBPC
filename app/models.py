from app import db, login
from datetime import datetime
from flask_login import UserMixin


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), index=True, unique=True)
    user_id = db.Column(db.Integer, unique=True)
    refresh_token = db.Column(db.String(128))
    requests = db.relationship('Request', backref='requester', lazy='dynamic')

    def __repr__(self):
        return '<User {}>'.format(self.username)


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request = db.Column(db.String(4096))
    create_time = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    char_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))
    complete_time = db.Column(db.DateTime)
    completed_by = db.Column(db.Integer)

    def __repr__(self):
        return '<Post {}>'.format(self.request)


@login.user_loader
def load_user(id):
    return User.query.get(id)
