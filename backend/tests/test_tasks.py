import pytest
from app.tasks import run_task

def test_generate_report():
    result = run_task("generate_report", {"records": 25}, 1)
    assert result["records_processed"] == 25

def test_fail_first_n_then_succeeds():
    with pytest.raises(RuntimeError):
        run_task("fail_first_n", {"fail_first_n": 2}, 1)
    with pytest.raises(RuntimeError):
        run_task("fail_first_n", {"fail_first_n": 2}, 2)
    result = run_task("fail_first_n", {"fail_first_n": 2}, 3)
    assert result["successful_attempt"] == 3

def test_fibonacci():
    assert run_task("fibonacci", {"n": 10}, 1)["value"] == 55
