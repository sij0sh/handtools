"""Draft workflow contract (G5/D10): foundation and untangle are expressible in it.

Checks the schema's required keys and enums plus the M4 semantic rules (known transitions,
reachable stages, defined outcomes, evidence gates). No runtime enforcement yet.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'skills' / '_engine' / 'policy' / 'workflow-contract.schema.json').read_text())
INSTANCES = sorted((ROOT / 'tests' / 'fixtures' / 'workflow-contracts').glob('*.json'))


def problems(m):
    out = [f'missing {k}' for k in SCHEMA['required'] if k not in m]
    out += [f'unknown {k}' for k in m if k not in SCHEMA['properties']]
    if out:
        return out
    recon = m['recon']
    if recon['depth'] not in SCHEMA['properties']['recon']['properties']['depth']['enum']:
        out.append('recon.depth')
    if recon['depth'] == 'none' and not recon.get('reason'):
        out.append('recon none needs a reason')
    if recon['depth'] != 'none':
        out += [f'recon.{k}' for k in ('required_records', 'external_scope', 'freshness') if k not in recon]
    names = [s['name'] for s in m['stages']]
    stage_keys = SCHEMA['properties']['stages']['items']['required']
    for s in m['stages']:
        out += [f'{s.get("name")}: missing {k}' for k in stage_keys if k not in s]
        out += [f'{s["name"]}: unknown next {n}' for n in s.get('next', []) if n is not None and n not in names]
        if not s.get('exit_check'):
            out.append(f'{s["name"]}: no exit check')
    reach, todo = {names[0]}, [names[0]]
    by_name = {s['name']: s for s in m['stages']}
    while todo:
        for n in by_name[todo.pop()]['next']:
            if n in by_name and n not in reach:
                reach.add(n)
                todo.append(n)
    out += [f'unreachable stage {n}' for n in names if n not in reach]
    if not any(None in s['next'] for s in m['stages']):
        out.append('no stage ends the run')
    if not m['outcomes'] or set(m['outcomes']) - {'complete', 'incomplete', 'cancelled'}:
        out.append('outcomes')
    return out


class WorkflowContractTest(unittest.TestCase):
    def test_existing_workflows_are_expressible(self):
        self.assertEqual([p.stem for p in INSTANCES], ['foundation', 'untangle'])
        for path in INSTANCES:
            with self.subTest(manifest=path.name):
                self.assertEqual(problems(json.loads(path.read_text())), [])

    def test_rules_reject_broken_manifests(self):
        good = json.loads(INSTANCES[0].read_text())
        self.assertIn('recon none needs a reason', problems(dict(good, recon={'depth': 'none'})))
        broken = json.loads(json.dumps(good))
        broken['stages'][0]['next'] = ['interview', 'nowhere']
        self.assertTrue(any('unknown next' in p for p in problems(broken)))
        self.assertIn('outcomes', problems(dict(good, outcomes=['success'])))


if __name__ == '__main__':
    unittest.main()
