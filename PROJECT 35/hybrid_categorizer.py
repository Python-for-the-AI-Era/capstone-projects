from langchain_openai import ChatOpenAI

def categorise_transaction(description, amount):
    # Tier 1: Rules
    rules = {"Uber": "Transport", "Supermarket": "Groceries"}
    for key, cat in rules.items():
        if key.lower() in description.lower():
            return cat
            
    # Tier 2: LLM (GPT-4o-mini)
    llm = ChatOpenAI(model="gpt-4o-mini")
    prompt = f"Categorise this transaction description: '{description}'. Return only the category name."
    return llm.invoke(prompt).content