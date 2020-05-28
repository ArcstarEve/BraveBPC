from datetime import datetime, timedelta
from app import app
import json
import os
import requests
import swagger_client

BRAVE_INDUSTRIES = 98445423

def update_bp_data():
    try:
        with open('{0}bps2.json'.format(app.config['ROOT_PATH'])) as json_file:
            existing_data = json.load(json_file)

        last_time = datetime.strptime(existing_data['last_updated'], "%Y-%m-%d %H:%M:%S.%f")
        refresh_time = last_time + timedelta(hours=1)

        if datetime.now() < refresh_time:
            print("Not enough time has passed to requery the blueprints")
            return
    except FileNotFoundError:
        pass

    headers = {'Content-Type': 'application/json',
            'Authorization': 'Basic OWNmZGZhMzJkMTIzNDhmMDkyYzEzNWQzMzU1MzQ1NDU6SGM4b0RDeGFUcHRnRlJZMUtLYlRUdnNDWklOckJPVlliS1ZldElZRA=='}
    payload = {'grant_type': 'refresh_token',
            'refresh_token': os.environ.get('ADMIN_TOKEN')}
    data = json.dumps(payload)

    r = requests.post("https://login.eveonline.com/oauth/token", data=data, headers=headers)

    config = swagger_client.Configuration()
    config.access_token = r.json()['access_token']
    api = swagger_client.CorporationApi(swagger_client.ApiClient(config))
    api.api_client.set_default_header('User-Agent', 'corporation-info')
    api.api_client.host = "https://esi.tech.ccp.is"

    items = []
    locations = []
    bp_data = []
    page = 1
    temp_data = api.get_corporations_corporation_id_blueprints(BRAVE_INDUSTRIES, page=page)

    bp_data.extend(temp_data)
    while len(temp_data) > 0:
        for item in temp_data:
            if int(item["type_id"]) not in items:
                items.append(int(item["type_id"]))
            if item["location_id"] not in locations:
                locations.append(item["location_id"])
        page += 1
        temp_data = api.get_corporations_corporation_id_blueprints(BRAVE_INDUSTRIES, page=page)
        bp_data.extend(temp_data)

    api = swagger_client.UniverseApi(swagger_client.ApiClient(config))
    api.api_client.set_default_header('User-Agent', 'universe-info')
    api.api_client.host = "https://esi.tech.ccp.is"

    print(len(items))
    item_names = api.post_universe_names(items[:750])
    item_names.extend(api.post_universe_names(items[750:]))
    print(len(item_names))
    names = {}
    for item in item_names:
        names[item["id"]] = item["name"]

    stock = {}
    for item in bp_data:
        me_te_run = "{0}/{1}/{2}".format(item["material_efficiency"], item["time_efficiency"], item["runs"])
        name = names[item["type_id"]]
        item["name"] = name
        if name in stock:
            if me_te_run in stock[name]:
                stock[name][me_te_run] += 1
            else:
                stock[name][me_te_run] = 1
        else:
            stock[name] = {me_te_run: 1}

    with open('{0}bps.json'.format(app.config['ROOT_PATH']), 'w') as outfile:
        json.dump(bp_data, outfile, indent=4)

    data = {'last_updated': str(datetime.now()),
            'bpcs': {},
            'bpos': {}}
    for item in sorted(stock):
        for entry in stock[item]:
            me, te, runs = entry.split('/')
            if runs == "-1":
                if item in data['bpos']:
                    if me in data['bpos'][item]:
                        if te in data['bpos'][item][me]:
                            data['bpos'][item][me][te] += stock[item][entry]
                        else:
                            data['bpos'][item]['variants'] += 1
                            data['bpos'][item][me]['variants'] += 1
                            data['bpos'][item][me][te] = stock[item][entry]
                    else:
                        data['bpos'][item]['variants'] += 1
                        data['bpos'][item][me] = {'variants': 1,
                                                te: stock[item][entry]}
                else:
                    data['bpos'][item] = {'variants': 1,
                                        me: {'variants': 1,
                                            te: stock[item][entry]}}

            else:
                if item in data['bpcs']:
                    if me in data['bpcs'][item]:
                        if te in data['bpcs'][item][me]:
                            if runs in data['bpcs'][item][me][te]:
                                data['bpcs'][item][me][te][runs] += 1
                            else:
                                data['bpcs'][item]['variants'] += 1
                                data['bpcs'][item][me]['variants'] += 1
                                data['bpcs'][item][me][te]['variants'] += 1
                                data['bpcs'][item][me][te][runs] = stock[item][entry]
                        else:
                            data['bpcs'][item]['variants'] += 1
                            data['bpcs'][item][me]['variants'] += 1
                            data['bpcs'][item][me][te] = {'variants': 1,
                                                        runs: stock[item][entry]}
                    else:
                        data['bpcs'][item]['variants'] += 1
                        data['bpcs'][item][me] = {'variants': 1,
                                                te: {'variants': 1,
                                                    runs: stock[item][entry]}}
                else:
                    data['bpcs'][item] = {'variants': 1,
                                        me: {'variants': 1,
                                            te: {'variants': 1,
                                                    runs: stock[item][entry]}}}

    with open('{0}bps2.json'.format(app.config['ROOT_PATH']), 'w') as outfile:
        json.dump(data, outfile, indent=4)

def update_job_data():
    headers = {'Content-Type': 'application/json',
            'Authorization': 'Basic OWNmZGZhMzJkMTIzNDhmMDkyYzEzNWQzMzU1MzQ1NDU6SGM4b0RDeGFUcHRnRlJZMUtLYlRUdnNDWklOckJPVlliS1ZldElZRA=='}
    payload = {'grant_type': 'refresh_token',
            'refresh_token': os.environ.get('ADMIN_TOKEN')}
    data = json.dumps(payload)

    r = requests.post("https://login.eveonline.com/oauth/token", data=data, headers=headers)

    config = swagger_client.Configuration()
    config.access_token = r.json()['access_token']
    api = swagger_client.IndustryApi(swagger_client.ApiClient(config))
    api.api_client.set_default_header('User-Agent', 'industry-info')
    api.api_client.host = "https://esi.tech.ccp.is"

    job_data = api.get_corporations_corporation_id_industry_jobs(BRAVE_INDUSTRIES)
    # print(json.dumps(job_data, indent=4))

    items = []
    for job in job_data:
        if job["blueprint_type_id"] not in items:
            items.append(job["blueprint_type_id"])

    api = swagger_client.UniverseApi(swagger_client.ApiClient(config))
    api.api_client.set_default_header('User-Agent', 'universe-info')
    api.api_client.host = "https://esi.tech.ccp.is"

    print(len(items))
    item_names = api.post_universe_names(items)
    print(len(item_names))
    names = {}
    for item in item_names:
        names[item["id"]] = item["name"]

    for job in job_data:
        job["name"] = names[job["blueprint_type_id"]]

    with open('{0}jobs.json'.format(app.config['ROOT_PATH']), 'w') as outfile:
        json.dump(job_data, outfile, indent=4)
