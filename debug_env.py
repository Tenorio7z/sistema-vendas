import os
from dotenv import load_dotenv

load_dotenv()

print("HOST:", os.getenv("DB_HOST"))
print("DB:", os.getenv("DB_NAME"))
print("USER:", os.getenv("DB_USER"))