import os

from dotenv import load_dotenv

load_dotenv()

class Config:
    """Bot Configuration"""

    PORT = 3978
    APP_ID = os.environ.get("CLIENT_ID", "")
    APP_PASSWORD = os.environ.get("CLIENT_SECRET", "")
    APP_TYPE = os.environ.get("BOT_TYPE", "")
    APP_TENANTID = os.environ.get("TENANT_ID", "")
    AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "") # Azure OpenAI API key
    AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "") # Azure OpenAI model deployment name
    AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "") # Azure OpenAI endpoint
    LANGFLOW_BASE_URL = os.environ.get("LANGFLOW_BASE_URL", "http://localhost:7860")
    LANGFLOW_FLOW_ID = os.environ.get("LANGFLOW_FLOW_ID", "269eaf37-3394-4a7a-84b0-8b8b3c362f17")
    QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "uganda_tax_law_v2")
