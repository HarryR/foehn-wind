import os
from os.path import dirname
import sys
import json
from typing import TypedDict
import requests
import pickle
from collections import defaultdict
from web3.types import EventData
from eth_utils.abi import event_abi_to_log_topic
from eth_utils.hexadecimal import encode_hex

class SyncCache(TypedDict):
    highest_block: int
    blocks: dict[int,dict[str,list[EventData]]]

ALCHEMY_API_KEY = None
try:
    import thaw_config as config
    ALCHEMY_API_KEY = config.ALCHEMY_API_KEY
except ImportError:
    ALCHEMY_API_KEY = os.getenv('ALCHEMY_API_KEY')
if ALCHEMY_API_KEY is None:
    raise RuntimeError('Cold not retrieve "ALCHEMY_API_KEY" from environment or "thaw_config.py"')

SOURCE_DIR = dirname(__file__)
FIRN_ABI_FILE = os.path.join(SOURCE_DIR, 'firn-abi.json')

from web3.contract import Contract
from web3 import Web3
from alchemy import Alchemy, Network

FIRN_PROXY = Web3.to_checksum_address('0x6cb5b67ebe8af11a8b88d740f95dd1316c26b701')
FIRN_DEPLOY_HEIGHT = 15949152
FIRN_IMPL = Web3.to_checksum_address('0x4ce75eafd588f36de4b4b6e15f5e4e44b2e67aa0')

SYNC_CACHE_FILE = os.path.join(SOURCE_DIR, 'sync-cache.pickle')

def get_firn_abi():
    if not os.path.exists(FIRN_ABI_FILE):
        resp = requests.get('https://api.etherscan.io/api?module=contract&action=getabi&address=' + FIRN_IMPL)
        data = resp.json()
        if data["status"] != "1":
            raise RuntimeError(data.get("message"))
        with open(FIRN_ABI_FILE, 'w') as handle:
            abi = json.loads(data['result'])
            handle.write(json.dumps(abi))
    if not os.path.exists(FIRN_ABI_FILE):
        raise RuntimeError('Firn abi file no exist', FIRN_ABI_FILE)
    with open(FIRN_ABI_FILE, 'r') as handle:
        return json.load(handle)

def make_ctx() -> tuple[Web3, Alchemy, Contract]:
    w3 = Web3(Web3.HTTPProvider("https://eth-mainnet.g.alchemy.com/v2/" + ALCHEMY_API_KEY))
    alc = Alchemy(ALCHEMY_API_KEY, Network.ETH_MAINNET)
    contract = w3.eth.contract(address=FIRN_PROXY, abi=get_firn_abi())
    return w3, alc, contract



def main():
    w3, alc, contract = make_ctx()

    cache = dict(highest_block=FIRN_DEPLOY_HEIGHT, blocks=dict())
    if os.path.exists(SYNC_CACHE_FILE):
        with open(SYNC_CACHE_FILE, 'rb') as handle:
            cache = pickle.load(handle)

    # Web3 py API is frankly fucking abysmally shit and retardedly hostile to the most common use cases
    parsed_events = [
        contract.events.WithdrawalOccurred(),
        contract.events.RegisterOccurred(),
        contract.events.DepositOccurred(),
        contract.events.TransferOccurred()
    ]
    event_topics = {encode_hex(event_abi_to_log_topic(e._get_event_abi())): e for e in parsed_events}

    while True:
        logs = alc.core.get_logs({
            'address': FIRN_PROXY,
            'fromBlock': cache['highest_block'] + 1
        })
        if not len(logs):
            break
        for l in logs:
            e = event_topics.get(l['topics'][0].hex())
            if e is None:
                continue
            x: EventData = e.process_log(l)
            if cache['highest_block'] is None or x['blockNumber'] > cache['highest_block']:
                cache['highest_block'] = x['blockNumber']
            if cache['highest_block'] not in cache['blocks']:
                print('Block', x['blockNumber'])
                cache['blocks'][cache['highest_block']] = defaultdict(list)
            cache['blocks'][cache['highest_block']][x['transactionHash']].append(x)
            print('\t', x['event'], 'tx', x['transactionHash'].hex())
        with open(SYNC_CACHE_FILE, 'wb') as handle:
            pickle.dump(cache, handle)
    return 0

if __name__ == "__main__":
    sys.exit(main())
