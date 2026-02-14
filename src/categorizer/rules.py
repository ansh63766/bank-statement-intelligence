import re
from typing import Tuple, Optional

# Pre-compiled regex patterns for categorization & merchant extraction
SALARY_PATTERNS = [
    r"salary", r"sal\b", r"neft-salary", r"credit-sal", r"direct deposit",
    r"direct dep", r"wipro sal", r"tcs sal", r"infosys sal", r"cognizant sal"
]

EMI_PATTERNS = [
    r"emi\b", r"loan\b", r"\bchg\b.*loan", r"hdfc loan", r"sbi loan",
    r"housing loan", r"car loan", r"auto loan", r"personal loan", r"billdesk.*loan",
    r"credit card", r"\bcc\b pay", r"card payment", r"sbi card", r"icici card"
]

RENT_PATTERNS = [
    r"rent\b", r"house rent", r"room rent", r"rental", r"mygate rent",
    r"nobroker rent", r"owner rent"
]

CASH_PATTERNS = [
    r"cash wdl", r"atm wdl", r"atm-wdl", r"cash withdrawal", r"atm cash",
    r"self withdrawal", r"wdl-atm"
]

INVESTMENT_PATTERNS = [
    r"mutual fund", r"\bmf\b", r"\bsip\b", r"zerodha", r"groww", r"securities",
    r"motilal", r"upstox", r"ndsl", r"cdsl", r"ppf\b", r"investment"
]

UTILITIES_PATTERNS = [
    r"electricity", r"water bill", r"gas bill", r"recharge", r"airtel",
    r"jio\b", r"broadband", r"internet bill", r"dth\b", r"act fiber",
    r"bescom", r"billdesk", r"paytm bill", r"tatapower"
]

FOOD_MERCHANTS = {
    "swiggy": r"swiggy",
    "zomato": r"zomato",
    "ubereats": r"ubereats",
    "starbucks": r"starbucks",
    "dominos": r"dominos",
    "mcdonalds": r"mcdonald|mcd\b",
    "kfc": r"kfc"
}

SHOPPING_MERCHANTS = {
    "amazon": r"amazon|amzn",
    "flipkart": r"flipkart",
    "myntra": r"myntra",
    "zepto": r"zepto",
    "blinkit": r"blinkit|grofers",
    "bigbasket": r"bigbasket|bb\b",
    "uber": r"uber",
    "ola": r"ola cab|olacabs",
    "dmart": r"dmart|avenue super",
    "reliance retail": r"reliance retail|jiomart"
}

def categorize_by_rules(desc: str, txn_type: str, amount: float) -> Tuple[str, Optional[str], bool]:
    """
    Categorizes a transaction based on description rules.
    
    Returns:
        (category, merchant, is_confident)
        category: The standardized category string.
        merchant: The extracted merchant name (or None).
        is_confident: True if the rule match is high-confidence, False if LLM fallback should be used.
    """
    desc_lower = desc.lower().strip()
    
    # 1. SALARY (Credits only, typically >= 10,000)
    if txn_type == "CREDIT" and amount >= 10000.0:
        if any(re.search(pat, desc_lower) for pat in SALARY_PATTERNS):
            return "Salary", None, True

    # 2. EMI / LOANS (Debits only)
    if txn_type == "DEBIT":
        if any(re.search(pat, desc_lower) for pat in EMI_PATTERNS):
            # Try to identify card merchant
            merchant = None
            if "sbi card" in desc_lower:
                merchant = "SBI Card"
            elif "hdfc card" in desc_lower:
                merchant = "HDFC Card"
            elif "icici card" in desc_lower:
                merchant = "ICICI Card"
            return "EMI", merchant, True

    # 3. RENT (Debits only, typically larger amounts)
    if txn_type == "DEBIT" and amount >= 2000.0:
        if any(re.search(pat, desc_lower) for pat in RENT_PATTERNS):
            return "Rent", None, True

    # 4. CASH WITHDRAWAL
    if any(re.search(pat, desc_lower) for pat in CASH_PATTERNS):
        return "Cash Withdrawal", "ATM", True

    # 5. INVESTMENT
    if any(re.search(pat, desc_lower) for pat in INVESTMENT_PATTERNS):
        merchant = None
        if "zerodha" in desc_lower:
            merchant = "Zerodha"
        elif "groww" in desc_lower:
            merchant = "Groww"
        return "Investment", merchant, True

    # 6. FOOD & SHOPPING MERCHANTS (High Confidence check)
    # Check food merchants
    for merch, pat in FOOD_MERCHANTS.items():
        if re.search(pat, desc_lower):
            return "Food", merch.title(), True
            
    # Check shopping/grocery/commute merchants
    for merch, pat in SHOPPING_MERCHANTS.items():
        if re.search(pat, desc_lower):
            return "Shopping", merch.title(), True

    # 7. UTILITIES
    if any(re.search(pat, desc_lower) for pat in UTILITIES_PATTERNS):
        merchant = None
        for u_name in ["airtel", "jio", "act fiber", "bescom", "tata power"]:
            if u_name in desc_lower:
                merchant = u_name.title()
                break
        return "Utilities", merchant, True

    # 8. UPI TRANSFER (Weak pattern - if it's general UPI, we categorize as UPI Transfer, but is_confident=False
    # because we want LLM to double check if it can classify the merchant/category better)
    if "upi" in desc_lower:
        # Try to extract a clean merchant name from UPI description (e.g. UPI/zomato@upi/...)
        merchant = None
        # Format often matches UPI/ref/merchant/or similar
        upi_parts = desc_lower.split("/")
        if len(upi_parts) > 2:
            # Let's inspect the parts for common clean strings that don't contain numbers
            for part in upi_parts:
                part_clean = part.strip()
                if part_clean and not part_clean.isdigit() and len(part_clean) > 2 and "@" not in part_clean:
                    merchant = part_clean.title()
                    break
        return "UPI Transfer", merchant, False

    # 9. Default Fallback
    return "Others", None, False
