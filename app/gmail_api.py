import imaplib
import email
import requests

# 🔐 Your Gmail credentials
EMAIL = "pandeyrahuler@gmail.com"
PASSWORD = "ocfxjoqnhggfhnwl"

# 🔗 Your API URL
API_URL = "http://127.0.0.1:5000/api/predict"

# Connect to Gmail
mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(EMAIL, PASSWORD)

mail.select("inbox")

# Get emails
status, messages = mail.search(None, "ALL")
mail_ids = messages[0].split()

print("\nChecking last 5 emails...\n")

for i in mail_ids[-5:]:
    status, msg_data = mail.fetch(i, "(RFC822)")

    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])

            subject = msg["subject"]

            # Send to API
            response = requests.post(API_URL, json={"message": subject})

            result = response.json()

            print("📧 Email:", subject)
            print("🔍 Prediction:", result["prediction"])
            print("📊 Confidence:", result["confidence"])
            print("-" * 50)