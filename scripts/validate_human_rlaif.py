#!/usr/bin/env python3
"""human-rlaif 的零依赖结构校验；不模拟模型行为。"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT


def main():
    errors = []
    required = ['SKILL.md', 'README.md', 'LICENSE', 'scripts/workspace.py',
                'references/protocol.md', 'references/install.md', 'references/research.md',
                'references/examples.md', 'assets/event.example.json']
    required += ['assets/templates/' + name for name in ('HUMAN.md', 'BASELINE.md', 'STATE.md', 'JOURNAL.md')]
    for name in required:
        if not (SKILL / name).is_file():
            errors.append('缺失 ' + name)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    text = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    parts = text.split('---', 2)
    if len(parts) != 3 or parts[0].strip():
        errors.append('SKILL 缺少前置元数据')
        front = ''
    else:
        front = parts[1]
    if not re.search(r'^name: human-rlaif$', front, re.M):
        errors.append('name 必须精确为 human-rlaif')
    desc = re.search(r'^description: (.+)$', front, re.M)
    if not desc or len(desc.group(1)) > 1024:
        errors.append('description 缺失或过长')
    if len(text.splitlines()) > 500:
        errors.append('SKILL 超过 500 行')
    for path in SKILL.rglob('*.md'):
        for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            target = link.split('#', 1)[0]
            if not target or '://' in target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(SKILL.resolve()) or not resolved.exists():
                errors.append(f'技能包外或失效链接：{path.name}: {link}')
    try:
        data = json.loads((ROOT / 'evals/human-rlaif-cases.json').read_text(encoding='utf-8'))
        cases = data['cases']
        if data['skill'] != 'human-rlaif' or data['skill_version'] != '0.1.0':
            errors.append('行为用例版本不匹配')
        ids = set()
        for case in cases:
            for key in ('id', 'prompt', 'mode', 'expected', 'forbidden'):
                if not isinstance(case.get(key), str) or not case[key].strip():
                    errors.append('用例字段无效：' + key)
            if case['id'] in ids:
                errors.append('重复用例 id')
            ids.add(case['id'])
        if len(cases) < 12:
            errors.append('行为用例少于 12 项')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        errors.append('行为用例无法读取：' + str(exc))
        cases = []
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'结构检查通过；{len(cases)} 个行为用例已定义，未在此运行模型评测。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
