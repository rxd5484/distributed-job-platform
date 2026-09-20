from app.queue import priority_score

def test_priority_ordering():
    t = 1700000000000
    assert priority_score(10, t) < priority_score(5, t) < priority_score(1, t)

def test_fifo_same_priority():
    assert priority_score(8, 1000) < priority_score(8, 2000)
