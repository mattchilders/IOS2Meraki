from ciscoconfparse import CiscoConfParse
import requests
import json
import time
from meraki import meraki


IOS = 0
MERAKI = 1
ACCESS = 0
TRUNK = 1
STP_GUARD_DISABLED = 'disabled'
STP_GUARD_BPDUGUARD = 'bpdu guard'
UDLD_ENABLED = 'Enforce'
UDLD_DISABLED = 'Alert only'
STORM_CONTROL_ENABLED = 1
STORM_CONTROL_DISABLED = 0


class Site():
    def __init__(self, name):
        self.name = name
        self.switches = {}

    def add_switch(self, switch):
        self.switches[switch.name] = switch

    def get_switch(self, name):
        return self.switches[name]

    def list_switches(self):
        return list(self.switches.keys())

    def print_switches(self):
        for switch in self.switches.keys():
            print(switch)


class Switch():
    def __init__(self, name, config_file):
        self.name = name.lower()
        self.config_file = config_file
        self.interfaces = {}
        self.parse_config()

    def parse_config(self):
        parse = CiscoConfParse(self.config_file)
        for interface_object in parse.find_objects(r"^interface [FG]"):
            port = interface_object.text.replace('interface ', '')
            self.interfaces[port] = SwitchPortConfig(port, interface_object)

    def list_interfaces(self):
        return list(self.interfaces.keys())

    def print_interfaces(self):
        for interface in self.interfaces.keys():
            print(interface)

    def get_ios_interface_object(self, interface):
        return self.interfaces[interface].ios_config_obj

    def get_interface_meraki_config(self, interface):
        return self.interfaces[interface].meraki_config

    def print_ios_interface_config(self, interface):
        self.interfaces[interface].print_ios_config()

    def print_meraki_interface_config(self, interface):
        self.interfaces[interface].print_meraki_config()

    def get_meraki_switchport_api_payload(self, interface):
        return self.interfaces[interface].get_meraki_switchport_api_payload()


