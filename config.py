import os
basedir = os.path.abspath(os.path.dirname(__file__))

# def gen_connection_string():
#     # if not on Google then use local MySQL
#     print("SERVER_SOFTWARE: {0}".format(os.getenv('SERVER_SOFTWARE', 'default')))
#     if not os.getenv('SERVER_SOFTWARE', '').startswith('gunicorn/'):
#         return 'sqlite:///' + os.path.join(basedir, 'app.db')
#     else:
#         conn_name = os.environ.get('CLOUDSQL_CONNECTION_NAME' '')
#         sql_user = os.environ.get('CLOUDSQL_USER', 'root')
#         sql_pass = os.environ.get('CLOUDSQL_PASSWORD', '')
#         conn_template = 'mysql://%s:%s@/bravebpc?unix_socket=/cloudsql/%s'
#         return conn_template % (sql_user, sql_pass, conn_name)


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    # SQLALCHEMY_DATABASE_URI = gen_connection_string()
    # SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTH_KEY = os.environ.get('AUTH_KEY') or 'you-will-never-guess'
    DEV_AUTH_KEY = os.environ.get('DEV_AUTH_KEY') or AUTH_KEY
    ROOT_PATH = os.environ.get('ROOT_PATH') or '/tmp/'
