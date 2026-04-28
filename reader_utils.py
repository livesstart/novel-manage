"""Reader helpers for text encoding and chapter parsing."""
import re


# 章节识别正则表达式模式
CHAPTER_PATTERNS = [
    # 第X章/回/节/集/卷
    r'^(第[\s]*[零一二三四五六七八九十百千万\d]+[\s]*[章回节集卷])',
    # Chapter X / CHAPTER X
    r'^(Chapter[\s]+\d+)',  # 英文章节
    # 数字开头 + 章节名
    r'^(\d+[\.\s、]+[^\n]+)',
    # 第X章：标题
    r'^(第[\s]*[零一二三四五六七八九十百千万\d]+[\s]*[章回节集卷][：:].+)',
    # 【第X章】
    r'^[【\[](第[\s]*[零一二三四五六七八九十百千万\d]+[\s]*[章回节集卷])[】\]]',
]


def detect_encoding(file_path):
    """检测文件编码"""
    import chardet
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding'] or 'utf-8'


def parse_chapters(content):
    """解析章节"""
    chapters = []
    lines = content.split('\n')

    # 合并所有模式
    combined_pattern = '|'.join(f'({p})' for p in CHAPTER_PATTERNS)
    chapter_regex = re.compile(combined_pattern, re.IGNORECASE)

    current_chapter = None
    current_content = []

    for line_num, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # 检查是否是章节标题
        match = chapter_regex.match(line)
        if match:
            # 保存上一章节
            if current_chapter:
                current_chapter['content'] = '\n'.join(current_content)
                chapters.append(current_chapter)

            # 开始新章节
            current_chapter = {
                'title': line,
                'content': '',
                'line_num': line_num
            }
            current_content = []
        else:
            if current_chapter:
                current_content.append(line)

    # 保存最后一章
    if current_chapter:
        current_chapter['content'] = '\n'.join(current_content)
        chapters.append(current_chapter)

    # 如果没有识别到章节，将全文作为一章
    if not chapters and content.strip():
        chapters = [{
            'title': '全文',
            'content': content.strip(),
            'line_num': 0
        }]

    return chapters
