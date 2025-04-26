# PLANNING.md

## 🧭 Project Purpose

**Taraiqi** is a system designed to monitor Arabic Telegram groups and receive user reports via a Telegram bot,  
process these reports with NLP to extract structured information (location, event type, time), verify and  
group reports to reduce noise, and finally deliver updates via the bot interface. The system aims to improve  
road condition visibility for drivers and logistics teams across Palestine.

---

## 🎯 Goals

- Automate the extraction of road-related updates from Arabic Telegram groups.
- Normalize and analyze messages using NLP techniques tailored for Arabic.
- Identify relevant road events (accidents, traffic, blockades, etc.) using entity recognition and classification.
- Remove duplicate or unreliable entries through validation.
- Store verified reports in a centralized database.
- Allow users to interact with the system via a WhatsApp bot.
- Maintain scalability, modularity, and test coverage across the system.

---

## 🏗️ Project Phases and Architecture

### Stage 1a: Telegram Group Scraping
- **Goal:** Collect raw messages from public Telegram groups.  
- **Tool:** Telethon  
- **Input:** Telegram API credentials, group IDs  
- **Output:** Raw group messages in PostgreSQL  
- **Next:** Stage 2 - Preprocessing

### Stage 1b: User-Submitted Reports via Telegram Bot
- **Goal:** Accept road condition updates directly from users through the Telegram bot.  
- **Tools:** FastAPI, Telegram Bot API  
- **Input:** User-submitted text reports  
- **Output:** Raw user reports in PostgreSQL  
- **Next:** Stage 2 - Preprocessing

### Stage 2: Text Preprocessing
- **Goal:** Normalize and clean Arabic text.  
- **Tool:** Hamza  
- **Input:** Raw messages (from groups and users)  
- **Output:** Cleaned/tokenized text  
- **Next:** Stage 3 - Entity Extraction

### Stage 3: Entity Extraction & Classification
- **Goal:** Extract location, time, type; classify relevance.  
- **Tools:** CAMeL Tools, optional rule-based classifier  
- **Input:** Cleaned text  
- **Output:** Structured JSON data  
- **Next:** Stage 4 - Validation

### Stage 4: Validation & Deduplication
- **Goal:** Group, verify, and deduplicate reports.  
- **Tools:** TF-IDF + Cosine similarity  
- **Input:** Structured JSON  
- **Output:** Verified incident data  
- **Next:** Stage 5 - Storage

### Stage 5: Storage Layer
- **Goal:** Store verified reports.  
- **Tools:** PostgreSQL, SQLAlchemy  
- **Input:** Grouped data  
- **Output:** Structured reports table

```sql
CREATE TABLE reports (
  id UUID PRIMARY KEY,
  source TEXT,
  location TEXT,
  event_type TEXT,
  time TEXT,
  verified BOOLEAN,
  raw_text TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```
---
### 🚀 Stage 6: Telegram Bot Interface
- **Goal:** Respond to user queries and accept new submissions.

**Tools:**  
- Telegram Bot API  
- FastAPI

**Input:**  
- User query OR submission + stored reports

**Output:**  
- Information message OR acknowledgment

---

## 🚢 Stage 7: Deployment & Orchestration

**Goal:**  
Deploy and run the system.

**Tools:**  
- Docker  
- GitHub Actions  
- Railway

**Input:**  
- Source code

**Output:**  
- Deployed stack

---

## 🗂️ Summary Table

| Stage | Purpose           | Tool(s)                    | Output                     |
|-------|-------------------|----------------------------|----------------------------|
| 1a    | Group Scraping    | Telethon                   | Raw messages               |
| 1b    | User Input        | Telegram Bot API, FastAPI  | Raw user reports           |
| 2     | Preprocessing     | Hamza                      | Normalized text            |
| 3     | Extraction        | CAMeL, regex               | JSON with entities         |
| 4     | Deduplication     | TF-IDF                     | Verified alerts            |
| 5     | Storage           | PostgreSQL                 | Report records             |
| 6     | Bot Interface     | FastAPI, Telegram Bot API  | Response or submission log |
| 7     | Deployment        | Docker, Railway            | Running system             |

---

## 🧱 Architecture Summary

```text
AWS EventBridge (every 5 mins)
    ↓
Telegram Scraper (Lambda)
    ↓
Text Preprocessor (Hamza)
    ↓
Entity Extractor (CAMeL Tools)
    ↓
Deduplicator & Validator (TF-IDF)
    ↓
PostgreSQL Storage
    ↓
FastAPI + Twilio WhatsApp Bot

## 🧰 Tech Stack

| Component           | Tool/Service                    | Justification                                  |
|---------------------|---------------------------------|------------------------------------------------|
| Telegram Scraping   | AWS Lambda + Telethon           | Serverless, async-friendly, cloud scalable     |
| Scheduling          | AWS EventBridge                 | Native Lambda scheduling                       |
| Preprocessing       | Hamza                           | Efficient Arabic text normalization/tokenizer  |
| Entity Extraction   | CAMeL Tools, regex              | High-quality NER models for Arabic             |
| Deduplication       | TF-IDF + Cosine Sim             | Lightweight and explainable clustering         |
| API Layer           | FastAPI                         | Async API with Pydantic validation             |
| Messaging Interface | Telegram Bot API                | Free and robust alternative to Twilio          |
| Database            | PostgreSQL + SQLAlchemy         | Reliable relational storage + ORM abstraction  |
| Deployment          | Docker, Railway, GitHub Actions | CI/CD and container portability                |

---

## ⚙️ Constraints & Rules

- Python 3.11+
- All internal data flow must use JSON-compatible structures
- No large ML models deployed in real-time pipelines
- All external credentials managed via `.env` files or GitHub Actions secrets
- Use `Pydantic` for data validation
- Include Google-style docstrings for all public functions
- Code should be readable and maintainable by mid-level developers
