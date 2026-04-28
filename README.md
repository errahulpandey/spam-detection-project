# 📧 Spam Shield - Email Spam Detection System

A full-stack machine learning web application that detects spam emails using NLP and provides a modern dashboard with Gmail integration.

---

## 🚀 Features

### 🔍 Core ML Features
- Spam detection using trained ML model
- Confidence score for each prediction
- Bulk message scanning
- Text file (.txt) upload scanning

### 📊 Dashboard & Analytics
- Total emails, spam, and non-spam stats
- Interactive charts (Chart.js)
- Top spam keywords detection

### 📂 History Management
- Search messages
- Filter (Spam / Not Spam)
- Sort (Latest / Oldest)
- Delete individual records
- Clear all history
- Export history as CSV

### 📧 Gmail Integration
- Fetch latest Gmail emails
- Auto-refresh inbox (every 20 seconds)
- Spam classification of Gmail subjects
- Save Gmail emails to database

### 🔐 Authentication
- Simple login system
- Session-based access control

### 🎨 UI/UX
- Modern glassmorphism UI
- Dark / Light theme toggle
- Responsive design

---

## 🗂 Project Structure
spam-detection/
│
├── model/
│ ├── model.pkl
│ └── vectorizer.pkl
│
├── app/
│ ├── app.py
│ ├── database.db
│ └── templates/
│ ├── base.html
│ ├── login.html
│ ├── index.html
│ ├── dashboard.html
│ ├── history.html
│ ├── gmail.html
│ └── profile.html
│
├── requirements.txt
└── README.md


---

## ⚙️ Installation

### 1. Clone or download project
```bash
git clone <your-repo-url>
cd spam-detection


2. Install dependencies
pip install -r requirements.txt


▶️ Run the project
cd app
python app.py

Open browser:
http://127.0.0.1:5000


🔐 Login Credentials
Username: admin
Password: 1234

👨‍💻 Author
Rahul Kumar


⭐ If you like this project
Give it a ⭐ on GitHub and use it in your portfolio 🚀