import os
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("LLM_MODEL", "gpt-4o")
        self.client = OpenAI(api_key=self.api_key)

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    def completion(self, prompt: str, system_prompt: str = "You are a helpful assistant.", json_mode: bool = False) -> str:
        """
        Generate a completion using the configured LLM.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        response_format = {"type": "json_object"} if json_mode else None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling LLM: {e}")
            raise

    def get_structured_completion(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """
        Get a JSON-parsed response from the LLM.
        """
        content = self.completion(prompt, system_prompt, json_mode=True)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
                return json.loads(content)
            raise ValueError(f"Failed to parse JSON from LLM response: {content}")
