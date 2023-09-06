from app import app, client, esi
from app.forms import LoginForm, RequestForm, CompleteForm
from app.models import User, Request
from collections import OrderedDict
from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_user, logout_user
from datetime import datetime, timezone
import json
import requests as req
import swagger_client
from google.cloud import datastore
from swagger_client.rest import ApiException


def my_sort(value):
    if value == 'variants':
        return 1000
    return int(value)


@app.route('/')
@app.route('/index')
def index():
    is_brave_collective = False
    is_brave_industries = False
    allow_request = False
    bpc_data = OrderedDict()
    form = RequestForm()

    if current_user.is_authenticated:
        api = swagger_client.CharacterApi()
        api.api_client.set_default_header('User-Agent', 'brave-bpc')
        api.api_client.host = "https://esi.evetech.net"

        response = api.get_characters_character_id(current_user.id)

        if response.alliance_id == 99003214 or response.alliance_id == 99010079:
            is_brave_collective = True
        if response.corporation_id == 98445423:
            is_brave_industries = True

        # Check if the user has an outstanding request
        query = client.query(kind='Request')
        query.add_filter('complete_time', '=', None)
        reqs = list(query.add_filter('char_id', '=', current_user.id).fetch())
        if len(reqs) == 0:
            allow_request = True

        esi.update_bp_data()

        with open('{0}bps2.json'.format(app.config['ROOT_PATH'])) as json_file:
            raw_data = json.load(json_file)

        bpc_names = sorted(raw_data['bpcs'])
        for name in bpc_names:
            bpc_data[name] = {}
            mes = sorted(raw_data['bpcs'][name], reverse=True, key=my_sort)
            for me in mes:
                if me == 'variants':
                    bpc_data[name]['variants'] = raw_data['bpcs'][name]['variants']
                    continue
                bpc_data[name][me] = {}
                tes = sorted(raw_data['bpcs'][name][me], reverse=True, key=my_sort)
                for te in tes:
                    if te == 'variants':
                        bpc_data[name][me]['variants'] = raw_data['bpcs'][name][me]['variants']
                        continue
                    bpc_data[name][me][te] = {}
                    runs = sorted(raw_data['bpcs'][name][me][te], reverse=True, key=my_sort)
                    for run in runs:
                        if run == 'variants':
                            bpc_data[name][me][te]['variants'] = raw_data['bpcs'][name][me][te]['variants']
                            continue
                        bpc_data[name][me][te][run] = raw_data['bpcs'][name][me][te][run]
            bpc_data[name]['have_bpo'] = (name in raw_data['bpos'])

    return render_template('index.html',
                           form=form,
                           title='Home',
                           bpcs=bpc_data,
                           allow_request=allow_request,
                           is_brave_industries=is_brave_industries,
                           is_brave_collective=is_brave_collective)


