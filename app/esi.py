from datetime import datetime, timedelta
from app import app
from swagger_client.rest import ApiException
import json
import os
import requests
import swagger_client
import time
from bravado.client import SwaggerClient
from google.cloud import secretmanager

BRAVE_INDUSTRIES = 98445423


def update_bp_data():
    try:
        with open('{0}bps2.json'.format(app.config['ROOT_PATH'])) as json_file:
            existing_data = json.load(json_file)

        last_time = datetime.strptime(existing_data['last_updated'], "%Y-%m-%d %H:%M:%S.%f")
        refresh_time = last_time + timedelta(hours=1)
        # refresh_time = last_time + timedelta(minutes=1)

        if datetime.now() < refresh_time:
            print("Not enough time has passed to requery the blueprints")
            return
    except FileNotFoundError:
        pass

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/bravebpc/secrets/refresh_token/versions/latest"
    response = client.access_secret_version(name=name)
    refresh_token = response.payload.data.decode('UTF-8')

    headers = {'Content-Type': 'application/x-www-form-urlencoded',
               'Authorization': 'Basic OWNmZGZhMzJkMTIzNDhmMDkyYzEzNWQzMzU1MzQ1NDU6SGM4b0RDeGFUcHRnRlJZMUtLYlRUdnNDWklOckJPVlliS1ZldElZRA==',
               'Host': 'login.eveonline.com'}
    data = "grant_type=refresh_token&refresh_token={0}".format(refresh_token)

    r = requests.post("https://login.eveonline.com/v2/oauth/token", data=data, headers=headers)
    access_token = r.json()['access_token']
    ref_token = r.json()['refresh_token']
    if ref_token != refresh_token:
        parent = f"projects/bravebpc/secrets/refresh_token"
        resp = client.add_secret_version(parent=parent, payload={'data': ref_token.encode('UTF-8')})
        print(f'(udpatebpdata) Added secret version: {resp.name}')

    client = SwaggerClient.from_url('https://esi.evetech.net/latest/swagger.json')
    api = client.Corporation

    items = []
    locations = []
    bp_data = []
    page = 1
    retry = True
    count = 0
    while retry and count < 10:
        retry = False
        try:
            temp_data = api.get_corporations_corporation_id_blueprints(corporation_id=BRAVE_INDUSTRIES,
                                                                       page=page,
                                                                       token=access_token).result()
        except Exception as e:
            print("Exception when calling Corporation->get_corporations_corporation_id_blueprints: %s\n" % e)
            time.sleep(10)
            retry = True
            count += 1
    if retry:
        print("Failed to refresh BP data")
        return
    for item in temp_data:
        if int(item["type_id"]) not in items:
            items.append(int(item["type_id"]))
        if item["location_id"] not in locations:
            locations.append(item["location_id"])

    bp_data.extend(temp_data)
    while len(temp_data) == 1000:
        page += 1
        retry = True
        count = 0
        while retry and count < 10:
            retry = False
            try:
                temp_data = api.get_corporations_corporation_id_blueprints(corporation_id=BRAVE_INDUSTRIES,
                                                                           page=page,
                                                                           token=access_token).result()
            except Exception as e:
                temp_data = []
                print(page)
                print(str(e))
                if "Requested page does not exist" in str(e):
                    print('Ending BP lookup')
                    break
                print("Exception when calling MarketApi->get_corporations_corporation_id_blueprints: %s\n" % e)
                time.sleep(10)
                retry = True
                count += 1
        if retry:
            print("Failed to refresh BP data page {0}".format(page))
            return
        for item in temp_data:
            if int(item["type_id"]) not in items:
                items.append(int(item["type_id"]))
            if item["location_id"] not in locations:
                locations.append(item["location_id"])
        bp_data.extend(temp_data)

    temp = []
    for item in bp_data:
        temp.append({"item_id": item.item_id,
                     "location_flag": item.location_flag,
                     "location_id": item.location_id,
                     "material_efficiency": item.material_efficiency,
                     "quantity": item.quantity,
                     "runs": item.runs,
                     "time_efficiency": item.time_efficiency,
                     "type_id": item.type_id})
    bp_data = temp

    api = client.Universe

    item_names = []
    start = 0
    BLOCK_SIZE=750
    temp = items[start:start+BLOCK_SIZE]

    while len(temp) > 0:
        retry = True
        count = 0
        while retry and count < 10:
            retry = False
            try:
                item_names.extend(api.post_universe_names(ids=temp).result())
            except Exception as e:
                print("Exception when calling UniverseApi->post_universe_names: %s\n" % e)
                time.sleep(10)
                retry = True
                count += 1
        if retry:
            print("Failed to get item names")
            return
        start += BLOCK_SIZE
        temp = items[start:start+BLOCK_SIZE]

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
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/bravebpc/secrets/refresh_token/versions/latest"
    response = client.access_secret_version(name=name)
    refresh_token = response.payload.data.decode('UTF-8')

    headers = {'Content-Type': 'application/x-www-form-urlencoded',
               'Authorization': 'Basic OWNmZGZhMzJkMTIzNDhmMDkyYzEzNWQzMzU1MzQ1NDU6SGM4b0RDeGFUcHRnRlJZMUtLYlRUdnNDWklOckJPVlliS1ZldElZRA==',
               'Host': 'login.eveonline.com'}
    data = "grant_type=refresh_token&refresh_token={0}".format(refresh_token)

    r = requests.post("https://login.eveonline.com/v2/oauth/token", data=data, headers=headers)
    ref_token = r.json()['refresh_token']
    if ref_token != refresh_token:
        parent = f"projects/bravebpc/secrets/refresh_token"
        resp = client.add_secret_version(parent=parent, payload={'data': ref_token.encode('UTF-8')})
        print(f'(udpatejobdata) Added secret version: {resp.name}')

    config = swagger_client.Configuration()
    config.access_token = r.json()['access_token']

    api = swagger_client.IndustryApi(swagger_client.ApiClient(config))
    api.api_client.set_default_header('User-Agent', 'industry-info')
    api.api_client.host = "https://esi.evetech.net"

    job_data = {}
    retry = True
    count = 0
    while retry and count < 10:
        retry = False
        try:
            job_data = api.get_corporations_corporation_id_industry_jobs(BRAVE_INDUSTRIES)
        except ApiException as e:
            # print("Exception when calling MarketApi->get_markets_structures_structure_id: %s\n" % e)
            time.sleep(10)
            retry = True
            count += 1
    if retry:
        # print("Failed to refresh BP data")
        return
    # print(json.dumps(job_data, indent=4))

    items = []
    for job in job_data:
        if job["blueprint_type_id"] not in items:
            items.append(job["blueprint_type_id"])

    api = swagger_client.UniverseApi(swagger_client.ApiClient(config))
    api.api_client.set_default_header('User-Agent', 'universe-info')
    api.api_client.host = "https://esi.evetech.net"

    print(len(items))
    item_names = []
    # print(len(items))
    retry = True
    count = 0

    if items:
        while retry and count < 10:
            retry = False
            try:
                item_names = api.post_universe_names(items)
            except ApiException as e:
                # print("Exception when calling MarketApi->get_markets_structures_structure_id: %s\n" % e)
                time.sleep(10)
                retry = True
                count += 1
        if retry:
            # print("Failed to refresh BP data")
            return
    print(len(item_names))
    names = {}
    for item in item_names:
        names[item["id"]] = item["name"]

    for job in job_data:
        job["name"] = names[job["blueprint_type_id"]]

    with open('{0}jobs.json'.format(app.config['ROOT_PATH']), 'w') as outfile:
        json.dump(job_data, outfile, indent=4)
