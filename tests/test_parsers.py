import pytest
from src.parsers.base import BaseParser

def test_clean_amount():
    assert BaseParser.clean_amount("1,500.50") == 1500.50
    assert BaseParser.clean_amount("Rs. 500") == 500.0
    assert BaseParser.clean_amount("10,000.00 Dr") == 10000.00
    assert BaseParser.clean_amount("-250.75") == -250.75
    assert BaseParser.clean_amount("") == 0.0
    assert BaseParser.clean_amount(None) == 0.0
    assert BaseParser.clean_amount("abc") == 0.0

def test_parse_date():
    assert BaseParser.parse_date("27 May 2026") == "2026-05-27"
    assert BaseParser.parse_date("27-May-2026") == "2026-05-27"
    assert BaseParser.parse_date("27/05/2026") == "2026-05-27"
    assert BaseParser.parse_date("27-05-26") == "2026-05-27"
    assert BaseParser.parse_date("2026-05-27") == "2026-05-27"
    # Messy date checks
    assert BaseParser.parse_date("27 May 26 Value Date...") == "2026-05-27"
    assert BaseParser.parse_date("Invalid Date") is None
    assert BaseParser.parse_date("") is None
    assert BaseParser.parse_date(None) is None

def test_match_headers():
    row_two_cols = ["Date", "Narration", "Chq/Ref No", "Withdrawal (Amt.)", "Deposit (Amt.)", "Closing Balance"]
    mapping = BaseParser.match_headers(row_two_cols)
    assert mapping["date"] == 0
    assert mapping["desc"] == 1
    assert mapping["chq"] == 2
    assert mapping["debit"] == 3
    assert mapping["credit"] == 4
    assert mapping["balance"] == 5

    row_single_col = ["Txn Date", "Particulars", "Amount", "Balance"]
    mapping_single = BaseParser.match_headers(row_single_col)
    assert mapping_single["date"] == 0
    assert mapping_single["desc"] == 1
    assert mapping_single["debit"] == 2
    assert mapping_single["credit"] == 2
    assert mapping_single["balance"] == 3
