
import sys
sys.path.insert(0, r'E:\\EDR\\EDRTest\\automation')
sys.path.insert(0, r'E:\\EDR\\EDRTest\\automation\\core')
from stdout_parser import parse_stdout_phases, parse_stdout
txt = open(r'E:\\EDR\\EDRTest\\automation\\runs\\Account\\ACCOUNT-CREATE-001\\ACCOUNT-CREATE-001_stdout.txt', encoding='utf-8').read()
runs = parse_stdout_phases(txt)
if not runs:
    runs = [parse_stdout(txt)]
for r in runs:
    print('test_case_id=', r.test_case_id)
    print('target_fields=', dict(r.target_fields))
    print('run_start=', r.run_start_utc, 'run_end=', r.run_end_utc)
    print('target_begin=', r.target_begin_utc, 'target_end=', r.target_end_utc)
