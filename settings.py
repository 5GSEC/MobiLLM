from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # local_model: str | None = "mistralai/Mixtral-8x7B-Instruct-v0.1"
    local_model: str | None = None
    google_api_key: str | None = "AIzaSyD5W_UAx2QRabottm6yh64vtDlLowUqVW4"
    gemini_model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    top_p: float = 0.9
    repetition_penalty: float = 1.15
    max_new_tokens: int = 384
    use_hf: bool = False
    fourbit: bool = True
    atebit: bool = False

    class Config:
        env_prefix = "MOBILLM_"


    # # Pydantic v2 style:
    # model_config = SettingsConfigDict(
    #     env_prefix="MOBILLM_",   # prefix for env vars
    #     env_file=".env",         # optional: load from .env
    #     env_file_encoding="utf-8"
    # )