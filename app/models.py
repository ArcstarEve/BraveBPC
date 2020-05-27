from app import db, login, client
from datetime import datetime
from flask_login import UserMixin


class User(UserMixin):
    username = ""
    id = 0
    refresh_token = ""

    def __init__(self, user, user_id, token):
        self.username = user
        self.id = user_id
        self.refresh_token = token

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
    print(id)
    query = client.query(kind='User')
    entities = list(query.fetch())
    # entity = list(query.add_filter('user_id', '=', id).fetch(1))
    for entity in entities:
        print(entity)
        print(entity['user_id'])
        if str(entity['user_id']) == str(id):
            return User(entity['username'], entity['user_id'], entity['refresh_token'])
    return User(entity['username'], entity['user_id'], entity['refresh_token'])
    # return client.get(key)
