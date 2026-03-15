import pytest


def test_calculate_news_weight_basic():
    from mcp_server.tools.analytics import calculate_news_weight
    # rank=1 -> score=10, count=1, hotness=100% (rank<=5)
    # total = 10*0.6 + 10*0.3 + 100*0.1 = 6+3+10 = 19.0
    news_data = {"ranks": [1], "count": 1}
    score = calculate_news_weight(news_data, rank_threshold=5)
    assert abs(score - 19.0) < 0.01


def test_calculate_news_weight_empty_ranks():
    from mcp_server.tools.analytics import calculate_news_weight
    assert calculate_news_weight({"ranks": [], "count": 0}) == 0.0


def test_calculate_news_weight_high_rank():
    from mcp_server.tools.analytics import calculate_news_weight
    # rank=1 five times, count=5: rank_w=10, freq_w=50, hot=100
    # 10*0.6 + 50*0.3 + 100*0.1 = 6+15+10 = 31
    news_data = {"ranks": [1, 1, 1, 1, 1], "count": 5}
    assert abs(calculate_news_weight(news_data, rank_threshold=5) - 31.0) < 0.01
