#!/usr/bin/env python3
"""Repository checks supplement, rather than replace, official skills-ref validation.

Developer dependency: strictyaml, installed with the pinned official skills-ref in CI.
The installed skill and its workspace helper do not require this dependency.
Specification: https://agentskills.io/specification
Official source: https://github.com/agentskills/agentskills/tree/
f130f348f502d9804278a617f86929846896d2e9/skills-ref
"""
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

try:
    import strictyaml
except ImportError:
    strictyaml = None

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skill' / 'human-rlaif'
ALLOWED_FIELDS = {'name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'}
REPO_REQUIRED = (
    'README.md', 'README.en.md', 'LICENSE', 'CONTRIBUTING.md', 'CHANGELOG.md',
    'PROVENANCE.md', 'PUBLISHING.md', 'RELATED_PROJECTS.md', 'CITATION.cff',
    'paper/README.md', 'paper/citation.bib', 'evals/HUMAN-RLAIF.md',
    'evals/human-rlaif-cases.json', 'requirements-dev.txt',
)
SKILL_REQUIRED = (
    'SKILL.md', 'LICENSE', 'scripts/workspace.py', 'references/protocol.md',
    'references/install.md', 'references/research.md', 'references/examples.md',
    'assets/event.example.json',
) + tuple('assets/templates/' + name for name in ('HUMAN.md', 'BASELINE.md', 'STATE.md', 'JOURNAL.md'))
IGNORED_DIRS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache', 'dist', 'build'}
# Markdown inline destinations, including one balanced pair of parentheses and
# optional titles; reference-style definitions are checked separately below.
DESTINATION = r'(?:<([^>\n]+)>|((?:\\.|[^\s()<>]|\([^()\n]*\))+))'
INLINE_LINK = re.compile(r'!?\[[^\]\n]*\]\(\s*' + DESTINATION + r'(?:\s+[\"\'][^\n]*?[\"\'])?\s*\)')
REFERENCE_LINK = re.compile(r'^ {0,3}\[[^\]\n]+\]:\s*' + DESTINATION, re.M)


def parse_frontmatter(text):
    """Use real, safe YAML parsing; never silently skip malformed frontmatter."""
    if strictyaml is None:
        raise ValueError('缺少开发校验依赖 strictyaml；请按 README 安装固定提交的官方 skills-ref')
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip('\r\n') != '---':
        raise ValueError('SKILL.md 必须以独立一行的 YAML 分隔符 --- 开始')
    closing = next((i for i in range(1, len(lines)) if lines[i].rstrip('\r\n') == '---'), None)
    if closing is None:
        raise ValueError('SKILL.md 前置元数据缺少结束分隔符 ---')
    try:
        front = strictyaml.load(''.join(lines[1:closing])).data
    except strictyaml.YAMLError as exc:
        raise ValueError('前置元数据 YAML 无效：' + str(exc)) from exc
    if not isinstance(front, dict):
        raise ValueError('前置元数据必须是 YAML 映射')
    return front, ''.join(lines[closing + 1:])


def validate_frontmatter(front, skill_dir):
    """Check the published field constraints, including optional field types.

    StrictYAML preserves scalar strings without YAML's implicit bool/number
    coercion, like the official reference parser. Nested values are not coerced
    to strings: metadata must genuinely be a string-to-string mapping.
    """
    if not isinstance(front, dict):
        return ['前置元数据必须是 YAML 映射']
    errors = []
    for field in front:
        if field not in ALLOWED_FIELDS:
            errors.append(f'不支持的前置字段：{field}')
    name = front.get('name')
    if not isinstance(name, str) or not 1 <= len(name) <= 64:
        errors.append('name 必须为 1–64 字符的字符串')
    else:
        if (name != name.lower() or not all(c.isalnum() or c == '-' for c in name)
                or name.startswith('-') or name.endswith('-') or '--' in name):
            errors.append('name 只能包含小写字母、数字和单个连字符，且不能以连字符开始或结束')
        if name != Path(skill_dir).name:
            errors.append('name 必须与技能目录名一致')
    description = front.get('description')
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        errors.append('description 必须为非空的 1–1024 字符字符串')
    if 'compatibility' in front:
        value = front['compatibility']
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            errors.append('compatibility 必须为非空的 1–500 字符字符串')
    for field in ('license', 'allowed-tools'):
        if field in front and not isinstance(front[field], str):
            errors.append(field + ' 必须是字符串')
    if 'metadata' in front:
        value = front['metadata']
        if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                              for k, v in value.items()):
            errors.append('metadata 必须为字符串到字符串的映射')
    return errors


def markdown_destinations(text):
    """Extract links from prose, excluding fenced/inline code examples.

    This is a local-file check, not a full Markdown renderer, anchor checker,
    or remote-link availability checker.
    """
    prose = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            value = marker.group(1)
            if fence is None:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = None
            prose.append('')
            continue
        prose.append(line if fence is None else '')
    text = re.sub(r'(`+).*?\1', '', '\n'.join(prose))
    for pattern in (INLINE_LINK, REFERENCE_LINK):
        for match in pattern.finditer(text):
            yield match.group(1) or match.group(2)


