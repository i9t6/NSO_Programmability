#!/usr/bin/python
# Copyright (c) 2021 Cisco and/or its affiliates.
# 
# This software is licensed to you under the terms of the Cisco Sample
# Code License, Version 1.1 (the "License"). You may obtain a copy of the
# License at
# 
#                https://developer.cisco.com/docs/licenses
# 
# All use of the material herein must be in accordance with the terms of
# the License. All rights not expressly granted by the License are
# reserved. Unless required by applicable law or agreed to separately in
# writing, software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.
# 
# AUTHOR(s): Francisco Quiroz <frquiroz@cisco.com>

import json
import csv
import sys
import requests
import logging
from datetime import datetime
import urllib3
urllib3.disable_warnings()

date = datetime.now().date().strftime('%Y-%d-%m')
console_formartter = logging.Formatter('%(asctime)s:module:%(module)s>> %(message)s')
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(console_formartter)
my_logger = logging.getLogger()
my_logger.addHandler(console_handler)

def read_csv(var_csv_file, *var_key):
    with open(var_csv_file, encoding='utf-8') as csvf:
        csvReader = csv.DictReader(csvf,delimiter=',')
        if var_key:
            data = {}
            for rows in csvReader:
                key = rows[var_key[0]]
                if not '#' in key:
                    data[key] = rows
        else:
            data = []
            for rows in csvReader:
                data.append(rows)
    return data

def restconf_nso(var_action,var_service, var_data):
    headersList = {
            "Accept": "application/yang-data+json",
            "Content-Type": "application/yang-data+json",
            "Authorization": "Basic YWRtaW46YWRtaW4=",
    }

    reqUrl_data = "https://172.16.1.122:8443/restconf/data/tailf-ncs:services"
    reqUrl_ops  = "https://172.16.1.122:8443/restconf/operations/tailf-ncs:devices/device=--DEVICE--"

    if 'post' in var_action:
        my_logger.warning(f"POST\n")
        for line in var_data:
            my_logger.warning(f"{line}\n")
            temp_str = f"""{{\"port-turnup:port-turnup\":[{{"""
            for k,v in line.items():
                if v:
                    temp_str += f""" \"{k}\":\"{v}\","""
            payload_ptu_post = temp_str[:-1] + f"""}} ]}}"""
            response = requests.request("POST", reqUrl_data, data=payload_ptu_post,  headers=headersList,verify=False)    
            my_logger.warning(f"{str(response)}\n")       
            if '201' in str(response):
                print(f"\t Creado {line}")
            elif '409' in str(response):
                print(f"\t Ya Existe {line}")
    elif 'delete' in var_action:
        for line in var_data:
            reqUrl = reqUrl_data + "/port-turnup:port-turnup"
            temp_str = "="
            for k,v in line.items():
                if v:
                    temp_str += f"""{v},"""
            temp_str = temp_str.replace("/","%2F")
            reqUrl += temp_str[:-1]
            #print(reqUrl)
            response = requests.request("DELETE", reqUrl, headers=headersList,verify=False)
            if '204' in str(response):
                print(f"\t Borrado {line}")
            elif '404' in str(response):
                print(f"\t No existe {line}")
    elif 'patch' in var_action:
        for line in var_data:
            reqUrl = reqUrl_data + "/port-turnup:port-turnup"
            temp_str = f"""{{\"port-turnup:port-turnup\":[{{"""
            for k,v in line.items():
                if v:
                    temp_str += f""" \"{k}\":\"{v}\","""
            payload_ptu_post = temp_str[:-1] + f"""}} ]}}"""
            response = requests.request("PATCH", reqUrl, data=payload_ptu_post,  headers=headersList,verify=False)
            if '204' in str(response):
                print(f"\t Modificado {line}")
    elif 'reconcile' in var_action:
        # Config No-networking
        payload = json.dumps({"input": {"reconcile": { }}})
        for line in var_data:
            reqUrl_1 = reqUrl_data + "?no-networking"
            reqUrl_2 = reqUrl_data + "/port-turnup:port-turnup"
            reqUrl_3 = reqUrl_ops + "/compare-config"
            reqUrl_4 = reqUrl_ops + "/sync-from"
            temp_str = f"""{{\"port-turnup:port-turnup\":[{{"""
            temp_str_2 = "="
            i = 0
            for k,v in line.items():
                if v:
                    temp_str += f""" \"{k}\":\"{v}\","""
                if v and (i<3):
                    temp_str_2 += f"""{v},"""
                    i += 1
            reqUrl_3 = reqUrl_3.replace('--DEVICE--',line['device'])
            response = requests.request("POST", reqUrl_3, headers=headersList,verify=False)
            if not response.json():
                print(f"\t Config Sync {line['device']}, ready to reconcile ")
            else:           
                print(f"\t Not Sync {line['device']}")
                synk_now = input("\t Syncronizar ahora? (yes/no):" )
                if synk_now in ['y','Y','yes','YES','Yes']:
                    reqUrl_4 = reqUrl_4.replace('--DEVICE--',line['device'])
                    response = requests.request("POST", reqUrl_4, headers=headersList,verify=False)
                    if '200' in str(response):
                        print(f"\t Config Sync, ready to continue ")
                    else:           
                        print(f"\t Not Sync {response.json()}")
                        continue
                else:
                    continue
            payload_ptu_post = temp_str[:-1] + f"""}} ]}}"""
            response_1 = requests.request("POST", reqUrl_1, data=payload_ptu_post,  headers=headersList,verify=False)     
            if '201' in str(response_1):
                print(f"\t Creado en CDB {line}")
            elif '409' in str(response_1):
                print(f"\t Ya Existe en CDB {line}")
            temp_str_2 = temp_str_2.replace("/","%2F")
            reqUrl_2 += temp_str_2[:-1] + "/re-deploy"
            response = requests.request("POST", reqUrl_2, data=payload, headers=headersList,verify=False)
            if ('204' in str(response)) and ('201' in str(response_1)):
                print(f"\t New Service Reconciled ")
            elif ('204' in str(response)) and ('409' in str(response_1)):            
                print(f"\t No Changes, no reconciled ")
            reqUrl_3 = reqUrl_3.replace('--DEVICE--',line['device'])
            response = requests.request("POST", reqUrl_3, headers=headersList,verify=False)
            if not response.json():
                print(f"\t Config Sync ")
            else:           
                print(f"\t Not Sync {response.json()}")
    return "complete"
    
