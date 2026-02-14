import logging
from typing import List, Dict, Any
from src.models.statements import Transaction
from src.categorizer.rules import categorize_by_rules
from src.categorizer.llm import LLMCategorizer

logger = logging.getLogger("bank_statement_intel.categorizer_engine")

async def categorize_statement_transactions(transactions: List[Transaction]) -> List[Transaction]:
    """
    Categorizes all transactions in a statement using a hybrid rule + LLM approach.
    Runs rule-based classification first, then batches unconfident items for LLM processing.
    
    Args:
        transactions (List[Transaction]): List of transactions to categorize.
        
    Returns:
        List[Transaction]: The categorized transactions.
    """
    if not transactions:
        return []

    logger.info(f"Starting categorization for {len(transactions)} transactions...")
    
    # 1. First Pass: Apply rules
    unconfident_items = []
    
    for idx, txn in enumerate(transactions):
        category, merchant, is_confident = categorize_by_rules(
            txn.description, txn.type, txn.amount
        )
        
        # Pre-populate rule results
        txn.category = category
        if merchant:
            txn.merchant = merchant
            
        if not is_confident:
            unconfident_items.append({
                "index": idx,
                "id": idx,
                "description": txn.description,
                "type": txn.type,
                "amount": txn.amount
            })
            
    logger.info(
        f"Rule-based pass complete. Confident: {len(transactions) - len(unconfident_items)}, "
        f"Unconfident (queued for LLM): {len(unconfident_items)}"
    )

    # 2. Second Pass: Batch process unconfident transactions with LLM (if any)
    if unconfident_items:
        llm_categorizer = LLMCategorizer()
        
        # Batch size of 40 is optimal for prompt size and categorization quality
        batch_size = 40
        batches = [unconfident_items[i:i + batch_size] for i in range(0, len(unconfident_items), batch_size)]
        
        for batch in batches:
            # We strip internal indices to prevent LLM confusion, sending only necessary payload
            llm_payload = [
                {
                    "id": item["id"],
                    "description": item["description"],
                    "type": item["type"],
                    "amount": item["amount"]
                }
                for item in batch
            ]
            
            llm_results = await llm_categorizer.categorize_batch(llm_payload)
            
            # Map results back to transactions
            results_map = {res["id"]: res for res in llm_results if "id" in res}
            
            for item in batch:
                txn_idx = item["index"]
                item_id = item["id"]
                
                if item_id in results_map:
                    res = results_map[item_id]
                    # Update with LLM results if valid category returned
                    llm_cat = res.get("category")
                    llm_merch = res.get("merchant")
                    
                    if llm_cat and llm_cat.lower() != "unknown":
                        # Standardize LLM category capitalization
                        transactions[txn_idx].category = llm_cat.title()
                    if llm_merch:
                        transactions[txn_idx].merchant = llm_merch.title()
                        
    # Ensure all category names are normalized to standard categories list
    valid_categories = {
        "Salary", "Rent", "EMI", "Food", "Shopping", 
        "Utilities", "Cash Withdrawal", "Investment", "UPI Transfer", "Others"
    }
    
    for txn in transactions:
        # Standardize category spelling and map outliers to "Others"
        cat_title = txn.category.title().strip()
        if cat_title in valid_categories:
            txn.category = cat_title
        elif "Upi" in cat_title or "Transfer" in cat_title:
            txn.category = "UPI Transfer"
        elif "Emi" in cat_title or "Loan" in cat_title or "Credit Card" in cat_title:
            txn.category = "EMI"
        else:
            txn.category = "Others"

    logger.info("Transaction categorization pipeline complete.")
    return transactions
