import re
import json
import logging
from typing import List, Dict, Any, Literal
import pdfplumber
from src.parsers.base import BaseParser
from src.models.statements import ParsedStatement, StatementMetadata, Transaction
from src.utils.llm_client import LLMClient
from src.utils.pdf import get_pdf_page_count, pdf_page_to_image_bytes

logger = logging.getLogger("bank_statement_intel.llm_parser")

class LLMParser(BaseParser):
    """
    Fallback parser using OpenRouter or other LLM providers.
    Supports text extraction for arbitrary banks and image/vision extraction for scanned PDFs.
    """
    def __init__(self, mode: Literal["TEXT", "SCANNED"]):
        self.mode = mode
        self.llm_client = LLMClient()

    async def parse(self, pdf_path: str) -> ParsedStatement:
        metadata = StatementMetadata()
        transactions: List[Transaction] = []
        
        page_count = get_pdf_page_count(pdf_path)
        logger.info(f"LLM Parser starting in {self.mode} mode for {page_count} pages.")
        
        # System prompt instructing the LLM on data structure and extraction details
        system_prompt = (
            "You are a precise financial data extraction agent.\n"
            "Your task is to analyze the bank statement page provided (as text or as an image) and extract ALL transactions and metadata.\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            "  \"metadata\": {\n"
            "    \"bank_name\": \"Name of the bank (e.g. SBI, HDFC, ICICI, AXIS, or Unknown)\",\n"
            "    \"account_holder\": \"Account holder name, or null\",\n"
            "    \"account_number\": \"Account number, or null\",\n"
            "    \"start_date\": \"YYYY-MM-DD format statement start date, or null\",\n"
            "    \"end_date\": \"YYYY-MM-DD format statement end date, or null\",\n"
            "    \"opening_balance\": float_or_null,\n"
            "    \"closing_balance\": float_or_null\n"
            "  },\n"
            "  \"transactions\": [\n"
            "    {\n"
            "      \"date\": \"YYYY-MM-DD\",\n"
            "      \"description\": \"Raw description\",\n"
            "      \"amount\": float_always_positive,\n"
            "      \"type\": \"DEBIT\" or \"CREDIT\",\n"
            "      \"balance\": float_or_null,\n"
            "      \"reference_id\": \"Ref id / Cheque no / UPI txn ref, or null\"\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Rules:\n"
            "1. Output ONLY JSON. No explanations, no markdown blocks.\n"
            "2. Convert transaction dates to YYYY-MM-DD. If year is missing, infer the statement year.\n"
            "3. Ensure 'amount' is always positive. 'type' must be 'DEBIT' for withdrawals and 'CREDIT' for deposits.\n"
            "4. Be extremely thorough: do not miss any transactions."
        )
        
        # We parse page-by-page to remain accurate and fit within context windows
        for page_num in range(page_count):
            logger.info(f"Processing page {page_num + 1}/{page_count}...")
            
            try:
                if self.mode == "TEXT":
                    # Extract digital text
                    page_text = ""
                    with pdfplumber.open(pdf_path) as pdf:
                        page_text = pdf.pages[page_num].extract_text() or ""
                    
                    if not page_text.strip():
                        logger.warning(f"No text extracted on page {page_num + 1}, skipping.")
                        continue
                        
                    user_prompt = f"Here is the text extracted from bank statement page {page_num + 1}:\n\n{page_text}"
                    response = await self.llm_client.generate_response(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        json_mode=True
                    )
                else:
                    # Scanned PDF: extract as image
                    image_bytes = pdf_page_to_image_bytes(pdf_path, page_num, dpi=150)
                    user_prompt = f"Please read the bank statement page image {page_num + 1} and extract the transactions."
                    response = await self.llm_client.generate_response(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        json_mode=True,
                        image_bytes=image_bytes,
                        mime_type="image/png"
                    )
                
                # Parse the response JSON
                page_data = self._clean_and_load_json(response)
                
                # Merge metadata (take first non-null values)
                page_meta = page_data.get("metadata", {})
                if page_meta:
                    if not metadata.bank_name or metadata.bank_name == "Unknown":
                        metadata.bank_name = page_meta.get("bank_name") or "Unknown"
                    if not metadata.account_holder:
                        metadata.account_holder = page_meta.get("account_holder")
                    if not metadata.account_number:
                        metadata.account_number = page_meta.get("account_number")
                    if not metadata.start_date:
                        metadata.start_date = page_meta.get("start_date")
                    if not metadata.end_date:
                        metadata.end_date = page_meta.get("end_date")
                    if metadata.opening_balance is None:
                        metadata.opening_balance = page_meta.get("opening_balance")
                    if page_meta.get("closing_balance") is not None:
                        metadata.closing_balance = page_meta.get("closing_balance")
                
                # Add transactions
                page_txns = page_data.get("transactions", [])
                for txn_dict in page_txns:
                    # Validate keys and types
                    try:
                        date_str = txn_dict.get("date")
                        desc_str = txn_dict.get("description") or ""
                        amount_val = float(txn_dict.get("amount") or 0)
                        type_str = txn_dict.get("type", "DEBIT").upper()
                        
                        if not date_str or not desc_str or amount_val <= 0:
                            continue
                            
                        balance_val = txn_dict.get("balance")
                        if balance_val is not None:
                            balance_val = float(balance_val)
                            
                        transactions.append(Transaction(
                            date=date_str,
                            description=desc_str,
                            amount=amount_val,
                            type=type_str,
                            balance=balance_val,
                            reference_id=txn_dict.get("reference_id")
                        ))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing single transaction from JSON: {txn_dict}. Error: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Failed to process page {page_num + 1} with LLM: {e}")
                # Continue to next page rather than crash the whole pipeline
                continue
                
        # Post-process transactions list
        if transactions:
            # Sort by date
            try:
                transactions.sort(key=lambda t: t.date)
            except Exception:
                pass
            
            # Re-estimate metadata start/end date if missing
            if not metadata.start_date:
                metadata.start_date = transactions[0].date
            if not metadata.end_date:
                metadata.end_date = transactions[-1].date
                
            if metadata.opening_balance is None and transactions[0].balance is not None:
                first_bal = transactions[0].balance
                first_amt = transactions[0].amount
                first_type = transactions[0].type
                metadata.opening_balance = round(first_bal - first_amt if first_type == "CREDIT" else first_bal + first_amt, 2)
                
            if metadata.closing_balance is None and transactions[-1].balance is not None:
                metadata.closing_balance = transactions[-1].balance
                
        return ParsedStatement(metadata=metadata, transactions=transactions)

    def _clean_and_load_json(self, text: str) -> Dict[str, Any]:
        """Cleans and loads LLM response text into JSON."""
        cleaned = text.strip()
        
        # Remove code blocks if present
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1)
            
        # Strip comments & trailing commas
        cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
        cleaned = re.sub(r"/\*[\s\S]*?\*/|//.*", "", cleaned) # Remove C-style/C++ comments
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError on text: '{text}'. Error: {e}")
            # Try a very loose extraction of transactions if structural load fails
            return {"metadata": {}, "transactions": []}
