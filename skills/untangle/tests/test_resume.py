import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class AuditResume(unittest.TestCase):
    def test_inventory_resumes_from_journal_with_shared_policy(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/workflow.py'
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / 'project'; root.mkdir()
            (root/'app.py').write_text('print(1)\n')
            env = dict(os.environ, HANDTOOLS_STATE=str(Path(name)/'state'))
            def run(args, payload=None):
                result = subprocess.run([sys.executable,str(script),'--root',str(root)]+args,
                                        input=json.dumps(payload) if payload else '', text=True,
                                        capture_output=True, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout
            self.assertIn('STEP: INVENTORY', run(['start']))
            self.assertIn('STEP: MAP', run(['done'], {'approved_by_user':True,
                'limits':{'max_files':100,'max_bytes':100000},'exclude':[]}))
            self.assertIn('STEP: MAP', run(['status']))
            self.assertEqual(len(list((Path(name)/'state').rglob('events.sqlite3'))), 1)
            self.assertEqual(list((Path(name)/'state').rglob('workflow.json')), [])
