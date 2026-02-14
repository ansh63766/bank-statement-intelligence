import json
import logging
from typing import List, Dict, Any
from src.utils.llm_client import LLMClient

logger = logging.getLogger("bank_statement_intel.llm_categorizer")

class LLMCategorizer:
    """
    Categorizes batches of transactions using the LLM.
    """
    def __init__(self):
        self.llm_client = LLMClient()

    async def categorize_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Classifies a batch of transactions.
        Each item in the batch should have: {'id': int, 'description': str, 'type': str, 'amount': float}
        
        Returns:
            List[Dict[str, Any]]: List of results containing {'id': int, 'category': str, 'merchant': str | None}
        """
        if not batch:
            return []

        logger.info(f"Categorizing batch of {len(batch)} transactions via LLM...")

        system_prompt = (
            "You are a transaction categorization engine for Indian bank statements.\n"
            "Given a list of transactions (description, type, amount), categorize each transaction into one of these exact categories:\n"
            "- Salary (Credits from employer, salary, wages)\n"
            "- Rent (Home/office rental payments)\n"
            "- EMI (Monthly loan repayments, credit card bill payments)\n"
            "- Food (Restaurants, Zomato, Swiggy, cafes, bars, grocery delivery)\n"
            "- Shopping (Amazon, Flipkart, supermarkets, clothing, electronics, fuel/gas, cab rides like Uber/Ola)\n"
            "- Utilities (Electricity, water, gas, phone recharge, DTH, internet)\n"
            "- Cash Withdrawal (ATM withdrawals, self cash checks)\n"
            "- Investment (Mutual funds, stocks, SIPs, Zerodha, PPF, gold)\n"
            "- UPI Transfer (Generic peer-to-peer transfers, money sent to friends/family)\n"
            "- Others (Any transaction that does not fit the above categories)\n\n"
            "Also, extract the merchant name if identifiable (e.g. Swiggy, Zomato, Uber, Amazon, Jio, Airtel, Zerodha, HDFC Card, etc.), otherwise set to null.\n"
            "Output ONLY a JSON array of objects, where each object contains 'id', 'category', and 'merchant'."
        )

        user_prompt = f"Please categorize the following transactions:\n\n{json.dumps(batch)}"

        try:
            response = await self.llm_client.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True
            )
            
            # Clean and parse JSON
            cleaned = response.strip()
            # Remove code block formatting
            match = re_match = json_match = None
            if cleaned.startswith("```"):
                cleaned = cleaned.replace("```json", "").replace("```", "").strip()
            
            results = json.loads(cleaned)
            if not isinstance(results, list):
                logger.error(f"Expected JSON array from LLM but got: {results}")
                return []
                
            return results
        except Exception as e:
            logger.error(f"Error during LLM batch categorization: {e}")
            # Return empty list on failure; the engine will fall back to rule-based defaults
            return []
