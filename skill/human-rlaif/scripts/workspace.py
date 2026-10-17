#!/usr/bin/env python3
"""human-rlaif 的可选本地文件助手；只处理本地记录，不联网或认证学习效果。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any
import warnings

PACKAGE = Path(__file__).resolve().parents[1]
FILES = ('HUMAN.md', 'BASELINE.md', 'STATE.md', 'JOURNAL.md')
MARKER = '.human-rlaif.json'
SCHEMA = {'skill': 'human-rlaif', 'schema_version': 2}
MODES = {'production', 'learning', 'assessment'}
STATUSES = {'pending', 'reported', 'externally_checked'}
ASSISTANCE = {'none', 'hint', 'critique', 'rewrite', 'solution', 'other', 'unknown'}
ISOLATION = {'clean', 'partial', 'contaminated', 'unknown'}
TEXT_FIELDS = ('human_input', 'ai_feedback', 'human_response', 'action', 'reality_feedback')
FIELDS = {'id', 'mode', 'evidence_status', 'sources', *TEXT_FIELDS}
FORECAST_FIELDS = {'prediction_type', 'prediction', 'confidence', 'resolution_criteria'}
OPTIONAL_FIELDS = {
    'task_type', 'assistance', 'isolation', 'rubric_ref', 'retest_interval', 'due_at',
    'human_draft_at', 'ai_feedback_at', 'retest_of', 'resolves_prediction', 'outcome',
    *FORECAST_FIELDS,
}
STORED_FIELDS = {'recorded_at', 'schema_version'}
ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,79}$')
TIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$')
DRAFT_RE = re.compile(r'(?:协议状态|protocol[ _]status|status)\s*[:：]\s*draft\b', re.I)
MAX_BYTES = 1024 * 1024
SYNC_NAMES = ('icloud', 'dropbox', 'onedrive', 'mobile documents', 'google drive',
              'googledrive', 'box sync', 'syncthing', 'nextcloud')


def _has_work_tree_marker(path: Path) -> bool:
    """git 不可用或拒绝作答时的降级判断：只认真工作树的标记。

    普通 `.git` 目录必须有 HEAD，gitlink 文件必须以 `gitdir:` 开头，符号链接
    一律按标记处理。占位用的空 `.git` 目录不算工作树，否则任何带 dotfiles 仓
    的 home、或宿主投放只读 `.git` 占位符的目录都会被整体封锁。
    """
    for part in (path, *path.parents):
        marker = part / '.git'
        if marker.is_symlink():
            return True
        if marker.is_dir() and (marker / 'HEAD').exists():
            return True
        if marker.is_file():
            try:
                head = marker.read_text(encoding='utf-8', errors='replace')[:8]
            except OSError:
                continue
            if head.lower().startswith('gitdir:'):
                return True
    return False


def _inside_work_tree(path: Path) -> bool:
    """由 git 自身判定 path 是否落在工作树内。

    `git rev-parse` 是权威判断：它认 gitlink、子模块和上溯目录，也不会把占位
    `.git` 目录当仓库。命令不可用或报错（例如 dubious ownership）时退回标记
    检查，保守而不误封。
    """
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    env = {k: v for k, v in os.environ.items()
           if k not in {'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'}}
    try:
        done = subprocess.run(
            ['git', '-C', str(probe), 'rev-parse', '--is-inside-work-tree'],
            capture_output=True, text=True, timeout=5, env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return _has_work_tree_marker(path)
    if done.returncode != 0:
        return _has_work_tree_marker(path)
    return done.stdout.strip() == 'true'


def safe_root(value: str | Path) -> Path:
    """拒绝相对路径、符号链接（包括悬空链接）和 Git 工作树。"""
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError('私人工作区和导出文件必须使用绝对本地路径。')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('路径包含符号链接，请指定真实私人目录。')
    if _inside_work_tree(path):
        raise ValueError('私人工作区和导出文件必须位于所有 Git 工作树之外。')
    return path.resolve()


def sync_warnings(path: Path) -> list[str]:
    result = ['请勿把私人工作区或未审核的导出放在 iCloud、Dropbox 等同步目录；本工具不能检测所有同步软件。']
    if any(name in part.casefold() for part in path.parts for name in SYNC_NAMES):
        result.append('检测到疑似云同步目录名称；本地写入可能被同步软件自动上传。')
    return result


def parse_time(value: Any, field: str) -> datetime:
    """有秒和明确时区的 RFC3339 时间；统一为 UTC 比较。"""
    if not isinstance(value, str) or not TIME_RE.fullmatch(value):
        raise ValueError(f'{field} 需为含秒和时区的 RFC3339 时间，例如 2026-10-17T12:00:00Z。')
    try:
        # datetime accepts +24:00 inconsistently across Python versions; reject explicitly.
        if value[-1] != 'Z' and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
            raise ValueError('invalid offset')
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f'{field} 不是有效时间。') from exc


def _identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    return info.st_dev, info.st_ino


def _remove_owned(path: Path, identity: tuple[int, int], *, directory: bool = False) -> None:
    """仅删除本次创建且身份未变的路径；永不递归删除或穿过父级链接。"""
    try:
        if any(parent.is_symlink() for parent in path.parents):
            return
        if _identity(path) != identity or path.is_symlink():
            return
        path.rmdir() if directory else path.unlink()
    except OSError:
        # New/unowned files in a directory must survive rollback.
        pass


def write_new(path: Path, text: str) -> tuple[int, int]:
    """独占创建；不覆盖；POSIX 上使用 0600，失败只清理所创建文件。"""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    info = os.fstat(fd)
    identity = (info.st_dev, info.st_ino)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        _remove_owned(path, identity)
        raise
    return identity


def _read_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'不是安全的普通文件：{path.name}')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('只接受普通 JSON 文件。')
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('JSON 文件超过 1 MiB。')
    # Duplicate keys are ambiguous, including security/evidence fields.
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f'JSON 字段重复：{key}')
            result[key] = item
        return result
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique_pairs)


def doctor(value: str | Path) -> dict[str, Any]:
    root = safe_root(value)
    problems: list[str] = []
    notices = sync_warnings(root)
    for name in (*FILES, MARKER):
        path = root / name
        if path.is_symlink() or not path.is_file():
            problems.append(f'缺失或不安全的文件：{name}')
    events = root / 'events'
    if events.is_symlink() or not events.is_dir():
        problems.append('缺失或不安全的目录：events')
    marker = None
    protocol_status = 'unverified'
    if not problems:
        try:
            marker = _read_json(root / MARKER)
            if (not isinstance(marker, dict) or set(marker) != {'skill', 'schema_version'}
                    or marker.get('skill') != 'human-rlaif'
                    or type(marker.get('schema_version')) is not int
                    or marker['schema_version'] not in (1, 2)):
                problems.append('工作区格式版本或技能标识不匹配，需要显式迁移。')
            if DRAFT_RE.search((root / 'HUMAN.md').read_text(encoding='utf-8')):
                protocol_status = 'draft'
                notices.append('HUMAN.md 仍为 draft，尚未确认；保存事件不代表本人同意协议。')
        except (ValueError, OSError):
            problems.append('工作区格式标记或 HUMAN.md 无法读取。')
    return {'ok': not problems, 'workspace': str(root), 'problems': problems,
            'warnings': notices, 'protocol_status': protocol_status,
            'schema_version': marker.get('schema_version') if isinstance(marker, dict) else None,
            'scope': '仅检查本地结构；未验证宿主自动加载、本人同意或学习效果。'}


def init(value: str | Path) -> dict[str, Any]:
    root = safe_root(value)
    if root.exists():
        report = doctor(root)
        if not report['ok']:
            raise ValueError('已有目录不完整或未识别，拒绝覆盖：' + '; '.join(report['problems']))
        return {'created': False, 'workspace': str(root), 'protocol_status': 'unchanged',
                'warnings': report['warnings']}
    # Read templates before creating anything, so missing assets leave no residue.
    templates = {name: (PACKAGE / 'assets' / 'templates' / name).read_text(encoding='utf-8')
                 for name in FILES}
    directories: list[tuple[Path, tuple[int, int]]] = []
    files: list[tuple[Path, tuple[int, int]]] = []
    try:
        missing = []
        candidate = root
        while not candidate.exists():
            missing.append(candidate)
            candidate = candidate.parent
        for path in reversed(missing):
            safe_root(path)
            path.mkdir(mode=0o700)  # exist_ok=False protects concurrent/unowned paths.
            directories.append((path, _identity(path)))
        events = root / 'events'
        events.mkdir(mode=0o700)
        directories.append((events, _identity(events)))
        for name, content in (*templates.items(), (MARKER, json.dumps(SCHEMA) + '\n')):
            target = root / name
            identity = write_new(target, content)
            files.append((target, identity))
    except BaseException:
        for path, identity in reversed(files):
            _remove_owned(path, identity)
        for path, identity in reversed(directories):
            _remove_owned(path, identity, directory=True)
        raise
    return {'created': True, 'workspace': str(root), 'protocol_status': 'draft',
            'warnings': doctor(root)['warnings']}


def _nonempty(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} 需为非空文本；未知的可选字段请省略。')


def _id(value: Any, field: str) -> None:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ValueError(f'{field} 需为 1 至 80 位小写字母、数字或连字符。')


def validate_event(event: Any, *, stored: bool = False) -> None:
    """输入拒绝存储元数据；已存事件需明确 v1/v2 版本及 recorded_at；均拒绝未知键。"""
    if not isinstance(event, dict) or any(not isinstance(key, str) for key in event):
        raise ValueError('事件必须是 JSON 对象。')
    required = FIELDS | (STORED_FIELDS if stored else set())
    allowed = FIELDS | OPTIONAL_FIELDS | (STORED_FIELDS if stored else set())
    if stored:
        version = event.get('schema_version')
        if type(version) is not int or version not in (1, 2):
            raise ValueError('已存事件的 schema_version 必须为 1 或 2。')
        if version == 1:
            allowed = FIELDS | STORED_FIELDS
    missing, unknown = required - event.keys(), event.keys() - allowed
    if missing or unknown:
        raise ValueError('事件缺失字段：' + ', '.join(sorted(missing))
                         + '；未知或禁止字段：' + ', '.join(sorted(unknown)))
    _id(event['id'], 'id')
    if (not isinstance(event['mode'], str) or event['mode'] not in MODES
            or not isinstance(event['evidence_status'], str) or event['evidence_status'] not in STATUSES):
        raise ValueError('mode 或 evidence_status 无效。')
    for key in TEXT_FIELDS:
        _nonempty(event[key], key)
    sources = event['sources']
    if not isinstance(sources, list) or any(not isinstance(x, str) or not x.strip() for x in sources):
        raise ValueError('sources 必须是来源指针字符串列表。')
    if event['evidence_status'] == 'externally_checked':
        if not sources or event['reality_feedback'].strip().lower() in {'unknown', 'pending'}:
            raise ValueError('externally_checked 需要来源和实际反馈；仍需本人核查真实性。')
    for field in ('task_type', 'rubric_ref'):
        if field in event:
            _nonempty(event[field], field)
    for field, options in (('assistance', ASSISTANCE), ('isolation', ISOLATION)):
        if field in event and (not isinstance(event[field], str) or event[field] not in options):
            raise ValueError(f'{field} 仅接受：' + ', '.join(sorted(options)))
    if 'retest_interval' in event:
        if type(event['retest_interval']) is not int or event['retest_interval'] <= 0:
            raise ValueError('retest_interval 必须为正整数天数。')
        if 'due_at' not in event:
            raise ValueError('retest_interval 需要显式 due_at；本工具不推测日期。')
    times = {field: parse_time(event[field], field) for field in
             ('due_at', 'human_draft_at', 'ai_feedback_at', 'recorded_at') if field in event}
    if ('human_draft_at' in event) != ('ai_feedback_at' in event):
        raise ValueError('human_draft_at 与 ai_feedback_at 必须成对提供；旧记录可同时省略。')
    is_v2 = event['schema_version'] == 2 if stored else bool(OPTIONAL_FIELDS & event.keys())
    needs_pair = ((is_v2 and event['mode'] in {'learning', 'assessment'})
                  or event.get('isolation') == 'clean' or 'retest_of' in event
                  or bool(FORECAST_FIELDS & event.keys()))
    if needs_pair and 'human_draft_at' not in times:
        raise ValueError('v2 learning/assessment、clean、复测与预测记录必须提供初稿和反馈时间。')
    if 'human_draft_at' in times and times['human_draft_at'] >= times['ai_feedback_at']:
        raise ValueError('human_draft_at 必须严格早于 ai_feedback_at。')
    if stored and any(times[field] > times['recorded_at'] for field in
                      ('human_draft_at', 'ai_feedback_at') if field in times):
        raise ValueError('初稿和反馈时间不得晚于 recorded_at。')
    if ('due_at' in times and 'ai_feedback_at' in times
            and times['due_at'] <= times['ai_feedback_at']):
        raise ValueError('due_at 必须晚于 ai_feedback_at。')
    forecast = FORECAST_FIELDS & event.keys()
    if forecast:
        if forecast != FORECAST_FIELDS:
            raise ValueError('二元预测需同时提供 prediction_type、prediction、confidence、resolution_criteria。')
        if event['prediction_type'] != 'binary':
            raise ValueError('prediction_type 仅支持 binary；一般技能自信不作为概率。')
        _nonempty(event['prediction'], 'prediction')
        _nonempty(event['resolution_criteria'], 'resolution_criteria')
        probability = event['confidence']
        if (type(probability) not in (int, float) or not 0 <= probability <= 100
                or not math.isfinite(probability)):
            raise ValueError('confidence 必须为 0 到 100 的有限数值百分比。')
        if 'human_draft_at' not in times:
            raise ValueError('预测需记录 human_draft_at 与 ai_feedback_at。')
    if ('resolves_prediction' in event) != ('outcome' in event):
        raise ValueError('resolves_prediction 与 outcome 必须成对提供。')
    for field in ('retest_of', 'resolves_prediction'):
        if field in event:
            _id(event[field], field)
            if event[field] == event['id']:
                raise ValueError(f'{field} 不能引用事件自身。')
    if 'outcome' in event:
        if type(event['outcome']) is not bool:
            raise ValueError('outcome 必须为 JSON true/false，未知结果请暂不提交解决事件。')
        if event['evidence_status'] != 'externally_checked':
            raise ValueError('预测结果需 externally_checked 与来源；未经核查的结果不进入校准。')


def validate_stored_event(event: Any) -> None:
    validate_event(event, stored=True)


def read_events(value: str | Path) -> list[dict[str, Any]]:
    report = doctor(value)
    if not report['ok']:
        raise ValueError('请先恢复工作区结构：' + '; '.join(report['problems']))
    events = []
    for path in sorted((safe_root(value) / 'events').iterdir()):
        if path.suffix != '.json':
            continue
        event = _read_json(path)
        validate_stored_event(event)
        if path.stem != event['id']:
            raise ValueError('事件文件名与 id 不匹配。')
        events.append(event)
    return events


def _check_links(event: dict[str, Any], previous: list[dict[str, Any]], now: datetime) -> None:
    index = {old['id']: old for old in previous}
    for field in ('retest_of', 'resolves_prediction'):
        if field not in event:
            continue
        target_id = event[field]
        target = index.get(target_id)
        if target is None:
            raise ValueError(f'{field} 引用了不存在的事件。')
        if any(old.get(field) == target_id for old in previous):
            raise ValueError(f'{field} 已有完成记录；不得重复或覆盖。')
        if parse_time(target['recorded_at'], 'recorded_at') >= now:
            raise ValueError('链接事件必须严格晚于被引用事件的 recorded_at。')
        if field == 'retest_of':
            if 'due_at' not in target:
                raise ValueError('retest_of 只能引用有 due_at 的复测安排。')
            if now < parse_time(target['due_at'], 'due_at'):
                raise ValueError('尚未到期，不能把提前练习标为延迟复测完成。')
            if ('human_draft_at' in event and parse_time(event['human_draft_at'], 'human_draft_at')
                    < parse_time(target['due_at'], 'due_at')):
                raise ValueError('复测初稿不能早于到期时间。')
        elif not FORECAST_FIELDS.issubset(target):
            raise ValueError('resolves_prediction 只能引用有效二元预测。')


@contextmanager
def _record_lock(root: Path):
    lock = root / '.record.lock'
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise ValueError('另一次 record 正在运行，或遗留 .record.lock；请核查后再重试。') from exc
    identity = _identity(lock)
    try:
        yield
    finally:
        _remove_owned(lock, identity, directory=True)


def record(value: str | Path, event: Any) -> Path:
    validate_event(event)
    report = doctor(value)
    if not report['ok']:
        raise ValueError('请先恢复工作区结构：' + '; '.join(report['problems']))
    if report['protocol_status'] == 'draft':
        warnings.warn('HUMAN.md 仍为 draft；保存事件不代表确认协议。', UserWarning, stacklevel=2)
    root = safe_root(value)
    with _record_lock(root):
        now = datetime.now(timezone.utc)
        previous = read_events(root)
        target = root / 'events' / (event['id'] + '.json')
        if target.exists() or target.is_symlink():
            raise FileExistsError(f'事件已存在，拒绝覆盖：{event["id"]}')
        _check_links(event, previous, now)
        version = 2 if OPTIONAL_FIELDS & event.keys() else 1
        payload = dict(event, recorded_at=now.isoformat(), schema_version=version)
        validate_stored_event(payload)
        write_new(target, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return target


def due(value: str | Path, as_of: str | None = None) -> dict[str, Any]:
    now = parse_time(as_of, 'as_of') if as_of is not None else datetime.now(timezone.utc)
    events = [event for event in read_events(value)
              if parse_time(event['recorded_at'], 'recorded_at') <= now]
    index = {event['id']: event for event in events}
    completions: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if 'retest_of' in event:
            completions.setdefault(event['retest_of'], []).append(event)
    completed = set()
    invalid = []
    for event_id, linked in sorted(completions.items()):
        target = index.get(event_id)
        reason = None
        if len(linked) != 1:
            reason = 'duplicate_completions'
        elif target is None or 'due_at' not in target:
            reason = 'missing_scheduled_event'
        else:
            finished = parse_time(linked[0]['recorded_at'], 'recorded_at')
            if finished <= parse_time(target['recorded_at'], 'recorded_at'):
                reason = 'completion_not_after_schedule'
            elif finished < parse_time(target['due_at'], 'due_at'):
                reason = 'completion_before_due'
            elif ('human_draft_at' in linked[0] and
                  parse_time(linked[0]['human_draft_at'], 'human_draft_at') < parse_time(target['due_at'], 'due_at')):
                reason = 'retest_draft_before_due'
        if reason:
            invalid.append({'id': event_id, 'reason': reason})
        else:
            completed.add(event_id)
    scheduled = [event for event in events if 'due_at' in event
                 and event['id'] not in completed
                 and parse_time(event['due_at'], 'due_at') <= now]
    scheduled.sort(key=lambda event: (parse_time(event['due_at'], 'due_at'), event['id']))
    return {'as_of': now.isoformat(), 'count': len(scheduled), 'due': [
        {key: event[key] for key in ('id', 'due_at', 'task_type', 'rubric_ref',
                                     'retest_interval', 'assistance', 'isolation') if key in event}
        for event in scheduled], 'invalid_completions': invalid,
        'scope': '只列出已记录且未显式完成的到期项；不会发送提醒或自动启动会话。'}


def calibration(value: str | Path) -> dict[str, Any]:
    events = read_events(value)
    forecasts = {event['id']: event for event in events if FORECAST_FIELDS.issubset(event)}
    resolutions: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if 'resolves_prediction' in event:
            resolutions.setdefault(event['resolves_prediction'], []).append(event)
    scored: list[tuple[float, int]] = []
    invalid = []
    unresolved = 0
    for event_id, forecast in forecasts.items():
        answers = resolutions.get(event_id, [])
        if not answers:
            unresolved += 1
            continue
        if len(answers) != 1:
            invalid.append({'id': event_id, 'reason': 'duplicate_resolutions'})
            continue
        answer = answers[0]
        if parse_time(answer['recorded_at'], 'recorded_at') <= parse_time(forecast['recorded_at'], 'recorded_at'):
            invalid.append({'id': event_id, 'reason': 'resolution_not_after_prediction'})
            continue
        scored.append((forecast['confidence'] / 100, int(answer['outcome'])))
    for event_id in sorted(resolutions.keys() - forecasts.keys()):
        invalid.append({'id': event_id, 'reason': 'missing_prediction'})
    bins = []
    for index in range(5):
        members = [(p, y) for p, y in scored if min(int(p * 5), 4) == index]
        bins.append({'lower': index / 5, 'upper': (index + 1) / 5,
                     'upper_inclusive': index == 4, 'count': len(members),
                     'mean_probability': sum(p for p, _ in members) / len(members) if members else None,
                     'observed_frequency': sum(y for _, y in members) / len(members) if members else None})
    count = len(scored)
    return {'forecast_count': len(forecasts), 'scored_count': count, 'unresolved_count': unresolved,
            'excluded_count': len(invalid), 'excluded': invalid,
            'non_prediction_event_count': sum('prediction' not in event and 'outcome' not in event for event in events),
            'brier_score': sum((p - y) ** 2 for p, y in scored) / count if count else None,
            'hit_rate': sum(int(p >= .5) == y for p, y in scored) / count if count else None,
            'hit_rate_rule': '预测 probability >= 0.5 为 true；命中率分母为 scored_count，命中率本身不是校准。',
            'bins': bins,
            'scope': '仅对带来源的已核查二元结果计算 Brier 与概率分档；不验证来源真实性、预注册或能力增长。'}


def export_redacted(value: str | Path, output: str | Path) -> Path:
    """本地白名单导出；不是匿名性保证，永不上传。"""
    events = read_events(value)
    target = safe_root(output)
    root = safe_root(value)
    if not target.parent.is_dir():
        raise ValueError('导出目录必须已经存在。')
    if target.parent == root / 'events' or target in {root / name for name in (*FILES, MARKER, '.record.lock')}:
        raise ValueError('导出不得写入工作区的事件或协议路径。')
    ids = {event['id']: f'event-{index:04d}' for index, event in enumerate(events, 1)}
    # task_type/rubric_ref and all timestamps are intentionally omitted: arbitrary text
    # and timing can identify people. There is no extensible metadata pass-through.
    safe_fields = ('schema_version', 'mode', 'evidence_status', 'assistance', 'isolation',
                   'retest_interval', 'prediction_type', 'confidence', 'outcome')
    sanitized = []
    for event in events:
        item = {'id': ids[event['id']]}
        item.update({key: event[key] for key in safe_fields if key in event})
        for field in ('retest_of', 'resolves_prediction'):
            if field in event and event[field] in ids:
                item[field] = ids[event[field]]
        sanitized.append(item)
    payload = {'format': 'human-rlaif-redacted-v1', 'events': sanitized,
               'notice': '仅供人工审核的本地脱敏副本；已移除自由文本、来源、路径、时间与原 ID，仍不保证匿名。'}
    write_new(target, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'doctor', 'record', 'due', 'calibration', 'export'))
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--event', help='record 的 UTF-8 JSON 输入文件，最多 1 MiB')
    parser.add_argument('--as-of', help='due 的确定性时间（含时区 RFC3339）；默认现在')
    parser.add_argument('--output', help='export 的全新绝对本地文件路径；绝不覆盖或上传')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = init(args.workspace)
        elif args.command == 'doctor':
            result = doctor(args.workspace)
        elif args.command == 'record':
            if not args.event:
                raise ValueError('record 需要 --event。')
            result = {'saved': str(record(args.workspace, _read_json(Path(args.event))))}
        elif args.command == 'due':
            result = due(args.workspace, args.as_of)
        elif args.command == 'calibration':
            result = calibration(args.workspace)
        else:
            if not args.output:
                raise ValueError('export 需要 --output。')
            result = {'saved': str(export_redacted(args.workspace, args.output)),
                      'warnings': sync_warnings(Path(args.output)),
                      'scope': '仅本地脱敏副本；分享前须人工审核，不会上传。'}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 1 if result.get('ok') is False else 0
    except (ValueError, TypeError, OSError) as exc:
        print(f'human-rlaif: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
