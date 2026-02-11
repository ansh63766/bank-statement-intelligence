from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class Transaction(BaseModel):
    date: str = Field(..., description="Transaction date in YYYY-MM-DD format")
    description: str = Field(..., description="Raw description of the transaction")
    amount: float = Field(..., description="Transaction amount (always positive)")
    type: Literal["DEBIT", "CREDIT"] = Field(..., description="Type of transaction: DEBIT (outflow) or CREDIT (inflow)")
    balance: Optional[float] = Field(default=None, description="Running balance after the transaction")
    category: str = Field(default="Others", description="Categorized category of transaction (e.g. Salary, Rent, EMI, Food, Shopping, UPI Transfer, Cash Withdrawal, Investment, Utilities, Others)")
    reference_id: Optional[str] = Field(default=None, description="Extracted UPI Ref, Cheque, NEFT/RTGS transaction ID")
    merchant: Optional[str] = Field(default=None, description="Identified merchant name if applicable")

class StatementMetadata(BaseModel):
    bank_name: str = Field(default="Unknown", description="Name of the bank (e.g., SBI, HDFC, ICICI, Axis, or Unknown)")
    account_holder: Optional[str] = Field(default=None, description="Name of the account holder")
    account_number: Optional[str] = Field(default=None, description="Account number (masked or full)")
    start_date: Optional[str] = Field(default=None, description="Statement start date in YYYY-MM-DD format")
    end_date: Optional[str] = Field(default=None, description="Statement end date in YYYY-MM-DD format")
    opening_balance: Optional[float] = Field(default=None, description="Opening balance of the statement period")
    closing_balance: Optional[float] = Field(default=None, description="Closing balance of the statement period")

class ParsedStatement(BaseModel):
    metadata: StatementMetadata = Field(default_factory=StatementMetadata)
    transactions: List[Transaction] = Field(default_factory=list)
