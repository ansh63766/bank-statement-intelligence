import pytest
from src.models.statements import ParsedStatement, StatementMetadata, Transaction
from src.signals.engine import compute_financial_signals

def test_financial_signals_calculation():
    # Setup test statement spanning 10 days (May 1 to May 10)
    meta = StatementMetadata(
        bank_name="Test Bank",
        start_date="2026-05-01",
        end_date="2026-05-10",
        opening_balance=10000.0
    )
    
    txns = [
        Transaction(
            date="2026-05-01",
            description="UPI/Friend/Debit",
            amount=1000.0,
            type="DEBIT",
            balance=9000.0,
            category="UPI Transfer"
        ),
        Transaction(
            date="2026-05-05",
            description="Salary Credit",
            amount=5000.0,
            type="CREDIT",
            balance=14000.0,
            category="Salary"
        ),
        Transaction(
            date="2026-05-10",
            description="ATM CASH withdrawal",
            amount=2000.0,
            type="DEBIT",
            balance=12000.0,
            category="Cash Withdrawal"
        )
    ]
    
    parsed = ParsedStatement(metadata=meta, transactions=txns)
    
    income, spending, debt, balance, negative = compute_financial_signals(parsed)
    
    # 1. Income check
    assert income.total_salary == 5000.0
    assert income.salary_frequency == "Irregular"  # only 1 salary credit
    assert income.other_credits == 0.0

    # 2. Spending check
    assert spending.total_debits == 3000.0
    assert spending.cash_withdrawal_ratio == round(2000.0 / 3000.0, 3)

    # 3. Balance checks
    # Expected daily balances (May 1 to 10):
    # May 1: 9000
    # May 2: 9000
    # May 3: 9000
    # May 4: 9000
    # May 5: 14000
    # May 6: 14000
    # May 7: 14000
    # May 8: 14000
    # May 9: 14000
    # May 10: 12000
    # ADB = (9000*4 + 14000*5 + 12000*1) / 10 = 11800.0
    assert balance.average_daily_balance == 11800.0
    assert balance.minimum_balance == 9000.0
    assert balance.ending_balance == 12000.0
    assert balance.low_balance_days == 0  # all balances >= 2000
    
def test_negative_signals_detection():
    meta = StatementMetadata(start_date="2026-05-01", end_date="2026-05-02")
    txns = [
        Transaction(
            date="2026-05-01",
            description="CHQ RETURN CHARGES ON BOUNCE",
            amount=500.0,
            type="DEBIT",
            balance=5000.0,
            category="Others"
        ),
        Transaction(
            date="2026-05-02",
            description="OD LIMIT OVERDRAFT INTERST PENALTY",
            amount=100.0,
            type="DEBIT",
            balance=4900.0,
            category="Others"
        ),
        Transaction(
            date="2026-05-02",
            description="DEBIT FAILED DUE TO NSF INSUFFICIENT BALANCE",
            amount=0.0,
            type="DEBIT",
            balance=4900.0,
            category="Others"
        )
    ]
    parsed = ParsedStatement(metadata=meta, transactions=txns)
    _, _, _, _, negative = compute_financial_signals(parsed)
    
    assert negative.cheque_bounce_count == 1
    assert negative.overdraft_occurrences == 1
    assert negative.nsf_count == 1
