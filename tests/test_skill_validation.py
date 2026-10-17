"""Agent Skills format, portable-link boundaries, and CI source regression tests."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_human_rlaif', ROOT / 'scripts/validate_human_rlaif.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def metadata(**changes):
    value = {'name': 'human-rlaif', 'description': 'Use for a requested learning review.'}
    value.update(changes)
    return value


def skill_text(extra=''):
    return '---\nname: human-rlaif\ndescription: Use for a requested learning review.\n' + extra + '---\n# Skill\n'


class FrontmatterTests(unittest.TestCase):
    def check(self, value, name='human-rlaif'):
        return validator.validate_frontmatter(value, Path(name))

    def test_required_fields(self):
        self.assertEqual(self.check(metadata()), [])
        for field in ('name', 'description'):
            value = metadata()
            del value[field]
            self.assertTrue(self.check(value), field)

    def test_name_character_and_length_constraints(self):
        for name in ('', 'A', '-name', 'name-', 'a--b', 'two words', 'a_b', 'a/b', 'x' * 65, ' human-rlaif'):
            with self.subTest(name=name):
                self.assertTrue(self.check(metadata(name=name), name))
        for name in ('a', '1', 'a-b-2', 'x' * 64, '共学'):
            with self.subTest(name=name):
                self.assertEqual(self.check(metadata(name=name), name), [])

    def test_name_must_match_folder(self):
        self.assertTrue(self.check(metadata(), 'different-folder'))

    def test_name_nonstring(self):
        for name in (None, 12, [], {}):
            self.assertTrue(self.check(metadata(name=name)))

    def test_description_boundaries_and_type(self):
        self.assertEqual(self.check(metadata(description='x' * 1024)), [])
        for value in ('', '   ', 'x' * 1025, [], {}, None, False):
            self.assertTrue(self.check(metadata(description=value)))

    def test_optional_compatibility_boundaries_and_type(self):
        self.assertEqual(self.check(metadata(compatibility='x' * 500)), [])
        for value in ('', '  ', 'x' * 501, [], {}, None, 42):
            self.assertTrue(self.check(metadata(compatibility=value)))

    def test_optional_fields_and_no_extra_fields(self):
        self.assertEqual(self.check(metadata(license='MIT', metadata={'version': '0.1.0'},
                                             **{'allowed-tools': 'Read Bash(git:*)'})), [])
        self.assertTrue(self.check(metadata(unexpected='no')))
        for field in ('license', 'allowed-tools'):
            self.assertTrue(self.check(metadata(**{field: ['Read']})))

    def test_metadata_must_map_strings_to_strings(self):
        for value in ([], 'not a map', {'version': 1}, {1: 'version'}, {'nested': {'key': 'value'}}, {'items': ['one']}):
            self.assertTrue(self.check(metadata(metadata=value)))
        self.assertEqual(self.check(metadata(metadata={})), [])

    def test_missing_dependency_is_actionable(self):
        with mock.patch.object(validator, 'strictyaml', None):
            with self.assertRaisesRegex(ValueError, 'strictyaml.*README'):
                validator.parse_frontmatter(skill_text())


@unittest.skipIf(validator.strictyaml is None, 'Install requirements-dev.txt for YAML parser tests')
class YamlParsingTests(unittest.TestCase):
    def test_quoted_strings_comments_and_metadata(self):
        front, body = validator.parse_frontmatter(skill_text('license: "MIT" # comment\nmetadata:\n  version: "0.1.0"\n'))
        self.assertEqual(front['license'], 'MIT')
        self.assertEqual(front['metadata'], {'version': '0.1.0'})
        self.assertEqual(validator.validate_frontmatter(front, Path('human-rlaif')), [])
        self.assertEqual(body, '# Skill\n')

    def test_literal_and_folded_description(self):
        for style, expected in (('|-', 'First line\nSecond line'), ('>-', 'First line Second line')):
            text = '---\nname: human-rlaif\ndescription: ' + style + '\n  First line\n  Second line\n---\nBody'
            front, body = validator.parse_frontmatter(text)
            self.assertEqual(front['description'], expected)
            self.assertEqual(body, 'Body')

    def test_delimiter_inside_scalar_does_not_end_frontmatter(self):
        front, _ = validator.parse_frontmatter(skill_text('license: "text---text"\n'))
        self.assertEqual(front['license'], 'text---text')

    def test_crlf_delimiters(self):
        front, _ = validator.parse_frontmatter(skill_text().replace('\n', '\r\n'))
        self.assertEqual(front['name'], 'human-rlaif')

    def test_missing_or_non_line_delimiters(self):
        for text in ('name: human-rlaif', '\n' + skill_text(), '---name: human-rlaif\n---',
                     '---\nname: human-rlaif\ndescription: Missing end', '----\nname: human-rlaif\n---'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    validator.parse_frontmatter(text)

    def test_invalid_yaml_duplicate_key_and_nonmapping(self):
        for text in (skill_text('name: another\n'), '---\n- first\n- second\n---\n',
                     '---\nname: [broken\n---\n', skill_text('license: !!python/object:bad x\n')):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    validator.parse_frontmatter(text)

    def test_nested_metadata_remains_invalid_instead_of_coerced(self):
        front, _ = validator.parse_frontmatter(skill_text('metadata:\n  nested:\n    key: value\n'))
        self.assertTrue(validator.validate_frontmatter(front, Path('human-rlaif')))


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'repo'
        self.skill = self.root / 'skill' / 'human-rlaif'
        (self.skill / 'references').mkdir(parents=True)
        (self.root / 'README.md').write_text('# Repository\n', encoding='utf-8')
        (self.skill / 'SKILL.md').write_text(skill_text(), encoding='utf-8')
        (self.skill / 'references' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
        self.document = self.skill / 'SKILL.md'

    def tearDown(self):
        self.temp.cleanup()

    def check(self, target, path=None, boundary=None):
        return validator.check_local_link(path or self.document, target, boundary or self.skill)

    def test_valid_relative_link(self):
        self.assertIsNone(self.check('references/guide.md#details'))

    def test_root_doc_may_link_into_skill(self):
        self.assertIsNone(self.check('skill/human-rlaif/SKILL.md', self.root / 'README.md', self.root))

    def test_nested_skill_doc_may_link_to_skill_root(self):
        self.assertIsNone(self.check('../SKILL.md', self.skill / 'references' / 'guide.md'))

    def test_skill_cannot_link_to_repo_docs(self):
        self.assertIsNotNone(self.check('../../README.md'))
        self.assertIsNotNone(self.check('%2e%2e/%2e%2e/README.md'))

    def test_repo_cannot_escape_repo(self):
        outside = self.base / 'outside.md'
        outside.write_text('private', encoding='utf-8')
        self.assertIsNotNone(self.check('../outside.md', self.root / 'README.md', self.root))

    def test_absolute_file_and_windows_paths_fail(self):
        for target in (str(self.document), 'file://' + str(self.document), r'C:\secret.md', r'..\..\README.md'):
            self.assertIsNotNone(self.check(target))

    def test_missing_file_fails(self):
        self.assertIsNotNone(self.check('missing.md'))

    def test_anchors_and_supported_remote_links(self):
        for target in ('#details', 'https://example.org/a_(b)#c', 'http://example.org', '//example.org/a',
                       'mailto:maintainer@example.org', 'tel:+1234'):
            self.assertIsNone(self.check(target))

    def test_unsafe_protocol_is_not_silently_skipped(self):
        self.assertIsNotNone(self.check('javascript:alert(1)'))

    def test_encoded_space_and_parentheses(self):
        (self.skill / 'references' / 'with space (v1).md').write_text('ok', encoding='utf-8')
        self.assertIsNone(self.check('references/with%20space%20(v1).md'))

    def test_symlink_destination_outside_skill_fails(self):
        (self.skill / 'outside.md').symlink_to(self.root / 'README.md')
        self.assertIsNotNone(self.check('outside.md'))

    def test_symlink_markdown_source_outside_skill_is_not_read(self):
        (self.skill / 'outside.md').symlink_to(self.root / 'README.md')
        errors = validator.validate_links(self.root, self.skill)
        self.assertTrue(any('Markdown' in error for error in errors))

    def test_markdown_inline_reference_images_and_titles(self):
        text = '[Guide](references/guide.md "A guide") ![Image](image.png)\n[ref]: <some file.md> "title"\n[complex](a_(b).md)'
        self.assertEqual(list(validator.markdown_destinations(text)),
                         ['references/guide.md', 'image.png', 'a_(b).md', 'some file.md'])

    def test_markdown_code_examples_are_not_followed(self):
        text = '`[fake](inline.md)`\n```md\n[fake](fenced.md)\n```\n[real](references/guide.md)\n'
        self.assertEqual(list(validator.markdown_destinations(text)), ['references/guide.md'])

    def test_scans_both_readmes_and_repository_docs(self):
        (self.root / 'README.en.md').write_text('[missing](missing-en.md)', encoding='utf-8')
        (self.root / 'CONTRIBUTING.md').write_text('[missing](missing-contribution.md)', encoding='utf-8')
        errors = validator.validate_links(self.root, self.skill)
        self.assertTrue(any('README.en.md' in error for error in errors))
        self.assertTrue(any('CONTRIBUTING.md' in error for error in errors))


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve() / 'repo'
        self.skill = self.root / 'skill' / 'human-rlaif'
        for directory, names in ((self.root, validator.REPO_REQUIRED), (self.skill, validator.SKILL_REQUIRED)):
            for name in names:
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('# Fixture\n', encoding='utf-8')
        (self.skill / 'SKILL.md').write_text(skill_text(), encoding='utf-8')
        self.cases = self.root / 'evals/human-rlaif-cases.json'
        data = {'skill': 'human-rlaif', 'skill_version': '0.1.0', 'cases': [
            {'id': str(i), 'prompt': 'p', 'mode': 'learning', 'expected': 'e', 'forbidden': 'f'}
            for i in range(12)]}
        self.cases.write_text(json.dumps(data), encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    @unittest.skipIf(validator.strictyaml is None, 'Install requirements-dev.txt for YAML parser tests')
    def test_minimal_valid_repository(self):
        self.assertEqual(validator.validate_repository(self.root), ([], 12))

    def test_missing_dependency_fails_repository_check(self):
        with mock.patch.object(validator, 'strictyaml', None):
            errors, count = validator.validate_repository(self.root)
        self.assertTrue(any('strictyaml' in error for error in errors))
        self.assertEqual(count, 12)

    def test_both_readmes_are_required(self):
        (self.root / 'README.en.md').unlink()
        errors, _ = validator.validate_repository(self.root)
        self.assertTrue(any('缺失 README.en.md' in error for error in errors))

    def test_skill_directory_symlink_is_rejected_before_reading(self):
        target = self.root.parent / 'outside-skill'
        self.skill.rename(target)
        self.skill.symlink_to(target, target_is_directory=True)
        with mock.patch.object(validator, 'parse_frontmatter') as parse:
            errors, _ = validator.validate_repository(self.root)
        self.assertTrue(any('符号链接' in error for error in errors))
        parse.assert_not_called()

    def test_case_symlink_outside_repo_is_rejected_before_reading(self):
        target = self.root.parent / 'outside-cases.json'
        self.cases.rename(target)
        self.cases.symlink_to(target)
        with mock.patch.object(validator, 'validate_cases') as read_cases:
            errors, _ = validator.validate_repository(self.root)
        self.assertTrue(any('超出' in error for error in errors))
        read_cases.assert_not_called()

    def test_missing_skill_resource(self):
        (self.skill / 'references/protocol.md').unlink()
        errors, _ = validator.validate_repository(self.root)
        self.assertTrue(any('skill/human-rlaif/references/protocol.md' in error for error in errors))

    def test_metadata_cannot_be_moved_to_repo_root(self):
        (self.skill / 'SKILL.md').rename(self.root / 'SKILL.md')
        errors, _ = validator.validate_repository(self.root)
        self.assertTrue(any('缺失 skill/human-rlaif/SKILL.md' in error for error in errors))

    @unittest.skipIf(validator.strictyaml is None, 'Install requirements-dev.txt for YAML parser tests')
    def test_project_line_budget(self):
        (self.skill / 'SKILL.md').write_text(skill_text() + '\n' * 501, encoding='utf-8')
        errors, _ = validator.validate_repository(self.root)
        self.assertTrue(any('500 行' in error for error in errors))

    def test_malformed_cases_return_errors_instead_of_crashing(self):
        for value in ([], {'cases': {}}, {'cases': [1, {'id': []}]}):
            self.cases.write_text(json.dumps(value), encoding='utf-8')
            errors, _ = validator.validate_cases(self.cases)
            self.assertTrue(errors)

    def test_duplicate_case_identifiers(self):
        data = json.loads(self.cases.read_text(encoding='utf-8'))
        data['cases'][1]['id'] = data['cases'][0]['id']
        self.cases.write_text(json.dumps(data), encoding='utf-8')
        errors, _ = validator.validate_cases(self.cases)
        self.assertTrue(any('重复' in error for error in errors))

    def test_main_reports_failure(self):
        with mock.patch.object(validator, 'validate_repository', return_value=(['fixture failure'], 0)):
            with contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(validator.main(), 1)
        self.assertIn('fixture failure', output.getvalue())

    def test_ci_uses_pinned_official_source_and_all_tests(self):
        requirements = (ROOT / 'requirements-dev.txt').read_text(encoding='utf-8')
        workflow = (ROOT / '.github/workflows/human-rlaif.yml').read_text(encoding='utf-8')
        self.assertIn('skills-ref @ git+https://github.com/agentskills/agentskills.git@'
                      'f130f348f502d9804278a617f86929846896d2e9#subdirectory=skills-ref', requirements)
        self.assertIn('pip install -r requirements-dev.txt', workflow)
        self.assertIn('skills-ref validate skill/human-rlaif', workflow)
        self.assertIn("-p 'test*.py'", workflow)


if __name__ == '__main__':
    unittest.main()
