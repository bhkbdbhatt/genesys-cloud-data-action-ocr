import os
import re
import json
import uuid
import base64
import requests
import boto3
import fitz  # PyMuPDF
from flask import Flask, request, jsonify

app = Flask(__name__)

# Environment Configuration
API_KEY = os.getenv("API_KEY", "default-secret-key-change-me")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
PAGE_THRESHOLD = int(os.getenv("SYNC_PAGE_THRESHOLD", "15"))

# AWS SDK Clients
textract_client = boto3.client("textract", region_name=AWS_REGION)
s3_client = boto3.client("s3", region_name=AWS_REGION)
sqs_client = boto3.client("sqs", region_name=AWS_REGION)

# PII Redaction
SSN_REGEX = r"\b\d{3}-\d{2}-\d{4}\b"
CREDIT_CARD_REGEX = r"\b(?:\d[ -]*?){13,16}\b"

def mask_pii(text: str) -> str:
    if not text:
        return ""
    text = re.sub(SSN_REGEX, "[REDACTED SSN]", text)
    text = re.sub(CREDIT_CARD_REGEX, "[REDACTED CC]", text)
    return text

def verify_api_key(req):
    token = req.headers.get("X-API-KEY") or req.args.get("api_key")
    return token == API_KEY

def process_image_bytes(image_bytes):
    """Synchronous single-page Textract processing."""
    response = textract_client.detect_document_text(
        Document={"Bytes": image_bytes}
    )
    blocks = []
    total_confidence = 0.0
    count = 0
    
    for item in response.get("Blocks", []):
        if item["BlockType"] in ["LINE", "WORD"]:
            raw_text = item.get("Text", "")
            clean_text = mask_pii(raw_text)
            bbox = item["Geometry"]["BoundingBox"]
            blocks.append({
                "text": clean_text,
                "type": item["BlockType"],
                "confidence": round(item.get("Confidence", 0.0), 2),
                "boundingBox": {
                    "width": round(bbox["Width"], 4),
                    "height": round(bbox["Height"], 4),
                    "left": round(bbox["Left"], 4),
                    "top": round(bbox["Top"], 4)
                }
            })
            total_confidence += item.get("Confidence", 0.0)
            count += 1
            
    avg_confidence = round(total_confidence / count, 2) if count > 0 else 0.0
    page_text = " ".join([b["text"] for b in blocks if b["type"] == "LINE"])
    
    return {
        "text": page_text,
        "averageConfidence": avg_confidence,
        "blocks": blocks
    }

def process_sync_pdf(file_bytes):
    """Process small PDFs inline synchronously."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_result = []
    
    for page_idx in range(len(doc)):
        page = doc.load_page(page_idx)
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        
        res = process_image_bytes(img_bytes)
        pages_result.append({
            "pageNumber": page_idx + 1,
            "text": res["text"],
            "confidence": res["averageConfidence"],
            "blocks": res["blocks"]
        })

    full_text = "\n\n".join([p["text"] for p in pages_result])
    overall_confidence = (
        round(sum([p["confidence"] for p in pages_result]) / len(pages_result), 2)
        if pages_result else 0.0
    )

    return {
        "status": "COMPLETED",
        "totalPages": len(pages_result),
        "overallConfidence": overall_confidence,
        "fullText": full_text,
        "pages": pages_result
    }

@app.route("/ocr", methods=["POST"])
def perform_ocr():
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized. Invalid X-API-KEY."}), 401

    data = request.get_json() or {}
    file_url = data.get("fileUrl")
    file_base64 = data.get("fileBase64")
    mime_type = data.get("mimeType", "application/pdf").lower()

    file_bytes = None
    if file_url:
        try:
            resp = requests.get(file_url, timeout=15)
            resp.raise_for_status()
            file_bytes = resp.content
        except Exception as e:
            return jsonify({"error": f"Failed to download file: {str(e)}"}), 400
    elif file_base64:
        try:
            file_bytes = base64.b64decode(file_base64)
        except Exception as e:
            return jsonify({"error": f"Invalid base64 payload: {str(e)}"}), 400
    else:
        return jsonify({"error": "Either fileUrl or fileBase64 is required."}), 400

    # Determine page count for PDF inputs
    page_count = 1
    if "pdf" in mime_type or file_bytes[:4] == b"%PDF":
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            doc.close()
        except Exception as e:
            return jsonify({"error": f"Corrupted PDF file: {str(e)}"}), 400

    # Branch 1: Synchronous execution for small files
    if page_count <= PAGE_THRESHOLD:
        if "pdf" in mime_type or file_bytes[:4] == b"%PDF":
            res = process_sync_pdf(file_bytes)
        else:
            img_res = process_image_bytes(file_bytes)
            res = {
                "status": "COMPLETED",
                "totalPages": 1,
                "overallConfidence": img_res["averageConfidence"],
                "fullText": img_res["text"],
                "pages": [{
                    "pageNumber": 1,
                    "text": img_res["text"],
                    "confidence": img_res["averageConfidence"],
                    "blocks": img_res["blocks"]
                }]
            }
        return jsonify(res)

    # Branch 2: Asynchronous execution for files > 15 pages
    job_id = str(uuid.uuid4())
    s3_key_raw = f"incoming/{job_id}.pdf"
    
    try:
        # Save raw PDF to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key_raw,
            Body=file_bytes,
            ContentType="application/pdf"
        )
        
        # Save pending job status state in S3
        pending_status = {
            "jobId": job_id,
            "status": "IN_PROGRESS",
            "pageCount": page_count,
            "message": "File exceeds threshold. Processing asynchronously via SQS/Textract."
        }
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"results/{job_id}.json",
            Body=json.dumps(pending_status),
            ContentType="application/json"
        )

        # Enqueue processing task to SQS
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps({
                "jobId": job_id,
                "s3Key": s3_key_raw,
                "pageCount": page_count
            })
        )
    except Exception as e:
        return jsonify({"error": f"Failed to dispatch async job: {str(e)}"}), 500

    return jsonify({
        "status": "QUEUED",
        "jobId": job_id,
        "pageCount": page_count,
        "statusCheckUrl": f"/ocr/status?jobId={job_id}"
    }), 202

@app.route("/ocr/status", methods=["GET"])
def check_job_status():
    """Endpoint for Genesys Cloud to poll async job progress."""
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401

    job_id = request.args.get("jobId")
    if not job_id:
        return jsonify({"error": "Query parameter 'jobId' is required."}), 400

    try:
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"results/{job_id}.json"
        )
        result_data = json.loads(response["Body"].read().decode("utf-8"))
        return jsonify(result_data)
    except s3_client.exceptions.NoSuchKey:
        return jsonify({"error": "Job ID not found."}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve status: {str(e)}"}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "UP"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)