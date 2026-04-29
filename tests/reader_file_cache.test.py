import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import reader_utils


class ReaderFileCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.book_path = Path(self.tmpdir.name) / 'cache-book.txt'
        self.book_path.write_text(
            '绗?绔?寮€濮媆n绗竴绔犲唴瀹筡n绗?绔?缁х画\n绗簩绔犲唴瀹?',
            encoding='utf-8'
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_reader_file_cache_reuses_parsed_content_until_file_changes(self):
        reader_utils.clear_reader_file_cache()
        original_parse_chapters = reader_utils.parse_chapters
        parse_calls = 0

        def counting_parse_chapters(content):
            nonlocal parse_calls
            parse_calls += 1
            return original_parse_chapters(content)

        reader_utils.parse_chapters = counting_parse_chapters
        try:
            first = reader_utils.get_cached_reader_file(str(self.book_path))
            second = reader_utils.get_cached_reader_file(str(self.book_path))

            self.assertIs(first, second)
            self.assertEqual(parse_calls, 1)

            self.book_path.write_text(
                '绗?绔?鏇存柊\n鏇存柊鍚庣殑鍐呭',
                encoding='utf-8'
            )
            os.utime(self.book_path, None)

            third = reader_utils.get_cached_reader_file(str(self.book_path))
            self.assertIsNot(third, first)
            self.assertEqual(parse_calls, 2)
        finally:
            reader_utils.parse_chapters = original_parse_chapters
            reader_utils.clear_reader_file_cache()

    def test_detect_encoding_prefers_valid_utf8_chinese_text(self):
        utf8_path = Path(self.tmpdir.name) / 'utf8-chinese.txt'
        utf8_path.write_text('第一章 开始\n这里是中文正文', encoding='utf-8')

        self.assertEqual(reader_utils.detect_encoding(str(utf8_path)).lower().replace('-', ''), 'utf8')


if __name__ == '__main__':
    unittest.main()
