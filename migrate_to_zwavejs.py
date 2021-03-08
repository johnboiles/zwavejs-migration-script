#!/usr/bin/python3

import argparse
import asyncio
import json
import os

import asyncws
from sty import fg

# Include any manually renamed pairs here
manual_rename_dict = {
    # Example entry:
    # "light.zjs_light_entity_id": "light.bedroom_light",    
}

message_id = 1

async def send_and_wait(websocket, request):
    '''Send a Websocket message and wait for the corresonding response'''
    message_id = request.get('id')    
    await websocket.send(json.dumps(request))

    message = await websocket.recv()
    if message is None:
        print('Received empty message')
        return None

    response = json.loads(message)
    if response.get('id') != message_id:
        print('Invalid message ID in response request={request} response={response}')    
        return None

    return response

async def get_platform_devices(websocket, platform):
    global message_id
    request = {
        'type': 'config/device_registry/list',
        'id': message_id,
    }
    response = await send_and_wait(websocket, request)
    message_id += 1

    devices = []
    for device in response["result"]:
        identifiers = device.get('identifiers')
        if len(identifiers) > 0 and identifiers[0][0] == platform:
            identifier = identifiers[0][0]
            devices.append(device)

    return devices


async def get_platform_entities(websocket, platform):
    global message_id
    request = {
        'type': 'config/entity_registry/list',
        'id': message_id,
    }
    response = await send_and_wait(websocket, request)
    message_id += 1

    entities = []
    all_entities = response["result"]
    for entity in all_entities:
        # EG , zwave_js
        if entity.get('platform') == platform:
            entities.append(entity)

    return entities


# TODO: Also do icon?
async def rename_entity(websocket, entity_id, new_entity_id, name=None):
    global message_id
    request = {
        'id': message_id,
        'type': 'config/entity_registry/update',
        'entity_id': entity_id,
        'new_entity_id': new_entity_id,
    }
    if name is not None:
        request['name'] = name
    response = await send_and_wait(websocket, request)
    message_id += 1

    if response is None or response["success"] == False:
        print(f'Error renaming: {entity_id}')
        return False

    return True


async def wait_for_message_id(websocket, message_id):
    while True:
        message = await websocket.recv()
        if message is None:
            return None
        response = json.loads(message)
        if "id" in response and response["id"] == message_id:
            return response
        else:
            print(f'discaring response: {response}')


async def build_zjs_node_dict(websocket, platform='zwave_js'):
    entities = await get_platform_entities(websocket, platform)
    devices = await get_platform_devices(websocket, platform)

    # Build a mapping of device_ids to node_ids
    devices_to_nodes = {}
    # Device
    # {'name': 'MotionLight',
    # 'identifiers': [['zwave_js', '3672945806-47']],
    # 'area_id': 'masterbathroom',
    # 'name_by_user': None,
    # 'disabled_by': None
    # }
    for device in devices:
        identifier = device.get('identifiers')[0][1]
        _, node_id = identifier.split('-')
        devices_to_nodes[device['id']] = node_id

    # Build a mapping of node_id to dicts containing entity_id and name pairs
    nodes_to_entities = {}
    # Entity
    # {'device_id': 'afd495d7e6d5db432f159256c1409954',
    # 'disabled_by': None,
    # 'entity_id': 'light.motionlight',
    # 'name': None,
    # 'icon': None,
    # 'platform': 'zwave_js'}
    for entity in entities:
        node_id = devices_to_nodes[entity['device_id']]
        node_dict = nodes_to_entities.get(node_id, {})
        node_dict[entity['entity_id']] = entity['name']
        nodes_to_entities[node_id] = node_dict
    
    return nodes_to_entities


# TODO: This is nearly the same as the zwave_js version, but node
# IDs are stored differently, could probably refactor this for better
# code reuse
async def build_ozw_node_dict(websocket, platform='ozw'):
    entities = await get_platform_entities(websocket, platform)
    devices = await get_platform_devices(websocket, platform)

    # Build a mapping of device_ids to node_ids
    devices_to_nodes = {}
    # Device
    # {'manufacturer': 'Zooz',
    # 'model': 'ZSE40 4-in-1 sensor',
    # 'name': 'Basement Motion',
    # 'sw_version': '32.02',
    # 'entry_type': None,
    # 'id': '8456a2f6ff255c9911dd13d5d6406589',
    # 'identifiers': [['ozw', '1.46.1']],
    # 'via_device_id': None,
    # 'area_id': None,
    # 'name_by_user': None,
    # 'disabled_by': None}
    for device in devices:
        identifier = device.get('identifiers')[0][1]
        _, node_id, _ = identifier.split('.')
        devices_to_nodes[device['id']] = node_id

    # Build a mapping of node_id to dicts containing entity_id and name pairs
    nodes_to_entities = {}
    # Entity
    # {'config_entry_id': '44e9eebce414058a04702b146a80d2e6',
    # 'device_id': 'b25ce08e59828c6afe04d62923600a4f',
    # 'area_id': None,
    # 'disabled_by': None,
    # 'entity_id': 'light.master_bathroom_light',
    # 'name': 'Master Bathroom Light',
    # 'icon': None,
    # 'platform': 'ozw'}
    for entity in entities:
        node_id = devices_to_nodes[entity['device_id']]
        node_dict = nodes_to_entities.get(node_id, {})
        node_dict[entity['entity_id']] = entity['name']
        nodes_to_entities[node_id] = node_dict
    
    return nodes_to_entities


