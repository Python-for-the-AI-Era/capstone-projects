from langchain.memory import ConversationSummaryBufferMemory
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4")

# TASK: Set a hard limit on memory
# This keeps the 'window' manageable while preserving long-term context
memory = ConversationSummaryBufferMemory(
    llm=llm, 
    max_token_limit=2000,
    return_messages=True
)