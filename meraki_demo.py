import IOS2Meraki
from meraki import meraki
import glob
import json
import os

switch_mapping = {'Switch1': 'XXXX-XXXX-XXXX', 'Switch2': 'XXXX-XXXX-XXXX', 'Switch3': 'XXXX-XXXX-XXXX', 'Switch4': 'XXXX-XXXX-XXXX'}
MERAKI_NETWORK = 'Site1'
CONFIG_PATH = 'data/*.txt'

# Edit api_config.json to include your api_key, org_id
with open('api_config.json', 'r') as api_config:
    settings = json.loads(api_config.read())

api_key = settings['api_key']
org_id = settings['org_id']
network_id = IOS2Meraki.get_network(api_key, org_id, MERAKI_NETWORK)

site = IOS2Meraki.Site('Site1')
configs = glob.glob(CONFIG_PATH)
for config_file in configs:
    switch_name = os.path.basename(config_file).replace('.txt', '')
    switch = IOS2Meraki.Switch(switch_name, config_file)
    site.add_switch(switch)

# Create an Action Batch Group object to handle the execution and monitoring
# of the action batch for each switch.
action_batch_group = IOS2Meraki.ActionBatchGroup()

for switch in site.list_switches():
    current_switch = site.get_switch(switch)
    serial_number = switch_mapping[switch]
    # Add the Meraki Device to the Network
    IOS2Meraki.add_device_to_network(api_key, network_id, serial_number)
    # Name the switch
    meraki.updatedevice(api_key, network_id, serial_number, name=switch)

    # Create Action Batch for all switchport configs for this switch
    action_batch = IOS2Meraki.ActionBatch(api_key, org_id)

    for name, port in current_switch.interfaces.items():
        # Ignore FastEthernet (such as management ports)
        if 'GigabitEthernet' not in name:
            continue

        # Get just the port num (drop everything before the last '/')
        # GigabitEthernet1/0/10 becomes 10
        meraki_port_num = name[name.rfind('/') + 1:]

        # Get the Meraki switchport Config and add it to the action batch
        payload = port.get_meraki_switchport_api_payload()
        url = "/devices/" + serial_number + "/switchPorts/" + str(meraki_port_num)
        action_batch.add_action(url, "update", payload)

    # Add the action batch to an ActionBatchGroup for execution
    action_batch_group.add_action_batch(switch, action_batch)

# ActionBatchGroup object handles the grouping and execution of ActionBatches.
# We can execute a maximum of 5 action batches at a time, and the execute method
# of the ActionBatchGroup handles the grouping, execution, and then monitors
# the status of each action batch.  Once those have completed, it will move on
# to the next group of 5 until all Action Batches have completed or failed.
action_batch_group.execute()

print('Completed')