class SwitchPortConfig():
    def __init__(self, port, config=None):
        self.port = port
        self.ios_config_obj = config
        self.description = ''
        self.type = 'access'
        self.vlan = 1
        self.voice_vlan = None
        self.native_vlan = 1
        self.trunk_vlans = '1-4094'
        self.tags = ''
        self.enabled = True
        self.poe = True
        self.speed = 'auto'
        self.duplex = 'auto'
        self.rstp = True
        self.stp_guard = STP_GUARD_BPDUGUARD
        self.udld = UDLD_DISABLED
        self.storm_control = STORM_CONTROL_ENABLED
        self.sticky_mac = None
        if config:
            self.parse_ios_config(config)

    def parse_ios_config(self, config=None):
        if not config:
            if not self.ios_config_obj:
                print('Error: No switchport config')
                return False
            config = self.ios_config_obj
        self.type = self.parse_switchport_type(config)
        self.enabled = self.parse_switchport_enabled(config)
        self.poe = self.parse_poe_enabled(config)
        self.vlan = self.parse_access_vlan(config)
        self.native_vlan = self.parse_native_vlan(config)
        self.trunk_vlans = self.parse_trunk_vlans(config)
        self.voice_vlan = self.parse_voice_vlan(config)
        self.speed, self.duplex = self.parse_link_type(config)
        self.stp_guard = self.parse_stp_guard(config)
        self.udld = self.parse_udld(config)
        self.description = self.parse_description(config)
        self.storm_control = self.parse_storm_control(config)
        self.sticky_mac = self.parse_sticky_mac(config)

    def parse_switchport_enabled(self, config):
        shut = config.re_search_children(r"^ shutdown")
        if not shut:
            return True
        return False

    def parse_switchport_type(self, config):
        access = config.re_search_children(r"^ switchport mode access")
        trunk = config.re_search_children(r"^ switchport mode trunk")
        if access and trunk:
            trunk_line_num = trunk[len(trunk) - 1].linenum
            access_line_num = access[len(access) - 1].linenum
            if access_line_num < trunk_line_num:
                return 'trunk'
            return 'access'
        if access:
            return 'access'
        return 'trunk'

    def parse_poe_enabled(self, config):
        poe = config.re_search_children(r"^ power inline never")
        if poe:
            return False
        return True

    def parse_access_vlan(self, config):
        line = config.re_search_children(r"^ switchport access vlan")
        if not line:
            return 1
        vlan = line[0].re_match_typed('switchport access vlan ([0-9]*)')
        return vlan

    def parse_native_vlan(self, config):
        line = config.re_search_children(r"^ switchport trunk native vlan")
        if not line:
            return 1
        vlan = line[0].re_match_typed('switchport trunk native vlan ([0-9]*)')
        return vlan

    def parse_trunk_vlans(self, config):
        lines = config.re_search_children(r"^ switchport trunk allowed vlan")
        if not lines:
            return '1-4094'
        vlans = []
        for line in lines:
            vlans.append(line.re_match_typed('switchport trunk allowed vlan.* ([0-9,\-]*)'))
        return ','.join(vlans)

    def parse_voice_vlan(self, config):
        line = config.re_search_children(r"^ switchport voice vlan")
        if not line:
            return None
        vlan = line[0].re_match_typed('switchport voice vlan ([0-9]*)')
        return vlan

    def parse_link_type(self, config):
        lines = config.re_search_children(r"^ speed |^ duplex ")
        if not lines:
            return ('auto', 'auto')
        speed = 'auto'
        duplex = 'auto'
        for line in lines:
            check_speed = line.re_match_typed('^ speed ([1-9]*)')
            if check_speed != '':
                speed = check_speed
            check_duplex = line.re_match_typed('^ duplex ([1-9]*)')
            if check_duplex != '':
                duplex = check_duplex
        return (speed, duplex)

    def parse_stp_guard(self, config):
        line = config.re_search_children(r"^ spanning-tree bpduguard")
        if not line:
            return STP_GUARD_DISABLED
        else:
            return STP_GUARD_BPDUGUARD

    def parse_udld(self, config):
        line = config.re_search_children(r"^ udld port")
        if not line:
            return UDLD_DISABLED
        else:
            return UDLD_ENABLED

    def parse_description(self, config):
        lines = config.re_search_children(r"^ description")
        if not lines:
            return ''
        for line in lines:
            description = line.re_match_typed('^ description (.*)')
            if not line:
                return ''
            else:
                return description

    def parse_storm_control(self, config):
        line_broadcast = config.re_search_children(r"^ storm-control broadcast")
        line_multicast = config.re_search_children(r"^ storm-control multicast")
        if line_broadcast or line_multicast:
            return STORM_CONTROL_ENABLED
        else:
            return STORM_CONTROL_DISABLED

    def parse_sticky_mac(self, config):
        lines = config.re_search_children(r"^ switchport port-security maximum")
        if not lines:
            return None
        for line in lines:
            port_security_max = line.re_match_typed('^ switchport port-security maximum (.*)')
            if port_security_max != '':
                break
        line_sticky = config.re_search_children(r"^ switchport port-security mac-address sticky$")
        if line_sticky and port_security_max:
            return int(port_security_max)
        else:
            return None

    def print_ios_config(self):
        for line in self.ios_config_obj.ioscfg:
            print(line)

    def print_meraki_config(self):
        print("Port Type: " + str(self.type))
        print("Access VLAN: " + str(self.vlan))
        print("Voice VLAN: " + str(self.voice_vlan))
        print("Native VLAN: " + str(self.native_vlan))
        print("Trunk VLANs: " + self.trunk_vlans)
        print("Enabled: " + str(self.enabled))
        print("PoE Enabled: " + str(self.poe))
        print("Speed: " + str(self.speed))
        print("Duplex: " + str(self.duplex))
        print("STP Enabled: " + str(self.rstp))
        print("STP Guard: " + str(self.stp_guard))
        print("UDLD Enabled: " + self.port_udld_to_str(self.udld))
        print("Storm Control Enabled: " + self.port_storm_control_to_str(self.storm_control))
        print("Sticky Mac Limit: " + str(self.sticky_mac))

    def get_meraki_switchport_api_payload(self):
        if self.type == 'trunk':
            vlan = self.native_vlan
        else:
            vlan = self.vlan

        payload = {}
        payload['name'] = self.description
        payload['enabled'] = self.enabled
        payload['poeEnabled'] = self.poe
        payload['type'] = self.type
        payload['vlan'] = vlan
        payload['voiceVlan'] = self.voice_vlan
        payload['allowedVlans'] = self.trunk_vlans
        payload['isolationEnabled'] = False
        payload['rstpEnabled'] = self.rstp
        payload['stpGuard'] = self.stp_guard
        # payload['accessPolicyNumber'] = None
        payload['udld'] = self.udld
        if self.sticky_mac is not None:
            payload['stickyMacWhitelist'] = []
            payload['stickyMacWhitelistLimit'] = self.sticky_mac
        return payload

    def port_type_to_str(self, value):
        if value == ACCESS:
            return "Access"
        if value == TRUNK:
            return 'Trunk'
        return ''

    def port_stp_guard_to_str(self, value):
        if value == STP_GUARD_DISABLED:
            return "Disabled"
        if value == STP_GUARD_BPDUGUARD:
            return 'Enabled'
        return ''

    def port_udld_to_str(self, value):
        if value == UDLD_DISABLED:
            return "Disabled"
        if value == UDLD_ENABLED:
            return 'Enabled'
        return ''

    def port_storm_control_to_str(self, value):
        if value == STORM_CONTROL_DISABLED:
            return "Disabled"
        if value == STORM_CONTROL_ENABLED:
            return 'Enabled'
        return ''


