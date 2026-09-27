# 1. Integration Container
resource "genesyscloud_integration" "ocr_integration" {
  intended_state   = "ENABLED"
  integration_type = "custom-rest-actions"
  name             = "OCR Service Integration"
}

# 2. Data Action Definition
resource "genesyscloud_integration_action" "ocr_action" {
  name           = "OCR Attachment Text Extractor"
  category       = "Web Services Data Actions"
  integration_id = genesyscloud_integration.ocr_integration.id
  secure         = false

  contract_input = jsonencode({
    "$schema"  = "http://json-schema.org/draft-04/schema#"
    "title"    = "OCRInput"
    "type"     = "object"
    "required" = ["fileUrl"]
    "properties" = {
      "fileUrl"  = { "type" = "string", "description" = "Attachment download URL" }
      "mimeType" = { "type" = "string", "default" = "application/pdf" }
    }
  })

  contract_output = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    "title"   = "OCROutput"
    "type"    = "object"
    "properties" = {
      "fullText"          = { "type" = "string" }
      "totalPages"        = { "type" = "integer" }
      "overallConfidence" = { "type" = "number" }
    }
  })

  config_request {
    request_url_template = "https://${aws_apprunner_service.ocr_service.service_url}/ocr"
    request_type         = "POST"
    headers = {
      "Content-Type" = "application/json"
      "X-API-KEY"    = var.ocr_api_key
    }
    request_template = "{\n  \"fileUrl\": \"$${input.fileUrl}\",\n  \"mimeType\": \"$${input.mimeType}\"\n}"
  }

  config_response {
    translation_map = {
      fullText          = "$.fullText"
      totalPages        = "$.totalPages"
      overallConfidence = "$.overallConfidence"
    }
    translation_map_defaults = {
      fullText          = "\"\""
      totalPages        = "0"
      overallConfidence = "0.0"
    }
    success_template = "{\n  \"fullText\": $${fullText},\n  \"totalPages\": $${totalPages},\n  \"overallConfidence\": $${overallConfidence}\n}"
  }
}