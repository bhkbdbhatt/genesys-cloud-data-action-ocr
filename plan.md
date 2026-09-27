# Implementation Plan: Genesys Cloud Data Action OCR Plugin

This document outlines the architecture, requirements, and execution roadmap for building and deploying a Genesys Cloud Data Action OCR integration.

---

## 1. System Architecture Overview

```
 +------------------------+      +---------------------------+      +-------------------------+
 | Genesys Cloud Flow     | ---> | Genesys Data Action       | ---> | Flask Microservice      |
 | (Chat/Email Attachment)|      | (Web Services REST Integration)  | (Docker / Gunicorn)     |
 +------------------------+      +---------------------------+      +-------------------------+
                                                                                 |
                                                                                 v
                                                                    +-------------------------+
                                                                    | AWS Textract / Cloud    |
                                                                    | Vision API              |
                                                                    +-------------------------+
```

---

## 2. Requirements Breakdown

1. **OCR Microservice (Python / Flask)**
   - Expose `/ocr` endpoint for handling document URLs and Base64 payloads.
   - Handle multi-page PDFs using `PyMuPDF` (`fitz`) by breaking them into individual pages.
   - Integrate with AWS Textract (or Google Cloud Vision) for text, confidence, and bounding box extraction.
   - Package inside a light Docker container (`python:3.11-slim`) with Gunicorn as the WSGI server.

2. **Genesys Cloud Data Action Integration**
   - Provide standard JSON configuration schema (`/v2/dataactions`) for request translation and response parsing.
   - Schema mapping for input (URL/Base64, MIME type) and output (full text, per-page breakdown, confidence scores, bounding boxes).

3. **Genesys Architect Workflow**
   - Provide an Inbound Message Architect Workflow JSON schema.
   - Parse inbound attachments from Chat or Email channels.
   - Trigger the OCR Data Action, evaluate confidence scores, set screen pop attributes, and route accordingly.

---

## 3. Implementation Phases & Milestones

### Phase 1: Microservice Development
- [x] Structure `app.py` with endpoints (`/ocr`, `/health`).
- [x] Implement multi-page PDF rendering to image buffer.
- [x] Integrate AWS Textract API for structured OCR response construction.
- [x] Configure `Dockerfile` and `requirements.txt`.

### Phase 2: Genesys Integration Configuration
- [x] Draft `OCR_DataAction.json` with input/output JSON schemas and request templates.
- [x] Draft `OCR_Workflow.json` for Genesys Architect inbound message handling.

### Phase 3: Documentation & Deployment Guidelines
- [x] Compile detailed step-by-step setup guides for deployment, API keys, and testing.

---

## 4. Verification and Testing Strategy

- **Local Endpoint Testing:** Test using `curl` / Postman with sample single-page PNG/JPEG and multi-page PDF files.
- **Data Action Validation:** Execute test runs via Genesys Data Action UI with public sample URLs.
- **Architect Workflow Test:** Simulate inbound chat/email attachment interaction in Genesys Cloud.