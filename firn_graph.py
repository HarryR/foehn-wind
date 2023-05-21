import os
import pickle
from dataclasses import dataclass
from collections import defaultdict

from firn_scan import SYNC_CACHE_FILE, SyncCache

# Notes:
# https://cs.stackexchange.com/questions/2875/determining-probability-from-a-graph

@dataclass(frozen=True)
class Deposit:
    height: int
    tx: bytes
    address: bytes
    amount: int

@dataclass(frozen=True)
class FundSource:
    deposit: Deposit
    chance: float

@dataclass
class PossibleBalance:
    height: int
    balance: int
    tx: bytes
    sources: set[FundSource]

def shorthex(x:bytes):
    return x.hex()[2:10]

def main():
    if not os.path.exists(SYNC_CACHE_FILE):
        raise RuntimeError('Sync cache no exist!', SYNC_CACHE_FILE)
    with open(SYNC_CACHE_FILE, 'rb') as handle:
        cache:SyncCache = pickle.load(handle)

    balances = defaultdict(list[PossibleBalance])
    total_deposits = defaultdict(int)

    print('digraph "Firn" {')
    for height in sorted(cache['blocks'].keys()):
        #print('Height', height)
        #print(f"\tsubgraph cluster_{height} {{")
        #print(f'\t\tlabel = "block {height}";')
        for tx in cache['blocks'][height]:
            #print(f"\t\tsubgraph cluster_{shorthex(tx)} {{")
            #print(f'\t\t\tlabel = "tx {shorthex(tx)}";')
            for e in cache['blocks'][height][tx]:
                if e['event'] == 'RegisterOccurred':
                    account = e['args']['account']
                    amount = e['args']['amount']
                    sender = e['args']['sender']
                    pb = PossibleBalance(height, amount, tx, set([FundSource(Deposit(height, tx, sender, amount), 1.0)]))
                    balances[account].append(pb)
                    total_deposits[account]= amount
                    print(f'\t\th{height}_tx{shorthex(tx)} [label="{amount}", style=filled, fillcolor="green"];')
                    print(f"\t\taddr_{sender} -> h{height}_tx{shorthex(tx)};")
                    #print(f'\t\t\th{height}_tx{shorthex(tx)}_{shorthex(account)} [label="+{amount}", tooltip="{shorthex(account)} = {amount}"];')
                    #print(f'\t\t\th{height}_tx{shorthex(tx)} -> h{height}_tx{shorthex(tx)}_{shorthex(account)};')
                elif e['event'] == 'WithdrawalOccurred':
                    amount = e['args']['amount']
                    #print(f'\t\th{height}_tx{shorthex(tx)} [label="{amount}", style=filled, fillcolor="red"];')
                    filtered_accounts = []
                    for account in e['args']['Y']:
                        if account == bytes([0]*32):
                            continue
                        if amount > total_deposits[account]:
                            continue
                        filtered_accounts.append(account)
                    sources:dict[Deposit,float] = defaultdict(float)
                    for account in filtered_accounts:
                        pb = balances[account][-1]
                        new_balance = pb.balance - (amount/len(filtered_accounts))
                        for s in pb.sources:
                            sources[s.deposit] += s.chance * (1/len(filtered_accounts))
                        nb = PossibleBalance(height, new_balance, tx, pb.sources)
                        balances[account].append(nb)
                    destination = e["args"]["destination"]
                    for d, p in sources.items():
                        print(f'\t\th{d.height}_tx{shorthex(d.tx)} -> addr_{destination} [weight={max(1,int(p*20))}, penwidth={max(1,int(p*20))}, len={10-max(1,int(p*10))}];')
                elif e['event'] == 'DepositOccurred':
                    amount = e['args']['amount']
                    source = e['args']['source']
                    print(f'\t\th{height}_tx{shorthex(tx)} [label="{amount}", style=filled, fillcolor="green"];')
                    print(f"\t\taddr_{source} -> h{height}_tx{shorthex(tx)};")
                    filtered_accounts = [account for account in e['args']['Y'] if account != bytes([0]*32)]
                    d = Deposit(height, tx, source, amount)
                    for account in filtered_accounts:
                        pb = balances[account][-1]
                        ns = set([FundSource(_.deposit, _.chance/((1/(len(filtered_accounts)-1))*len(filtered_accounts))) for _ in pb.sources])
                        ns.add(FundSource(d, 1/len(filtered_accounts)))
                        nb = PossibleBalance(height, pb.balance + (amount/len(filtered_accounts)), tx, ns)
                        balances[account].append(nb)
                        total_deposits[account] += amount
                elif e['event'] == 'TransferOccurred':
                    raise RuntimeError('Transfer unhandled!', e)
                else:
                    raise RuntimeError('Unhandled error', e)
            #print("\t\t}")  # end of tx cluster
        #print("\t}")  # end of height cluster
    print("}")
if __name__ == "__main__":
    main()

