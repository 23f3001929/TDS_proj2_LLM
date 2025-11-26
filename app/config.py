import os
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("EMAIL", "")
SECRET = os.getenv("SECRET", "")
MAX_QUIZ_SECONDS = int(os.getenv("MAX_QUIZ_SECONDS", "180"))  # 3 minutes default
