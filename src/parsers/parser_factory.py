import logging
from src.parsers.base import BaseParser
from src.parsers.pdf_detector import detect_pdf_type_and_bank
from src.parsers.sbi_parser import SBIParser
from src.parsers.hdfc_parser import HDFCParser
from src.parsers.icici_parser import ICICIParser
from src.parsers.axis_parser import AxisParser
from src.parsers.llm_parser import LLMParser
from src.models.statements import ParsedStatement

logger = logging.getLogger("bank_statement_intel.factory")

async def parse_statement(pdf_path: str) -> ParsedStatement:
    """
    Main entry point for statement parsing. Automatically detects format,
    applies the correct parsing rules, and handles self-healing fallback.
    
    Args:
        pdf_path (str): Absolute path to the PDF statement.
        
    Returns:
        ParsedStatement: The standardized transaction list and bank metadata.
    """
    # 1. Detect PDF type and Bank
    pdf_type, bank_name = detect_pdf_type_and_bank(pdf_path)
    
    # 2. Select appropriate parser
    if pdf_type == "SCANNED":
        logger.info("Scanned PDF detected. Dispatching to LLM Vision parser.")
        parser = LLMParser(mode="SCANNED")
        return await parser.parse(pdf_path)
        
    # Text-based statements
    if bank_name == "SBI":
        parser = SBIParser()
    elif bank_name == "HDFC":
        parser = HDFCParser()
    elif bank_name == "ICICI":
        parser = ICICIParser()
    elif bank_name == "Axis":
        parser = AxisParser()
    else:
        logger.info(f"Digital PDF from unknown bank '{bank_name}' detected. Dispatching to LLM Text parser.")
        parser = LLMParser(mode="TEXT")
        return await parser.parse(pdf_path)
        
    # 3. Parse with rule-based parser, falling back to LLM Text parser on failure (self-healing)
    try:
        logger.info(f"Attempting rule-based parsing using {parser.__class__.__name__} for bank {bank_name}...")
        return await parser.parse(pdf_path)
    except Exception as e:
        logger.warning(
            f"Rule-based parsing failed for {bank_name} statement: {e}. "
            f"Falling back to LLM-based text extraction for self-healing..."
        )
        fallback_parser = LLMParser(mode="TEXT")
        try:
            return await fallback_parser.parse(pdf_path)
        except Exception as fallback_err:
            logger.critical(f"Both rule-based and LLM fallback parsing failed: {fallback_err}")
            raise fallback_err
