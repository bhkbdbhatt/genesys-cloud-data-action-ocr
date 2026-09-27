# Architecture Specification

## Synchronous Data Action Flow

[ Customer Chat/Email ] ──> [ Genesys Architect ]
│
│ HTTPS POST (15s Timeout)
▼
[ AWS App Runner (Flask) ]
│
│ boto3 SDK
▼
[ AWS Textract API ]

## Security Controls
1. **API Key Authentication:** Request calls must carry the `X-API-KEY` header matching the Terraform-configured secret.
2. **In-Memory Processing:** Document bytes are processed entirely in-memory and rendered into PNG byte streams via PyMuPDF. No image files are saved to container disks.
3. **PII Masking:** Text returned from Textract is evaluated against standard regular expressions before being packaged into the JSON response body to prevent sensitive data leakage.