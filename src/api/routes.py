import os
import uuid
import logging
import shutil
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse

from src.parsers.parser_factory import parse_statement
from src.categorizer.engine import categorize_statement_transactions
from src.signals.engine import compute_financial_signals
from src.underwriting.score import evaluate_creditworthiness
from src.models.underwriting import UnderwritingEvaluation

logger = logging.getLogger("bank_statement_intel.api_routes")

router = APIRouter(prefix="/api/v1")

# Create local temp directory within workspace if it doesn't exist
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp")
os.makedirs(TEMP_DIR, exist_ok=True)

@router.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """
    Health check endpoint to verify system status.
    """
    return {"status": "healthy", "service": "Bank Statement Intelligence"}

@router.post(
    "/analyze",
    response_model=UnderwritingEvaluation,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid file format or bad request"},
        500: {"description": "Internal server or processing error"}
    }
)
async def analyze_statement(file: UploadFile = File(...)) -> Any:
    """
    Uploads a bank statement PDF and extracts structured transactions,
    financial signals, and underwriting evaluation.
    """
    # 1. Validate file extension
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a PDF statement."
        )

    # 2. Save file temporarily in local workspace
    temp_file_name = f"{uuid.uuid4()}_{file.filename}"
    temp_file_path = os.path.join(TEMP_DIR, temp_file_name)

    try:
        logger.info(f"Received statement upload: '{file.filename}'. Saving temporarily to {temp_file_path}...")
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. Step 1: Parse the PDF statement (Text or Scanned)
        parsed_stmt = await parse_statement(temp_file_path)
        if not parsed_stmt.transactions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract any transactions from the uploaded PDF. Ensure it is a valid bank statement."
            )

        # 4. Step 2: Categorize transactions
        parsed_stmt.transactions = await categorize_statement_transactions(parsed_stmt.transactions)

        # 5. Step 3: Compute financial signals
        income, spending, debt, balance, negative = compute_financial_signals(parsed_stmt)

        # 6. Step 4: Perform Underwriting Evaluation
        evaluation = evaluate_creditworthiness(income, spending, debt, balance, negative)
        
        logger.info("Statement analysis completed successfully.")
        return evaluation

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing statement: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the bank statement: {str(e)}"
        )
    finally:
        # Clean up temporary file to release resources
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as clean_err:
                logger.warning(f"Failed to delete temporary file {temp_file_path}: {clean_err}")
