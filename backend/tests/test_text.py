from vector_match.core.text import to_fts_tokens


def test_chinese_tokenized():
    tokens = to_fts_tokens("易方达蓝筹精选混合A")
    parts = tokens.split(" ")
    assert "易方达" in parts
    assert "蓝筹" in parts
    assert "A" in parts


def test_punctuation_filtered():
    tokens = to_fts_tokens("中证500指数(LOF)，A类!")  # noqa: RUF001
    for tok in tokens.split(" "):
        assert tok.strip() != ""
        assert all(ch not in tok for ch in "(),，!！")  # noqa: RUF001


def test_empty_input():
    assert to_fts_tokens("") == ""
    assert to_fts_tokens("，。！") == ""  # noqa: RUF001
