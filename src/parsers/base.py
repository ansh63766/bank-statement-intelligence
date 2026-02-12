import re
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
from src.models.statements import ParsedStatement, Transaction

logger = logging.getLogger("bank_statement_intel.parser_base")

class BaseParser(ABC):
    """
    Abstract base class for all bank statement parsers.
    Includes common utility methods for parsing dates, cleaning amounts, and matching headers.
    """
    
    @abstractmethod
    async def parse(self, pdf_path: str) -> ParsedStatement:
        """
        Asynchronously parses the PDF file and returns a standardized ParsedStatement object.
        """
        pass

    @staticmethod
    def clean_amount(amount_str: Optional[str]) -> float:
        """
        Cleans currency strings (e.g., '1,520.50', 'Rs. 500', '100.00 Dr') and converts to float.
        """
        if not amount_str:
            return 0.0
        
        # Pre-strip currency prefixes/suffixes to prevent their periods from being treated as decimals
        pre_cleaned = re.sub(r"(?i)rs\.?|inr|usd|eur|gbp|\$", "", amount_str)
        pre_cleaned = pre_cleaned.replace(",", "").strip()
        
        # Keep only digits, decimals, signs, and exponents
        cleaned = re.sub(r"[^\d\.\-\+eE]", "", pre_cleaned)
        if not cleaned:
            return 0.0
        
        try:
            return float(cleaned)
        except ValueError:
            logger.warning(f"Failed to parse amount from string: '{amount_str}' (cleaned: '{cleaned}')")
            return 0.0

    @staticmethod
    def parse_date(date_str: Optional[str]) -> Optional[str]:
        """
        Attempts to parse typical Indian bank statement date formats and converts to YYYY-MM-DD.
        Supports formats:
        - 27 May 2026 / 27-May-2026 / 27-May-26
        - 27/05/2026 / 27/05/26 / 27-05-2026
        - 2026-05-27
        """
        if not date_str:
            return None
        
        cleaned = date_str.strip().replace("\n", " ")
        
        # Candidate formats
        formats = [
            "%d %b %Y", "%d-%b-%Y", "%d-%b-%y",
            "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y",
            "%Y-%m-%d"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
                
        # Regex fallback for messy dates like "27 May 2026Value Date..."
        match = re.search(r"(\d{1,2})[-/\s]([a-zA-Z]{3}|\d{1,2})[-/\s](\d{2,4})", cleaned)
        if match:
            day, month, year = match.groups()
            # Normalize year
            if len(year) == 2:
                year = "20" + year
            
            # Format combined string and try again
            joined = f"{day} {month} {year}"
            for fmt in ["%d %b %Y", "%d %B %Y", "%d %m %Y"]:
                try:
                    dt = datetime.strptime(joined, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
                    
        logger.warning(f"Could not parse date string: '{date_str}'")
        return None

    @staticmethod
    def match_headers(row: List[str]) -> Dict[str, int]:
        """
        Dynamically detects indices of columns based on common bank statement column names.
        
        Returns:
            Dict[str, int]: Mapping of field names ('date', 'desc', 'debit', 'credit', 'balance', 'chq') to row indices.
        """
        mapping = {}
        row_lower = [str(cell).lower().strip() for cell in row]
        
        # Key terms to look for
        date_terms = ["date", "txn date", "transaction date", "value date", "post date"]
        desc_terms = ["particulars", "narration", "description", "remarks", "transaction remarks"]
        chq_terms = ["chq", "cheque", "ref", "reference", "chq/ref", "instrument", "doc"]
        debit_terms = ["debit", "withdrawal", "withdraw", "dr", "withdrawal (amt.)", "amount (dr)"]
        credit_terms = ["credit", "deposit", "cr", "deposit (amt.)", "amount (cr)"]
        balance_terms = ["balance", "bal", "closing balance", "running balance"]
        
        # Check date
        for term in date_terms:
            for idx, cell in enumerate(row_lower):
                if term in cell and "value" not in term:  # Prefer txn date over value date
                    mapping["date"] = idx
                    break
            if "date" in mapping:
                break
        
        # If no date found yet, search with value date
        if "date" not in mapping:
            for idx, cell in enumerate(row_lower):
                if "value date" in cell or "date" in cell:
                    mapping["date"] = idx
                    break

        # Check description
        for term in desc_terms:
            for idx, cell in enumerate(row_lower):
                if term in cell:
                    mapping["desc"] = idx
                    break
            if "desc" in mapping:
                break

        # Check cheque/ref
        for term in chq_terms:
            for idx, cell in enumerate(row_lower):
                if term in cell:
                    mapping["chq"] = idx
                    break
            if "chq" in mapping:
                break

        # Check debit
        for term in debit_terms:
            for idx, cell in enumerate(row_lower):
                if term in cell:
                    mapping["debit"] = idx
                    break
            if "debit" in mapping:
                break

        # Check credit
        for term in credit_terms:
            for idx, cell in enumerate(row_lower):
                if term in cell:
                    mapping["credit"] = idx
                    break
            if "credit" in mapping:
                break

        # Check balance
        for term in balance_terms:
            for idx, cell in enumerate(row_lower):
                if term in cell:
                    mapping["balance"] = idx
                    break
            if "balance" in mapping:
                break

        # Fallback for combined single-column amount layout
        if "debit" not in mapping or "credit" not in mapping:
            amount_terms = ["amount", "amt", "transaction amount"]
            for term in amount_terms:
                for idx, cell in enumerate(row_lower):
                    if term in cell:
                        mapping["debit"] = idx
                        mapping["credit"] = idx
                        break
                if "debit" in mapping:
                    break

        return mapping
