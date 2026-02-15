import pytest
from src.categorizer.rules import categorize_by_rules

def test_salary_categorization():
    # Credit Salary
    cat, merch, conf = categorize_by_rules("NEFT-SALARY FOR MAY", "CREDIT", 25000.0)
    assert cat == "Salary"
    assert conf is True

    # Salary below 10k is ignored as salary
    cat_low, _, conf_low = categorize_by_rules("SALARY", "CREDIT", 5000.0)
    assert cat_low != "Salary"
    assert conf_low is False

    # Debit Salary is not salary
    cat_deb, _, _ = categorize_by_rules("SALARY", "DEBIT", 25000.0)
    assert cat_deb != "Salary"

def test_emi_categorization():
    # Loan EMI
    cat, merch, conf = categorize_by_rules("SBI LOAN EMI DEBIT", "DEBIT", 12000.0)
    assert cat == "EMI"
    assert conf is True

    # Credit Card
    cat_cc, merch_cc, _ = categorize_by_rules("SBI CARD PAYMENT", "DEBIT", 5000.0)
    assert cat_cc == "EMI"
    assert merch_cc == "SBI Card"

def test_rent_categorization():
    cat, _, conf = categorize_by_rules("HOUSE RENT TRANSFER", "DEBIT", 15000.0)
    assert cat == "Rent"
    assert conf is True

    # Rent credit is not Rent category (should map to Others/UPI)
    cat_cred, _, _ = categorize_by_rules("RENT", "CREDIT", 15000.0)
    assert cat_cred != "Rent"

def test_merchant_food_shopping():
    # Zomato Food
    cat, merch, conf = categorize_by_rules("UPI/zomato@upi/Food Order", "DEBIT", 450.0)
    assert cat == "Food"
    assert merch == "Zomato"
    assert conf is True

    # Amazon Shopping
    cat_s, merch_s, conf_s = categorize_by_rules("AMZN PAY INDIA", "DEBIT", 1200.0)
    assert cat_s == "Shopping"
    assert merch_s == "Amazon"
    assert conf_s is True

def test_utilities():
    cat, merch, conf = categorize_by_rules("AIRTEL MOBILE BILL RECHARGE", "DEBIT", 399.0)
    assert cat == "Utilities"
    assert merch == "Airtel"
    assert conf is True

def test_upi_fallback():
    cat, merch, conf = categorize_by_rules("UPI/1234567890/Friend/Transfer", "DEBIT", 1000.0)
    assert cat == "UPI Transfer"
    assert conf is False  # LLM should verify peer-to-peer transfers
