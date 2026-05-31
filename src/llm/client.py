import os
import json
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

T = TypeVar('T', bound=BaseModel)

class LLMClient:
    """
    Client for communicating with LLM APIs.
    Supports both OpenAI and Groq (free open-source models).
    Implements Cost-Aware Model Routing (fast tier vs. smart tier).
    """
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

        if self.groq_key:
            print("INFO: Initializing LLM Client with Groq API (Llama 3)...")
            self.client = OpenAI(
                api_key=self.groq_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.fast_model = "llama-3.1-8b-instant"
            self.smart_model = "llama-3.3-70b-versatile"
            
        elif self.openai_key:
            print("INFO: Initializing LLM Client with OpenAI API...")
            self.client = OpenAI(api_key=self.openai_key)
            self.fast_model = "gpt-4o-mini"
            self.smart_model = "gpt-4o"
            
        else:
            raise ValueError("ERROR: Neither GROQ_API_KEY nor OPENAI_API_KEY found in .env file!")

    def analyze_with_structured_output(self, system_prompt: str, user_prompt: str, response_model: Type[T], tier: str = "smart") -> T:
        """
        Sends a request to the LLM and forces the output to match the given Pydantic model.
        tier: 'fast' or 'smart'. Determines which LLM to route the request to based on complexity.
        """
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        enriched_system_prompt = f"{system_prompt}\n\nYou MUST reply strictly in valid JSON format matching this schema:\n{schema_json}"

        selected_model = self.fast_model if tier == "fast" else self.smart_model

        try:
            response = self.client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": enriched_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            raw_json_response = response.choices[0].message.content
            validated_object = response_model.model_validate_json(raw_json_response)
            
            return validated_object
            
        except ValidationError as e:
            print(f"LLM Parsing Error (Model: {selected_model}): The model did not return the expected JSON structure.\n{e}")
            raise
        except Exception as e:
            print(f"LLM API Error (Model: {selected_model}): {e}")
            raise