@app.route('/sales')
def sales():
    is_brave_collective = False
    is_brave_industries = False
    bpo_data = OrderedDict()

    # print(current_user.is_authenticated)
    if current_user.is_authenticated:
        api = swagger_client.CharacterApi()
        api.api_client.set_default_header('User-Agent', 'brave-bpc')
        api.api_client.host = "https://esi.evetech.net"

        response = api.get_characters_character_id(current_user.id)

        # print(response)

        if response.alliance_id == 99003214 or response.alliance_id == 99010079:
            is_brave_collective = True
        if response.corporation_id == 98445423:
            is_brave_industries = True

        esi.update_bp_data()

        with open('{0}bps2.json'.format(app.config['ROOT_PATH'])) as json_file:
            raw_data = json.load(json_file)

        bpo_names = sorted(raw_data['bpos'])
        for name in bpo_names:
            bpos = raw_data['bpos'][name]
            qty = 0
            for mes in bpos:
                if mes == 'variants':
                    continue
                for tes in bpos[mes]:
                    if tes == 'variants':
                        continue
                    qty += bpos[mes][tes]
            if qty > 2:
                bpo_data[name] = qty - 2

    return render_template('sales.html',
                           title='Sales',
                           extra_bpos=bpo_data,
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
                                                                 current_user.id))
    output = ''
    print(request.values)
    for item in request.values:
        if item == "csrf_token":
            continue
        if item == "submit":
            continue
        if request.values[item] and int(request.values[item]) != 0:
            requested += int(request.values[item])
            print("  {0}: {1}".format(item, request.values[item]))
            output = '{0}{1}_{2}\n'.format(output, item, request.values[item])
    print(requested)
    print(output)

    if requested == 0:
        flash('Please select at least one item before submitting a request.')
        return redirect(url_for('index'))

    if requested > 10:
        flash('Please limit your requests to 10 BPCs at a time.')
        return redirect(url_for('index'))

    new_request = Request(request=output,
                          create_time=datetime.utcnow(),
                          char_id=current_user.id,
                          complete_time=None,
                          completed_by=None)

    new_req = datastore.Entity(client.key('Request'))
    new_req.update({'request': new_request.request,
                    'create_time': new_request.create_time,
                    'char_id': new_request.char_id,
                    'complete_time': new_request.complete_time,
                    'completed_by': new_request.completed_by})
    client.put(new_req)
    # db.session.add(new_request)
    # db.session.commit()

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
        api.api_client.host = "https://esi.evetech.net"

        response = api.get_characters_character_id(current_user.id)

        if response.alliance_id == 99003214 or response.alliance_id == 99010079:
            is_brave_collective = True
        if response.corporation_id == 98445423:
            is_brave_industries = True

        reqs = {}
        if is_brave_industries:
            query = client.query(kind='Request')
            reqs = list(query.add_filter('complete_time', '=', None).fetch())
        elif is_brave_collective:
            query = client.query(kind='Request')
            query.add_filter('complete_time', '=', None)
            reqs = list(query.add_filter('char_id', '=', current_user.id).fetch())

        i = 1
        for entry in reqs:
            data[i] = []
            items = entry['request'].split('\n')
            # items = entry.request.split('\n')
            query = client.query(kind='User')
            user = list(query.add_filter('user_id', '=', entry['char_id']).fetch())[0]
            now = datetime.now(timezone.utc)
            delta = str(now - entry['create_time'])
            delta = delta.split('.', 2)[0]
            print(delta)
            for item in items:
                if item == "":
                    continue
                # print(item)
                tokens = item.split('_')
                # user = User.query.filter_by(user_id=entry.char_id).first()
                temp = {"Character": user['username'],
                        'ID': user['user_id'],
                        'Name': tokens[0],
                        'ME': tokens[1],
                        'TE': tokens[2],
                        'Runs': tokens[3],
                        'Copies': tokens[4],
                        'Age': delta,
                        'Completed': False}
                data[i].append(temp)
            i += 1

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
        api.api_client.host = "https://esi.evetech.net"

        response = api.get_characters_character_id(current_user.id)

        if response.alliance_id == 99003214 or response.alliance_id == 99010079:
            is_brave_collective = True
        if response.corporation_id == 98445423:
            is_brave_industries = True

        if not is_brave_industries:
            return redirect(url_for('index'))

    esi.update_bp_data()
    esi.update_job_data()

    ignore = ['Civilian Data Analyzer Blueprint',
              'Improved Frentix Booster Reaction Formula',
              'Standard Frentix Booster Reaction Formula',
              'Axosomatic Neurolink Enhancer Reaction Formula',
              'C3-FTM Acid Reaction Formula',
              'Caesarium Cadmide Reaction Formula',
              'Carbon Fiber Reaction Formula',
              'Carbon Polymers Reaction Formula',
              'Carbon-86 Epoxy Resin Reaction Formula',
              'Ceramic Powder Reaction Formula',
              'Cogni-Emotive Neurolink Enhancer Reaction Formula',
              'Crystalline Carbonide Reaction Formula',
              'Crystallite Alloy Reaction Formula',
              'Dysporite Reaction Formula',
              'Fernite Alloy Reaction Formula',
              'Fernite Carbide Reaction Formula',
              'Ferrogel Reaction Formula',
              'Fluxed Condensates Reaction Formula',
              'Fullerene Intercalated Graphite Reaction Formula',
              'Fulleroferrocene Reaction Formula',
              'Goal-Orienting Neurolink Stabilizer Reaction Formula',
              'Graphene Nanoribbons Reaction Formula',
              'Hexite Reaction Formula',
              'Hypnagogic Neurolink Enhancer Reaction Formula',
              'Isotropic Neofullerene Alpha-3 Reaction Formula',
              'Isotropic Neofullerene Beta-6 Reaction Formula',
              'Isotropic Neofullerene Gamma-9 Reaction Formula',
              'Lanthanum Metallofullerene Reaction Formula',
              'Methanofullerene Reaction Formula',
              'Neo Mercurite Reaction Formula',
              'Nonlinear Metamaterials Reaction Formula',
              'Oxy-Organic Solvents Reaction Formula',
              'PPD Fullerene Fibers Reaction Formula',
              'Phenolic Composites Reaction Formula',
              'Plasmonic Metamaterials Reaction Formula',
              'Pressurized Oxidizers Reaction Formula',
              'Prometium Reaction Formula',
              'Reinforced Carbon Fiber Reaction Formula',
              'Rolled Tungsten Alloy Reaction Formula',
              'Scandium Metallofullerene Reaction Formula',
              'Silicon Diborite Reaction Formula',
              'Solerium Reaction Formula',
              'Stress-Responding Neurolink Stabilizer Reaction Formula',
              'Sylramic Fibers Reaction Formula',
              'Synth Crash Booster Reaction Formula',
              'Terahertz Metamaterials Reaction Formula',
              'Thermosetting Polymer Reaction Formula',
              'Thulium Hafnite Reaction Formula',
              'Titanium Carbide Reaction Formula',
              'Ultradian-Cycling Neurolink Stabilizer Reaction Formula',
              'Unrefined Dysporite Reaction Formula',
              'Unrefined Ferrofluid Reaction Formula',
              'Unrefined Fluxed Condensates Reaction Formula',
              'Unrefined Hexite Reaction Formula',
              'Unrefined Hyperflurite Reaction Formula',
              'Unrefined Neo Mercurite Reaction Formula',
              'Unrefined Promethium Mercurite Reaction Formula',
              'Unrefined Prometium Reaction Formula',
              'Unrefined Solerium Reaction Formula',
              'Unrefined Titanium Chromide Reaction Formula',
              'Unrefined Vanadium Hafnite Reaction Formula',
              'Vanadium Hafnite Reaction Formula']
    adjust = ['Ansiblex Jump Gate Blueprint',
              'Apocalypse Blueprint',
              'Apostle Blueprint',
              'Athanor Blueprint',
              'Chimera Blueprint',
              'Heavy Fleeting Compact Warp Disruptor Blueprint',
              'Heavy J5 Enduring Warp Disruptor Blueprint',
              'Heavy J5b Enduring Warp Scrambler Blueprint',
              'Heavy Warp Scrambler I Blueprint',
              'Ion Siege Blaster I Blueprint',
              'Lif Blueprint',
              'Nidhoggur Blueprint',
              'Pharolux Cyno Beacon Blueprint',
              'Rapid Torpedo Launcher I Blueprint',
              'Standup Einherji I Blueprint',
              'Standup Equite I Blueprint',
              'Standup Guided Bomb Launcher I Blueprint',
              'Standup M-Set Biochemical Reactor Time Efficiency I Blueprint',
              'Structure Acceleration Coils Blueprint',
              'Structure Advertisement Nexus Blueprint',
              'Structure Construction Parts Blueprint',
              'Structure Docking Bay Blueprint',
              'Structure EXERT Conduit Coupler Blueprint',
              'Structure Electromagnetic Sensor Blueprint',
              'Structure Factory Blueprint',
              'Structure Hangar Array Blueprint',
              'Structure Laboratory Blueprint',
              'Structure Medical Center Blueprint',
              'Structure Office Center Blueprint',
              'Structure Repair Facility Blueprint',
              'Structure Reprocessing Plant Blueprint',
              'Structure Storage Bay Blueprint',
              'Tenebrex Cyno Jammer Blueprint',
              'Territorial Claim Unit Blueprint',
              'Thanatos Blueprint',
              'Triple Neutron Blaster Cannon I Blueprint']

    with open('{0}bps2.json'.format(app.config['ROOT_PATH'])) as json_file:
        raw_data = json.load(json_file)

    with open('{0}jobs.json'.format(app.config['ROOT_PATH'])) as json_file:
        job_data = json.load(json_file)

    bpo_names = sorted(raw_data['bpos'])
    for name in bpo_names:
        bpo_data[name] = raw_data['bpos'][name]

    needed_copies = {}

    for name in bpo_names:
        if name in ignore:
            continue

        desired_me = '10'
        desired_te = '20'

        if name in adjust:
            desired_me = '0'
            desired_te = '0'
            for me in raw_data['bpos'][name]:
                if me == 'variants':
                    continue
                if int(me) > int(desired_me):
                    desired_me = me
            for te in raw_data['bpos'][name][desired_me]:
                if te == 'variants':
                    continue
                if int(te) > int(desired_te):
                    desired_te = te

        max_runs = 0
        qty = 0
        if name in raw_data['bpcs'] and desired_me in raw_data['bpcs'][name] and desired_te in raw_data['bpcs'][name][desired_me]:
            # if name == 'Medium Ancillary Current Router I Blueprint':
            #     qty = raw_data['bpcs'][name][desired_me][desired_te]['60']
            # else:
            for entry in raw_data['bpcs'][name][desired_me][desired_te]:
                if entry == 'variants':
                    continue
                runs = int(entry)
                if runs > max_runs:
                    max_runs = runs
                    qty = raw_data['bpcs'][name][desired_me][desired_te][entry]
        if qty < 5:
            # needed_copy = [Quantity, Copy Job Running, Research Job Running, BPO Needs Research]
            needed_copies[name] = [qty, False, False, True]

            if desired_me in raw_data['bpos'][name]:
                if desired_te in raw_data['bpos'][name][desired_me]:
                    needed_copies[name][3] = False
    
    for job in job_data:
        if job["name"] in needed_copies:
            if job["activity_id"] == 3 or job["activity_id"] == 4:
                needed_copies[job["name"]][2] = True
            if job["activity_id"] == 5:
                needed_copies[job["name"]][1] = True

    return render_template('todo.html',
                           title='Work To Do',
                           needed=needed_copies,
                           is_brave_industries=is_brave_industries,
                           is_brave_collective=is_brave_collective)


