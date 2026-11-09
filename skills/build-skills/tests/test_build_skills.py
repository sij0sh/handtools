"""End-to-end tests: copy the skill to a temp dir and drive scripts/build-skills.py as the agent would."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE.parent))
if str(SOURCE / 'scripts') not in sys.path:
    sys.path.insert(0, str(SOURCE / 'scripts'))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.home = self.tmp / 'state'  # HANDTOOLS_STATE: never the real ~/.agents/state
        env = mock.patch.dict(os.environ, {'HANDTOOLS_STATE': str(self.home)})
        env.start()
        self.addCleanup(env.stop)
        self.skill = self.tmp / 'build-skills'
        for sub in ('scripts', 'references', 'templates'):
            shutil.copytree(SOURCE / sub, self.skill / sub, ignore=shutil.ignore_patterns('__pycache__'))
        # handtools' engine beside the skill, as in an installed bundle
        shutil.copytree(SOURCE.parent / '_engine', self.tmp / '_engine', ignore=shutil.ignore_patterns('__pycache__'))
        self.project = self.tmp / 'project'
        self.project.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cmd(self, *args, payload=None, root=None, ok=True, script='scripts/build-skills.py'):
        cmd = [sys.executable, str(self.skill / script), '--root', str(root or self.project), *args]
        data = json.dumps(payload) if payload is not None else ''
        proc = subprocess.run(cmd, input=data, capture_output=True, text=True)
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return proc.stdout
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        return proc.stderr

    def done(self, payload=None, sid='s1', ok=True):
        return self.run_cmd('done', '--session', sid, payload=payload if payload is not None else {}, ok=ok)

    def registry(self, root=None):
        root = str((root or self.project).resolve())
        from _engine.events import Journal
        for f in (self.home / 'build-skills').glob('*/events.sqlite3'):
            data = Journal(f).read('workflow.json')
            if data['root'] == root:
                return data
        raise AssertionError('registry not found')

    def session(self, sid='s1'):
        return next(s for s in self.registry()['sessions'] if s['id'] == sid)

    def ground_payload(self, **extra):
        payload = {'mode': 'new', 'kind': 'prompt', 'target': 'skills/demo', 'purpose': 'p', 'trigger': 't', 'gap': 'g',
                   'pass_condition': 'pc', 'plan': {'goal': 'p', 'constraints': [], 'criteria': ['pc'],
                   'decisions': [], 'blocking': [], 'verification': 'inspect output', 'challenged': True},
                   'confirmed': True}
        payload.update(extra)
        return payload

    def start(self, sid='s1', **extra):
        self.run_cmd('start')
        return self.done(self.ground_payload(**extra), sid)

    def design(self, model='stateless', router=False, ok=True, **extra):
        criteria = {'stateful': ['focus', 'resume']}.get(model, [])
        payload = {'model': model, 'router': router, 'why': 'w', 'confirmed': True,
                   'criteria': criteria + (['conditional'] if router else []),
                   'stages': [{'name': n, 'output': 'o', 'check': 'c'} for n in 'xyz']}
        payload.update(extra)
        return self.done(payload, ok=ok)

    def review(self, findings=None, ok=True, **extra):
        payload = {'findings': findings if findings is not None else
                   [{'file': 'SKILL.md:1', 'finding': 'f', 'action': 'applied', 'why': 'w'}], 'confirmed': True}
        payload.update(extra)
        out = self.done(payload, ok=ok)
        if ok and payload.get('confirmed') and 'PHASE: APPLY' in out:
            self.done()
            out = self.done()
        return out

    def wdir(self, kind='draft', sid='s1'):
        return next((self.home / 'build-skills').glob(f'*/{sid}/{kind}/demo'))

    def write_skill(self, path, body='Do the thing.', ref=False):
        path.mkdir(parents=True, exist_ok=True)
        if ref:
            body += '\nSee references/more.md.'
            (path / 'references').mkdir(exist_ok=True)
            (path / 'references' / 'more.md').write_text('more')
        (path / 'SKILL.md').write_text(
            f'---\nname: demo\ndescription: Use when testing.\ndisable-model-invocation: true\n---\n\n{body}\n')
        return path

    def staged(self, path, mode):
        shutil.copytree(self.skill / 'templates' / 'workflow' / 'scripts', path / 'scripts', dirs_exist_ok=True)
        steps = path / 'scripts' / 'steps.py'
        steps.write_text(steps.read_text().replace("MODE = 'stateful'", f"MODE = '{mode}'").replace("ORDER = ['plan', 'work', 'verify']", "ORDER = ['x', 'y', 'z']"))

    def to_review(self, **extra):
        self.start(**extra)
        self.write_skill(self.wdir())
        return self.done()


class Sessions(Base):
    def test_concurrent_sessions_and_abandon_keeps_record(self):
        self.run_cmd('start')
        self.run_cmd('start')
        self.assertIn('pass --session', self.run_cmd('done', payload={}, ok=False))
        self.run_cmd('abandon', '--session', 's1')
        self.assertEqual(self.session('s1')['status'], 'abandoned')
        self.assertIn('s2', self.run_cmd('status'))
        self.assertIn('s1', self.run_cmd('status', '--all'))

    def test_project_keys_are_isolated(self):
        other = self.tmp / 'other' / 'project'
        other.mkdir(parents=True)
        self.run_cmd('start')
        self.run_cmd('start', root=other)
        self.assertEqual(len(list((self.home / 'build-skills').glob('*/events.sqlite3'))), 2)

    def test_target_held_by_one_active_session(self):
        self.start()
        self.run_cmd('start')
        self.assertIn('held by', self.done(self.ground_payload(), 's2', ok=False))

    def test_ground_requires_confirmation(self):
        self.run_cmd('start')
        self.assertIn('confirmed', self.done(self.ground_payload(confirmed=False), ok=False))
        self.assertIn('kind', self.done(self.ground_payload(kind='semantic'), ok=False))
        self.assertIn('PHASE: DESIGN', self.done(self.ground_payload(kind='staged')))


class Stages(Base):
    def test_saved_prompt_skips_design(self):
        out = self.start(wording='Summarize the diff.')
        self.assertIn('PHASE: DRAFT', out)
        self.assertIn('Kind: saved prompt', out)
        self.assertIn('Summarize the diff.', out)
        self.assertNotIn('design', self.session())
        self.write_skill(self.wdir())
        out = self.done()
        self.assertIn('exactly this text', out)
        self.assertIn("wording only if they agree", out)
        self.assertIn('Kind: saved prompt.', self.review())

    def test_design_validates_and_writes_artifact(self):
        self.start(kind='staged')
        self.assertIn('model', self.design('semantic', ok=False))
        self.assertIn('confirmed', self.design(confirmed=False, ok=False))
        self.assertIn('PHASE: DRAFT', self.design())
        design = self.session()['design']
        self.assertEqual(design['model'], 'stateless')
        self.assertEqual(design['backend'], 'none')
        self.assertNotIn('artifact', design)

    def test_design_criteria_and_stages(self):
        self.start(kind='staged')
        stages = [{'name': n, 'output': 'o', 'check': 'c'} for n in 'xyz']
        self.assertIn('labels', self.design(criteria=['nope'], ok=False))
        self.assertIn('stateful needs', self.design('stateful', criteria=['focus'], ok=False))
        self.assertIn('requires stateful', self.design('stateless', criteria=['focus', 'loop'], ok=False))
        self.assertIn('conditional', self.design(router=True, criteria=[], ok=False))
        self.assertIn('`stages`', self.design('stateless', stages=[], ok=False))
        self.assertIn('output', self.design('stateless', stages=[{'name': 'x', 'check': 'c'}], ok=False))
        self.assertIn('loop_limit', self.design('stateful', criteria=['focus', 'loop'], ok=False))
        looped = stages[:2] + [dict(stages[2], loop_limit=0)]
        self.assertIn('>= 1', self.design('stateful', criteria=['focus', 'loop'], stages=looped, ok=False))
        looped[2]['loop_limit'] = 3
        out = self.design('stateful', criteria=['gate', 'loop'], stages=looped)
        self.assertIn("ORDER = ['x', 'y', 'z']", out)
        self.assertEqual(self.session()['design']['stages'][2]['loop_limit'], 3)
        self.assertEqual(self.session()['design']['criteria'], ['gate', 'loop'])

    def test_draft_checks_order_matches_stages(self):
        self.start(kind='staged')
        self.design('stateful', stages=[{'name': n, 'output': 'o', 'check': 'c'} for n in 'xy'])
        self.write_skill(self.wdir())
        self.assertIn('must match design stages', self.done(ok=False))

    def test_ground_requires_gap(self):
        self.run_cmd('start')
        payload = self.ground_payload()
        del payload['gap']
        self.assertIn('gap', self.done(payload, ok=False))

    def test_draft_checks_files(self):
        self.start()
        self.assertIn('SKILL.md', self.done(ok=False))
        path = self.write_skill(self.wdir())
        (path / 'references').mkdir()
        (path / 'references' / 'orphan.md').write_text('x')
        self.assertIn('orphan.md', self.done(ok=False))

    def test_draft_checks_short_description_and_invocation(self):
        self.start()
        path = self.write_skill(self.wdir())
        skill = path / 'SKILL.md'
        text = skill.read_text()
        skill.write_text(text.replace('disable-model-invocation: true\n', ''))
        self.assertIn('disable-model-invocation', self.done(ok=False))
        skill.write_text(text.replace('Use when testing.', 'x' * 101))
        self.assertIn('1-100', self.done(ok=False))

    def test_model_gate_and_engine_install(self):
        self.start(kind='staged')
        out = self.design('stateless', router=True)
        self.assertIn('done --stage S', out)
        path = self.write_skill(self.wdir())
        steps = path / 'scripts' / 'steps.py'
        self.assertIn("MODE = 'stateless'", steps.read_text())
        self.assertIn(f"AREA = '{path.name}'", steps.read_text())
        engine = path / 'scripts' / '_engine'
        self.assertEqual((engine / 'flow.py').read_bytes(), (SOURCE.parent / '_engine' / 'flow.py').read_bytes())
        self.assertFalse((engine / 'tests').exists())
        self.assertTrue((engine / 'recon' / 'cli.py').is_file())
        self.assertFalse((engine / 'recon' / 'SKILL.md').exists())
        self.assertEqual(json.loads((engine / 'distribution.json').read_text()),
                         {'engine_api': 1, 'event_schema': 1, 'policy': 1, 'recon': 1, 'backend': 'none'})
        steps.write_text(steps.read_text().replace("ORDER = ['plan', 'work', 'verify']", "ORDER = ['x', 'y', 'z']"))
        self.assertIn('router', self.done(ok=False))
        self.staged(path, 'stateful')
        self.assertIn("MODE = 'stateless'", self.done(ok=False))
        self.staged(path, 'stateless')
        self.write_skill(path, ref=True)
        out = self.done()
        self.assertIn('PHASE: REVIEW', out)
        self.assertIn('steps.py', out)

    def test_prompt_rejects_engine_leaves_and_model_invocation(self):
        self.start()
        path = self.write_skill(self.wdir(), ref=True)
        self.assertIn('remove references/', self.done(ok=False))
        shutil.rmtree(path / 'references')
        self.staged(path, 'stateful')
        self.assertIn('remove scripts/', self.done(ok=False))
        shutil.rmtree(path / 'scripts')
        skill = path / 'SKILL.md'
        skill.write_text(skill.read_text().replace('invocation: true', 'invocation: false'))
        self.assertIn('user-invoked', self.done(ok=False))

    def test_review_gates_and_loop(self):
        out = self.to_review()
        self.assertIn('Loop: 1/3', out)
        self.assertIn('exactly this text', out)
        rejected = [{'file': 'f', 'finding': 'f', 'action': 'rejected', 'why': 'w'}]
        self.assertIn('none_found', self.review(findings=[], ok=False))
        self.assertIn('action', self.review(findings=[dict(rejected[0], action='x')], ok=False))
        self.assertIn('file', self.review(findings=[{'finding': 'f', 'action': 'applied', 'why': 'w'}], ok=False))
        self.assertIn('nothing applied', self.review(findings=rejected, confirmed=False, ok=False))
        self.assertIn('Loop: 2/3', self.review(confirmed=False))
        self.assertIn('Loop: 3/3', self.review(confirmed=False))
        self.assertIn('last', self.review(confirmed=False, ok=False))
        self.assertIn('DONE', self.review(findings=[], none_found=True))
        self.assertEqual(len(self.session()['reviews']), 3)

    def test_review_rechecks_shape(self):
        self.to_review()
        (self.wdir() / 'references').mkdir()
        (self.wdir() / 'references' / 'orphan.md').write_text('x')
        self.assertIn('orphan.md', self.review(confirmed=False, ok=False))
        self.assertEqual(self.session()['reviews'], [])

    def test_finish_new_writes_target(self):
        self.to_review()
        self.assertIn('Written to', self.review())
        self.assertTrue((self.project / 'skills' / 'demo' / 'SKILL.md').is_file())

    def test_new_mode_rejects_existing_target(self):
        self.write_skill(self.project / 'skills' / 'demo')
        self.run_cmd('start')
        self.assertIn('revise', self.done(self.ground_payload(), ok=False))


class Revise(Base):
    def setUp(self):
        super().setUp()
        self.target = self.write_skill(self.project / 'skills' / 'demo', body='Old.')

    def test_backup_and_overlay(self):
        self.start(mode='revise')
        self.assertIn('Old.', (self.wdir('backup') / 'SKILL.md').read_text())
        self.write_skill(self.wdir(), body='New.')
        self.done()
        out = self.review()
        self.assertIn('Original backup', out)
        self.assertIn('New.', (self.target / 'SKILL.md').read_text())
        self.assertIn('Old.', (self.wdir('backup') / 'SKILL.md').read_text())

    def test_model_change_sets_mode(self):
        self.staged(self.target, 'stateful')
        self.start(mode='revise', kind='staged')
        self.design('stateless')
        steps = self.wdir() / 'scripts' / 'steps.py'
        self.assertIn("MODE = 'stateless'", steps.read_text())

    def test_staged_to_saved_prompt_removes_scripts(self):
        self.staged(self.target, 'stateful')
        self.start(mode='revise')
        self.assertIn('remove scripts/', self.done(ok=False))
        shutil.rmtree(self.wdir() / 'scripts')
        self.done()
        self.review()
        self.assertFalse((self.target / 'scripts').exists())

    def test_target_changed_blocks_finish(self):
        self.start(mode='revise')
        self.done()
        (self.target / 'SKILL.md').write_text((self.target / 'SKILL.md').read_text() + 'edit\n')
        self.assertIn('changed since GROUND', self.review(ok=False))


class Template(Base):
    script = 'templates/workflow/scripts/workflow.py'

    def states(self):
        from _engine.events import Journal
        return [p for p in (self.home / 'workflow').glob('*/events.sqlite3') if Journal(p).read('workflow.json') is not None]

    def test_stateful_planning_work_and_verification(self):
        self.assertIn('STEP: PLAN', self.run_cmd('start', script=self.script))
        self.assertIn('unfinished', self.run_cmd('start', script=self.script, ok=False))
        self.assertEqual(len(self.states()), 1)
        self.assertIn('plan', self.run_cmd('done', script=self.script, ok=False))
        self.run_cmd('done', script=self.script, payload={'plan': self.ground_payload()['plan']})
        self.assertIn('result', self.run_cmd('done', script=self.script, ok=False))
        self.run_cmd('done', script=self.script, payload={'result': 'produced'})
        self.assertIn('evidence', self.run_cmd('done', script=self.script, ok=False))
        self.assertIn('DONE', self.run_cmd('done', script=self.script, payload={'passed': True, 'evidence': 'observed result'}))
        self.assertEqual(self.states(), [])

    def test_abandon_and_resume_isolation(self):
        other = self.tmp / 'other'; other.mkdir()
        self.run_cmd('start', script=self.script)
        self.run_cmd('start', script=self.script, root=other)
        self.assertEqual(len(self.states()), 2)
        self.run_cmd('abandon', script=self.script)
        self.assertIn('STEP: PLAN', self.run_cmd('status', script=self.script, root=other))
        self.assertIn('STEP: PLAN', self.run_cmd('start', script=self.script))

    def test_ephemeral_uses_no_persistent_state(self):
        steps = self.skill / 'templates/workflow/scripts/steps.py'
        steps.write_text(steps.read_text().replace("MODE = 'stateful'", "MODE = 'stateless'"))
        self.assertIn('done --stage plan', self.run_cmd('start', script=self.script))
        self.run_cmd('done', '--stage', 'plan', script=self.script, payload={'plan': self.ground_payload()['plan']})
        self.assertIn('nothing', self.run_cmd('status', script=self.script, ok=False))
        self.assertFalse((self.home / 'workflow').exists())


class RecoveryAndPlanning(Base):
    def accepted(self):
        self.to_review()
        out = self.done({'findings': [], 'none_found': True, 'confirmed': True})
        self.assertIn('PHASE: APPLY', out)
        return self.session()

    def test_acceptance_does_not_write_target_and_apply_verifies(self):
        s = self.accepted()
        self.assertFalse(Path(s['target']).exists())
        self.assertIn('PHASE: VERIFY', self.done())
        self.assertTrue(Path(s['target']).is_dir())
        self.assertIn('DONE', self.done())
        self.assertEqual(self.session()['status'], 'complete')

    def test_changed_accepted_draft_cannot_apply(self):
        s = self.accepted()
        (self.wdir() / 'SKILL.md').write_text((self.wdir() / 'SKILL.md').read_text()+'changed')
        self.assertIn('draft changed', self.done(ok=False))
        self.assertFalse(Path(s['target']).exists())

    def test_crash_after_write_is_reconciled_without_duplicate_effect(self):
        from _engine import effects, storage
        from build_skills.skill import copy_skill, overlay, tree_hash
        s = self.accepted()
        base = self.wdir().parents[2]
        def interrupted(src, dst):
            overlay(src, dst)
            if dst == Path(s['target']):
                raise OSError('simulated interrupted completion')
        with self.assertRaises(OSError):
            effects.apply(base, s, self.wdir(), Path(s['target']), copy_skill, interrupted, tree_hash)
        self.assertEqual(self.session()['phase'], 'apply')
        self.assertIn('PHASE: VERIFY', self.done())
        self.assertIn('DONE', self.done())
        self.assertEqual(storage.journal(base).read('effect/'+s['effect_id'])['status'], 'applied')

    def test_partial_writes_require_explicit_reconciliation(self):
        from _engine import effects
        from build_skills.skill import copy_skill, overlay, tree_hash
        s = self.accepted(); base = self.wdir().parents[2]
        def interrupted(src, dst):
            if dst == Path(s['target']):
                dst.mkdir(parents=True, exist_ok=True)
                (dst / 'external.txt').write_text('external edit')
                raise OSError('interrupted')
            overlay(src, dst)
        with self.assertRaises(OSError):
            effects.apply(base, s, self.wdir(), Path(s['target']), copy_skill, interrupted, tree_hash)
        self.assertIn('partial/conflicting', self.done(ok=False))
        self.assertIn('conflicting target bytes', self.done({'recover':'retry'}, ok=False))

    def test_replan_preserves_run_and_invalidates_acceptance(self):
        self.to_review()
        plan = self.ground_payload()['plan']; plan['goal'] = 'revised goal'
        out = self.done({'replan':True, 'plan':plan})
        self.assertIn('PHASE: DRAFT', out)
        self.assertEqual(self.session()['plan_revision'], 2)
        self.assertNotIn('authorization', self.session())
        self.assertTrue(self.wdir().exists())

    def test_revision_flags_make_command_retry_idempotent(self):
        self.run_cmd('start')
        payload = self.ground_payload()
        args = ['done', '--session', 's1', '--expect-revision', '0', '--request-id', 'ground-once']
        self.run_cmd(*args, payload=payload)
        self.run_cmd(*args, payload=payload)
        self.assertEqual(self.session()['revision'], 1)
        self.assertEqual(self.session()['phase'], 'draft')
        changed = dict(payload, purpose='changed')
        self.assertIn('different payload', self.run_cmd(*args, payload=changed, ok=False))
        self.assertIn('stale', self.run_cmd('done', '--session', 's1', '--expect-revision', '0', payload={}, ok=False))

    def test_ready_plan_required_at_authoring_boundary(self):
        self.run_cmd('start')
        payload = self.ground_payload(); payload['plan']['blocking'] = ['missing intent']
        self.assertIn('needs_input', self.done(payload, ok=False))
        self.assertEqual(self.session()['phase'], 'ground')


class CodexPolicyTest(unittest.TestCase):
    def make(self, root, invocation, yaml=None):
        skill = Path(root) / 'demo'
        skill.mkdir()
        (skill / 'SKILL.md').write_text(f'---\nname: demo\ndescription: Demo.\ndisable-model-invocation: {invocation}\n---\nBody\n',
                                        encoding='utf-8')
        if yaml is not None:
            (skill / 'agents').mkdir()
            (skill / 'agents' / 'openai.yaml').write_text(yaml, encoding='utf-8')
        return skill

    def test_writes_policy_from_frontmatter(self):
        from build_skills.skill import write_codex_policy
        with tempfile.TemporaryDirectory() as tmp:
            path = write_codex_policy(self.make(tmp, 'true'))
            self.assertEqual(path.read_text(), 'policy:\n  allow_implicit_invocation: false\n')

    def test_updates_existing_yaml_in_place(self):
        from build_skills.skill import write_codex_policy
        with tempfile.TemporaryDirectory() as tmp:
            yaml = 'interface:\n  display_name: Demo\npolicy:\n  allow_implicit_invocation: false\n'
            text = write_codex_policy(self.make(tmp, 'false', yaml)).read_text()
            self.assertIn('display_name: Demo', text)
            self.assertIn('  allow_implicit_invocation: true', text)
            self.assertNotIn('false', text)

if __name__ == '__main__':
    unittest.main()
