import base64
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import forgejo_release as release

SOURCE = 'a' * 40
REVISION = 'b' * 40
PLAN = release.release_plan('0.0.0', SOURCE, [(SOURCE, 'feat: portable skills')])


class ProposalAPI:
    """Faithful ordering fixture: no transport, tokens or actual repository."""
    def __init__(self):
        self.main = SOURCE
        self.branch = None
        self.plan = None
        self.pr = None
        self.writes = []
        self.fail_after_branch = False

    def listing(self, path):
        return [self.pr] if self.pr else []

    def request(self, path, method='GET', data=None, **kwargs):
        if method != 'GET':
            self.writes.append((path, method, data))
        if path == 'branches/main':
            return {'commit': {'id': self.main}}
        if path.startswith('branches/'):
            return {'commit': {'id': self.branch}} if self.branch else None
        if path == 'branches':
            self.branch = data['old_ref_name']
            if self.fail_after_branch:
                raise release.Refusal('indeterminate fixture write')
            return {}
        if path.startswith('contents/'):
            if 'ref=release-pr' in path and self.plan:
                return {'content': base64.b64encode(json.dumps(self.plan).encode()).decode()}
            return None
        if path == 'contents':
            for operation in data['files']:
                if operation['path'] == 'release-plan.json':
                    self.plan = json.loads(base64.b64decode(operation['content']))
            return {}
        if path == 'pulls':
            self.pr = {'number': 1, 'head': {'ref': data['head']}, 'base': {'ref': data['base']}}
            return self.pr
        if path == 'pulls/1':
            return self.pr
        raise AssertionError(path)


