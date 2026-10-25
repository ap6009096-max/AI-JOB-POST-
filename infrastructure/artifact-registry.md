# Artifact Registry (Aether Hire)

Production images live in:

```text
asia-south1-docker.pkg.dev/PROJECT_ID/aether-hire/{aether-web,aether-api,aether-worker}
```

Create (also done by `infrastructure/scripts/bootstrap_gcp.ps1`):

```powershell
gcloud artifacts repositories create aether-hire --repository-format=docker --location=asia-south1
```

Build & deploy:

```powershell
gcloud builds submit --config infrastructure/cloudbuild.yaml .
```