def get_switchport_config(site, switch, port):
    curr_switch = site.get_switch(switch)
    print('Switch: ' + switch + ' - ' + port)
    print('IOS Config:')
    print('=' * 80)
    curr_switch.print_ios_interface_config(port)
    print()
    print('Meraki Config:')
    print('=' * 80)
    curr_switch.print_meraki_interface_config(port)


class ActionBatch():
    def __init__(self, api_key, org_id):
        self.MAX_ACTIONS = 100
        self.action_list = []
        self.api_key = api_key
        self.org_id = org_id
        self.url = 'https://api.meraki.com/api/v0/organizations/' + org_id + '/actionBatches'
        self.headers = {'X-Cisco-Meraki-API-Key': self.api_key, 'Content-Type': 'application/json'}
        self.action_batch_id = None
        self.execute_time = None
        self.completed = False
        self.failed = False
        self.errors = None

    def add_action(self, resource, operation, body):
        if len(self.action_list) > self.MAX_ACTIONS:
            print('Action Batch List already has more than max allowed ' + str(self.MAX_ACTIONS) + ' actions')
        action = {"resource": resource,
                  "operation": operation,
                  "body": body
                  }
        self.action_list.append(action)

    def execute_batch(self, confirmed=True):
        self.execute_time = time.time()
        payload = {"actions": self.action_list, "confirmed": confirmed}
        # print(payload)
        try:
            response = requests.request('POST', self.url, headers=self.headers, data=json.dumps(payload), allow_redirects=True, timeout=30)
            if response.status_code != 201:
                print("Error Creating Action Batch")
                self.error_details(response)
                self.failed = True
                self.errors = response
                return None
            response = json.loads(response.text)
            self.action_batch_id = response['id']
            return self.action_batch_id
        except Exception as e:
            print('Error in submitting action batch: ')
            if response:
                self.failed = True
                self.errors = response
                self.error_details(response)
            print(e)
            return None

    def check_status(self):
        url = self.url + '/' + self.action_batch_id
        try:
            response = requests.request('GET', url, headers=self.headers, allow_redirects=True, timeout=30)
            if response.status_code != 200:
                print("Error Getting Status for ID: " + self.action_batch_id)
                self.error_details(response)
                return None
            response = json.loads(response.text)
            if "status" in response:
                self.completed = response['status']['completed']
                self.failed = response['status']['failed']
                self.errors = response['status']['errors']
            return (self.completed, self.failed, self.errors)
        except Exception as e:
            print('Error in getting status of action batch: ')
            if response:
                self.error_details(response)
            print(e)
            return None

    def error_details(self, response):
        print('Status Code:' + str(response.status_code))
        print('Response: ' + response.text)


def get_network(api_key, org_id, network_name):
    networks = meraki.getnetworklist(api_key, org_id, suppressprint=True)
    for network in networks:
        if network['name'] == network_name:
            return network['id']

    print('Error: Network Not found: ' + network_name)
    return None


def add_device_to_network(api_key, network_id, serial):
    base_url = 'https://api.meraki.com/api/v0'
    posturl = '{0}/networks/{1}/devices/claim'.format(str(base_url), str(network_id))
    headers = {
        'x-cisco-meraki-api-key': format(str(api_key)),
        'Content-Type': 'application/json'
    }
    postdata = {
        'serial': format(str(serial))
    }
    response = requests.post(posturl, data=json.dumps(postdata), headers=headers)
    if response.status_code == 200:
        print('Device Successfully Added')
        return response
    else:
        return response
