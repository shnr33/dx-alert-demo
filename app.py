"""
DX-Alert-Demo.

A demo app to listen to dropbox events and send an email alert on file events
"""
import hmac
import threading
import urlparse
import json
import sqlite3
import shelve
import logging
from logging.handlers import RotatingFileHandler
from hashlib import sha256
from flask import Flask, request, render_template, redirect, url_for, \
    session, abort, g, flash
from dropbox import DropboxOAuth2Flow, dropbox
from dropbox.oauth import BadRequestException, BadStateException, \
    CsrfException, NotApprovedException, ProviderException
from dropbox.files import DeletedMetadata, FileMetadata, FolderMetadata
from flask_mail import Mail, Message


app = Flask(__name__)
app.config.from_pyfile('config_file.cfg')

mail = Mail(app)

# Shelve objects to keep track of access_tokens and cursors of dropbox users
# These act as persistent dictionaries.
tokens_of_user = shelve.open('user_tokens')
cursors = shelve.open('cursors')


def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Initialized the database.')


def get_db():
    """
    Opens a new database connection if there is none yet for the
    current application context.
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """
    Helper function to get close connection to the database.

    Closes the database at the end of the request.
    """
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """Helper function to get query the database."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def insert_update_db(insert_statement, args=()):
    db = get_db()
    db.execute(insert_statement, args)
    db.commit()


def get_url(route):
    """Generate a proper URL, forcing HTTPS if not running locally."""
    host = urlparse.urlparse(request.url).hostname
    url = url_for(
        route,
        _external=True,
        _scheme='http' if host in ('127.0.0.1', 'localhost') else 'https'
    )

    return url


def get_flow():
    """Helper function to get the Oauth2 Flow."""
    return DropboxOAuth2Flow(
        app.config['APP_KEY'],
        app.config['APP_SECRET'],
        get_url('oauth_callback'),
        session,
        'dropbox-auth-csrf-token')


@app.route('/')
def index():
    """Index page."""
    return render_template("index.html")


@app.route('/dropbox-connect', methods=['POST'])
def dropbox_connect():
    """Main function to save the email and start the Oauth flow."""
    email = request.form['email']
    user = query_db('select * from users where email = ?', (email,), one=True)

    if not user:
        # If the user doesn't exist already, create a new row.
        insert_update_db('insert into users(email) values (?)', (email,))
    return redirect(get_flow().start(email))


@app.route('/oauth_callback')
def oauth_callback():
    """Callback function for when the user returns from OAuth."""
    try:
        oauth_result = get_flow().finish(request.args)
    except BadRequestException, e:
        abort(400)
    except BadStateException, e:
        # Start the auth flow again.
        redirect("/index")
    except CsrfException, e:
        abort(403)
    except NotApprovedException, e:
        flash('Not approved?  Why not?')
        return redirect("/index")
    except ProviderException, e:
        app.logger.error("Auth error: %s" % (e,))
        abort(403)

    # oauth_result contains - access_token, account_id, user_id, url_state
    uid = oauth_result.user_id
    access_token = oauth_result.access_token
    email = oauth_result.url_state

    tokens_of_user[uid] = access_token
    insert_update_db('update users set uid = ?, alert_enabled = ? where email = ?', (uid, True, email))

    process_user(uid)

    return redirect(url_for('alert_config'))


@app.route('/alert_config')
def alert_config():
    """Final page after oauth flow."""
    users = query_db('select * from users')
    return render_template("alert_config.html", users=users)


@app.route('/change_alert', methods=['POST'])
def change_alert():
    """View method to change the alert status for emails"""
    alert_check = request.form.getlist('alert_check')
    # alert_check will be of format: email-Yes or email-No
    for data in alert_check:
        user_email, status = data.split('-')  # Email will be part of the value returned from options
        alert_enabled = True if status == 'Yes' else False
        insert_update_db('update users set alert_enabled = ? where email = ?', (alert_enabled, user_email))
    return redirect(url_for('alert_config'))


def send_alerts(uid, user_name, new_files, new_folders, deleted_files):
    with app.app_context():
        # Need to use app_context since this is run through a separate thread.
        users = query_db('select email, alert_enabled from users where uid = ?', (uid,))
        # If there are multiple emails tagged for same Dropbox user id,
        # sending alerts for all the emails.
        for user in users:
            email, alert_enabled = user

            if alert_enabled:
                # If alert_enabled for this user, send alert
                app.logger.info('Sending email alert to - {}'.format(email))
                msg = Message('Dropbox File change alert',
                              recipients=[email]
                              )
                msg.html = render_template("mail.html", **({'user_name': user_name,
                                                            'new_files': new_files,
                                                            'new_folders': new_folders,
                                                            'deleted_files': deleted_files}
                                                           )
                                           )
                mail.send(msg)


def process_user(uid):
    """Call /files/list_folders for the given user ID and process any changes."""

    uid = str(uid)  # Converting to string, since shelve accepts only strings as keys.
    token = tokens_of_user[uid]
    client = dropbox.Dropbox(token)

    user_account = client.users_get_current_account()
    user_name = user_account.name.display_name

    deleted_files = []
    new_files = []
    new_folders = []

    cursor = cursors.get(uid)
    if not cursor:
        result = client.files_list_folder_get_latest_cursor(path='',
                                                            recursive=True,
                                                            include_deleted=True)
        cursor = result.cursor

    has_more = True

    while has_more:
        result = client.files_list_folder_continue(cursor)

        for metadata in result.entries:
            if isinstance(metadata, DeletedMetadata):
                deleted_files.append(metadata.name)
            elif isinstance(metadata, FileMetadata):
                new_files.append(metadata.name)
            elif isinstance(metadata, FolderMetadata):
                new_folders.append(metadata.name)

        cursors[uid] = result.cursor

        # Repeat only if there's more to do
        has_more = result.has_more

    # print "New files-{}".format(new_files)
    # print "Deleted files n folders-{}".format(deleted_files)
    # print "New Folders-{}".format(new_folders)

    if new_files or new_folders or deleted_files:
        # If one of these list has any values, send email alerts
        send_alerts(uid, user_name, new_files, new_folders, deleted_files)


def validate_request():
    """
    Validate that the request is properly signed by Dropbox.
    (If not, this is a spoofed webhook.)
    """
    signature = request.headers.get('X-Dropbox-Signature')
    return signature == hmac.new(app.config['APP_SECRET'], request.data, sha256).hexdigest()


@app.route('/webhook', methods=['GET'])
def challenge():
    """
    Respond to the webhook challenge (GET request) by echoing back the challenge parameter.
    """
    return request.args.get('challenge')


@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive a list of changed user IDs from Dropbox and process each."""
    # Make sure this is a valid request from Dropbox
    if not validate_request():
        abort(403)

    for uid in json.loads(request.data)['delta']['users']:
        # We need to respond quickly to the webhook request, so we do the
        # actual work in a separate thread. For more robustness, it's a
        # good idea to add the work to a reliable queue and process the queue
        # in a worker process.
        threading.Thread(target=process_user, args=(uid,)).start()
    return ''

if __name__ == '__main__':
    handler = RotatingFileHandler('dx-alert-demo.log', maxBytes=10000,
                                  backupCount=1)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.run()
