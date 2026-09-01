import json
from pathlib import Path

RUNS = Path(r'E:\EDR\results\runs')
CONFIG = Path(r'E:\EDR\automation\config')

cases = json.load(open(CONFIG / 'test_cases.json', encoding='utf-8'))['cases']
ev = json.load(open(CONFIG / 'sysmon_evidence.json', encoding='utf-8'))

# 期望 EventID 前缀映射
EXPECT = {'REG':[12,13],'PROC-CREATE':[1],'PROC-TERMINATE':[5],'PROC-ACCESS':[10],
          'PROC-TAMPER':[8,10],'PROC-REMOTE-THREAD':[8],'PROC-IMAGE-LOAD':[7],
          'FILE-CREATE':[11],'FILE-OPEN':[11],'FILE-MODIFY':[11],'FILE-RENAME':[11],'FILE-DELETE':[23,26],
          'NET-TCP':[3],'NET-UDP':[3],'NET-URL':[3],'NET-DNS':[22],'NET-DOWNLOAD':[3],
          'DRIVER':[6],'WMI':[19,20,21],'PIPE':[17,18],'HASH':[1],'PS':[1],'BIT':[1],
          'GPO':[1],'DEVICE':[1],'ACCOUNT':[1],'TASK':[1],'SVC':[1]}

def exp_ids(cid):
    for p, ids in EXPECT.items():
        if cid.startswith(p):
            return ids
    return [1]

print("模块\tCase\t行为\t样本\tSysmon基线EventID\t结论")
for c in sorted(cases, key=lambda x:(x['module'], x['id'])):
    cid = c['id']; mod = c['module']; bhv = c.get('behavior',''); prog = c.get('program','')
    e = ev.get(cid, {})
    if not e:
        print(f"{mod}\t{cid}\t{bhv}\t{prog}\t—\t无证据(无evtx/Driver)")
        continue
    got = set(str(k) for k in e.get('event_ids', {}))
    base = [str(x) for x in exp_ids(cid)]
    hit = [b for b in base if b in got]
    miss = [b for b in base if b not in got]
    if hit:
        print(f"{mod}\t{cid}\t{bhv}\t{prog}\t{','.join(base)}\t✓ 采到{hit}")
    else:
        print(f"{mod}\t{cid}\t{bhv}\t{prog}\t{','.join(base)}\t✗ 缺{miss}")

print()
print("=== 测试时间覆盖（各 case 的 TARGET 时间窗）===")
tw = []
for c in sorted(cases, key=lambda x:(x['module'], x['id'])):
    p = RUNS / c['module'] / c['id'] / 'target_window.json'
    if p.exists():
        d = json.loads(p.read_text(encoding='utf-8'))
        tw.append((c['id'], d.get('begin','')[:19], d.get('end','')[:19]))
if tw:
    earliest = min(t[1] for t in tw if t[1])
    latest = max(t[2] for t in tw if t[2])
    print(f"共 {len(tw)} 个 case 有时间窗记录")
    print(f"整体时间范围: {earliest} ~ {latest}")
    for cid, b, e in tw:
        print(f"  {cid}: {b} ~ {e}")
