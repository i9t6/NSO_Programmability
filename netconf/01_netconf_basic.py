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


from ncclient import manager
import xmltodict
import csv
import re
import sys
from lxml import etree

import logging
from datetime import datetime


date = datetime.now().date().strftime('%Y-%d-%m')
console_formartter = logging.Formatter('%(asctime)s:module:%(module)s>> %(message)s')
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(console_formartter)
my_logger = logging.getLogger()
my_logger.addHandler(console_handler)

# NSO Settings for 
nso_srv = {'host':'172.16.1.122','port':'2022','username':'admin','password':'admin','hostkey_verify':False}

def read_csv(var_csv_file, var_key):
    data = {}
    with open(var_csv_file, encoding='utf-8') as csvf:
        csvReader = csv.DictReader(csvf,delimiter=';')
        for rows in csvReader:
            key = rows[var_key]
            if not '#' in key:
                data[key] = rows
    return data

# Read and adjust device list to reflect changes
def fix_device_list(var_srv,var_key,var_data,var_case):
    dic={}
    with manager.connect(**nso_srv) as m:
        for key in var_data.keys():
            netconf_reply = m.get(filter=('xpath',f"/services/{var_srv}[{var_key}='{key}']/device-list"))
            devices_list = xmltodict.parse(netconf_reply.xml)["rpc-reply"]["data"]
            if not devices_list == None:
                if type(devices_list['services'][var_srv]['device-list']) == type('str'):
                    dic[key] = [devices_list['services'][var_srv]['device-list']]
                else:
                    dic[key] = devices_list['services'][var_srv]['device-list']
            else:
                dic[key] = []
    for key, values in var_data.items():
        final_list =[]
        if not values['devices'] == '':
            for device in eval(values['devices']):
                if var_case == 'config':
                    final_list = dic[key]
                    if not device in dic[key]:
                        final_list.append(device)
                elif var_case == 'delete':
                    final_list.append(device)
        else:
            final_list = []
        var_data[key]['devices'] = final_list
    #print(var_data)
    return var_data


# Fill QoS XML Template
def fill_template_qos(var_template_file,var_data, var_verbose):
    dic = {}
    netconf_template = open(var_template_file).read()
    for key, values in var_data.items():
        list = []
        for line in netconf_template.split('\n'):
            if (('delete' in line) and (not "device" in line)):
                if not len(values['devices']) == 0:
                    final_line = line.replace("operation=\"delete\"", "" )
                    list.append(final_line)
                else:
                    list.append(line)
            elif '{' in line:
                value = re.search(r"\{(.*)\}",line).group(1)
                if not value == 'devices':
                    if not values[value] == '':
                        final_line = line.replace("{" + value + "}", values[value] )
                        list.append(final_line)
                    else:
                        continue
                else:
                    for device in values['devices']:
                        final_line = line.replace("{" + value + "}",device)
                        list.append(final_line)
            else:
                list.append(line)
        # verbose
        if 'v' in var_verbose:
            for i in list:
                print(i)    
        dic[key]="\n".join(list)
    return dic

def config_netconf(var_dic_templates):
    with manager.connect(**nso_srv) as m:
        for key, case in var_dic_templates.items():
            try:
                # merge also usefull for reconcile, similar to no-network
                netconf_reply = m.edit_config(case, target="running", default_operation='merge')        
            except:
                print(f"Error {key}, Possible service instance/device not existing or not in sync")
            else:
                if netconf_reply.ok:
                    print(f"Service: {key} : Change Completed")
    return 'Netconf config: Done'

def device_action(var_device, var_action):
    action  = etree.Element("action",  nsmap = {None: 'http://tail-f.com/ns/netconf/actions/1.0'})
    data = etree.SubElement(action, "data")
    devices = etree.SubElement(data, "devices", nsmap = {None: 'http://tail-f.com/ns/ncs'})
    device = etree.SubElement(devices, "device")
    name = etree.SubElement(device, "name").text = f"{var_device}"
    check = etree.SubElement(device,f"{var_action}")
    try:
        with manager.connect(**nso_srv) as m:
            response = m.dispatch(action)
    except Exception as e:
        my_logger.warning(f" exception {str(e)}")
        response = False
    return response