async def main():
    parser = argparse.ArgumentParser(description="Migration tool for renaming ZWaveJS entities semi-automatically based on their OpenZWave names.")
    parser.add_argument('--url', default='ws://homeassistant.local:8123/api/websocket', help="URL for the websocket as used by the HA frontend.")
    parser.add_argument('--commit', action='store_true', help="Actually do the renaming. If not set, this script will just print all the renames it _wants_ to do.")
    parser.add_argument('--rollback', action='store_true', help="If specified, this will remove the suffix from all the OpenZWave nodes. Run this after deleting the ZWaveJS integration if you want to roll back.")
    parser.add_argument('--access_token', default=os.environ.get('HA_ACCESS_TOKEN'), help="This must either be passed in as an arg or in the environment variable HA_ACCESS_TOKEN")
    args = parser.parse_args()
    rollback = args.rollback
    commit = args.commit
    access_token = args.access_token
    url = args.url

    if not access_token:
        exit(parser.print_help())

    errors = 0
    renamed = 0
    not_renamed = 0
    ozw_suffix = '_ozwmigration'

    websocket = await asyncws.connect(url)

    async def rename_if_commit(entity_id, new_entity_id):
        nonlocal commit
        nonlocal renamed
        nonlocal errors
        print(fg.magenta + entity_id + fg.li_blue + '->' + fg.cyan + new_entity_id + fg.rs)
        if commit:
            success = await rename_entity(websocket, entity_id, new_entity_id)
            if success:
                renamed += 1
            else:
                errors += 1

    await websocket.send(json.dumps(
        {
            'type': 'auth',
            'access_token': access_token
        }
    ))

    # Wait for login
    while True:
        message = await websocket.recv()
        response = json.loads(message)
        if response["type"] == "auth_ok":
            break

    ozw_nodes_to_entities = await build_ozw_node_dict(websocket)

    if rollback:
        for node_id in ozw_nodes_to_entities:
            for entity_id in ozw_nodes_to_entities[node_id]:
                if entity_id.endswith(ozw_suffix):
                    new_entity_id = entity_id[:-len(ozw_suffix)]
                    await rename_if_commit(entity_id, new_entity_id)
        print(fg.green + f'Rolled back {renamed} entities ({errors} errors) entities' + fg.rs)
        exit()

    zjs_nodes_to_entities = await build_zjs_node_dict(websocket)
    if len(zjs_nodes_to_entities) == 0:
        print(fg.red + "Didn't find any ZWaveJS Nodes, exiting")
        exit()
    
    # Rename all ozw nodes out of the way
    print(fg.green + f'Suffixing OpenZWave nodes with {ozw_suffix}' + fg.rs)
    ozw_entity_ids = []
    for node_id in ozw_nodes_to_entities:
        for entity_id in ozw_nodes_to_entities[node_id]:
            if entity_id.endswith(ozw_suffix):
                print(fg.yellow + f'Entity {entity_id} already has suffix, skipping.')
                continue
            new_entity_id = f'{entity_id}{ozw_suffix}'
            await rename_if_commit(entity_id, new_entity_id)

    # For each zjs node
    print(fg.green + f'Renaming ZWaveJS nodes' + fg.rs)
    unable_to_resolve = {}
    all_node_ids = set([node_id for node_id in zjs_nodes_to_entities])
    for node_id in zjs_nodes_to_entities:
        # Look up the same node from the ozw list
        ozw_node = ozw_nodes_to_entities[node_id]
        zjs_node = zjs_nodes_to_entities[node_id]

        # For each entity of the node
        for zjs_entity_id in zjs_node:
            # If the entity is in the manual rename list, just rename
            if zjs_entity_id in manual_rename_dict:
                new_entity_id = manual_rename_dict[zjs_entity_id]
                all_node_ids.discard(node_id)
                await rename_if_commit(zjs_entity_id, new_entity_id)
                continue

            # TODO: It would be awesome to add some fuzzy matching based on similarity of names

            # If there is one entity of a type, rename to the original ozw name
            entity_type = zjs_entity_id.split('.')[0]
            zjs_entities_of_type = [e for e in zjs_node if e.split('.')[0] == entity_type]
            ozw_entities_of_type = [e for e in ozw_node if e.split('.')[0] == entity_type]
            if len(ozw_entities_of_type) == 1 and len(zjs_entities_of_type) == 1:
                ozw_entity_id = ozw_entities_of_type[0]
                all_node_ids.discard(node_id)
                await rename_if_commit(zjs_entity_id, ozw_entity_id)
                continue

            # If the above two are not true then print out (so we can build the manual renaming list)
            line = unable_to_resolve.get(node_id, {})
            line[zjs_entity_id] = ozw_entities_of_type
            unable_to_resolve[node_id] = line

    # global not_renamed
    if len(unable_to_resolve) > 0:
        print(fg.yellow + f'Note: Could not auto-rename some entities.')
        print(f'You can copy/paste the below `manual_rename_dict` as a starting')
        print(f'point for adding manual renaming entries.' + fg.rs)
        print('manual_rename_dict = {')
        for node_id in unable_to_resolve:
            unrenamed_entities = unable_to_resolve[node_id]
            for entity_id in unrenamed_entities:
                not_renamed += 1
                possible_names = unrenamed_entities[entity_id]
                possible_names_string = ''
                if len(possible_names) > 0:
                    possible_names_string = f'entities: {", ".join(possible_names)}'
                print(f"    '{entity_id}': '??', # Node {node_id} {possible_names_string}")
        print('}')

    if len(all_node_ids) > 0:
        print(fg.yellow + f'Warning: Nodes {all_node_ids} had no entities renamed' + fg.rs)

    print(fg.green + f'Renamed {renamed} entities ({errors} errors) and skipped {not_renamed} entities' + fg.rs)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
