import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("8862547712:AAHSNSb73Y06qvKoU9x7BI3BvCLxo1bJ3S0", "")
ADMIN_ID: int = int(os.getenv("576948888", "0"))

if not BOT_TOKEN:
    raise ValueError("8862547712:AAHSNSb73Y06qvKoU9x7BI3BvCLxo1bJ3S0")