@app.route('/callback')
def callback():
    code = request.args.get('code')
    url = "https://login.eveonline.com/v2/oauth/token"
    # payload = {"grant_type": "authorization_code",
    #            "code": code}
    # data = json.dumps(payload)
    data = "grant_type=authorization_code&code={0}".format(code)
    headers = {'Content-Type': 'application/x-www-form-urlencoded',
               'Authorization': 'Basic ' + app.config['DEV_AUTH_KEY'],
               'Host': 'login.eveonline.com'}

    r = req.post(url, data=data, headers=headers)

    print(r)

    raw = r.json()

    print(raw)

    access_token = raw['access_token']
    refresh_token = raw['refresh_token']

    url = "https://login.eveonline.com/oauth/verify"
    headers = {'Content-Type': 'application/x-www-form-urlencoded',
               'Authorization': 'Bearer {0}'.format(str(access_token))}

    r2 = req.get(url, headers=headers)
    raw = r2.json()

    username = raw['CharacterName']
    char_id = raw['CharacterID']
    
    # user = User.query.filter_by(username=username).first()
    query = client.query(kind='User')
    result = list(query.add_filter('username', '=', username).fetch(1))
    print(result)
    user = User(user=username, user_id=char_id, token=refresh_token)
    if len(result) == 0:
        entry = datastore.Entity(client.key('User'))
        entry.update({'username': username,
                      'user_id': char_id,
                      'refresh_token': refresh_token})
        client.put(entry)

    login_user(user, remember=True)

    return redirect(url_for('index'))
    # return render_template('view.html', raw=raw, access_token=access_token, refresh_token=refresh_token)


@app.route('/complete', methods=['GET', 'POST'])
def complete():
    if current_user.is_anonymous:
        return redirect(url_for('index'))

    print("User '{0}' ({1}) is completing the following requests:".format(current_user.username,
                                                                          current_user.id))
    print(request.values)
    output = ""
    for item in request.values:
        if item == "csrf_token":
            continue
        if item == "submit":
            continue
        if request.values[item]:
            print("  {0}: {1}".format(item, request.values[item]))
            output = '{0}{1}_{2}\n'.format(output, item, request.values[item])
            query = client.query(kind='Request')
            query.add_filter('complete_time', '=', None)
            reqs = list(query.add_filter('char_id', '=', int(item)).fetch())
            print(reqs)

            reqs[0]['completed_by'] = current_user.id
            reqs[0]['complete_time'] = datetime.utcnow()

            print(reqs[0])

            client.put(reqs[0])

            # order = Request.query.filter_by(id=item).first()
            # print(order)
            # order.complete_time = datetime.utcnow()
            # order.completed_by = current_user.id
            # db.session.commit()

    return redirect(url_for('requests'))