class ReleaseTests(unittest.TestCase):
    def test_conventional_versions_and_prose_control(self):
        for previous, subject, expected in [('1.2.3', 'fix: repair', '1.2.4'),
                ('1.2.3', 'feat: feature', '1.3.0'), ('1.2.3', 'feat!: incompatible', '2.0.0'),
                ('0.2.3', 'feat!: incompatible', '0.3.0'),
                ('1.2.3', 'fix: repair\n\nBREAKING CHANGE: new contract', '2.0.0')]:
            with self.subTest(subject=subject, previous=previous):
                self.assertEqual(release.release_plan(previous, SOURCE, [(SOURCE, subject)])['version'], expected)
        self.assertIsNone(release.release_plan('1.2.3', SOURCE, [(SOURCE, 'docs: explain')]))

    def test_invalid_version_and_revision_refuse(self):
        for version, source in [('01.2.3', SOURCE), ('1.2.3-rc1', SOURCE), ('1.2.3', 'HEAD')]:
            with self.assertRaises(release.Refusal):
                release.release_plan(version, source, [])

    def test_proposal_creates_exact_three_files_and_readbacks(self):
        api = ProposalAPI()
        with patch.object(release, 'plan_from_git', return_value=PLAN):
            self.assertEqual(release.propose(api, Path('.'), SOURCE), {'state': 'created', 'number': 1})
        self.assertEqual([x[0] for x in api.writes], ['branches', 'contents', 'pulls'])
        self.assertEqual({x['path'] for x in api.writes[1][2]['files']}, release.FILES)
        self.assertEqual(api.plan, PLAN)

    def test_existing_identical_proposal_is_read_only(self):
        api = ProposalAPI()
        with patch.object(release, 'plan_from_git', return_value=PLAN):
            release.propose(api, Path('.'), SOURCE)
            api.writes.clear()
            self.assertEqual(release.propose(api, Path('.'), SOURCE)['state'], 'existing')
        self.assertEqual(api.writes, [])

    def test_advanced_main_refuses_before_writes(self):
        api = ProposalAPI()
        api.main = REVISION
        with patch.object(release, 'plan_from_git', return_value=PLAN), self.assertRaises(release.Refusal):
            release.propose(api, Path('.'), SOURCE)
        self.assertEqual(api.writes, [])

    def test_indeterminate_branch_write_never_blindly_repeats(self):
        api = ProposalAPI()
        api.fail_after_branch = True
        with patch.object(release, 'plan_from_git', return_value=PLAN):
            with self.assertRaises(release.Refusal):
                release.propose(api, Path('.'), SOURCE)
            with self.assertRaisesRegex(release.Refusal, 'indeterminate release branch'):
                release.propose(api, Path('.'), SOURCE)
        self.assertEqual(len(api.writes), 1)

    def test_changed_proposal_does_not_claim_old_review(self):
        api = ProposalAPI()
        with patch.object(release, 'plan_from_git', return_value=PLAN):
            release.propose(api, Path('.'), SOURCE)
            api.writes.clear()
            api.plan['source_revision'] = REVISION
            with self.assertRaisesRegex(release.Refusal, 'refresh'):
                release.propose(api, Path('.'), SOURCE)
        self.assertEqual(api.writes, [])

    def test_exact_merged_release_admission_and_negative_controls(self):
        pr = {'merged': True, 'merge_commit_sha': REVISION, 'base': {'ref': 'main'},
              'head': {'ref': 'release-pr/0.1.0', 'repo': {'full_name': 'example/skills'}},
              'body': release.MARKER}
        release.admitted_release(pr, 'example/skills', REVISION, PLAN, release.FILES)
        for field, value in [('merged', False), ('merge_commit_sha', SOURCE), ('body', '')]:
            bad = copy.deepcopy(pr)
            bad[field] = value
            with self.assertRaises(release.Refusal):
                release.admitted_release(bad, 'example/skills', REVISION, PLAN, release.FILES)
        with self.assertRaises(release.Refusal):
            release.admitted_release(pr, 'another/skills', REVISION, PLAN, release.FILES)
        with self.assertRaises(release.Refusal):
            release.admitted_release(pr, 'example/skills', REVISION, PLAN, release.FILES | {'extra'})

    def test_cross_origin_asset_never_reaches_transport(self):
        api = release.Forgejo('https://forge.example', 'example/skills', 'fixture-token')
        with patch.object(api.opener, 'open') as transport, self.assertRaises(release.Refusal):
            api.request('https://foreign.example/asset', binary=True)
        transport.assert_not_called()

    def test_publisher_missing_merged_marker_is_read_only(self):
        api = ProposalAPI()
        api.pr = {'merged': True, 'merge_commit_sha': REVISION, 'body': 'ordinary PR'}
        self.assertIsNone(release.publish(api, Path('.'), REVISION, Path('unused')))
        self.assertEqual(api.writes, [])

    def test_execution_refuses_wrong_event_ref_or_revision_before_api(self):
        for event, ref, sha in [('pull_request', 'refs/heads/main', SOURCE),
                ('workflow_dispatch', 'refs/heads/main', SOURCE),
                ('push', 'refs/heads/feature', SOURCE), ('push', 'refs/heads/main', REVISION)]:
            with self.subTest(event=event, ref=ref, sha=sha), \
                    patch.object(sys, 'argv', ['forgejo_release.py', '--execute']), \
                    patch.dict(os.environ, {'FORGEJO_EVENT_NAME': event, 'FORGEJO_REF': ref,
                                            'FORGEJO_SHA': sha}, clear=True), \
                    patch.object(release, 'git', return_value=SOURCE.encode()), \
                    patch.object(release, 'Forgejo') as constructor:
                with self.assertRaises(release.Refusal):
                    release.main()
                constructor.assert_not_called()

    def test_publisher_asset_readback_and_tag_mismatch(self):
        class PublisherAPI:
            repository = 'example/skills'

            def __init__(self):
                self.writes = []
                self.assets = {}
                self.tag = None
                self.release = None
                self.corrupt = False

            def listing(self, path):
                if path == 'pulls?state=closed':
                    return [{'number': 1, 'merged': True, 'merge_commit_sha': REVISION,
                             'base': {'ref': 'main'}, 'head': {'ref': 'release-pr/0.1.0',
                             'repo': {'full_name': self.repository}}, 'body': release.MARKER}]
                if path == 'pulls/1/files':
                    return [{'filename': name} for name in release.FILES]
                if path == 'releases':
                    return []
                if path == 'releases/1/assets':
                    return [{'name': name, 'browser_download_url': 'asset/' + name}
                            for name in self.assets]
                raise AssertionError(path)

            def request(self, path, method='GET', data=None, **kwargs):
                if method != 'GET':
                    self.writes.append((path, method))
                if path == 'branches/main':
                    return {'commit': {'id': REVISION}}
                if path == 'tags':
                    self.tag = {'commit': {'sha': data['target']}}
                    return self.tag
                if path == 'tags/v0.1.0':
                    return self.tag
                if path == 'releases':
                    self.release = {'id': 1, 'draft': True, 'tag_name': data['tag_name']}
                    return self.release
                if path == 'releases/tags/v0.1.0':
                    return self.release
                if path.startswith('releases/1/assets?name='):
                    name = path.split('name=')[1]
                    self.assets[name] = data.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n--', 1)[0]
                    return {}
                if path.startswith('asset/'):
                    return b'corrupt' if self.corrupt else self.assets[path[6:]]
                if path == 'releases/1':
                    if method == 'PATCH':
                        self.release.update(data)
                    return self.release
                raise AssertionError(path)

        def package(root, revision, output, version):
            output.mkdir()
            for name in ['skein-0.1.0.tar.gz', 'SHA256SUMS', 'bundle.json']:
                (output / name).write_bytes(name.encode())
            return {'version': '0.1.0'}

        for case in ['positive', 'wrong-tag', 'corrupt-asset']:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                api = PublisherAPI()
                if case == 'wrong-tag':
                    api.tag = {'commit': {'sha': SOURCE}}
                api.corrupt = case == 'corrupt-asset'
                with patch.object(release, 'committed', return_value=json.dumps(PLAN).encode()), \
                        patch.object(release, 'plan_from_git', return_value=PLAN), \
                        patch.object(release, 'git', side_effect=lambda root, *args:
                                     f'{REVISION} {SOURCE}'.encode() if args[0] == 'rev-list' else b''), \
                        patch.object(release, 'build_bundle', side_effect=package):
                    if case == 'positive':
                        result = release.publish(api, Path('.'), REVISION, Path(temp) / 'out')
                        self.assertEqual(result['state'], 'published')
                        self.assertEqual(set(api.assets), {'skein-0.1.0.tar.gz', 'SHA256SUMS', 'bundle.json'})
                        self.assertFalse(api.release['draft'])
                    else:
                        with self.assertRaises(release.Refusal):
                            release.publish(api, Path('.'), REVISION, Path(temp) / 'out')
                        self.assertNotIn(('releases/1', 'PATCH'), api.writes)
                        if case == 'wrong-tag':
                            self.assertEqual(api.writes, [])


