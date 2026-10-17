#!/usr/bin/env python3
"""human-rlaif 的可选本地文件助手；不执行学习评估或联网。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
FILES = ('HUMAN.md', 'BASELINE.md', 'STATE.md', 'JOURNAL.md')
MARKER = '.human-rlaif.json'
SCHEMA = {'skill': 'human-rlaif', 'schema_version': 1}
MODES = {'production', 'learning', 'assessment'}
STATUSES = {'pending', 'reported', 'externally_checked'}
TEXT_FIELDS = ('human_input', 'ai_feedback', 'human_response', 'action', 'reality_feedback')
FIELDS = {'id', 'mode', 'evidence_status', 'sources', *TEXT_FIELDS}
ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,79}$')


def safe_root(value: str | Path) -> Path:
    """拒绝相对路径、已存在的符号链接和 Git 工作树。"""
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError('私人工作区必须使用绝对路径。')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('工作区路径包含符号链接，请指定真实私人目录。')
        if (part / '.git').exists():
            raise ValueError('私人工作区必须位于所有 Git 工作树之外。')
    return path.resolve()


def write_new(path: Path, text: str) -> None:
    """独占创建，绝不覆盖；支持的平台使用仅所有者可读写权限。"""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def doctor(value: str | Path) -> dict[str, Any]:
    root = safe_root(value)
    problems = []
    for name in (*FILES, MARKER):
        path = root / name
        if path.is_symlink() or not path.is_file():
            problems.append(f'缺失或不安全的文件：{name}')
    events = root / 'events'
    if events.is_symlink() or not events.is_dir():
        problems.append('缺失或不安全的目录：events')
    if not problems:
        try:
            marker = json.loads((root / MARKER).read_text(encoding='utf-8'))
            if marker != SCHEMA:
                problems.append('工作区格式版本或技能标识不匹配，需要显式迁移。')
        except (ValueError, OSError):
            problems.append('工作区格式标记无法读取。')
    return {'ok': not problems, 'workspace': str(root), 'problems': problems,
            'scope': '仅检查本地结构；未验证宿主自动加载、本人同意或学习效果。'}


def init(value: str | Path) -> dict[str, Any]:
    root = safe_root(value)
    if root.exists():
        report = doctor(root)
        if not report['ok']:
            raise ValueError('已有目录不完整或未识别，拒绝覆盖：' + '; '.join(report['problems']))
        return {'created': False, 'workspace': str(root), 'protocol_status': 'unchanged'}
    templates = {name: (PACKAGE / 'assets' / 'templates' / name).read_text(encoding='utf-8')
                 for name in FILES}
    root.mkdir(parents=True, mode=0o700)
    (root / 'events').mkdir(mode=0o700)
    for name, text in templates.items():
        write_new(root / name, text)
    write_new(root / MARKER, json.dumps(SCHEMA, ensure_ascii=False) + '\n')
    return {'created': True, 'workspace': str(root), 'protocol_status': 'draft'}


def validate_event(event: Any) -> None:
    if not isinstance(event, dict) or set(event) != FIELDS:
        raise ValueError('事件字段必须为：' + ', '.join(sorted(FIELDS)))
    if not isinstance(event['id'], str) or not ID_RE.fullmatch(event['id']):
        raise ValueError('事件 id 需为 1 至 80 位小写字母、数字或连字符。')
    if event['mode'] not in MODES or event['evidence_status'] not in STATUSES:
        raise ValueError('mode 或 evidence_status 无效。')
    for key in TEXT_FIELDS:
        if not isinstance(event[key], str) or not event[key].strip():
            raise ValueError(f'{key} 需为非空文本；未知请填写 unknown 或 pending。')
    sources = event['sources']
    if not isinstance(sources, list) or any(not isinstance(x, str) or not x.strip() for x in sources):
        raise ValueError('sources 必须是来源指针字符串列表。')
    if event['evidence_status'] == 'externally_checked':
        if not sources or event['reality_feedback'].strip().lower() in {'unknown', 'pending'}:
            raise ValueError('externally_checked 需要来源和实际反馈；仍需本人核查真实性。')


def record(value: str | Path, event: Any) -> Path:
    validate_event(event)
    report = doctor(value)
    if not report['ok']:
        raise ValueError('请先恢复工作区结构：' + '; '.join(report['problems']))
    root = safe_root(value)
    payload = dict(event, recorded_at=datetime.now(timezone.utc).isoformat(), schema_version=1)
    target = root / 'events' / (event['id'] + '.json')
    write_new(target, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'doctor', 'record'))
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--event', help='record 使用的 UTF-8 JSON 文件，最多 1 MiB')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = init(args.workspace)
        elif args.command == 'doctor':
            result = doctor(args.workspace)
        else:
            if not args.event:
                raise ValueError('record 需要 --event。')
            with open(args.event, 'rb') as stream:
                data = stream.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                raise ValueError('事件文件超过 1 MiB。')
            result = {'saved': str(record(args.workspace, json.loads(data.decode('utf-8'))))}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('ok') is False else 0
    except (ValueError, TypeError, OSError) as exc:
        print(f'human-rlaif: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