def check_local_link(path, destination, boundary):
    """A skill link must survive copying only its skill directory elsewhere."""
    destination = html.unescape(re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]\\^_`{|}~])', r'\1', destination))
    try:
        parsed = urlsplit(destination)
    except ValueError:
        return '无效链接：' + destination
    if parsed.scheme.lower() in {'https', 'http', 'mailto', 'tel'} or (not parsed.scheme and parsed.netloc):
        return None
    if parsed.scheme:
        return '不支持的链接协议：' + destination
    target = unquote(parsed.path)
    if not target:
        return None
    if '\\' in target or Path(target).is_absolute():
        return '本地链接必须是可移植的相对路径：' + destination
    try:
        resolved = (path.parent / target).resolve()
        if not resolved.is_relative_to(boundary.resolve()):
            return '链接超出允许目录：' + destination
        if not resolved.exists():
            return '失效本地链接：' + destination
    except (OSError, RuntimeError, ValueError) as exc:
        return f'无法解析本地链接：{destination}: {exc}'
    return None


def validate_links(root, skill):
    errors = []
    for path in sorted(root.rglob('*.md')):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        boundary = skill if path.is_relative_to(skill) else root
        label = str(path.relative_to(root))
        try:
            if not path.resolve().is_relative_to(boundary.resolve()):
                errors.append(label + ': Markdown 文件链接超出允许目录')
                continue
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError, RuntimeError) as exc:
            errors.append(f'{label}: 无法读取：{exc}')
            continue
        for destination in markdown_destinations(text):
            problem = check_local_link(path, destination, boundary)
            if problem:
                errors.append(label + ': ' + problem)
    return errors


def validate_cases(path):
    errors = []
    count = 0
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('顶层必须是对象')
        cases = data.get('cases')
        if not isinstance(cases, list):
            raise ValueError('cases 必须是数组')
        if data.get('skill') != 'human-rlaif' or data.get('skill_version') != '0.1.0':
            errors.append('行为用例版本不匹配')
        ids = set()
        count = len(cases)
        for index, case in enumerate(cases, 1):
            if not isinstance(case, dict):
                errors.append(f'用例 {index} 必须是对象')
                continue
            for key in ('id', 'prompt', 'mode', 'expected', 'forbidden'):
                if not isinstance(case.get(key), str) or not case[key].strip():
                    errors.append(f'用例 {index} 字段无效：{key}')
            identifier = case.get('id')
            if isinstance(identifier, str):
                if identifier in ids:
                    errors.append('重复用例 id：' + identifier)
                ids.add(identifier)
        if count < 12:
            errors.append('行为用例少于 12 项')
    except (ValueError, TypeError, OSError, UnicodeError) as exc:
        errors.append('行为用例无法读取：' + str(exc))
    return errors, count


def validate_repository(root=ROOT):
    root = Path(root).resolve()
    skill = root / 'skill' / 'human-rlaif'
    errors = []
    # Reject a redirected package before walking or opening anything below it.
    if skill.is_symlink() or (root / 'skill').is_symlink():
        return ['技能目录不能是符号链接'], 0
    for directory, names in ((root, REPO_REQUIRED), (skill, SKILL_REQUIRED)):
        for name in names:
            path = directory / name
            if not path.is_file():
                errors.append('缺失 ' + str(path.relative_to(root)))
            elif not path.resolve().is_relative_to(directory.resolve()):
                errors.append('必需文件超出允许目录：' + str(path.relative_to(root)))
    # Package portability: do not rely on symbolic links to unbundled files.
    if skill.exists():
        for path in skill.rglob('*'):
            if path.is_symlink():
                errors.append('技能包不能包含符号链接：' + str(path.relative_to(root)))
    entry = skill / 'SKILL.md'
    if entry.is_file() and entry.resolve().is_relative_to(skill.resolve()):
        try:
            text = entry.read_text(encoding='utf-8')
            front, _ = parse_frontmatter(text)
            errors.extend(validate_frontmatter(front, skill))
            if front.get('name') != 'human-rlaif':
                errors.append('本项目的 name 必须精确为 human-rlaif')
            # Repository convention, following the spec's progressive-disclosure recommendation.
            if len(text.splitlines()) > 500:
                errors.append('SKILL.md 超过本项目的 500 行上限')
        except (ValueError, OSError, UnicodeError) as exc:
            errors.append(str(exc))
    errors.extend(validate_links(root, skill))
    cases_path = root / 'evals/human-rlaif-cases.json'
    if cases_path.resolve().is_relative_to(root):
        case_errors, count = validate_cases(cases_path)
        errors.extend(case_errors)
    else:
        errors.append('行为用例文件超出仓库目录')
        count = 0
    return errors, count


def main():
    errors, count = validate_repository()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'仓库与技能包补充检查通过；{count} 个行为用例已定义，未在此运行模型评测。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
