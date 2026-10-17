"""Synthetic filesystem/schema regressions; not evidence of human learning or agent behavior."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skill/human-rlaif/scripts/workspace.py'
if not SCRIPT.exists():
    SCRIPT = ROOT / 'scripts/workspace.py'
spec = importlib.util.spec_from_file_location('workspace_v2', SCRIPT)
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


def event(event_id='example-1', **extra):
    result = dict(id=event_id, mode='learning', human_input='Original judgment',
                ai_feedback='One challenge', human_response='Reason for keeping my view',
                action='pending', reality_feedback='unknown', evidence_status='pending', sources=[])
    result.update(extra)
    if workspace.OPTIONAL_FIELDS & extra.keys():
        day = '08' if 'retest_of' in extra else '01'
        result.setdefault('human_draft_at', f'2026-10-{day}T00:00:00Z')
        result.setdefault('ai_feedback_at', f'2026-10-{day}T00:01:00Z')
    return result


def forecast(event_id='forecast-1', probability=80):
    return event(event_id, prediction_type='binary', prediction='At least five orders arrive.',
                 confidence=probability, resolution_criteria='Count paid orders by October 8.',
                 human_draft_at='2026-10-01T09:00:00Z', ai_feedback_at='2026-10-01T09:01:00Z')


def resolution(event_id='resolution-1', target='forecast-1', outcome=True):
    result = event(event_id, resolves_prediction=target, outcome=outcome)
    result.update(evidence_status='externally_checked', sources=['local:verified-count'],
                  reality_feedback='The original report was checked.')
    return result


class WorkspaceV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'private'
        self.warning_filter = warnings.catch_warnings()
        self.warning_filter.__enter__()
        warnings.simplefilter('ignore', UserWarning)

    def tearDown(self):
        self.warning_filter.__exit__(None, None, None)
        self.temp.cleanup()

    def initialize(self):
        return workspace.init(self.root)

    def record_at(self, data, when='2026-10-02T00:00:00Z'):
        instant = datetime.fromisoformat(when.replace('Z', '+00:00'))
        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz) if tz is not None else instant.replace(tzinfo=None)
        with mock.patch.object(workspace, 'datetime', FrozenDatetime):
            return workspace.record(self.root, data)

    def raw(self, data, when='2026-10-02T00:00:00Z', version=None):
        if version is None:
            version = 2 if workspace.OPTIONAL_FIELDS & data.keys() else 1
        saved = dict(data, recorded_at=when, schema_version=version)
        path = self.root / 'events' / (data['id'] + '.json')
        path.write_text(json.dumps(saved), encoding='utf-8')
        return path

    def test_new_workspace_v2_and_draft_warning(self):
        result = self.initialize()
        self.assertEqual(json.loads((self.root / workspace.MARKER).read_text()), workspace.SCHEMA)
        self.assertTrue(any('draft' in notice for notice in result['warnings']))
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter('always')
            self.record_at(event())
        self.assertTrue(any('HUMAN.md' in str(item.message) and 'draft' in str(item.message) for item in observed))

    def test_legacy_marker_and_event_are_not_migrated(self):
        self.initialize()
        marker = self.root / workspace.MARKER
        marker.write_text('{"skill": "human-rlaif", "schema_version": 1}\n')
        old = self.raw(event('legacy-1'), version=1)
        snapshots = marker.read_bytes(), old.read_bytes()
        self.assertTrue(workspace.doctor(self.root)['ok'])
        self.assertFalse(workspace.init(self.root)['created'])
        simple = self.record_at(event('legacy-2'))
        modern = self.record_at(event('modern-1', task_type='negotiation'))
        self.assertEqual(json.loads(simple.read_text())['schema_version'], 1)
        self.assertEqual(json.loads(modern.read_text())['schema_version'], 2)
        self.assertEqual(len(workspace.read_events(self.root)), 3)
        self.assertEqual((marker.read_bytes(), old.read_bytes()), snapshots)

    def test_original_v1_records_work_through_all_reports_without_changes(self):
        self.initialize()
        marker = self.root / workspace.MARKER
        marker.write_text('{"skill":"human-rlaif","schema_version":1}')
        path = self.raw(event('old-v1'), version=1)
        original_marker, original_event = marker.read_bytes(), path.read_bytes()
        self.assertEqual(workspace.due(self.root, '2026-10-09T00:00:00Z')['count'], 0)
        report = workspace.calibration(self.root)
        self.assertEqual(report['forecast_count'], 0)
        self.assertEqual(report['non_prediction_event_count'], 1)
        output = workspace.export_redacted(self.root, self.base / 'v1-redacted.json')
        exported = json.loads(output.read_text())['events']
        self.assertEqual(exported, [{'id': 'event-0001', 'schema_version': 1,
                                     'mode': 'learning', 'evidence_status': 'pending'}])
        self.assertEqual((marker.read_bytes(), path.read_bytes()), (original_marker, original_event))

    def test_input_and_stored_validation_are_separate(self):
        sample = event()
        workspace.validate_event(sample)
        stored = dict(sample, schema_version=1, recorded_at='2026-10-02T00:00:00Z')
        workspace.validate_stored_event(stored)
        with self.assertRaises(ValueError):
            workspace.validate_event(stored)
        with self.assertRaises(ValueError):
            workspace.validate_stored_event(sample)
        for field in workspace.STORED_FIELDS:
            with self.subTest(field=field), self.assertRaises(ValueError):
                workspace.validate_event(dict(sample, **{field: stored[field]}))

    def test_unknown_fields_rejected_in_input_and_storage(self):
        with self.assertRaises(ValueError):
            workspace.validate_event(event(metadata={'private': '/secret'}))
        for version in (1, 2):
            with self.subTest(version=version), self.assertRaises(ValueError):
                workspace.validate_stored_event(dict(event(extra='x'), schema_version=version,
                                                     recorded_at='2026-10-02T00:00:00Z'))
        with self.assertRaises(ValueError):
            workspace.validate_stored_event(dict(event(task_type='x'), schema_version=1,
                                                 recorded_at='2026-10-02T00:00:00Z'))

    def test_all_optional_descriptive_fields_round_trip(self):
        self.initialize()
        data = event(task_type='pricing', assistance='critique', isolation='partial',
                     rubric_ref='local:rubric-v1', retest_interval=7,
                     due_at='2026-10-08T09:01:00Z', human_draft_at='2026-10-01T09:00:00Z',
                     ai_feedback_at='2026-10-01T09:01:00Z')
        original = json.dumps(data, sort_keys=True)
        saved = json.loads(self.record_at(data).read_text())
        for key in data:
            self.assertEqual(saved[key], data[key])
        self.assertEqual(json.dumps(data, sort_keys=True), original)
        self.assertEqual(saved['recorded_at'], '2026-10-02T00:00:00+00:00')
        workspace.validate_stored_event(saved)

    def test_missing_timestamp_pair_rejected_but_legacy_omission_allowed(self):
        workspace.validate_event(event())
        for key in ('human_draft_at', 'ai_feedback_at'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                workspace.validate_event(dict(event(), **{key: '2026-10-01T09:00:00Z'}))

    def test_nonforecast_v2_learning_assessment_and_clean_require_times(self):
        for mode, extras in [('learning', {'task_type': 'pricing'}),
                             ('assessment', {'isolation': 'unknown'}),
                             ('assessment', {'isolation': 'clean'}),
                             ('learning', {'due_at': '2026-10-08T00:00:00Z'}),
                             ('production', {'isolation': 'clean'})]:
            sample = dict(event(), mode=mode, **extras)
            with self.subTest(mode=mode, extras=extras), self.assertRaises(ValueError):
                workspace.validate_event(sample)
        for mode in ('learning', 'assessment', 'production'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                workspace.validate_event(dict(event(), mode=mode, retest_of='scheduled'))
        with self.assertRaises(ValueError):
            workspace.validate_stored_event(dict(event(), schema_version=2,
                                                 recorded_at='2026-10-02T00:00:00Z'))

    def test_production_exemption_and_legacy_writes_in_new_workspace(self):
        self.initialize()
        for mode in ('learning', 'assessment', 'production'):
            sample = dict(event('legacy-' + mode), mode=mode)
            saved = json.loads(self.record_at(sample).read_text())
            self.assertEqual(saved['schema_version'], 1)
            self.assertNotIn('human_draft_at', saved)
        production = dict(event('production-modern'), mode='production', task_type='delivery',
                          assistance='rewrite', isolation='unknown')
        workspace.validate_event(production)
        saved = json.loads(self.record_at(production).read_text())
        self.assertEqual(saved['schema_version'], 2)
        self.assertNotIn('human_draft_at', saved)
        with self.assertRaises(ValueError):
            workspace.validate_event(dict(production, **{key: forecast()[key] for key in workspace.FORECAST_FIELDS}))

    def test_timestamps_equal_reversed_and_same_instant_offsets_rejected(self):
        pairs = [('2026-10-01T09:00:00Z', '2026-10-01T09:00:00Z'),
                 ('2026-10-01T09:01:00Z', '2026-10-01T09:00:00Z'),
                 ('2026-10-01T09:00:00Z', '2026-10-01T17:00:00+08:00')]
        for first, last in pairs:
            with self.subTest(pair=(first, last)), self.assertRaises(ValueError):
                workspace.validate_event(event(human_draft_at=first, ai_feedback_at=last))

    def test_offsets_compare_by_instant_not_lexical_order(self):
        workspace.validate_event(event(human_draft_at='2026-10-02T00:00:00+08:00',
                                       ai_feedback_at='2026-10-01T17:00:00Z'))
        workspace.validate_event(event(human_draft_at='2026-10-01T09:00:00.000001Z',
                                       ai_feedback_at='2026-10-01T09:00:00.000002Z'))

    def test_invalid_or_naive_times_rejected_everywhere(self):
        invalid = [None, 123, '', '2026-10-01', '2026-10-01T09:00:00',
                   '2026-10-01 09:00:00Z', '2026-02-30T09:00:00Z',
                   '2026-10-01T09:00:00+24:00', '2026-10-01T09:00:00+01:60',
                   '2026-10-01T09:00:00.1234567Z']
        for value in invalid:
            for field in ('due_at', 'recorded_at'):
                with self.subTest(value=value, field=field), self.assertRaises(ValueError):
                    workspace.parse_time(value, field)

    def test_record_rejects_future_claimed_feedback(self):
        self.initialize()
        with self.assertRaises(ValueError):
            self.record_at(forecast(), '2026-10-01T09:00:30Z')
        self.assertEqual(list((self.root / 'events').iterdir()), [])
        self.assertFalse((self.root / '.record.lock').exists())

    def test_optional_types_and_enums_are_strict(self):
        cases = [('task_type', None), ('task_type', ''), ('rubric_ref', []),
                 ('assistance', 'clean'), ('assistance', []), ('isolation', 'independent'),
                 ('retest_interval', True), ('retest_interval', 0), ('retest_interval', -1),
                 ('retest_interval', 1.5), ('retest_interval', '7')]
        for field, value in cases:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                workspace.validate_event(event(**{field: value}))
        with self.assertRaises(ValueError):
            workspace.validate_event(event(retest_interval=7))
        workspace.validate_event(event(retest_interval=7, due_at='2026-10-08T00:00:00Z'))

    def test_due_at_must_follow_feedback(self):
        sample = forecast()
        for value in ('2026-10-01T09:01:00Z', '2026-10-01T09:00:00Z'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                workspace.validate_event(dict(sample, due_at=value))

    def test_due_boundaries_offsets_sorting_missing_dates_and_determinism(self):
        self.initialize()
        for event_id, due_at in [('b', '2026-10-08T08:00:00+08:00'),
                                 ('a', '2026-10-08T00:00:00Z'),
                                 ('earlier', '2026-10-07T23:59:59Z'),
                                 ('future', '2026-10-08T00:00:01Z')]:
            self.record_at(event(event_id, due_at=due_at))
        self.record_at(event('no-schedule'))
        result = workspace.due(self.root, '2026-10-08T00:00:00Z')
        self.assertEqual([row['id'] for row in result['due']], ['earlier', 'a', 'b'])
        self.assertEqual(result, workspace.due(self.root, '2026-10-08T08:00:00+08:00'))
        self.assertEqual(workspace.due(self.root, '2026-10-01T00:00:00Z')['count'], 0)

    def test_due_completion_immutable_explicit_and_historical(self):
        self.initialize()
        path = self.record_at(event('scheduled', due_at='2026-10-08T00:00:00Z'))
        before = path.read_bytes()
        self.record_at(event('unrelated', action='scheduled completed'), '2026-10-09T00:00:00Z')
        self.assertEqual(workspace.due(self.root, '2026-10-09T00:00:00Z')['count'], 1)
        self.record_at(event('retest', retest_of='scheduled'), '2026-10-10T00:00:00Z')
        self.assertEqual(workspace.due(self.root, '2026-10-10T00:00:00Z')['count'], 0)
        self.assertEqual(workspace.due(self.root, '2026-10-09T00:00:00Z')['count'], 1)
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(ValueError):
            self.record_at(event('duplicate', retest_of='scheduled'), '2026-10-11T00:00:00Z')

    def test_due_completion_rejects_missing_early_self_or_unscheduled_links(self):
        self.initialize()
        self.record_at(event('scheduled', due_at='2026-10-08T00:00:00Z'))
        self.record_at(event('unscheduled'))
        for target in ('missing', 'self', 'unscheduled', 'scheduled'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.record_at(event('self', retest_of=target), '2026-10-03T00:00:00Z')
        with self.assertRaises(ValueError):
            self.record_at(event('early-draft', retest_of='scheduled',
                                 human_draft_at='2026-10-07T00:00:00Z',
                                 ai_feedback_at='2026-10-09T00:00:00Z'), '2026-10-10T00:00:00Z')

    def test_due_does_not_trust_invalid_stored_completions(self):
        self.initialize()
        self.record_at(event('scheduled', due_at='2026-10-08T00:00:00Z'))
        early = self.raw(event('early', retest_of='scheduled',
                               human_draft_at='2026-10-02T23:00:00Z',
                               ai_feedback_at='2026-10-02T23:01:00Z'), '2026-10-03T00:00:00Z')
        self.raw(event('dangling', retest_of='missing'), '2026-10-09T00:00:00Z')
        result = workspace.due(self.root, '2026-10-10T00:00:00Z')
        self.assertEqual(result['count'], 1)
        self.assertEqual({x['reason'] for x in result['invalid_completions']},
                         {'completion_before_due', 'missing_scheduled_event'})
        early.unlink()
        self.raw(event('one', retest_of='scheduled'), '2026-10-09T00:00:00Z')
        self.raw(event('two', retest_of='scheduled'), '2026-10-10T00:00:00Z')
        result = workspace.due(self.root, '2026-10-11T00:00:00Z')
        self.assertEqual(result['count'], 1)
        self.assertIn('duplicate_completions', {x['reason'] for x in result['invalid_completions']})

    def test_calibration_empty_has_null_metrics(self):
        self.initialize()
        self.record_at(event())
        result = workspace.calibration(self.root)
        self.assertEqual(result['forecast_count'], 0)
        self.assertEqual(result['scored_count'], 0)
        self.assertEqual(result['non_prediction_event_count'], 1)
        self.assertIsNone(result['brier_score'])
        self.assertIsNone(result['hit_rate'])
        self.assertTrue(all(row['mean_probability'] is None for row in result['bins']))

    def test_calibration_known_brier_hit_rate_bins_and_unresolved(self):
        self.initialize()
        for index, (probability, outcome) in enumerate([(0, False), (20, True), (50, False),
                                                       (80, True), (100, True)]):
            self.record_at(forecast(f'p-{index}', probability))
            self.record_at(resolution(f'r-{index}', f'p-{index}', outcome), '2026-10-09T00:00:00Z')
        self.record_at(forecast('unresolved', 70))
        result = workspace.calibration(self.root)
        self.assertEqual(result['forecast_count'], 6)
        self.assertEqual(result['scored_count'], 5)
        self.assertEqual(result['unresolved_count'], 1)
        self.assertAlmostEqual(result['brier_score'], (0 + .64 + .25 + .04 + 0) / 5)
        self.assertAlmostEqual(result['hit_rate'], .6)
        self.assertEqual([row['count'] for row in result['bins']], [1, 1, 1, 0, 2])
        self.assertAlmostEqual(result['bins'][4]['mean_probability'], .9)
        self.assertEqual(result['bins'][4]['observed_frequency'], 1)
        self.assertIn('不是校准', result['hit_rate_rule'])

    def test_confidence_boundaries_and_nonprobability_rejected(self):
        for valid in (0, 0.1, 50, 99.9, 100):
            workspace.validate_event(forecast(probability=valid))
        for bad in (True, False, -0.1, 100.1, '80%', None, float('nan'), float('inf'), 10**500):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                workspace.validate_event(forecast(probability=bad))
        with self.assertRaises(ValueError):
            workspace.validate_event(dict(forecast(), prediction_type='skill-confidence'))

    def test_forecast_group_and_timestamps_are_required(self):
        for field in workspace.FORECAST_FIELDS | {'human_draft_at', 'ai_feedback_at'}:
            data = forecast()
            del data[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                workspace.validate_event(data)
        for field in ('prediction', 'resolution_criteria'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                workspace.validate_event(dict(forecast(), **{field: ' '}))

    def test_resolution_requires_boolean_verified_source_and_prior_forecast(self):
        self.initialize()
        self.record_at(forecast())
        for bad in (0, 1, None, 'true', 'hit'):
            with self.subTest(outcome=bad), self.assertRaises(ValueError):
                workspace.validate_event(resolution(outcome=bad))
        for key, value in [('sources', []), ('evidence_status', 'reported'), ('reality_feedback', 'unknown')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                workspace.validate_event(dict(resolution(), **{key: value}))
        for data in (event(outcome=True), event(resolves_prediction='forecast-1')):
            with self.assertRaises(ValueError):
                workspace.validate_event(data)
        for target in ('missing', 'resolution-1'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.record_at(resolution(target=target), '2026-10-09T00:00:00Z')
        with self.assertRaises(ValueError):
            self.record_at(resolution(), '2026-10-02T00:00:00Z')

    def test_resolution_preserves_original_and_refuses_second_result(self):
        self.initialize()
        path = self.record_at(forecast())
        before = path.read_bytes()
        self.record_at(resolution(), '2026-10-09T00:00:00Z')
        with self.assertRaises(ValueError):
            self.record_at(resolution('other', outcome=False), '2026-10-10T00:00:00Z')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(workspace.calibration(self.root)['scored_count'], 1)

    def test_calibration_excludes_raw_duplicate_dangling_and_early_resolutions(self):
        self.initialize()
        self.record_at(forecast('duplicated'))
        self.record_at(forecast('early'))
        self.raw(resolution('r1', 'duplicated'), '2026-10-09T00:00:00Z')
        self.raw(resolution('r2', 'duplicated', False), '2026-10-10T00:00:00Z')
        self.raw(dict(resolution('r3', 'early'), human_draft_at='2026-09-30T23:00:00Z',
                      ai_feedback_at='2026-09-30T23:01:00Z'), '2026-10-01T00:00:00Z')
        self.raw(resolution('r4', 'missing'), '2026-10-09T00:00:00Z')
        result = workspace.calibration(self.root)
        self.assertEqual(result['scored_count'], 0)
        self.assertEqual(result['excluded_count'], 3)
        self.assertEqual({item['reason'] for item in result['excluded']},
                         {'duplicate_resolutions', 'resolution_not_after_prediction', 'missing_prediction'})

    def test_init_rolls_back_owned_files_and_new_parents_on_write_failure(self):
        self.root = self.base / 'new-parent' / 'nested' / 'private'
        original = workspace.write_new
        count = 0
        def failing(path, content):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError('injected write failure')
            return original(path, content)
        with mock.patch.object(workspace, 'write_new', side_effect=failing), self.assertRaises(OSError):
            self.initialize()
        self.assertFalse((self.base / 'new-parent').exists())
        self.assertTrue(self.initialize()['created'])

    def test_init_rollback_keeps_unowned_injected_files(self):
        original = workspace.write_new
        def failing(path, content):
            if path.name == 'BASELINE.md':
                (self.root / 'unowned.txt').write_text('keep me')
                raise OSError('injected')
            return original(path, content)
        with mock.patch.object(workspace, 'write_new', side_effect=failing), self.assertRaises(OSError):
            self.initialize()
        self.assertEqual((self.root / 'unowned.txt').read_text(), 'keep me')
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ['unowned.txt'])

    def test_init_rollback_keeps_replacement_inode(self):
        original = workspace.write_new
        def replacing(path, content):
            if path.name == 'BASELINE.md':
                raise OSError('injected')
            identity = original(path, content)
            if path.name == 'HUMAN.md':
                replacement = self.root / 'replacement.tmp'
                replacement.write_text('unowned replacement')
                replacement.replace(path)
            return identity
        with mock.patch.object(workspace, 'write_new', side_effect=replacing), self.assertRaises(OSError):
            self.initialize()
        self.assertEqual((self.root / 'HUMAN.md').read_text(), 'unowned replacement')

    def test_init_missing_template_creates_nothing(self):
        with mock.patch.object(workspace, 'PACKAGE', self.base / 'missing'), self.assertRaises(OSError):
            self.initialize()
        self.assertFalse(self.root.exists())

    def test_write_new_fsync_failure_removes_only_own_file(self):
        target = self.base / 'new-file'
        with mock.patch.object(workspace.os, 'fsync', side_effect=OSError('full disk')):
            with self.assertRaises(OSError):
                workspace.write_new(target, 'private')
        self.assertFalse(target.exists())
        target.write_text('preserve')
        with self.assertRaises(FileExistsError):
            workspace.write_new(target, 'replacement')
        self.assertEqual(target.read_text(), 'preserve')

    def test_existing_directory_untouched_and_symlink_ancestors_rejected(self):
        self.root.mkdir()
        keep = self.root / 'keep'
        keep.write_text('mine')
        with self.assertRaises(ValueError):
            self.initialize()
        self.assertEqual(keep.read_text(), 'mine')
        link = self.base / 'link'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            workspace.init(link / 'child')
        dangling = self.base / 'dangling'
        dangling.symlink_to(self.base / 'missing')
        with self.assertRaises(ValueError):
            workspace.init(dangling)

    def test_git_worktree_markers_rejected_then_placeholder_allowed(self):
        marker = self.base / '.git'
        for kind in ('file', 'symlink'):
            with self.subTest(kind=kind):
                if kind == 'file':
                    marker.write_text('gitdir: elsewhere')
                else:
                    marker.symlink_to(self.base / 'absent-git')
                with self.assertRaises(ValueError):
                    self.initialize()
                marker.unlink()
        self.assertFalse(self.root.exists())
        # 空 `.git` 目录只是占位标记，不是工作树。旧实现按祖先标记一律拒绝，
        # 会把 home（dotfiles 仓）和宿主共享目录整片封锁。
        marker.mkdir()
        self.assertTrue(self.initialize()['created'])

    @unittest.skipUnless(shutil.which('git'), 'git required to build a real work tree')
    def test_real_git_work_tree_rejected_including_nested(self):
        subprocess.run(['git', 'init', '-q', str(self.base)], check=True, timeout=20)
        with self.assertRaises(ValueError):
            self.initialize()
        nested = self.base / 'notes'
        nested.mkdir()
        with self.assertRaises(ValueError):
            workspace.init(nested)
        self.assertFalse(self.root.exists())

    @unittest.skipUnless(os.name == 'posix', 'POSIX permissions')
    def test_all_new_directories_files_events_and_export_private(self):
        self.root = self.base / 'new-parent' / 'private'
        self.initialize()
        saved = self.record_at(event())
        output = workspace.export_redacted(self.root, self.base / 'redacted.json')
        for path in (self.root.parent, self.root, self.root / 'events'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        for path in [*(self.root / name for name in (*workspace.FILES, workspace.MARKER)), saved, output]:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_sync_warning_is_heuristic_and_does_not_claim_detection(self):
        self.root = self.base / 'Dropbox' / 'private'
        result = self.initialize()
        self.assertTrue(any('疑似' in warning for warning in result['warnings']))
        self.assertTrue(any('不能检测所有' in warning for warning in result['warnings']))

    def test_unsafe_event_files_and_mismatched_id_fail_closed(self):
        self.initialize()
        external = self.base / 'external.json'
        external.write_text('{}')
        link = self.root / 'events' / 'bad.json'
        link.symlink_to(external)
        with self.assertRaises(ValueError):
            workspace.read_events(self.root)
        link.unlink()
        path = self.raw(event())
        path.rename(self.root / 'events' / 'different.json')
        with self.assertRaises(ValueError):
            workspace.read_events(self.root)

    def test_record_lock_prevents_racing_updates_and_is_never_removed_if_unowned(self):
        self.initialize()
        lock = self.root / '.record.lock'
        lock.mkdir()
        with self.assertRaises(ValueError):
            self.record_at(event())
        self.assertTrue(lock.is_dir())
        lock.rmdir()
        self.record_at(event())
        self.assertFalse(lock.exists())

    def test_doctor_reports_event_count_and_stale_lock(self):
        self.initialize()
        self.assertEqual(workspace.doctor(self.root)['event_count'], 0)
        self.record_at(event())
        fresh = workspace.doctor(self.root)
        self.assertEqual(fresh['event_count'], 1)
        self.assertTrue(fresh['ok'])
        self.assertFalse(any('.record.lock' in note for note in fresh['warnings']))
        (self.root / '.record.lock').mkdir()
        stale = workspace.doctor(self.root)
        # 结构完好但写不进去：doctor 必须说出来，否则每轮第一个命令会误导人。
        self.assertTrue(stale['ok'])
        self.assertTrue(any('.record.lock' in note for note in stale['warnings']))

    def test_cli_version_matches_skill_frontmatter(self):
        front = (ROOT / 'skill/human-rlaif/SKILL.md').read_text(encoding='utf-8')
        declared = next(line.split(':', 1)[1].strip().strip('"') for line in front.splitlines()
                        if line.strip().startswith('version:'))
        run = subprocess.run([sys.executable, str(SCRIPT), '--version'],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), f'human-rlaif {declared}')

    def test_export_whitelist_removes_free_text_paths_ids_and_timestamps(self):
        self.initialize()
        secret = 'sensitive-person-42'
        sample = forecast(secret)
        for field in workspace.TEXT_FIELDS:
            sample[field] = secret + ' /home/private/secret'
        sample.update(prediction=secret, resolution_criteria=secret, task_type=secret,
                      rubric_ref='/private/' + secret, sources=[secret], assistance='critique',
                      isolation='partial', due_at='2026-10-08T00:00:00Z', retest_interval=7)
        self.record_at(sample)
        resolved = resolution('resolution-private', secret)
        resolved['sources'] = ['/secret/path']
        self.record_at(resolved, '2026-10-09T00:00:00Z')
        output = workspace.export_redacted(self.root, self.base / 'redacted.json')
        content = output.read_text()
        for private in (secret, '/home/', '/secret/', '2026-', 'resolution-private', 'rubric_ref',
                        'human_input', 'resolution_criteria', 'recorded_at', 'sources', 'metadata'):
            self.assertNotIn(private, content)
        result = json.loads(content)
        self.assertEqual(result['format'], 'human-rlaif-redacted-v1')
        rows = result['events']
        forecast_row = next(row for row in rows if 'confidence' in row)
        resolution_row = next(row for row in rows if 'outcome' in row)
        self.assertEqual(resolution_row['resolves_prediction'], forecast_row['id'])
        allowed = {'id', 'schema_version', 'mode', 'evidence_status', 'assistance', 'isolation',
                   'retest_interval', 'prediction_type', 'confidence', 'outcome', 'resolves_prediction', 'retest_of'}
        self.assertTrue(all(set(row) <= allowed for row in rows))

    def test_export_refuses_overwrite_symlink_url_relative_and_events_target(self):
        self.initialize()
        output = self.base / 'export.json'
        output.write_text('keep')
        with self.assertRaises(FileExistsError):
            workspace.export_redacted(self.root, output)
        link = self.base / 'export-link.json'
        link.symlink_to(output)
        for invalid in (link, 'relative.json', 'https://example.com/upload',
                        self.root / 'events' / 'new.json', self.base / 'missing' / 'out.json'):
            with self.subTest(invalid=str(invalid)), self.assertRaises(ValueError):
                workspace.export_redacted(self.root, invalid)
        self.assertEqual(output.read_text(), 'keep')

    def test_duplicate_json_keys_and_oversized_input_rejected(self):
        source = self.base / 'input.json'
        source.write_text('{"id":"one","id":"two"}')
        with self.assertRaises(ValueError):
            workspace._read_json(source)
        source.write_bytes(b' ' * (workspace.MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            workspace._read_json(source)

    def test_invalid_marker_versions_do_not_pass_bool_as_one(self):
        self.initialize()
        marker = self.root / workspace.MARKER
        for bad in (True, False, 3, '2', None):
            with self.subTest(bad=bad):
                marker.write_text(json.dumps({'skill': 'human-rlaif', 'schema_version': bad}))
                self.assertFalse(workspace.doctor(self.root)['ok'])

    def test_cli_new_commands_errors_and_json_outputs(self):
        self.initialize()
        for command, extra in [('due', ['--as-of', '2026-10-09T00:00:00Z']),
                                ('calibration', []),
                                ('export', ['--output', str(self.base / 'cli-export.json')])]:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(workspace.main([command, '--workspace', str(self.root), *extra]), 0)
            self.assertIsInstance(json.loads(output.getvalue()), dict)
        for args in (['export'], ['record'], ['due', '--as-of', '2026-10-01T00:00:00']):
            with redirect_stderr(io.StringIO()):
                self.assertEqual(workspace.main([*args, '--workspace', str(self.root)]), 1)


if __name__ == '__main__':
    unittest.main()
