from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from support.settings import groq_api_key_value


def load_openAI_model():
    MODEL = ChatOpenAI(
        model="gpt-4.1",
        temperature=0,
        top_p=0,
        max_tokens=None,
        timeout=None,
        max_retries=1,
        seed=42,
    )

    return MODEL


def load_gemini_model():
    MODEL = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_retries=1,
        api_key=groq_api_key_value,
    )

    return MODEL
