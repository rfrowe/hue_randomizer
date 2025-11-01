"""Configuration management for The Randomizer."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Configuration settings for the Hue Randomizer."""

    # Bridge settings
    HUE_BRIDGE_HOST = os.getenv('HUE_BRIDGE_HOST')
    HUE_API_KEY = os.getenv('HUE_API_KEY')

    # API base URL (CLIP v2)
    @property
    def BASE_URL(self):
        """Construct the base API URL for CLIP v2."""
        return f"https://{self.HUE_BRIDGE_HOST}/clip/v2"

    def validate(self):
        """Validate that all required settings are present."""
        if not self.HUE_BRIDGE_HOST:
            raise ValueError("HUE_BRIDGE_HOST not set in .env file")
        if not self.HUE_API_KEY:
            raise ValueError("HUE_API_KEY not set in .env file")


# Global config instance
config = Config()
