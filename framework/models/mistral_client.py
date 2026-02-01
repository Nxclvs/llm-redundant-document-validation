from mistralai import Mistral
from config.localconfig import config

def get_mistral_client() -> Mistral:
    """
    Delivers configured MistralAI client
    ---------------------------------
    Input: None
    Output: Mistral
    """
    api_key = config.get("mistral")
    if not api_key:
        raise ValueError("No MistralAI ke set in config")
    return Mistral(api_key=api_key, timeout_ms=120000)