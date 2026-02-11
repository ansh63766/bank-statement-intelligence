from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field

class IncomeSignals(BaseModel):
    total_salary: float = Field(default=0.0, description="Total salary income identified during the statement period")
    salary_frequency: Literal["Monthly", "Bi-weekly", "Irregular", "None"] = Field(default="None", description="Identified frequency of salary credits")
    salary_dates: List[str] = Field(default_factory=list, description="Dates when salary credits were received")
    other_credits: float = Field(default=0.0, description="Total other credits (non-salary inflows)")
    income_stability_score: float = Field(default=0.0, description="Income stability score from 0 (unstable) to 100 (highly stable)")

class SpendingSignals(BaseModel):
    total_debits: float = Field(default=0.0, description="Total spending/debits during the statement period")
    discretionary_spending: float = Field(default=0.0, description="Total spending on food, shopping, travel, entertainment, etc.")
    essential_spending: float = Field(default=0.0, description="Total spending on rent, EMI, utilities, insurance, etc.")
    spending_volatility: float = Field(default=0.0, description="Coefficient of variation of daily debit volumes")
    cash_withdrawal_ratio: float = Field(default=0.0, description="Ratio of cash withdrawals to total spending (0 to 1)")
    top_spending_categories: Dict[str, float] = Field(default_factory=dict, description="Spend breakdown per category")

class DebtSignals(BaseModel):
    total_emi: float = Field(default=0.0, description="Total identified monthly loan EMI payments")
    emi_to_income_ratio: float = Field(default=0.0, description="Ratio of EMIs to total salary income (0 to 1)")
    loan_payments_count: int = Field(default=0, description="Number of loan payments/EMIs detected")

class BalanceSignals(BaseModel):
    average_daily_balance: float = Field(default=0.0, description="Average running balance across the statement period")
    minimum_balance: float = Field(default=0.0, description="Minimum balance observed during the statement period")
    ending_balance: float = Field(default=0.0, description="Final closing balance")
    monthly_closing_balances: Dict[str, float] = Field(default_factory=dict, description="Closing balances by month")
    low_balance_days: int = Field(default=0, description="Number of days the running balance fell below Rs. 2000 (or equivalent threshold)")

class NegativeSignals(BaseModel):
    cheque_bounce_count: int = Field(default=0, description="Count of cheque bounce transactions")
    overdraft_occurrences: int = Field(default=0, description="Count of overdraft or penalty instances")
    nsf_count: int = Field(default=0, description="Non-sufficient funds (NSF) or transaction decline counts due to low balance")

class UnderwritingEvaluation(BaseModel):
    creditworthiness_score: int = Field(..., description="Overall credit score from 0 to 100")
    rating: Literal["GOOD", "FAIR", "POOR"] = Field(..., description="Qualitative rating of creditworthiness")
    justifications: List[str] = Field(default_factory=list, description="Key justifications for the assigned score & rating")
    income_signals: IncomeSignals = Field(..., description="Aggregated income signals")
    spending_signals: SpendingSignals = Field(..., description="Aggregated spending signals")
    debt_signals: DebtSignals = Field(..., description="Aggregated debt and EMI signals")
    balance_signals: BalanceSignals = Field(..., description="Aggregated balance and liquidity signals")
    negative_signals: NegativeSignals = Field(..., description="Aggregated negative and risk signals")
