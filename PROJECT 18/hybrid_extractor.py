import spacy
import re
from langchain.llms import OpenAI
from langchain.chains import create_extraction_chain

nlp = spacy.load("en_core_web_lg")

def extract_metadata(text: str):
    # 1. Regex for Dates
    dates = re.findall(r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}', text)
    
    # 2. spaCy for Parties
    doc = nlp(text[:2000]) # Scan the first 2000 chars for speed
    orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
    
    return {"dates": dates, "parties": orgs}

# TASK: Implement the LangChain extraction for the 'termination_clause'