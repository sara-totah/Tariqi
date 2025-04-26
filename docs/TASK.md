# TASK.md

## [2025-04-23] Stage 1: Telegram Group Scraping & User‑Submitted Reports

### Stage 1a: Telegram Group Scraping
- [x] Set up Telethon client with Telegram API credentials and target group IDs  
- [x] Define PostgreSQL table `raw_group_messages` (fields: `id`, `source_group`, `message_id`, `reply_to_message_id`, `text`, `raw_payload`, `timestamp`)  
- [x] Implement an AWS Lambda function using Telethon to fetch new messages from each group  
- [x] Schedule the Lambda scraper to run every 5 minutes via AWS EventBridge  
- [x] Handle reply‑to‑message scenarios:  
  - If `reply_to_message_id` is present, fetch the original message text and store both IDs  
  - Ensure the DB schema captures the relationship (`reply_to_message_id` → original message text)  
- [x] Add robust logging, retries, and error handling (network/API rate limit failures)
- [x] Write Pytest unit tests for:
  - [x] Telethon client setup (`client.py`)
  - [x] Basic scraping logic (`handler.py` - fetch & save)
  - [x] Duplicate message handling (`save_message`)
  - [x] Error handling for invalid group IDs / permissions (`fetch_and_save_messages`)
  - [x] Edge case: messages that reply to missing or deleted originals (if applicable)

### Stage 1b: User‑Submitted Reports via Telegram Bot
- [x] Create FastAPI app with a POST endpoint for incoming reports  
- [x] Configure a Telegram Bot webhook (or polling) to forward user messages to the FastAPI endpoint
  - [x] Implement polling mechanism for local development
  - [x] (Future) Set up webhook for production deployment
- [x] Define PostgreSQL table `raw_user_reports` (fields: `id`, `user_id`, `message_id`, `text`, `raw_payload`, `timestamp`)  
- [x] Validate incoming payloads with Pydantic models and insert into `raw_user_reports`  
- [x] Implement logging and error handling for invalid inputs or bot API errors
- [x] Set up Pytest configuration (fixtures, etc.)
- [x] Write Pytest unit tests for: 
  - [x] API endpoint validation (`/webhook/telegram`)
  - [x] Storing valid user reports
  - [x] Handling invalid/malformed Telegram updates
  - [x] Database interaction for `raw_user_reports`

## [2025-04-24] Stage 2: Text Preprocessing (Using camel-tools)
- [x] Integrate the `camel-tools` library (`pip install camel-tools`).
- [x] Create a preprocessing service/module (e.g., `app/services/nlp/preprocessing.py`).
- [x] Implement a function within the service to perform text normalization using `camel-tools` utilities:
  - [x] Remove diacritics (e.g., `camel_tools.utils.dediac.dediac_ar`).
  - [x] Normalize Alef (e.g., `camel_tools.utils.normalize.normalize_alef`).
  - [x] Normalize Yaa (e.g., `camel_tools.utils.normalize.normalize_alef_maksura_ar`).
  - [x] Normalize Haa (e.g., `camel_tools.utils.normalize.normalize_teh_marbuta`).
  - [x] Normalize Unicode (e.g., `camel_tools.utils.normalize.normalize_unicode`).
  - [x] Consider order and combination of normalization steps.
- [x] Implement a function (or extend the previous one) to perform tokenization using `camel-tools` (e.g., `camel_tools.tokenizers.word.simple_word_tokenize`).
- [x] Decide and document how processed text will be stored or passed to Stage 3 (e.g., update existing tables, create new table, pass in memory). # Decision: Process in-memory for now. Stage 3 will call preprocessing functions as needed.
- [x] Write Pytest unit tests for the preprocessing functions using `camel-tools`:
  - [x] Test normalization with various inputs.
  - [x] Test tokenization (check punctuation handling).
  - [x] Test handling of edge cases (empty strings, non-Arabic text if applicable).