class MergedPlanTests(unittest.TestCase):
    def exercise(self, stale):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / 'repo'
        root.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args],
                                           stderr=subprocess.DEVNULL, text=True).strip()
        git('init', '-q')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        git('config', 'maintenance.auto', 'false')
        git('config', 'gc.auto', '0')
        for name, data in {'version.txt': '0.0.0\n', 'README.md': 'Skills\n',
                           'LICENSE': 'MIT\n', 'skills/example/SKILL.md': 'Example\n'}.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        git('add', '.')
        git('commit', '-qm', 'fix: initial skill')
        source = git('rev-parse', 'HEAD')
        plan = release.plan_from_git(root, source)
        if stale:
            (root / 'README.md').write_text('A newer feature\n')
            git('add', '.')
            git('commit', '-qm', 'feat: newer feature')
            self.assertEqual(release.plan_from_git(root, git('rev-parse', 'HEAD'))['version'], '0.1.0')
            self.assertEqual(plan['version'], '0.0.1')
        for name, data in {'version.txt': plan['version'] + '\n',
                           'CHANGELOG.md': '# Changelog\n', 'release-plan.json': json.dumps(plan)}.items():
            (root / name).write_text(data)
        git('add', '.')
        git('commit', '-qm', 'chore(release): ' + plan['version'])
        revision = git('rev-parse', 'HEAD')

        class TagBoundary(RuntimeError):
            pass

        class API:
            repository = 'example/skills'
            attempts = 0

            def listing(self, path):
                if path == 'pulls?state=closed':
                    return [{'number': 1, 'merged': True, 'merge_commit_sha': revision,
                             'body': release.MARKER, 'base': {'ref': 'main'},
                             'head': {'ref': 'release-pr/' + plan['version'],
                                      'repo': {'full_name': self.repository}}}]
                if path == 'pulls/1/files':
                    return [{'filename': name} for name in release.FILES]
                raise AssertionError(path)

            def request(self, path, method='GET', data=None, **kwargs):
                if path == 'branches/main':
                    return {'commit': {'id': revision}}
                if path.startswith('tags/') and method == 'GET':
                    return None
                if path == 'tags' and method == 'POST':
                    self.attempts += 1
                    raise TagBoundary('private tag boundary')
                raise AssertionError((path, method))

        api = API()
        output = Path(temp.name) / 'assets'
        with self.assertRaises(release.Refusal if stale else TagBoundary):
            release.publish(api, root, revision, output)
        self.assertEqual(api.attempts, 0 if stale else 1)
        if stale:
            self.assertFalse(output.exists())

    def test_current_source_parent_reaches_private_tag_positive_control(self):
        self.exercise(False)

    def test_newer_unplanned_main_changes_refuse_before_assets_or_tag(self):
        self.exercise(True)


if __name__ == '__main__':
    unittest.main()
