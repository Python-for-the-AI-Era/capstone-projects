import logging
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.pydantic_v1 import BaseModel, Field
from scraper import CompetitorScraper
from config import settings

logger = logging.getLogger(__name__)


class CompetitiveInsights(BaseModel):
    """Structured output for competitive intelligence insights"""
    product_updates: List[str] = Field(description="New product features or updates")
    pricing_changes: List[str] = Field(description="Pricing changes or new pricing tiers")
    strategic_shifts: List[str] = Field(description="Strategic moves, partnerships, or significant changes")
    summary: str = Field(description="Brief summary of key findings")
    confidence_score: float = Field(description="Confidence in the analysis (0-1)")


class IntelligenceEngine:
    """Handles LLM-based competitive intelligence extraction"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            openai_api_key=settings.openai_api_key
        )
        self.scraper = CompetitorScraper()
        self.output_parser = PydanticOutputParser(pydantic_object=CompetitiveInsights)
        
        self.prompt_template = PromptTemplate(
            template="""You are a competitive intelligence analyst. Analyze the following competitor webpage content and extract key business insights.

Focus on identifying:
1. Product Feature Updates - New features, product launches, improvements, or deprecations
2. Pricing Changes - New pricing tiers, price changes, discounts, or billing model updates  
3. Strategic Shifts - Hiring trends, partnerships, market positioning changes, company direction shifts

Content to analyze:
{content}

{format_instructions}

Provide specific, actionable insights based on the content. If no relevant information is found for a category, return an empty list for that field.""",
            input_variables=["content"],
            partial_variables={"format_instructions": self.output_parser.get_format_instructions()}
        )
        
        self.chain = self.prompt_template | self.llm | self.output_parser
    
    def extract_insights(self, content: str, url: str = "") -> Optional[CompetitiveInsights]:
        """Extract structured insights from webpage content"""
        try:
            # Extract clean text content
            scraper = CompetitorScraper()
            clean_content = scraper.extract_text_content(content)
            
            if not clean_content or len(clean_content.strip()) < 100:
                logger.warning(f"Insufficient content for analysis: {url}")
                return None
            
            # Limit content to avoid token limits
            limited_content = clean_content[:8000]
            
            # Extract insights using LLM
            insights = self.chain.invoke({"content": limited_content})
            
            logger.info(f"Successfully extracted insights from: {url}")
            return insights
            
        except Exception as e:
            logger.error(f"Error extracting insights from {url}: {e}")
            return None
    
    def extract_insights_from_url(self, url: str) -> Optional[CompetitiveInsights]:
        """Convenience method to scrape and extract insights from a URL"""
        try:
            # Scrape the page
            page_data = self.scraper.get_page_content(url)
            if not page_data or not page_data.get('content'):
                logger.error(f"Failed to get content from {url}")
                return None
            
            # Extract insights
            insights = self.extract_insights(page_data['content'], url)
            
            # Add URL metadata
            if insights:
                insights.url = url
                insights.page_title = page_data.get('title', '')
                insights.scraped_at = page_data.get('scraped_at', '')
            
            return insights
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            return None
    
    def batch_extract_insights(self, urls: List[str]) -> List[CompetitiveInsights]:
        """Extract insights from multiple URLs"""
        results = []
        
        for url in urls:
            try:
                insights = self.extract_insights_from_url(url)
                if insights:
                    results.append(insights)
            except Exception as e:
                logger.error(f"Failed to process {url}: {e}")
                continue
        
        return results
    
    def get_insights_summary(self, insights_list: List[CompetitiveInsights]) -> Dict:
        """Generate a summary of insights across multiple competitors"""
        if not insights_list:
            return {"message": "No insights available"}
        
        summary = {
            "total_insights": len(insights_list),
            "product_updates": [],
            "pricing_changes": [],
            "strategic_shifts": [],
            "high_confidence_insights": []
        }
        
        for insights in insights_list:
            if hasattr(insights, 'product_updates'):
                summary["product_updates"].extend(insights.product_updates)
            if hasattr(insights, 'pricing_changes'):
                summary["pricing_changes"].extend(insights.pricing_changes)
            if hasattr(insights, 'strategic_shifts'):
                summary["strategic_shifts"].extend(insights.strategic_shifts)
            
            if hasattr(insights, 'confidence_score') and insights.confidence_score > 0.8:
                summary["high_confidence_insights"].append(insights.summary)
        
        return summary


# Backward compatibility function
def extract_insights(html_content: str, url: str = "") -> Optional[CompetitiveInsights]:
    """Legacy function for backward compatibility"""
    engine = IntelligenceEngine()
    return engine.extract_insights(html_content, url)