## [Date TBD] Stage 3: Entity Extraction & Classification
- [x] Research and select appropriate CAMeL Tools NER model (e.g., `ner_ar_bert`). # Selected ner-arabert
- [x] Download the selected CAMeL Tools NER model (e.g., run `camel_data -i <model_name>` in terminal). # Done for ner-arabert
- [x] Create a service/module for entity extraction (e.g., `app/services/nlp/entity_extraction.py`). # Done
- [x] Implement a function in the service to load the NER model. # Done (loaded on module import)
- [x] Implement a function that takes preprocessed tokens (output from Stage 2) and returns identified entities using the loaded CAMeL Tools NER model. # Done (_extract_entities_from_tokens helper)
- [x] Define a Pydantic schema for the structured output (e.g., `schemas.ExtractedInfo` containing original text, list of entities, relevance flag). # Done in schemas.py
- [x] Implement logic to map raw NER tags (e.g., PER, LOC, ORG, TIME) to the desired structured fields (Location, Time, potentially inferring Event Type from keywords or context). # Done in _process_ner_tags helper
- [x] Implement a basic rule-based classifier function (`classify_relevance`) that takes the text or entities and returns `True` if likely related to road conditions/traffic, `False` otherwise (e.g., looking for keywords like "accident", "traffic", "road", "street", location names etc.). # Done
- [x] Combine extraction and classification into a primary service function (e.g., `extract_and_classify(text: str) -> schemas.ExtractedInfo`). # Done
- [x] Write Pytest unit tests for: # Done in test_entity_extraction.py
  - [x] Entity extraction (mocking the NER model call if necessary, testing with sample token lists and expected entity outputs). # Tested via _process_ner_tags tests and main function tests
  - [x] Relevance classification function with relevant and irrelevant examples. # Done
  - [x] The main `extract_and_classify` function. # Done

## [Date TBD] Stage 4: Validation & Deduplication
- [x] Install NLP/ML libraries: `pip install scikit-learn`. # Done (already installed + added to requirements)
- [x] Create a service/module (e.g., `app/services/nlp/deduplication.py`). # Done
- [x] Implement TF-IDF vectorization: # Done (vectorize_texts function)
    - [x] Create a function `vectorize_texts(texts: List[str])` using `sklearn.feature_extraction.text.TfidfVectorizer`.
    - [x] Ensure it handles Arabic text appropriately (consider using preprocessed/normalized text from Stage 2/3). # Uses normalized text input
- [x] Implement similarity calculation: # Done (calculate_similarity function)
    - [x] Create a function `calculate_similarity(tfidf_matrix)` using `sklearn.metrics.pairwise.cosine_similarity`.
- [x] Develop grouping logic: # Done (group_similar_reports function)
    - [x] Define a similarity threshold (e.g., 0.8).
    - [x] Implement a function `group_similar_reports(reports: List[schemas.ExtractedReportInfo], similarity_matrix, threshold: float)`.
    - [x] Consider adding time window checks (e.g., only group reports within X hours). # Implemented
    - [ ] Consider adding location proximity checks (requires comparing extracted `LocationInfo`, potentially basic string matching for now). # Deferred
- [x] Develop verification logic: # Done (verify_groups function)
    - [x] Define criteria (e.g., > 1 report in a group).
    - [x] Implement a function `verify_groups(groups: List[List[schemas.ExtractedReportInfo]])` that returns verified incident data.
- [x] Define output schema for verified incidents (e.g., `schemas.VerifiedIncident` in `app/schemas.py`). # Done
- [x] Combine steps into a main service function (e.g., `process_batch_for_deduplication(reports: List[schemas.ExtractedReportInfo]) -> List[schemas.VerifiedIncident]`). # Done
- [x] Write Pytest unit tests for: # Done (test_deduplication.py)
    - [x] `vectorize_texts`. # Basic test added
    - [x] `calculate_similarity`. # Basic test added
    - [x] `group_similar_reports` (with various similarity scores, time/location scenarios if added). # Tested with time window
    - [x] `verify_groups`. # Tested