def reconcile(var_dic_reconcile):
    for key, info in var_dic_reconcile.items():
        action = etree.Element("action",  nsmap = {None: 'http://tail-f.com/ns/netconf/actions/1.0'})
        data = etree.SubElement(action, "data")
        srvs = etree.SubElement(data, "services", nsmap = {None: 'http://tail-f.com/ns/ncs'})
        srv_pol_map = etree.SubElement(srvs, "Srv_Policy_Map",nsmap = {None: 'http://example.com/Srv_Policy_Map'})
        pn = etree.SubElement(srv_pol_map, "policy_name").text = f"{key}"
        rd = etree.SubElement(srv_pol_map, "re-deploy")
        rc = etree.SubElement(rd,"reconcile")
        try:                   
            with manager.connect(**nso_srv) as m:
                response = m.dispatch(action)
            my_logger.warning(f" reconcile {response.xml}")
            for device in info['devices']:
                response = device_action(device, 'compare-config')
                my_logger.warning(f" {device} resultado \n {response.xml} \n")
                print(f"{device} config sync checked")
        except Exception as e:
            my_logger.warning(f" exception {str(e)}")
    return '\nReconcile complete\n'

def check_sync(var_dic_reconcile):
    for key, info in var_dic_reconcile.items():
        for device in eval(info['devices']):
            if 'out-of-sync' in device_action(device,'check-sync').xml:
                synk_now = input(f"\t {device} Not in sync. Sync now? (yes/no):")
                if synk_now in ['y','Y','yes','YES','Yes']:
                    if 'true' in device_action(device, 'sync-from').xml:
                        print(f"\t Config Sync, ready to continue ")
                    else:           
                        print(f"\t {device} not in sync")
                        continue
                else:
                    continue

def main():
    try:
        option = sys.argv[1]
    except:
        # Default option is confirure
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

    # Configure, file used: srv_policy.csv
    try:
        if 'c' in option :
            data = read_csv('srv_policy.csv','policy_name')
            my_logger.warning(f"{data}\n-----------------------")
            data_fixed = fix_device_list('Srv_Policy_Map','policy_name', data, 'config')
            my_logger.warning(f"{data_fixed}\n-----------------------")
            dic_templates = fill_template_qos('config_qos.xml', data_fixed, verbose) 
            print(config_netconf(dic_templates),"\n-----------------------")

        # Delete, file used: srv_policy_delete.csv
        elif 'd' in option:
            data_delete = read_csv('srv_policy_delete.csv','policy_name')
            my_logger.warning(f"{data_delete}\n-----------------------")
            data_fixed_delete = fix_device_list('Srv_Policy_Map','policy_name', data_delete,'delete')
            my_logger.warning(f"{data_fixed_delete}\n-----------------------")
            dic_templates_delete = fill_template_qos('config_qos_delete.xml', data_fixed_delete, verbose)
            print(config_netconf(dic_templates_delete),"\n-----------------------")

        # Reconcile, file used: srv_policy_reconcile.csv
        elif 'r' in option:
            # this is two steps process, configure then reconcile
            data_reconcile = read_csv('srv_policy_reconcile.csv','policy_name')
            my_logger.warning(f"{data_reconcile}\n-----------------------")
            check_sync(data_reconcile)
            data_fixed = fix_device_list('Srv_Policy_Map','policy_name', data_reconcile, 'config')
            my_logger.warning(f"{data_fixed}\n-----------------------")
            dic_templates = fill_template_qos('config_qos.xml', data_fixed, verbose) 
            print(config_netconf(dic_templates),"\n-----------------------")
            print(reconcile(data_reconcile))
    except Exception as e:
        print(f"{str(e)}")
    finally:
        print("------ COMPLETE ------")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
        
