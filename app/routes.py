from app import app, db, esi
from app.forms import LoginForm, RequestForm, CompleteForm
from app.models import User, Request
from collections import OrderedDict
from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_user, logout_user
import datetime
import json
import requests as req
import swagger_client
from swagger_client.rest import ApiException


@app.route('/')
@app.route('/index')
def index():
    is_brave_collective = False
    is_brave_industries = False
    allow_request = False
    bpc_data = OrderedDict()
    form = RequestForm()

    # print(current_user.is_authenticated)
    if current_user.is_authenticated:
        api = swagger_client.CharacterApi()
        api.api_client.set_default_header('User-Agent', 'brave-bpc')
        api.api_client.host = "https://esi.tech.ccp.is"

        response = api.get_characters_character_id(current_user.user_id)

        # print(response)

        if response.alliance_id == 99003214:
            is_brave_collective = True
        if response.corporation_id == 98445423:
            is_brave_industries = True

        reqs = Request.query.filter_by(complete_time=None, char_id=current_user.user_id).first()
        if reqs is None:
            allow_request = True
        # Check if the user has an outstanding request

        esi.update_bp_data()

        with open('bps2.json') as json_file:
            raw_data = json.load(json_file)

        bpc_names = sorted(raw_data['bpcs'])
        for name in bpc_names:
            bpc_data[name] = raw_data['bpcs'][name]

        # print(bpc_data)

    return render_template('index.html',
                           form=form,
                           title='Home',
                           bpcs=bpc_data,
                           allow_request=allow_request,
                           is_brave_industries=is_brave_industries,
                           is_brave_collective=is_brave_collective)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        flash('Login requested for user {}, remember_me={}'.format(
            form.username.data, form.remember_me.data))
        return redirect(url_for('index'))
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if current_user.is_anonymous:
        return redirect(url_for('index'))
    requested = 0
    print("User '{0}' ({1}) is requesting the following:".format(current_user.username,
                                                                 current_user.user_id))
    output = ''
    for item in request.values:
        if item == "csrf_token":
            continue
        if item == "submit":
            continue
        if request.values[item]:
            requested += int(request.values[item])
            print("  {0}: {1}".format(item, request.values[item]))
            output = '{0}{1}_{2}\n'.format(output, item, request.values[item])
    print(requested)
    print(output)

    if requested > 10:
        return redirect(url_for('index'))

    new_request = Request(request=output,
                          create_time=datetime.datetime.utcnow(),
                          char_id=current_user.user_id,
                          complete_time=None,
                          completed_by=None)

    db.session.add(new_request)
    db.session.commit()

    return redirect(url_for('requests'))


@app.route('/requests', methods=['GET'])
def requests():
    if current_user.is_anonymous:
        return redirect(url_for('index'))
    is_brave_collective = False
    is_brave_industries = False
    data = {}
    form = CompleteForm()
    if current_user.is_authenticated:
        api = swagger_client.CharacterApi()
        api.api_client.set_default_header('User-Agent', 'brave-bpc')
        api.api_client.host = "https://esi.tech.ccp.is"

        response = api.get_characters_character_id(current_user.user_id)

        if response.alliance_id == 99003214:
            is_brave_collective = True
        if response.corporation_id == 98445423:
            is_brave_industries = True

        reqs = {}
        if is_brave_industries:
            reqs = Request.query.filter_by(complete_time=None)
        elif is_brave_collective:
            reqs = Request.query.filter_by(complete_time=None, char_id=current_user.user_id)

        for entry in reqs:
            data[entry.id] = []
            items = entry.request.split('\n')
            for item in items:
                if item == "":
                    continue
                print(item)
                tokens = item.split('_')
                user = User.query.filter_by(user_id=entry.char_id).first()
                temp = {"Character": user.username,
                        'Name': tokens[0],
                        'ME': tokens[1],
                        'TE': tokens[2],
                        'Runs': tokens[3],
                        'Copies': tokens[4],
                        'Completed': False}
                data[entry.id].append(temp)

    return render_template('requests.html',
                           form=form,
                           title='Requests',
                           requests=data,
                           is_brave_industries=is_brave_industries,
                           is_brave_collective=is_brave_collective)


