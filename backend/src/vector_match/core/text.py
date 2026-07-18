import re

import jieba

_KEEP = re.compile(r"[\w一-鿿]+", re.UNICODE)


def to_fts_tokens(text: str) -> str:
    """jieba cut_for_search 分词, 过滤标点/空白 token, 空格拼接.

    结果用于 PG `to_tsvector('simple', ...)` 全文检索, 写入与查询两侧共用.
    """
    tokens = [t for t in jieba.cut_for_search(text) if _KEEP.fullmatch(t)]
    return " ".join(tokens)
