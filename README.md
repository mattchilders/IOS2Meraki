# IOS2Meraki
Converts IOS Configs to Meraki

This library converts IOS switch configurations for fixed switches to Meraki configurations that can be used with the Dashboard API.  While this will work for chassis and stacked IOS switch configurations, some work will need to be done to seperate the configs/port numbering to assign each Meraki switch it's portion of the config. (Meraki switches have an individual switch config per switch, regardless of whether they are stacked or not, whereas IOS switches have a single config for stacks or chassis')

This library also provides an interface for the Mearki Action Batch API, which allows us to group all API calls to configure a switchport into a single Action Batch... using this we can make a single API call to provision all switchports on a switch (rather than 24 or 48 individual API calls)


## How it works
Step 1. Create a site

```
import IOS2Meraki
site = IOS2Meraki.Site('Site0001')
```

Step 2. Iterate through a directory of configuration files and create a switch object for each config

```
import glob
CONFIG_PATH = '/path/to/configs/*.txt'
configs = glob.glob(CONFIG_PATH)
for config_file in configs:
    switch_name = os.path.basename(config_file).replace('.txt', '')
    switch = IOS2Meraki.Switch(switch_name, config_file)
    site.add_switch(switch)
```

Step 3. Generate Meraki API Calls to create the switches and switchports

```
# Serial number mapping for each switch
switch_mapping = {'switch1': 'XXXX-XXXX-XXXX', 'switch2': 'XXXX-XXXX-XXXX', 'switch3': 'XXXX-XXXX-XXXX'}

for switch in site.list_switches():
    current_switch = site.get_switch(switch)
    # Add the Meraki Device to the Network
    IOS2Meraki.add_device_to_network(api_key, network_id, switch_mapping[switch])
    
    #Create Action Batch for all switchport configs for this switch
    action_batch = IOS2Meraki.ActionBatch(api_key, org_id)
    
    for name, port in current_switch.interfaces.items():   
        # Ignore FastEthernet (such as management ports)
        if 'GigabitEthernet' not in name:
            continue
        
        # If you are working with IOS stacks... here is where you would need additional
        # code to handle splitting the configs and making additional switches
        
        # Get the Meraki switchport Config and add it to the action batch
        payload = port.get_meraki_switchport_api_payload()
        action_batch.add_action("/devices/" + details['serial'] + "/switchPorts/" + str(meraki_port_num), "update", payload)
        
        # Alternatively, you could get the api payload and just call a switchport config
        # instead of using action batches here.
    
    # Execute the action batch
    action_batch.execute_batch()
```

## Site Object Examples

```
>>> site.print_switches()
switch1
switch2
switch3
>>> site.list_switches()
['switch1', 'switch2', 'switch3']
>>> switch = site.get_switch('switch1')
>>> switch
<IOS2Meraki.Switch object at 0x10e5c7a50>
```

## Switch Object Examples

```
>>> switch = site.get_switch('switch1')
>>> switch.name
'switch1'
>>>
>>> switch.print_interfaces()
FastEthernet0
GigabitEthernet1/0/1
GigabitEthernet1/0/2
 ...
GigabitEthernet1/0/52
>>>
>>> switch.list_interfaces()
['FastEthernet0', 'GigabitEthernet1/0/1', ... 'GigabitEthernet1/0/52']
>>>
>>> switch.print_ios_interface_config('GigabitEthernet1/0/37')
interface GigabitEthernet1/0/37
 switchport access vlan 525
 switchport trunk encapsulation dot1q
 switchport trunk native vlan 910
 switchport mode access
 no cdp enable
 spanning-tree portfast
>>>
>>> switch.print_meraki_interface_config('GigabitEthernet1/0/37')
Port Type: access
Access VLAN: 525
Voice VLAN: None
Native VLAN: 910
Trunk VLANs: 1-4094
Enabled: True
PoE Enabled: True
Speed: auto
Duplex: auto
STP Enabled: True
STP Guard: disabled
UDLD Enabled: Disabled
Storm Control Enabled: Disabled
Sticky Mac Limit: None
>>>
>>> switch.get_meraki_switchport_api_payload('GigabitEthernet1/0/37')
{'name': '', 'enabled': True, 'poeEnabled': True, 'type': 'access', 'vlan': '525', 'voiceVlan': None, 'allowedVlans': '1-4094', 'isolationEnabled': False, 'rstpEnabled': True, 'stpGuard': 'disabled', 'udld': 'Alert only'}
```
