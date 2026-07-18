from uuid import uuid4

from vector_match.services.fusion import rrf_fuse


def test_rrf_orders_by_summed_score():
    a, b, c = uuid4(), uuid4(), uuid4()
    fused = rrf_fuse([[a, b], [b, c]])
    assert fused[0][0] == b  # 两路都命中, 排第一
    assert fused[0][1] == 1 / 62 + 1 / 61  # b 在两路中分别 rank 2 和 rank 1
    assert {i for i, _ in fused} == {a, b, c}


def test_rrf_empty_lists():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[]]) == []
