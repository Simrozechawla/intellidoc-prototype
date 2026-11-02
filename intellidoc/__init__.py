"""IntelliDoc: an agentic document-processing pipeline built on LangGraph."""

__version__ = "0.1.0"

try:  # read TYPESAFE_API_KEY etc. from a local .env file if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
