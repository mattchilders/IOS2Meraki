# IOS2Meraki
Converts IOS Configs to Meraki

This library converts IOS switch configurations for fixed switches to Meraki configurations that can be used with the Dashboard API.  While this will work for chassis and stacked IOS switch configurations, some work will need to be done to seperate the configs/port numbering to assign each Meraki switch it's portion of the config. (Meraki switches have an individual switch config per switch, regardless of whether they are stacked or not, whereas IOS switches have a single config for stacks or chassis')

This library also provides an interface for the Mearki Action Batch API, which allows us to group all API calls to configure a switchport into a single Action Batch... using this we can make a single API call to provision all switchports on a switch (rather than 24 or 48 individual API calls)


## Youtube Demo of IOS2Meraki Library
https://www.youtube.com/watch?v=6YNBlKm8erA

You can run the demo yourself with the following steps:
1. Clone the github repo:
```
git clone https://github.com/mattchilders/IOS2Meraki.git
```

2. Install the Python dependencies (create a virtualenv if you'd like.)
```
python3 -m venv IOS2Meraki/
pip install -r requirements.txt
```

3. Rename the api_config_example.json to api_config.json and edit to include your API key and org id.

4. Modify meraki_demo.py to include serial numbers of your own switches.  You can use fewer than four switches, just remove the additional switches from the switch mapping.  Also, make sure these switches are claimed into your org's inventory.
```
switch_mapping = {'Switch1': 'XXXX-XXXX-XXXX', 'Switch2': 'XXXX-XXXX-XXXX', 'Switch3': 'XXXX-XXXX-XXXX', 'Switch4': 'XXXX-XXXX-XXXX'}
```

5. Modify MERAKI_NETWORK variable in meraki_demo.py to the name of the network you want to create the switches in.

```
MERAKI_NETWORK = 'Site1'
```

6. Run the meraki_demo.py script
```
python meraki_demo.py
```

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
        
        # Get just the port num (drop everything before the last '/')
        # GigabitEthernet1/0/10 becomes 10
        meraki_port_num = name[name.rfind('/') + 1:]

        # Get the Meraki switchport Config and add it to the action batch
        payload = port.get_meraki_switchport_api_payload()
        action_batch.add_action("/devices/" + switch_mapping[switch] + "/switchPorts/" + str(meraki_port_num), "update", payload)
        
        # Alternatively, you could get the api payload and just call a switchport config
        # instead of using action batches here.
    
    # Execute the action batch
    action_batch.execute_batch()
```

## Action Batch Handling
Action batches are a way to group API calls into a single API call.  For example, when configuring a 48 port switch, it requires 48 (+ 4 uplinks) switchport API calls to configure each port.  An action batch can take all 52 of these API calls and batch them together, and submit one API call to do the same thing.  The ActionBatch() class in IOS2Meraki, enables you to use this functionality.  It uses the add_action() method to add individual API calls into a batch like below:

```
action_batch = IOS2Meraki.ActionBatch(api_key, org_id)
action_batch.add_action(url, "update", payload)
```
https://developer.cisco.com/meraki/api/#/rest/guides/action-batches

Action batches work differently than individual API calls, in that when you submit an action batch for execution, it doesn't immediately give you a response.  Instead it returns an ID that you can use to check the status of your action batch, to see when it has completed (or failed).  For this functionality IOS2Meraki also includes a ActionBatchGroup() class, which handles the details of executing and monitoring your Action Batches.  You need to add your Action Batch to the ActionBatchGroup Object and then execute the group.  Action Batches have limitations around the maximum number that can be run simultaneously (5), so the ActionBatchGroup object also handles splitting the batches for you and running them in groups.

```
action_batch = IOS2Meraki.ActionBatch(api_key, org_id)
action_batch.add_action(url, "update", payload)

action_batch_group = IOS2Meraki.ActionBatchGroup()
action_batch_group.add_action_batch(name, action_batch)
action_batch_group.execute()
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