@app.route('/todo', methods=['GET'])
def todo():
    if current_user.is_anonymous:
        return redirect(url_for('index'))
    data = {}
    form = CompleteForm()
    bpo_data = OrderedDict()
    is_brave_collective = False
    is_brave_industries = False

    if current_user.is_authenticated:
        is_brave_industries = False
        api = swagger_client.CharacterApi()
        api.api_client.set_default_header('User-Agent', 'brave-bpc')
        api.api_client.host = "https://esi.tech.ccp.is"

        response = api.get_characters_character_id(current_user.user_id)

        if response.alliance_id == 99003214:
            is_brave_collective = True
        if response.corporation_id == 98445423:
            is_brave_industries = True

        if not is_brave_industries:
            return redirect(url_for('index'))

    esi.update_bp_data()
    esi.update_job_data()

    with open('bps2.json') as json_file:
        raw_data = json.load(json_file)

    with open('jobs.json') as json_file:
        job_data = json.load(json_file)

    bpo_names = sorted(raw_data['bpos'])
    for name in bpo_names:
        bpo_data[name] = raw_data['bpos'][name]

    needed_copies = {}

    for name in bpo_names:
        max_runs = 0
        qty = 0
        if name in raw_data['bpcs'] and "10" in raw_data['bpcs'][name] and "20" in raw_data['bpcs'][name]['10']:
            for entry in raw_data['bpcs'][name]['10']['20']:
                if entry == 'variants':
                    continue
                runs = int(entry)
                if runs > max_runs:
                    max_runs = runs
                    qty = raw_data['bpcs'][name]['10']['20'][entry]
        if qty < 5:
            needed_copies[name] = [qty, False, False]
    
    for job in job_data:
        if job["name"] in needed_copies:
            if job["activity_id"] == 3 or job["activity_id"] == 4:
                needed_copies[job["name"]][2] = True
            if job["activity_id"] == 5:
                needed_copies[job["name"]][1] = True

    return render_template('todo.html',
                           form=form,
                           title='Work To Do',
                           requests=data,
                           needed=needed_copies,
                           is_brave_industries=is_brave_industries,
                           is_brave_collective=is_brave_collective)


@app.route('/callback')
def callback():
    code = request.args.get('code')
    url = "https://login.eveonline.com/oauth/token"
    payload = {"grant_type": "authorization_code",
               "code": code}
    data = json.dumps(payload)
    headers = {'Content-Type': 'application/json',
               'Authorization': 'Basic ' + app.config['AUTH_KEY']}

    r = req.post(url, data=data, headers=headers)
    raw = r.json()

    access_token = raw['access_token']
    refresh_token = raw['refresh_token']

    url = "https://login.eveonline.com/oauth/verify"
    headers = {'Content-Type': 'application/json',
               'Authorization': 'Bearer {0}'.format(str(access_token))}

    r2 = req.get(url, headers=headers)
    raw = r2.json()

    username = raw['CharacterName']
    char_id = raw['CharacterID']
    
    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username, user_id=char_id, refresh_token=refresh_token)
        db.session.add(user)
        db.session.commit()
    
    login_user(user, remember=True)

    return render_template('view.html', raw=raw, access_token=access_token, refresh_token=refresh_token)


@app.route('/complete', methods=['GET', 'POST'])
def complete():
    if current_user.is_anonymous:
        return redirect(url_for('index'))

    print("User '{0}' ({1}) is completing the following requests:".format(current_user.username,
                                                                          current_user.user_id))
    output = ""
    for item in request.values:
        if item == "csrf_token":
            continue
        if item == "submit":
            continue
        if request.values[item]:
            print("  {0}: {1}".format(item, request.values[item]))
            output = '{0}{1}_{2}\n'.format(output, item, request.values[item])
            order = Request.query.filter_by(id=item).first()
            print(order)
            order.complete_time = datetime.datetime.utcnow()
            order.completed_by = current_user.user_id
            db.session.commit()

    return redirect(url_for('requests'))
