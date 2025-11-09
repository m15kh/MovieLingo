import ollama
import json
import re
from typing import Dict, Optional
from app.core.config import settings
from loguru import logger


class OllamaService:
    """Service for AI-powered question generation using Ollama"""
    
    def __init__(self):
        self.client = ollama.Client(host=settings.OLLAMA_API_URL)
        self.model = settings.OLLAMA_MODEL
        self._verify_connection()
    
    def _verify_connection(self):
        """Verify connection to Ollama"""
        try:
            self.client.list()
            logger.success(f"Connected to Ollama at {settings.OLLAMA_API_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            logger.warning("Make sure Ollama is running with: ollama serve")
    
    async def generate_question(
        self, 
        phrase: str, 
        context: str = None
    ) -> Optional[Dict]:
        """
        Generate a multiple choice question about a phrase
        
        Args:
            phrase: The English phrase to create a question about
            context: Optional context (movie name, scene description)
            
        Returns:
            Dictionary with question, options, correct answer, and example
        """
        prompt = self._create_question_prompt(phrase, context)
        
        try:
            logger.info(f"Generating question for phrase: {phrase}")
            
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an English teacher creating multiple choice questions. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            content = response['message']['content']
            question_data = self._parse_response(content)
            
            if question_data:
                logger.success(f"Question generated successfully")
                return question_data
            else:
                logger.error("Failed to parse question data")
                return None
                
        except Exception as e:
            logger.error(f"Error generating question: {e}")
            return None
    
    def _create_question_prompt(self, phrase: str, context: str = None) -> str:
        """Create prompt for question generation"""
        context_info = f"\nContext: {context}" if context else ""
        
        prompt = f"""Create a multiple choice question to test understanding of this English phrase:

Phrase: "{phrase}"{context_info}

Generate a JSON response with this EXACT structure (no other text):
{{
    "question": "What does '{phrase}' mean?",
    "options": {{
        "A": "First option",
        "B": "Second option",
        "C": "Third option (correct)",
        "D": "Fourth option"
    }},
    "correct": "C",
    "example": "An example sentence using the phrase naturally"
}}

Requirements:
- Make one option clearly correct
- Make other options plausible but wrong
- Keep options concise (under 15 words each)
- Provide a natural example sentence
- Return ONLY valid JSON, no additional text
"""
        return prompt
    
    def _parse_response(self, response: str) -> Optional[Dict]:
        """Parse LLM response to extract question data"""
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                
                # Validate structure
                required_keys = ["question", "options", "correct", "example"]
                if all(key in data for key in required_keys):
                    if all(opt in data["options"] for opt in ["A", "B", "C", "D"]):
                        return data
            
            logger.error("Invalid question structure in response")
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None
    
    async def generate_fallback_question(self, phrase: str) -> Dict:
        """
        Generate a simple fallback question if AI fails
        
        Args:
            phrase: The phrase to create a question about
            
        Returns:
            Basic question dictionary
        """
        return {
            "question": f"What does '{phrase}' mean?",
            "options": {
                "A": "This is a common English expression",
                "B": "This is a greeting",
                "C": "This is a question",
                "D": "This is an exclamation"
            },
            "correct": "A",
            "example": f"Example: {phrase}"
        }
    
    async def validate_phrase(self, phrase: str) -> bool:
        """
        Validate if phrase is appropriate for learning
        
        Args:
            phrase: Phrase to validate
            
        Returns:
            True if phrase is appropriate
        """
        try:
            prompt = f"""Is this an appropriate English phrase for language learning?
Phrase: "{phrase}"

Respond with ONLY "YES" or "NO" and a brief reason."""

            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response['message']['content'].upper()
            return "YES" in content
            
        except Exception as e:
            logger.error(f"Error validating phrase: {e}")
            return True  # Default to allowing phrase


# Global instance
ollama_service = OllamaService()
