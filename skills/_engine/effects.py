"""Durable intent and reconciliation for build-skills' multi-file target application."""
import hashlib
import shutil
from pathlib import Path
from . import storage


def target_lock(target):
    key = hashlib.sha256(str(Path(target).resolve()).encode()).hexdigest()
    return storage.lock(storage.state_root() / 'target-locks' / key)


def apply(base, session, draft, target, copy_skill, overlay, tree_hash, recover=None):
    """Intent is committed before target writes. Replay never calls this function."""
    store = storage.journal(base)
    key = 'effect/' + session['effect_id']
    expected_dir = Path(base) / session['id'] / 'application' / target.name
    with target_lock(target):
        if target.is_symlink() or any(p.is_symlink() for p in target.rglob('*')):
            raise ValueError('target contains symlinks; application refused')
        intent = store.read(key)
        if intent is None:
            if session.get('mode') == 'revise':
                backup = Path(base) / session['id'] / 'backup' / target.name
                if not backup.exists() or tree_hash(backup) != session['target_hash']:
                    raise ValueError('backup unavailable or changed; restore original backup before applying')
            baseline = tree_hash(target) if target.exists() else None
            if baseline != session['target_hash']:
                raise ValueError('target changed since GROUND; replan before applying')
            if tree_hash(draft) != session['draft_hash']:
                raise ValueError('draft changed after acceptance')
            if expected_dir.exists():
                shutil.rmtree(expected_dir)
            if target.exists():
                copy_skill(target, expected_dir)
            else:
                expected_dir.mkdir(parents=True)
            overlay(draft, expected_dir)
            intent = {'before': baseline, 'after': tree_hash(expected_dir), 'status': 'prepared',
                      'draft_hash': session['draft_hash'], 'expected_dir': str(expected_dir)}
            store.put(key, intent)
        if not expected_dir.exists() or tree_hash(expected_dir) != intent['after']:
            raise ValueError('application bytes unavailable or changed; recover from backup')
        current = tree_hash(target) if target.exists() else None
        if current == intent['after']:
            intent['status'] = 'applied'
            store.put(key, intent)
            return intent
        if intent['status'] == 'applied':
            raise ValueError('target changed after application; reconcile manually')
        if current != intent['before']:
            if recover != 'retry':
                raise ValueError('partial/conflicting application; inspect target and backup; send recover=retry after reconciliation')
            # Never overwrite an external edit: only preimage/postimage bytes are eligible.
            backup = Path(base) / session['id'] / 'backup' / target.name
            before = {p.relative_to(backup).as_posix(): p.read_bytes() for p in backup.rglob('*') if p.is_file()} if backup.exists() else {}
            after = {p.relative_to(expected_dir).as_posix(): p.read_bytes() for p in expected_dir.rglob('*') if p.is_file()}
            missing = [rel for rel in before.keys() & after.keys() if not (target / rel).is_file()]
            if missing:
                raise ValueError('conflicting missing target file: ' + missing[0])
            for p in target.rglob('*'):
                if p.is_file():
                    rel = p.relative_to(target).as_posix()
                    if p.read_bytes() not in (before.get(rel), after.get(rel)):
                        raise ValueError('conflicting target bytes: ' + rel)
        if tree_hash(draft) != intent['draft_hash']:
            raise ValueError('draft changed after intent; restore accepted draft')
        overlay(draft, target)
        if tree_hash(target) != intent['after']:
            raise ValueError('application verification failed; reconcile before retry')
        intent['status'] = 'applied'
        store.put(key, intent)
        return intent
