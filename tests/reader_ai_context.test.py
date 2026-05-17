import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import reader_utils


class ReaderAIContextTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        reader_utils.clear_reader_file_cache()

    def tearDown(self):
        reader_utils.clear_reader_file_cache()
        self.tmpdir.cleanup()

    def write_book(self, name, content):
        path = Path(self.tmpdir.name) / name
        path.write_text(content, encoding='utf-8')
        return path

    def resolve_path(self, file_path):
        path = Path(file_path)
        if path.exists():
            return str(path), [str(path)]
        return None, [str(path)]

    def is_readable(self, file_path):
        return Path(file_path).suffix.lower() == '.txt'

    def test_short_book_uses_complete_context(self):
        import ai_context

        book_path = self.write_book(
            'short.txt',
            'Chapter 1\nOpening clue.\nChapter 2\nFinal answer.'
        )
        novel = {
            'title': 'Short Context Book',
            'author': 'Context Author',
            'description': 'A compact book.',
            'category_name': 'Mystery',
            'tags': [{'name': 'clue'}, {'name': 'short'}],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=2000,
        )

        self.assertTrue(context['is_full_text'])
        self.assertFalse(context['is_truncated'])
        self.assertIn('Title: Short Context Book', context['metadata_text'])
        self.assertIn('Tags: clue, short', context['metadata_text'])
        self.assertIn('Opening clue.', context['content_text'])
        self.assertIn('Final answer.', context['content_text'])
        self.assertEqual(context['chapter_count'], 2)

    def test_long_book_samples_start_middle_and_end(self):
        import ai_context

        chapters = []
        for index in range(1, 13):
            marker = f'Middle clue {index}.'
            if index == 1:
                marker = 'Opening clue.'
            if index == 12:
                marker = 'Ending clue.'
            chapters.append(f'Chapter {index}\n{marker}\n' + ('filler text ' * 80))
        book_path = self.write_book('long.txt', '\n'.join(chapters))
        novel = {
            'title': 'Long Context Book',
            'author': 'Context Author',
            'description': 'A long book.',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=1800,
        )

        self.assertFalse(context['is_full_text'])
        self.assertTrue(context['is_truncated'])
        self.assertIn('Opening clue.', context['content_text'])
        self.assertIn('Ending clue.', context['content_text'])
        self.assertRegex(context['content_text'], r'Middle clue (4|5|6|7|8|9)\.')
        self.assertGreaterEqual(len(context['segments']), 4)
        self.assertLessEqual(context['included_chars'], 1800)

    def test_focus_chapter_is_prioritized_in_sampled_context(self):
        import ai_context

        chapters = []
        for index in range(1, 16):
            marker = f'Normal chapter {index}.'
            if index == 9:
                marker = 'Focused chapter secret.'
            chapters.append(f'Chapter {index}\n{marker}\n' + ('padding ' * 100))
        book_path = self.write_book('focused.txt', '\n'.join(chapters))
        novel = {
            'title': 'Focused Context Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=1600,
            focus_chapter_index=8,
        )

        self.assertFalse(context['is_full_text'])
        self.assertIn('Focused chapter secret.', context['content_text'])
        self.assertTrue(any(segment['chapter_index'] == 8 for segment in context['segments']))

    def test_unreadable_content_is_not_marked_full_text(self):
        import ai_context

        missing_path = Path(self.tmpdir.name) / 'missing.txt'
        novel = {
            'title': 'Missing Content Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(missing_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=2000,
        )

        self.assertFalse(context['is_full_text'])
        self.assertFalse(context['is_truncated'])
        self.assertEqual(context['content_text'], '')
        self.assertIn('Novel content context: Not available.', context['context_text'])

    def test_late_focus_chapter_is_retained_with_tight_budget(self):
        import ai_context

        long_title = 'Chapter heading with extra context ' * 7
        chapters = []
        for index in range(1, 21):
            marker = f'Ordinary sampled chapter {index}.'
            if index == 19:
                marker = 'Late focused chapter secret.'
            chapters.append(f'Chapter {index} {long_title}\n{marker}\n' + ('padding ' * 120))
        book_path = self.write_book('late-focus.txt', '\n'.join(chapters))
        novel = {
            'title': 'Late Focus Context Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=1000,
            focus_chapter_index=18,
        )

        self.assertFalse(context['is_full_text'])
        self.assertIn('Late focused chapter secret.', context['content_text'])
        self.assertTrue(any(segment['chapter_index'] == 18 for segment in context['segments']))
        self.assertLessEqual(context['included_chars'], 1000)

    def test_long_book_can_sample_more_than_four_segments_when_budget_allows(self):
        import ai_context

        chapters = []
        for index in range(1, 21):
            chapters.append(f'Chapter {index}\nSegment marker {index}.\n' + ('filler ' * 120))
        book_path = self.write_book('many-segments.txt', '\n'.join(chapters))
        novel = {
            'title': 'Many Segment Context Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=9000,
        )

        self.assertFalse(context['is_full_text'])
        self.assertGreater(len(context['segments']), 4)
        self.assertLessEqual(len(context['segments']), ai_context.MAX_SAMPLED_CONTEXT_SEGMENTS)
        self.assertLessEqual(context['included_chars'], 9000)

    def test_ending_sample_uses_tail_of_final_chapter(self):
        import ai_context

        chapters = []
        for index in range(1, 8):
            if index == 7:
                body = ('final filler ' * 220) + 'ENDING TAIL MARKER'
            else:
                body = f'Middle marker {index}.\n' + ('filler ' * 220)
            chapters.append(f'Chapter {index}\n{body}')
        book_path = self.write_book('ending-tail.txt', '\n'.join(chapters))
        novel = {
            'title': 'Ending Tail Context Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=2200,
        )

        self.assertFalse(context['is_full_text'])
        self.assertIn('ENDING TAIL MARKER', context['content_text'])
        self.assertLessEqual(context['included_chars'], 2200)

    def test_many_omitted_tiny_chapters_are_marked_truncated(self):
        import ai_context

        chapters = []
        for index in range(1, 31):
            chapters.append(f'Chapter {index}\nTiny {index}.')
        book_path = self.write_book('tiny-chapters.txt', '\n'.join(chapters))
        novel = {
            'title': 'Tiny Chapter Context Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=1000,
        )

        self.assertFalse(context['is_full_text'])
        self.assertLess(len(context['segments']), context['chapter_count'])
        self.assertTrue(context['is_truncated'])

    def test_focus_sample_never_exceeds_max_segments(self):
        import ai_context

        chapters = []
        for index in range(1, 21):
            marker = f'Chapter marker {index}.'
            if index == 19:
                marker = 'Focused max segment marker.'
            chapters.append(f'Chapter {index}\n{marker}\n' + ('filler ' * 160))
        book_path = self.write_book('focus-max-segments.txt', '\n'.join(chapters))
        novel = {
            'title': 'Focus Max Segment Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=9000,
            focus_chapter_index=18,
        )

        self.assertLessEqual(len(context['segments']), ai_context.MAX_SAMPLED_CONTEXT_SEGMENTS)
        self.assertTrue(any(segment['chapter_index'] == 18 for segment in context['segments']))
        self.assertIn('Focused max segment marker.', context['content_text'])

    def test_final_focus_chapter_uses_tail_when_long(self):
        import ai_context

        chapters = []
        for index in range(1, 8):
            if index == 7:
                body = ('focused final filler ' * 180) + 'FOCUSED FINAL TAIL MARKER'
            else:
                body = f'Ordinary chapter {index}.\n' + ('filler ' * 180)
            chapters.append(f'Chapter {index}\n{body}')
        book_path = self.write_book('focused-final-tail.txt', '\n'.join(chapters))
        novel = {
            'title': 'Focused Final Tail Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=2200,
            focus_chapter_index=6,
        )

        self.assertFalse(context['is_full_text'])
        self.assertIn('FOCUSED FINAL TAIL MARKER', context['content_text'])
        self.assertTrue(any(segment['chapter_index'] == 6 for segment in context['segments']))

    def test_tiny_ending_trim_does_not_exceed_budget(self):
        import ai_context

        long_title = 'Long budget title ' * 7
        chapters = []
        for index in range(1, 21):
            body = f'Budget chapter {index}.\n' + ('filler ' * 180)
            if index == 20:
                body = ('ending filler ' * 180) + 'BUDGET TAIL'
            chapters.append(f'Chapter {index} {long_title}\n{body}')
        book_path = self.write_book('tight-ending-budget.txt', '\n'.join(chapters))
        novel = {
            'title': 'Tight Ending Budget Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=1000,
        )

        self.assertFalse(context['is_full_text'])
        self.assertLessEqual(context['included_chars'], 1000)
        self.assertLessEqual(len(context['content_text']), 1000)

    def test_nearly_header_only_budget_drops_segments_instead_of_overflowing(self):
        import ai_context

        long_title = 'T' * 190
        chapters = []
        for index in range(1, 9):
            body = f'Header budget chapter {index}.\n' + ('filler ' * 220)
            chapters.append(f'Chapter {index} {long_title}\n{body}')
        book_path = self.write_book('header-pressure.txt', '\n'.join(chapters))
        novel = {
            'title': 'Header Pressure Context Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }
        char_budget = 1851

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=char_budget,
        )

        self.assertFalse(context['is_full_text'])
        self.assertLessEqual(context['included_chars'], char_budget)
        self.assertLessEqual(len(context['content_text']), char_budget)

    def test_positive_char_budget_below_default_floor_is_respected(self):
        import ai_context

        chapters = []
        for index in range(1, 12):
            chapters.append(f'Chapter {index}\nSmall budget marker {index}.\n' + ('filler ' * 120))
        book_path = self.write_book('small-budget.txt', '\n'.join(chapters))
        novel = {
            'title': 'Small Budget Context Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=500,
        )

        self.assertFalse(context['is_full_text'])
        self.assertLessEqual(context['included_chars'], 500)
        self.assertLessEqual(len(context['content_text']), 500)

    def test_metadata_is_bounded_for_huge_description_and_tags(self):
        import ai_context

        book_path = self.write_book('huge-metadata.txt', 'Chapter 1\nMetadata content.')
        novel = {
            'title': 'Huge Metadata Context Book',
            'author': 'Metadata Author',
            'description': 'Bounded description begins. ' + ('description overflow ' * 400),
            'category_name': 'Metadata',
            'tags': [{'name': f'tag-{index}-' + ('overflow' * 20)} for index in range(80)],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=500,
        )

        self.assertIn('Title: Huge Metadata Context Book', context['metadata_text'])
        self.assertIn('Description: Bounded description begins.', context['metadata_text'])
        self.assertLessEqual(len(context['metadata_text']), 1600)
        self.assertLessEqual(len(context['context_text']), 1600 + 500 + 200)
        self.assertEqual(context['included_chars'], len(context['content_text']))


if __name__ == '__main__':
    unittest.main()
