import re
import logging
from typing import List, Dict, Any
import pdfplumber
from src.parsers.base import BaseParser
from src.models.statements import ParsedStatement, StatementMetadata, Transaction

logger = logging.getLogger("bank_statement_intel.icici_parser")

class ICICIParser(BaseParser):
    """
    Parser for ICICI Bank statements.
    """
    async def parse(self, pdf_path: str) -> ParsedStatement:
        metadata = StatementMetadata(bank_name="ICICI")
        transactions: List[Transaction] = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # 1. Extract metadata from first page
                if pdf.pages:
                    first_page_text = pdf.pages[0].extract_text() or ""
                    self._extract_metadata(first_page_text, metadata)
                
                # 2. Extract transactions
                header_map: Dict[str, int] = {}
                for page_idx, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                                continue
                            
                            row_str = [str(cell).strip() if cell is not None else "" for cell in row]
                            
                            # ICICI headers usually contain: Date, Description/Narration/Remarks, Cheque No, Withdrawal/Debit, Deposit/Credit, Balance
                            is_header = any("date" in cell.lower() for cell in row_str) and \
                                        any("remarks" in cell.lower() or "particulars" in cell.lower() or "narration" in cell.lower() for cell in row_str) and \
                                        any("withdrawal" in cell.lower() or "deposit" in cell.lower() or "debit" in cell.lower() or "credit" in cell.lower() for cell in row_str)
                            
                            if is_header:
                                matched = self.match_headers(row_str)
                                if "date" in matched and "desc" in matched:
                                    header_map = matched
                                continue
                            
                            if not header_map:
                                continue
                            
                            # Verify transaction row
                            date_idx = header_map["date"]
                            if date_idx >= len(row_str):
                                continue
                                
                            raw_date = row_str[date_idx]
                            parsed_date = self.parse_date(raw_date)
                            if not parsed_date:
                                continue
                            
                            # Extract fields
                            desc = row_str[header_map["desc"]] if header_map["desc"] < len(row_str) else ""
                            
                            ref_id = None
                            if "chq" in header_map and header_map["chq"] < len(row_str):
                                ref_val = row_str[header_map["chq"]].strip()
                                if ref_val and ref_val.lower() not in ["", "-", "nan"]:
                                    ref_id = ref_val
                            
                            if not ref_id:
                                upi_match = re.search(r"(\d{12})", desc)
                                if upi_match:
                                    ref_id = upi_match.group(1)
                            
                            debit_val = 0.0
                            credit_val = 0.0
                            
                            if "debit" in header_map and header_map["debit"] < len(row_str):
                                debit_val = self.clean_amount(row_str[header_map["debit"]])
                            if "credit" in header_map and header_map["credit"] < len(row_str):
                                credit_val = self.clean_amount(row_str[header_map["credit"]])
                                
                            if credit_val > 0:
                                txn_type = "CREDIT"
                                amount = credit_val
                            elif debit_val > 0:
                                txn_type = "DEBIT"
                                amount = debit_val
                            else:
                                if "debit" in header_map and "credit" in header_map and header_map["debit"] == header_map["credit"]:
                                    val = self.clean_amount(row_str[header_map["debit"]])
                                    if val < 0:
                                        txn_type = "DEBIT"
                                        amount = abs(val)
                                    else:
                                        txn_type = "CREDIT"
                                        amount = val
                                else:
                                    continue
                            
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
            logger.error(f"Error parsing ICICI Statement: {e}")
            raise e

        # Standardize statement period dates and balances from transactions list
        if transactions:
            try:
                transactions.sort(key=lambda t: t.date)
            except Exception:
                pass
            
            metadata.start_date = transactions[0].date
            metadata.end_date = transactions[-1].date
            
            if transactions[0].balance is not None:
                first_amount = transactions[0].amount
                first_type = transactions[0].type
                first_bal = transactions[0].balance
                metadata.opening_balance = round(first_bal - first_amount if first_type == "CREDIT" else first_bal + first_amount, 2)
            
            if transactions[-1].balance is not None:
                metadata.closing_balance = transactions[-1].balance
        
        return ParsedStatement(metadata=metadata, transactions=transactions)

    def _extract_metadata(self, text: str, metadata: StatementMetadata):
        """Extract ICICI account details from text."""
        # Account Holder
        name_match = re.search(r"Account Name\s*:\s*(.*)", text, re.IGNORECASE)
        if name_match:
            metadata.account_holder = name_match.group(1).split("\n")[0].strip()
        else:
            name_match_alt = re.search(r"Name\s*:\s*(.*)", text, re.IGNORECASE)
            if name_match_alt:
                metadata.account_holder = name_match_alt.group(1).split("\n")[0].strip()
            
        # Account Number
        acc_match = re.search(r"Account No\s*.\s*:\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        if acc_match:
            metadata.account_number = acc_match.group(1).strip()
        else:
            acc_match_alt = re.search(r"A/c No\s*:\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
            if acc_match_alt:
                metadata.account_number = acc_match_alt.group(1).strip()
