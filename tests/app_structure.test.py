import os
import sys
import ast
import io
import tokenize
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as novel_app


EXPECTED_ROUTES = [
    ('/', 'GET'),
    ('/api/ai/chat', 'POST'),
    ('/api/ai/configs', 'GET'),
    ('/api/ai/configs', 'POST'),
    ('/api/ai/configs/<int:config_id>', 'DELETE'),
    ('/api/ai/configs/<int:config_id>', 'GET'),
    ('/api/ai/configs/<int:config_id>', 'PUT'),
    ('/api/ai/configs/<int:config_id>/activate', 'POST'),
    ('/api/ai/configs/<int:config_id>/test', 'POST'),
    ('/api/ai/configs/test', 'POST'),
    ('/api/ai/novels/<int:novel_id>/characters/analyze', 'POST'),
    ('/api/ai/novels/metadata', 'POST'),
    ('/api/ai/novels/metadata/feedback', 'POST'),
    ('/api/ai/providers', 'GET'),
    ('/api/categories', 'GET'),
    ('/api/categories', 'POST'),
    ('/api/categories/<int:category_id>', 'DELETE'),
    ('/api/categories/<int:category_id>', 'PUT'),
    ('/api/crawler/rules', 'GET'),
    ('/api/crawler/rules', 'POST'),
    ('/api/crawler/rules/<int:rule_id>', 'DELETE'),
    ('/api/crawler/rules/<int:rule_id>', 'PUT'),
    ('/api/crawler/stats', 'GET'),
    ('/api/crawler/tasks', 'GET'),
    ('/api/crawler/tasks', 'POST'),
    ('/api/crawler/tasks/<int:task_id>', 'DELETE'),
    ('/api/crawler/tasks/<int:task_id>/run', 'POST'),
    ('/api/files/upload', 'POST'),
    ('/api/fix-paths', 'POST'),
    ('/api/import/batch', 'POST'),
    ('/api/import/scan', 'POST'),
    ('/api/novels', 'GET'),
    ('/api/novels', 'POST'),
    ('/api/novels/<int:novel_id>', 'DELETE'),
    ('/api/novels/<int:novel_id>', 'GET'),
    ('/api/novels/<int:novel_id>', 'PUT'),
    ('/api/novels/<int:novel_id>/chapters/<int:chapter_index>', 'GET'),
    ('/api/novels/<int:novel_id>/characters', 'GET'),
    ('/api/novels/<int:novel_id>/check-file', 'GET'),
    ('/api/novels/<int:novel_id>/download', 'GET'),
    ('/api/novels/<int:novel_id>/read', 'GET'),
    ('/api/novels/<int:novel_id>/reading-progress', 'PUT'),
    ('/api/novels/batch/category', 'POST'),
    ('/api/novels/batch/delete', 'POST'),
    ('/api/novels/batch/status', 'POST'),
    ('/api/novels/batch/tags', 'POST'),
    ('/api/search/fulltext', 'GET'),
    ('/api/stats', 'GET'),
    ('/api/tags', 'GET'),
    ('/api/tags', 'POST'),
    ('/api/tags/<int:tag_id>', 'DELETE'),
    ('/api/tags/<int:tag_id>', 'PUT'),
]


class AppStructureTest(unittest.TestCase):
    def test_public_route_map_is_unchanged(self):
        routes = sorted(
            (str(rule), ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'})))
            for rule in novel_app.app.url_map.iter_rules()
            if rule.endpoint != 'static'
        )

        self.assertEqual(routes, EXPECTED_ROUTES)

    def test_app_py_is_split_into_smaller_modules(self):
        app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app.py')
        with open(app_path, 'r', encoding='utf-8') as handle:
            line_count = sum(1 for _ in handle)

        self.assertLessEqual(line_count, 1500)

    def test_python_comments_and_docstrings_are_readable(self):
        project_root = os.path.dirname(os.path.dirname(__file__))
        python_files = [
            'app.py',
            'ai_routes.py',
            'crawler_routes.py',
            'reader_utils.py',
            'search_routes.py',
            'storage_utils.py',
        ]
        unreadable_items = []

        for relative_path in python_files:
            path = os.path.join(project_root, relative_path)
            with open(path, 'r', encoding='utf-8') as handle:
                source = handle.read()

            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type == tokenize.COMMENT and '???' in token.string:
                    unreadable_items.append(f'{relative_path}:{token.start[0]} comment')

            tree = ast.parse(source)
            nodes = [('module', tree)] + [
                (getattr(node, 'name', '<anonymous>'), node)
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            ]
            for name, node in nodes:
                docstring = ast.get_docstring(node, clean=False)
                if docstring and '???' in docstring:
                    line_number = getattr(node, 'lineno', 1)
                    unreadable_items.append(f'{relative_path}:{line_number} {name} docstring')

        self.assertEqual(unreadable_items, [])


if __name__ == '__main__':
    unittest.main()
