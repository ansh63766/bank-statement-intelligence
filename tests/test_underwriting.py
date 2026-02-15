import pytest
from src.models.underwriting import (
    IncomeSignals,
    SpendingSignals,
    DebtSignals,
    BalanceSignals,
    NegativeSignals
)
from src.underwriting.score import evaluate_creditworthiness

def test_good_credit_profile():
    income = IncomeSignals(
        total_salary=50000.0,
        salary_frequency="Monthly",
        income_stability_score=100.0
    )
    spending = SpendingSignals(total_debits=30000.0)
    debt = DebtSignals(total_emi=0.0, emi_to_income_ratio=0.0)
    balance = BalanceSignals(
        average_daily_balance=60000.0,
        minimum_balance=45000.0,
        ending_balance=55000.0,
        low_balance_days=0
    )
    negative = NegativeSignals(cheque_bounce_count=0, overdraft_occurrences=0, nsf_count=0)
    
    evaluation = evaluate_creditworthiness(income, spending, debt, balance, negative)
    
    assert evaluation.rating == "GOOD"
    assert evaluation.creditworthiness_score >= 80
    assert any("Zero active EMI" in j for j in evaluation.justifications)
    assert any("Strong average daily balance" in j for j in evaluation.justifications)

def test_poor_credit_profile():
    income = IncomeSignals(
        total_salary=0.0,
        salary_frequency="None",
        income_stability_score=0.0
    )
    spending = SpendingSignals(total_debits=5000.0)
    debt = DebtSignals(total_emi=4000.0, emi_to_income_ratio=0.8)
    balance = BalanceSignals(
        average_daily_balance=1000.0,
        minimum_balance=100.0,
        ending_balance=200.0,
        low_balance_days=8
    )
    negative = NegativeSignals(cheque_bounce_count=2, overdraft_occurrences=1, nsf_count=3)
    
    evaluation = evaluate_creditworthiness(income, spending, debt, balance, negative)
    
    assert evaluation.rating == "POOR"
    assert evaluation.creditworthiness_score < 40
    assert any("Detected 2 cheque bounce" in j for j in evaluation.justifications)
    assert any("Critically low average balance" in j for j in evaluation.justifications)
