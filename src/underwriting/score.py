import logging
from typing import List, Tuple
from src.models.underwriting import (
    UnderwritingEvaluation,
    IncomeSignals,
    SpendingSignals,
    DebtSignals,
    BalanceSignals,
    NegativeSignals
)

logger = logging.getLogger("bank_statement_intel.underwriting")

def evaluate_creditworthiness(
    income: IncomeSignals,
    spending: SpendingSignals,
    debt: DebtSignals,
    balance: BalanceSignals,
    negative: NegativeSignals
) -> UnderwritingEvaluation:
    """
    Computes a creditworthiness score (0 to 100) and maps it to a rating (GOOD/FAIR/POOR)
    based on computed financial signals and risk thresholds.
    """
    justifications: List[str] = []
    
    # ----------------------------------------------------
    # 1. Average Daily Balance & Liquidity Score (Max 30 pts)
    # ----------------------------------------------------
    bal_score = 0.0
    adb = balance.average_daily_balance
    
    if adb >= 50000.0:
        bal_score = 30.0
        justifications.append("Positive: Strong average daily balance maintained (above Rs. 50,000).")
    elif adb >= 20000.0:
        bal_score = 25.0
        justifications.append("Positive: Healthy average daily balance maintained (above Rs. 20,000).")
    elif adb >= 10000.0:
        bal_score = 20.0
        justifications.append("Neutral: Moderate average daily balance maintained (above Rs. 10,000).")
    elif adb >= 5000.0:
        bal_score = 15.0
        justifications.append("Neutral: Low average daily balance maintained (above Rs. 5,000).")
    elif adb >= 2000.0:
        bal_score = 10.0
        justifications.append("Negative: Weak average daily balance maintained, indicating tight liquidity.")
    else:
        bal_score = 5.0
        justifications.append("Negative: Critically low average balance maintained (below Rs. 2,000).")
        
    # Deductions for low balance days
    low_days = balance.low_balance_days
    if low_days > 0:
        deduction = min(low_days * 1.0, 10.0) # Deduct 1 pt per low balance day, cap at 10 pts
        bal_score = max(bal_score - deduction, 0.0)
        if deduction >= 5.0:
            justifications.append(f"Negative: Frequent low balance days observed ({low_days} days below Rs. 2,000).")
        elif deduction > 0:
            justifications.append(f"Negative: Occasional low balance instances observed ({low_days} days below Rs. 2,000).")

    # ----------------------------------------------------
    # 2. Debt Service & EMI-to-Income Score (Max 30 pts)
    # ----------------------------------------------------
    debt_score = 0.0
    ratio = debt.emi_to_income_ratio
    
    # If no income signals exist (total credits = 0)
    has_income = (income.total_salary + income.other_credits) > 0
    
    if not has_income:
        debt_score = 5.0
        justifications.append("Negative: No income detected on the statement, debt service capacity unestablished.")
    elif debt.total_emi == 0.0:
        debt_score = 30.0
        justifications.append("Positive: Zero active EMI outflow detected, maximizing credit headroom.")
    elif ratio <= 0.20:
        debt_score = 25.0
        justifications.append(f"Positive: Low debt burden (EMI-to-income ratio is healthy at {ratio * 100:.1f}%).")
    elif ratio <= 0.35:
        debt_score = 20.0
        justifications.append(f"Neutral: Moderate debt burden (EMI-to-income ratio is manageable at {ratio * 100:.1f}%).")
    elif ratio <= 0.50:
        debt_score = 15.0
        justifications.append(f"Negative: Elevated debt burden (EMI-to-income ratio is high at {ratio * 100:.1f}%).")
    elif ratio <= 0.70:
        debt_score = 5.0
        justifications.append(f"Negative: High debt stress (EMI-to-income ratio is risky at {ratio * 100:.1f}%).")
    else:
        debt_score = 0.0
        justifications.append(f"Negative: Over-leveraged profile (EMI-to-income ratio is critical at {ratio * 100:.1f}%).")

    # ----------------------------------------------------
    # 3. Income Stability & Volume Score (Max 25 pts)
    # ----------------------------------------------------
    stability_pts = (income.income_stability_score / 100.0) * 20.0 # Scale 100 to 20 pts
    
    # Credit volume points (Max 5 pts)
    volume_pts = 0.0
    total_credits = income.total_salary + income.other_credits
    if total_credits >= 100000.0:
        volume_pts = 5.0
    elif total_credits >= 50000.0:
        volume_pts = 4.0
    elif total_credits >= 20000.0:
        volume_pts = 3.0
    elif total_credits >= 10000.0:
        volume_pts = 2.0
    else:
        volume_pts = 1.0
        
    stability_score = stability_pts + volume_pts
    
    if income.salary_frequency == "Monthly":
        justifications.append("Positive: Stable, recurring monthly salary credits detected.")
    elif income.salary_frequency == "Bi-weekly":
        justifications.append("Positive: Stable, recurring bi-weekly salary credits detected.")
    elif income.salary_frequency == "Irregular" and income.total_salary > 0:
        justifications.append("Neutral: Salary detected but frequency is irregular or statement is short.")
    elif total_credits > 20000.0:
        justifications.append("Neutral: General credits present, but no standard payroll credits detected.")
    else:
        justifications.append("Negative: Low or non-existent credits, indicating lack of active income stream.")

    # ----------------------------------------------------
    # 4. Risk & Negative Events Score (Max 15 pts)
    # ----------------------------------------------------
    risk_score = 15.0
    
    bounces = negative.cheque_bounce_count
    ods = negative.overdraft_occurrences
    nsfs = negative.nsf_count
    
    # Deduct points
    bounce_deduct = bounces * 5.0
    od_deduct = ods * 3.0
    nsf_deduct = nsfs * 1.0
    
    total_deduct = bounce_deduct + od_deduct + nsf_deduct
    risk_score = max(risk_score - total_deduct, 0.0)
    
    if bounces > 0:
        justifications.append(f"Negative: Critical Risk! Detected {bounces} cheque bounce/return event(s) indicating potential default.")
    if ods > 0:
        justifications.append(f"Negative: Detected {ods} overdraft limit/overuse event(s), indicating liquidity stress.")
    if nsfs > 0:
        justifications.append(f"Negative: Detected {nsfs} transaction declines due to non-sufficient funds.")
    if total_deduct == 0.0:
        justifications.append("Positive: Clean history with zero bounces, NSF declines, or overdraft charges.")

    # ----------------------------------------------------
    # Final Score & Rating Aggregation
    # ----------------------------------------------------
    final_score = int(round(bal_score + debt_score + stability_score + risk_score))
    # Cap between 0 and 100
    final_score = max(0, min(100, final_score))
    
    if final_score >= 70:
        rating = "GOOD"
    elif final_score >= 50:
        rating = "FAIR"
    else:
        rating = "POOR"
        
    logger.info(f"Underwriting evaluation complete: Score={final_score}, Rating={rating}")
    
    return UnderwritingEvaluation(
        creditworthiness_score=final_score,
        rating=rating,
        justifications=justifications,
        income_signals=income,
        spending_signals=spending,
        debt_signals=debt,
        balance_signals=balance,
        negative_signals=negative
    )