def main():
    try:
        option = sys.argv[1]
    except:
        option = 'c'
    
    try:
        verbose = sys.argv[2]
    except:
        verbose = ''

    # ERROR < WARNING < INFO
    if 'vv' in verbose:    
        vb = 'INFO'
    elif 'v' in verbose:
        vb='WARNING'
    else:
        vb ='ERROR'
    my_logger.setLevel(eval(f"logging.{vb}"))
    
    try:
        # Configure
        if 'c' in option :
            # leer PTU
            data_list = read_csv('ptu_vars.csv')
            my_logger.warning(f"{data_list}\n-----------------------")

            result = restconf_nso('post','ptu',data_list)
            print(result)

        # Delete
        elif 'd' in option:
            data_list = read_csv('ptu_vars_delete.csv')
            my_logger.warning(f"{data_list}\n-----------------------")

            result = restconf_nso('delete','ptu',data_list)
            print(result)    
        # Patch (modify)
        elif 'p' in option:
            data_list = read_csv('ptu_vars.csv')
            my_logger.warning(f"{data_list}\n-----------------------")

            result = restconf_nso('patch','ptu',data_list)
            print(result) 
        # Reconcile
        elif 'r' in option:
            data_list = read_csv('ptu_vars_reconcile.csv')
            my_logger.warning(f"{data_list}\n-----------------------")

            result = restconf_nso('reconcile','ptu',data_list)
            print(result)
    except Exception as e:
        print(f"{str(e)}")
    finally:
        print("------ COMPLETE ------")
    

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass