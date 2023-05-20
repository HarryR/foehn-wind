import os
import pickle
from dataclasses import dataclass
from collections import defaultdict

from firn_scan import SYNC_CACHE_FILE, SyncCache

@dataclass
class PossibleBalance:
    height: int
    balance: int
    tx: bytes

def shorthex(x:bytes):
    return x.hex()[2:10]

def main():
    if not os.path.exists(SYNC_CACHE_FILE):
        raise RuntimeError('Sync cache no exist!', SYNC_CACHE_FILE)
    with open(SYNC_CACHE_FILE, 'rb') as handle:
        cache:SyncCache = pickle.load(handle)

    #known_accounts = set()

    balances = defaultdict(list[PossibleBalance])

    print('digraph "Firn" {')
    for height in sorted(cache['blocks'].keys()):
        #print('Height', height)
        print(f"\tsubgraph cluster_{height} {{")
        print(f'\t\tlabel = "block {height}";')
        for tx in cache['blocks'][height]:
            print(f"\t\tsubgraph cluster_{shorthex(tx)} {{")
            print(f'\t\t\tlabel = "tx {shorthex(tx)}";')
            #print('\ttx', tx)
            for e in cache['blocks'][height][tx]:
                if e['event'] == 'RegisterOccurred':
                    account = e['args']['account']
                    #known_accounts.add(e['args']['account'])
                    #print('\t\tRegister', e['args']['account'])
                    balances[account].append(PossibleBalance(height, 0, tx))
                    print(f'\t\t\th{height}_tx{shorthex(tx)}_{shorthex(account)} [label="{shorthex(account)}"];')
                elif e['event'] == 'WithdrawalOccurred':
                    #print('\t\tWithdraw', e['args']['amount'], e['args']['Y'])
                    amount = e['args']['amount']
                    print(f'\t\th{height}_tx{shorthex(tx)} [label="{amount}", style=filled, fillcolor="red"];')
                    for account in e['args']['Y']:
                        if account == bytes([0]*32):
                            continue
                        pb = balances[account][-1]
                        new_balance = pb.balance - amount
                        nb = PossibleBalance(height, new_balance, tx)
                        balances[account].append(nb)
                        print(f'\t\t\th{height}_tx{shorthex(tx)}_{shorthex(account)} [label="{shorthex(account)} = {new_balance}"];')
                        print(f'\t\t\th{pb.height}_tx{shorthex(pb.tx)}_{shorthex(account)} -> h{height}_tx{shorthex(tx)}_{shorthex(account)};')
                        print(f'\t\t\th{height}_tx{shorthex(tx)}_{shorthex(account)} -> h{height}_tx{shorthex(tx)};')
                elif e['event'] == 'DepositOccurred':
                    #print('\t\tDeposit', e['args']['amount'], e['args']['Y'])
                    amount = e['args']['amount']
                    print(f'\t\th{height}_tx{shorthex(tx)} [label="{amount}", style=filled, fillcolor="green"];')
                    for account in e['args']['Y']:
                        if account == bytes([0]*32):
                            continue
                        pb = balances[account][-1]
                        nb = PossibleBalance(height, pb.balance + amount, tx)
                        balances[account].append(nb)
                        print(f'\t\t\th{height}_tx{shorthex(tx)}_{shorthex(account)} [label="{shorthex(account)} = {new_balance}"];')
                        print(f'\t\t\th{pb.height}_tx{shorthex(pb.tx)}_{shorthex(account)} -> h{height}_tx{shorthex(tx)}_{shorthex(account)};')
                        print(f'\t\t\th{height}_tx{shorthex(tx)} -> h{height}_tx{shorthex(tx)}_{shorthex(account)};')
                elif e['event'] == 'TransferOccurred':
                    #print('\t\tTransfer', e['args']['Y'])
                    raise RuntimeError('Transfer unhandled!', e)
                    pass
                else:
                    raise RuntimeError('Unhandled error', e)
                    #print('\t\t', e)
            print("\t\t}")  # end of tx cluster
        print("\t}")  # end of height cluster
    print("}")
if __name__ == "__main__":
    main()

