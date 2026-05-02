from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

def extract_insights(html_content):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    template = """
    Analyze the following competitor webpage content. 
    Identify and summarize in 3 bullet points:
    1. Product Feature updates
    2. Pricing or Plan changes
    3. Key Hiring/Strategic shifts
    
    Content: {content}
    """
    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm
    return chain.invoke({"content": html_content[:8000]}).content # Truncate for tokens