output "app_runner_url" {
  value       = "https://${aws_apprunner_service.ocr_service.service_url}"
  description = "The HTTPS URL of the deployed App Runner OCR service."
}

output "genesys_data_action_id" {
  value       = genesyscloud_integration_action.ocr_action.id
  description = "The ID of the created Genesys Cloud Data Action."
}