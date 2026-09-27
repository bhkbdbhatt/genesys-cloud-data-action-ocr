# Customer Onboarding Checklist

Pre-installation requirements for system administrators deploying this blueprint:

1. **AWS Account Access:**
   - Active AWS account with permissions to manage IAM roles and AWS App Runner.
2. **Genesys Cloud OAuth Client Creation:**
   - Go to **Genesys Cloud Admin > Integrations > OAuth**.
   - Create a Client with **Client Credentials** grant type.
   - Assign roles: `Data Actions > All`, `Architect > All`.
3. **System Requirements:**
   - Linux / macOS or WSL2 on Windows.
   - `terraform` CLI installed.
   - `archy` CLI installed.