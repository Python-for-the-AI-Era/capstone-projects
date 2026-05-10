import pandas as pd
import random
from faker import Faker

# Initialize Faker for realistic legal case names
fake = Faker()

# Sample legal case templates and topics
legal_topics = [
    "land ownership dispute", "contract breach", "employment termination", 
    "intellectual property infringement", "corporate governance", "tax evasion",
    "environmental regulation", "consumer protection", "bankruptcy proceedings",
    "family law dispute", "criminal defense", "civil rights violation",
    "medical malpractice", "insurance claim dispute", "real estate transaction"
]

case_templates = [
    "Case concerning {topic} between plaintiff and defendant involving {details}",
    "Legal proceeding on {topic} with focus on {details} and precedent implications",
    "Judicial review of {topic} case highlighting {details} and legal interpretation",
    "Appeal in {topic} matter addressing {details} and statutory compliance",
    "Litigation involving {topic} where {details} are central to the outcome"
]

details_templates = [
    "contractual obligations and breach of terms",
    "property rights and title disputes", 
    "employment law and worker protections",
    "intellectual property and copyright issues",
    "regulatory compliance and statutory interpretation",
    "due process and constitutional rights",
    "negligence and duty of care",
    "fiduciary responsibilities and corporate governance"
]

def generate_legal_case_summary():
    """Generate a realistic legal case summary"""
    topic = random.choice(legal_topics)
    details = random.choice(details_templates)
    template = random.choice(case_templates)
    
    summary = template.format(topic=topic, details=details)
    
    # Add some legal complexity
    legal_terms = ["precedent", "jurisdiction", "statutory", "regulatory", "constitutional", 
                   "procedural", "substantive", "equitable", "remedial", "injunctive"]
    
    if random.random() > 0.7:
        summary += f" Key legal principles include {random.choice(legal_terms)} considerations."
    
    return summary

def generate_sample_data(num_cases=100000):
    """Generate sample legal case data"""
    print(f"Generating {num_cases:,} legal case summaries...")
    
    data = []
    for i in range(num_cases):
        case_id = f"CASE_{i:06d}"
        title = f"{fake.company()} v. {fake.company()} - {random.choice(legal_topics).title()}"
        summary = generate_legal_case_summary()
        
        data.append({
            'case_id': case_id,
            'title': title,
            'summary': summary
        })
        
        if (i + 1) % 10000 == 0:
            print(f"Generated {i + 1:,} cases...")
    
    # Create DataFrame and save
    df = pd.DataFrame(data)
    
    # Save main data file
    df.to_csv('legal_cases.csv', index=False)
    print(f"Saved {num_cases:,} cases to legal_cases.csv")
    
    # Save metadata file (for search API)
    metadata = df[['case_id', 'title']].copy()
    metadata.to_csv('metadata.csv', index=False)
    print(f"Saved metadata to metadata.csv")
    
    return df

if __name__ == "__main__":
    # Generate 100,000 sample legal cases
    df = generate_sample_data(100000)
    
    print("\nSample data generation complete!")
    print(f"Total cases: {len(df):,}")
    print(f"Average summary length: {df['summary'].str.len().mean():.1f} characters")
    print("\nFirst 5 cases:")
    print(df.head())
