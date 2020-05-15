from app import app, db
from app.models import User, Request


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Request': Request}

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