## [Date TBD] Stage 5: Storage Layer
- [x] Define SQLAlchemy model `VerifiedReport` in `app/models.py` based on `schemas.VerifiedIncident`: # Done
    - [x] `id`: UUID PRIMARY KEY
    - [x] `representative_text`: TEXT
    - [x] `location_text`: TEXT NULLABLE
    - [x] `time_text`: TEXT NULLABLE
    - [x] `event_type`: TEXT NULLABLE
    - [x] `contributing_report_count`: INTEGER
    - [x] `first_report_at`: TIMESTAMP NULLABLE
    - [x] `last_report_at`: TIMESTAMP NULLABLE
    - [x] `db_created_at`: TIMESTAMP DEFAULT NOW()
- [ ] Update database schema (e.g., modify/run `create_tables.py`) to include the `reports` table.
- [x] Create storage service module (`app/services/storage_service.py`). # Done
- [x] Implement `save_verified_incident(db: Session, incident: schemas.VerifiedIncident)` function in the service. # Done
- [x] Implement `save_verified_incidents_batch(db: Session, incidents: List[schemas.VerifiedIncident])` function. # Done
- [x] Write Pytest unit tests for storage service functions (`tests/services/test_storage_service.py`), mocking the DB session. # Done

## [Date TBD] Stage 6: Verification Service
- [x] Create the Verification Service module (`app/services/verification_service.py`).
- [x] Implement the main orchestration logic (`run_verification_pipeline`):
  - [x] Fetch unprocessed reports (`RawGroupMessage`, `RawUserReport`).
  - [x] Add `processed` flag to raw report models & update schema.
  - [x] Call preprocessing service (`app.services.nlp.preprocessing`). # Handled within entity extraction
  - [x] Call entity extraction & classification service (`app.services.nlp.entity_extraction`).
  - [x] Call deduplication & verification service (`app.services.nlp.deduplication`).
  - [x] Call storage service (`app.services.storage_service`).
  - [x] Mark raw reports as processed in the database.
- [x] Implement trigger mechanism (Scheduled Task using `APScheduler` in `app/scheduler.py`).
- [x] Add configuration for scheduler interval (`PIPELINE_RUN_INTERVAL_MINUTES` in `app/settings.py`).
- [x] Write Unit Tests for `run_verification_pipeline` (`tests/services/test_verification_service.py`), mocking dependencies.
- [x] Update `README.md` with instructions for running the scheduler.

## [Date TBD] Stage 7: Telegram Bot Interface
- [x] Define basic bot commands (e.g., `/start`, `/help`, `/check <location>`, `/latest`).
- [x] Implement command handlers in `app/services/bot/handlers.py` or a similar module.
- [x] Create database query functions (in `storage_service` or a new query service) to fetch verified incidents based on criteria (e.g., location keywords, latest N reports).
- [x] Format query results into user-friendly messages for Telegram.
- [x] Connect command handlers to the Telegram bot framework (e.g., `python-telegram-bot` dispatcher) within the polling/webhook setup.
- [x] Add basic error handling for invalid commands or queries.
- [x] Write unit/integration tests for bot command handlers (mocking DB queries).

## [Date TBD] Stage 8: Deployment & Orchestration
- [x] Create a `Dockerfile` for the main application (FastAPI + Scheduler).
- [x] Set up a PostgreSQL database on a hosting provider (e.g., Railway, Neon, Aiven). # Instructions added to README
- [x] Configure GitHub Actions workflow for:
  - [x] Running tests on push/PR.
  - [x] Building the Docker image.
  - [x] Pushing the Docker image to a registry (e.g., Docker Hub, GitHub Container Registry).
  - [x] Deploying the image to the hosting provider (e.g., Railway).
- [x] Configure environment variables and secrets securely in the deployment environment (e.g., Railway secrets, GitHub Actions secrets). # Documented in README
- [x] Ensure database migrations/table creation runs correctly during deployment or as a separate step. # Handled by create_tables.py / Documented
- [x] Set up monitoring/logging for the deployed application. # Basic instructions in README
- [ ] (Future) Replace Telegram Bot polling with a webhook for production deployment.
- [x] Update `README.md` with deployment instructions.

## Discovered During Work
- None yet
