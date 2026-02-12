import re
import logging
from typing import List, Dict, Any
import pdfplumber
from src.parsers.base import BaseParser
from src.models.statements import ParsedStatement, StatementMetadata, Transaction

logger = logging.getLogger("bank_statement_intel.sbi_parser")

class SBIParser(BaseParser):
    """
    Parser for State Bank of India (SBI) statements.
    """
    async def parse(self, pdf_path: str) -> ParsedStatement:
        metadata = StatementMetadata(bank_name="SBI")
        transactions: List[Transaction] = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # 1. Extract metadata from the first page text
                if pdf.pages:
                    first_page_text = pdf.pages[0].extract_text() or ""
                    self._extract_metadata(first_page_text, metadata)
                
                # 2. Extract transactions from tables across all pages
                header_map: Dict[str, int] = {}
                for page_idx, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            # Skip empty rows
                            if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                                continue
                            
                            row_str = [str(cell).strip() if cell is not None else "" for cell in row]
                            
                            # Detect or update header mapping
                            # SBI headers usually contain: Date, Description, Debit, Credit, Balance
                            is_header = any("date" in cell.lower() for cell in row_str) and \
                                        any("debit" in cell.lower() or "withdrawal" in cell.lower() for cell in row_str)
                            
                            if is_header:
                                # Update column map dynamically
                                matched = self.match_headers(row_str)
                                if "date" in matched and "desc" in matched:
                                    header_map = matched
                                continue
                            
                            # If we don't have a header map yet, we can't process transactions
                            if not header_map:
                                continue
                            
                            # Verify if this is a transaction row by checking if it has a valid date
                            date_idx = header_map["date"]
                            if date_idx >= len(row_str):
                                continue
                                
                            raw_date = row_str[date_idx]
                            parsed_date = self.parse_date(raw_date)
                            if not parsed_date:
                                # Not a transaction row (might be metadata/summary row at the bottom)
                                continue
                            
                            # Extract other fields
                            desc = row_str[header_map["desc"]] if header_map["desc"] < len(row_str) else ""
                            
                            # Reference ID extraction (e.g. UPI Ref / Cheque No)
                            ref_id = None
                            if "chq" in header_map and header_map["chq"] < len(row_str):
                                ref_val = row_str[header_map["chq"]].strip()
                                if ref_val and ref_val.lower() not in ["", "-", "nan"]:
                                    ref_id = ref_val
                            
                            # Fallback reference ID search in description
                            if not ref_id:
                                # UPI Ref numbers are usually 12 digits
                                upi_match = re.search(r"(\d{12})", desc)
                                if upi_match:
                                    ref_id = upi_match.group(1)
                            
                            # Debit & Credit
                            debit_val = 0.0
                            credit_val = 0.0
                            
                            if "debit" in header_map and header_map["debit"] < len(row_str):
                                debit_val = self.clean_amount(row_str[header_map["debit"]])
                            if "credit" in header_map and header_map["credit"] < len(row_str):
                                credit_val = self.clean_amount(row_str[header_map["credit"]])
                                
                            # Determine type
                            if credit_val > 0:
                                txn_type = "CREDIT"
                                amount = credit_val
                            elif debit_val > 0:
                                txn_type = "DEBIT"
                                amount = debit_val
                            else:
                                # Check if debit & credit are combined in a single column
                                # If debit and credit columns map to the same column, we need to inspect it
                                if "debit" in header_map and "credit" in header_map and header_map["debit"] == header_map["credit"]:
                                    val = self.clean_amount(row_str[header_map["debit"]])
                                    if val < 0:
                                        txn_type = "DEBIT"
                                        amount = abs(val)
                                    else:
                                        txn_type = "CREDIT"
                                        amount = val
                                else:
                                    # Amount is zero, skip it or default to DEBIT
                                    continue
                            
                            # Balance
                            balance = None
                            if "balance" in header_map and header_map["balance"] < len(row_str):
                                balance = self.clean_amount(row_str[header_map["balance"]])
                                
                            transactions.append(Transaction(
                                date=parsed_date,
                                description=desc,
                                amount=amount,
                                type=txn_type,
                                balance=balance,
                                reference_id=ref_id
                            ))
                            
        except Exception as e:
            logger.error(f"Error parsing SBI Statement: {e}")
            raise e

        # Standardize statement period dates and balances from transactions list
        if transactions:
            # Sort transactions by date to ensure proper order
            try:
                transactions.sort(key=lambda t: t.date)
            except Exception:
                pass
            
            metadata.start_date = transactions[0].date
            metadata.end_date = transactions[-1].date
            
            # Estimate opening / closing balances
            if transactions[0].balance is not None:
                first_amount = transactions[0].amount
                first_type = transactions[0].type
                first_bal = transactions[0].balance
                # Opening balance = Balance after first txn - Credit (or + Debit)
                metadata.opening_balance = round(first_bal - first_amount if first_type == "CREDIT" else first_bal + first_amount, 2)
            
            if transactions[-1].balance is not None:
                metadata.closing_balance = transactions[-1].balance
        
        return ParsedStatement(metadata=metadata, transactions=transactions)

    def _extract_metadata(self, text: str, metadata: StatementMetadata):
        """Extract account details using regex from raw text."""
        # Account Holder
        name_match = re.search(r"Account Name\s*:\s*(.*)", text, re.IGNORECASE)
        if name_match:
            metadata.account_holder = name_match.group(1).strip()
            
        # Account Number
        acc_match = re.search(r"Account Number\s*:\s*(\d+)", text, re.IGNORECASE)
        if acc_match:
            metadata.account_number = acc_match.group(1).strip()
