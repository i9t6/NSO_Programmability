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

import ncs
import _ncs
import csv
import sys
import logging
from datetime import datetime

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

def create_update_l3vpn(var_data_csv,*var_reconcile):
    with ncs.maapi.Maapi() as m:
        with ncs.maapi.Session(m, 'admin', 'python'):
            for line in var_data_csv:
                print(f"vrf {line['vrf_name']} {line['device']}")
                with m.start_write_trans() as t:
                    root = ncs.maagic.get_root(t)
                    vrf_list = root.services.vrf          
                    vrf = vrf_list.create(line['vrf_name'])
                    device = vrf.devices.create(line['device'])
                    device.primary_route_target = line['rt_primary']
                    if line['rt_import']:
                        device.RT_import = [i for i in line['rt_import'].split(' ')]
                    if line['rt_export']:
                        device.RT_export = [i for i in line['rt_export'].split(' ')]
                    if line['rm_export']:
                        if 'xe' in line['tipo']:
                            device.iosxe.route_map_export = line['rm_export']
                        elif 'xr' in line['tipo']:
                            device.iosxr.route_map_export = line['rm_export']
                    if line['rm_import']:
                        if 'xe' in line['tipo']:
                            device.iosxe.route_map_import = line['rm_import']
                        elif 'xr' in line['tipo']:
                            device.iosxr.route_map_import = line['rm_import']
                    if len(var_reconcile):
                        if 'reconcile' in var_reconcile[0]:
                            device = root.devices.device[line['device']]
                            result = device.check_sync()
                            if 'out-of-sync' in str(result.result):
                                synk_now = input(f"Device {line['device']}, OOS, sync now (yes/no)? ")
                                if synk_now in ['y','Y','yes','YES','Yes']:
                                    result = device.sync_from()
                                    if result.result:
                                        t.apply(True, _ncs.maapi.COMMIT_NCS_NO_NETWORKING)
                                        print("Config in CDB")
                                else:
                                    last = 'OOS'
                                    continue
                            else:
                                # Commit No-networking
                                t.apply(True, _ncs.maapi.COMMIT_NCS_NO_NETWORKING)
                                print("Config in CDB")
                            # Re-deploy reconcile
                            inputs = vrf.re_deploy.get_input()
                            inputs.reconcile.create()
                            vrf.re_deploy(inputs)
                            print("re-deploy, check_config ")
                            result = device.compare_config()
                            if result.diff:
                                print('Need Sync')
                            else:
                                print("Reconciled")
                        last = 'ok'
                    else:
                        print("no Reconcile")
                        t.apply()
                        last = 'ok'
                print("Ready")
            return last

def delete_l3vpn(var_data_csv):
    with ncs.maapi.Maapi() as m:
        with ncs.maapi.Session(m, 'admin', 'python'):
            for line in var_data_csv:
                print(f"vrf {line['vrf_name']} {line['device']} ") 
                with m.start_write_trans() as t:
                    root = ncs.maagic.get_root(t)
                    vrf_list = root.services.vrf
                    if line['device']:
                        vrf = vrf_list[line['vrf_name']]
                        del vrf.devices[ line['device'] ]
                    else:
                        del vrf_list[line['vrf_name']]
                    t.apply()
                print("Ready")
            return 'ok'



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
            data_list = read_csv('vrf_vars.csv')
            my_logger.warning(f"{data_list}\n-----------------------")
            result = create_update_l3vpn(data_list)
            print(result)
        # Delete
        elif 'd' in option:
            # leer PTU
            data_list = read_csv('vrf_vars_delete.csv')
            my_logger.warning(f"{data_list}\n-----------------------")
            result = delete_l3vpn(data_list)
            print(result)
        # Patch (modify)
        #elif 'p' in option:
            #data_list = read_csv('ptu_vars.csv')
            #my_logger.warning(f"{data_list}\n-----------------------")
   
            #result = restconf_nso('patch','ptu',data_list)
            #print(result) 
        # Reconcile
        elif 'r' in option:
            data_list = read_csv('vrf_vars_reconcile.csv')
            my_logger.warning(f"{data_list}\n-----------------------")

            result = create_update_l3vpn(data_list,'reconcile')
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