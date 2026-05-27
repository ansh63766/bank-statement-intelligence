import logging
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from src.models.statements import ParsedStatement, Transaction
from src.models.underwriting import (
    IncomeSignals,
    SpendingSignals,
    DebtSignals,
    BalanceSignals,
    NegativeSignals
)

logger = logging.getLogger("bank_statement_intel.signals")

def compute_financial_signals(parsed_statement: ParsedStatement) -> Tuple[IncomeSignals, SpendingSignals, DebtSignals, BalanceSignals, NegativeSignals]:
    """
    Computes all quantitative financial signals from a parsed bank statement.
    """
    txns = parsed_statement.transactions
    meta = parsed_statement.metadata
    
    # Return empty schemas if no transactions exist
    if not txns:
        return (
            IncomeSignals(),
            SpendingSignals(),
            DebtSignals(),
            BalanceSignals(),
            NegativeSignals()
        )
        
    # Sort transactions chronologically
    try:
        sorted_txns = sorted(txns, key=lambda t: t.date)
    except Exception:
        sorted_txns = txns

    # Extract dates
    dates = [t.date for t in sorted_txns]
    start_date_str = meta.start_date or dates[0]
    end_date_str = meta.end_date or dates[-1]
    
    # ----------------------------------------------------
    # 1. Income Signals
    # ----------------------------------------------------
    salary_txns = [t for t in sorted_txns if t.category == "Salary" and t.type == "CREDIT"]
    total_salary = sum(t.amount for t in salary_txns)
    salary_dates = [t.date for t in salary_txns]
    
    other_credits = sum(t.amount for t in sorted_txns if t.type == "CREDIT" and t.category != "Salary")
    
    # Determine Salary Frequency
    salary_count = len(salary_txns)
    if salary_count >= 3:
        # Check delta in days between consecutive salaries
        deltas = []
        for i in range(1, len(salary_dates)):
            d1 = datetime.strptime(salary_dates[i-1], "%Y-%m-%d")
            d2 = datetime.strptime(salary_dates[i], "%Y-%m-%d")
            deltas.append(abs((d2 - d1).days))
            
        avg_delta = sum(deltas) / len(deltas)
        std_delta = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
        
        if 25 <= avg_delta <= 35:
            salary_frequency = "Monthly"
            # Deduct stability if salary date varies heavily (std_delta > 5 days)
            stability = max(100.0 - (std_delta * 4), 50.0)
        elif 10 <= avg_delta <= 18:
            salary_frequency = "Bi-weekly"
            stability = max(100.0 - (std_delta * 4), 60.0)
        else:
            salary_frequency = "Irregular"
            stability = 50.0
    elif salary_count > 0:
        salary_frequency = "Irregular"
        stability = 40.0 * salary_count  # 40 for 1, 80 for 2
    else:
        salary_frequency = "None"
        # If no formal salary, check general credits frequency
        credits_count = len([t for t in sorted_txns if t.type == "CREDIT"])
        if credits_count >= 3:
            stability = 30.0
        else:
            stability = 0.0
            
    income_signals = IncomeSignals(
        total_salary=round(total_salary, 2),
        salary_frequency=salary_frequency,
        salary_dates=salary_dates,
        other_credits=round(other_credits, 2),
        income_stability_score=round(stability, 2)
    )

    # ----------------------------------------------------
    # 2. Spending Signals
    # ----------------------------------------------------
    total_debits = sum(t.amount for t in sorted_txns if t.type == "DEBIT")
    
    # Top spending categories
    category_totals = defaultdict(float)
    for t in sorted_txns:
        if t.type == "DEBIT":
            category_totals[t.category] += t.amount
            
    top_spending_categories = {cat: round(amt, 2) for cat, amt in category_totals.items()}
    
    # Discretionary vs Essential
    # Essential: Rent, EMI, Utilities
    essential_spending = (
        category_totals["Rent"] + 
        category_totals["EMI"] + 
        category_totals["Utilities"]
    )
    discretionary_spending = total_debits - essential_spending
    
    # Spending Volatility (Coefficient of variation of daily debit volumes)
    # 1. Map debits to daily totals
    daily_debits = defaultdict(float)
    for t in sorted_txns:
        if t.type == "DEBIT":
            daily_debits[t.date] += t.amount
            
    # Include all calendar days in the statement range to get a correct daily volume distribution
    try:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
        delta_days = (end_dt - start_dt).days + 1
        
        all_daily_debits = []
        for i in range(delta_days):
            day_str = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
            all_daily_debits.append(daily_debits.get(day_str, 0.0))
            
        mean_debit = statistics.mean(all_daily_debits) if all_daily_debits else 0.0
        std_debit = statistics.stdev(all_daily_debits) if len(all_daily_debits) > 1 else 0.0
        spending_volatility = (std_debit / mean_debit) if mean_debit > 0 else 0.0
    except Exception:
        spending_volatility = 0.0
        
    # Cash withdrawal ratio
    cash_withdrawn = category_totals["Cash Withdrawal"]
    cash_withdrawal_ratio = (cash_withdrawn / total_debits) if total_debits > 0 else 0.0
    
    spending_signals = SpendingSignals(
        total_debits=round(total_debits, 2),
        discretionary_spending=round(discretionary_spending, 2),
        essential_spending=round(essential_spending, 2),
        spending_volatility=round(spending_volatility, 3),
        cash_withdrawal_ratio=round(cash_withdrawal_ratio, 3),
        top_spending_categories=top_spending_categories
    )

    # ----------------------------------------------------
    # 3. Debt Signals
    # ----------------------------------------------------
    total_emi = category_totals["EMI"]
    emi_txns_count = len([t for t in sorted_txns if t.category == "EMI" and t.type == "DEBIT"])
    
    # EMI to Income ratio
    denominator = total_salary if total_salary > 0 else (total_salary + other_credits)
    emi_to_income_ratio = (total_emi / denominator) if denominator > 0 else 0.0
    
    debt_signals = DebtSignals(
        total_emi=round(total_emi, 2),
        emi_to_income_ratio=round(emi_to_income_ratio, 3),
        loan_payments_count=emi_txns_count
    )

    # ----------------------------------------------------
    # 4. Balance Signals (Daily Forward-Fill)
    # ----------------------------------------------------
    # Map raw transaction balances
    # If a date has multiple transactions, we take the balance of the last transaction of that day.
    daily_balances_map = {}
    for t in sorted_txns:
        if t.balance is not None:
            daily_balances_map[t.date] = t.balance
            
    # Forward-fill balances for all dates
    min_bal = float("inf")
    ending_balance = 0.0
    average_daily_balance = 0.0
    low_balance_days = 0
    monthly_closing = {}
    
    try:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
        delta_days = (end_dt - start_dt).days + 1
        
        last_known_balance = meta.opening_balance or 0.0
        daily_balances_list = []
        
        for i in range(delta_days):
            current_dt = start_dt + timedelta(days=i)
            day_str = current_dt.strftime("%Y-%m-%d")
            
            # If there is a transaction balance recorded for this day, update last known balance
            if day_str in daily_balances_map:
                last_known_balance = daily_balances_map[day_str]
                
            daily_balances_list.append(last_known_balance)
            min_bal = min(min_bal, last_known_balance)
            
            if last_known_balance < 2000.0:
                low_balance_days += 1
                
            # Log monthly closing balances (take the balance on the last day of each month)
            month_key = current_dt.strftime("%Y-%m")
            monthly_closing[month_key] = last_known_balance
            
        average_daily_balance = statistics.mean(daily_balances_list) if daily_balances_list else last_known_balance
        ending_balance = daily_balances_list[-1] if daily_balances_list else last_known_balance
        
    except Exception:
        # Fallback if dates are unparseable
        balances = [t.balance for t in sorted_txns if t.balance is not None]
        if balances:
            min_bal = min(balances)
            average_daily_balance = statistics.mean(balances)
            ending_balance = balances[-1]
        else:
            min_bal = 0.0
            average_daily_balance = 0.0
            ending_balance = 0.0
            
    if min_bal == float("inf"):
        min_bal = 0.0
        
    balance_signals = BalanceSignals(
        average_daily_balance=round(average_daily_balance, 2),
        minimum_balance=round(min_bal, 2),
        ending_balance=round(ending_balance, 2),
        monthly_closing_balances=monthly_closing,
        low_balance_days=low_balance_days
    )

    # ----------------------------------------------------
    # 5. Negative Signals (Risk Triggers)
    # ----------------------------------------------------
    cheque_bounce_count = 0
    overdraft_occurrences = 0
    nsf_count = 0
    
    bounce_keywords = [
        "bounce", "return", "chq ret", "dishonour", "insufficient funds",
        "chq bounce", "returned chq", "cheque return"
    ]
    od_keywords = [
        "od limit", "overdraft", "limit exceeded", "excess pull", "adhoc limit",
        "od chg", "overdraft charge"
    ]
    nsf_keywords = [
        "declined", "insufficient balance", "failed txn", "nsf", "insufficient fund"
    ]
    
    for t in sorted_txns:
        desc_lower = t.description.lower()
        
        # Check bounces
        if any(kw in desc_lower for kw in bounce_keywords):
            cheque_bounce_count += 1
            
        # Check overdraft limits
        if any(kw in desc_lower for kw in od_keywords):
            overdraft_occurrences += 1
            
        # Check NSF transaction declines (use regex word boundary for 'nsf' to avoid subword matches like 'fttransf')
        import re
        if any(kw in desc_lower for kw in ["declined", "insufficient balance", "failed txn", "insufficient fund"]) or re.search(r"\bnsf\b", desc_lower):
            nsf_count += 1

            
    negative_signals = NegativeSignals(
        cheque_bounce_count=cheque_bounce_count,
        overdraft_occurrences=overdraft_occurrences,
        nsf_count=nsf_count
    )

    return (
        income_signals,
        spending_signals,
        debt_signals,
        balance_signals,
        negative_signals
    )
