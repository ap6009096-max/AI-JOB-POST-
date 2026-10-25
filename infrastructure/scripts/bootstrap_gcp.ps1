#Requires -Version 5.1
<#
.SYNOPSIS
  Bootstrap GCP resources for Aether Hire production on Cloud Run.

.DESCRIPTION
  Enables APIs, creates Artifact Registry, GCS bucket, Cloud Tasks queue,
  service accounts + IAM, Secret Manager secret placeholders, and optional
  uptime checks. Safe to re-run (idempotent where gcloud allows).

.EXAMPLE
  .\infrastructure\scripts\bootstrap_gcp.ps1 -ProjectId imagi-ai-gpami -Region asia-south1
#>
param(
  [string]$ProjectId = "imagi-ai-gpami",
  [string]$Region = "asia-south1",
  [string]$Repository = "aether-hire",
  [string]$GcsBucket = "aether-hire-resumes-$ProjectId",
  [string]$TasksQueue = "aether-hire-tasks",
  [string]$DocumentAiProcessorId = ""
)

$ErrorActionPreference = "Stop"

function Invoke-Gcloud {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GcloudArgs)
  Write-Host ">> gcloud $($GcloudArgs -join ' ')" -ForegroundColor Cyan
  & gcloud @GcloudArgs
  if ($LASTEXITCODE -ne 0) {
    throw "gcloud failed: $($GcloudArgs -join ' ')"
  }
}

Write-Host "Bootstrapping Aether Hire on project=$ProjectId region=$Region" -ForegroundColor Green
Invoke-Gcloud config set project $ProjectId

$apis = @(
  "run.googleapis.com",
  "cloudbuild.googleapis.com",
  "artifactregistry.googleapis.com",
  "secretmanager.googleapis.com",
  "cloudtasks.googleapis.com",
  "aiplatform.googleapis.com",
  "documentai.googleapis.com",
  "storage.googleapis.com",
  "logging.googleapis.com",
  "monitoring.googleapis.com",
  "iam.googleapis.com"
)
Invoke-Gcloud services enable @apis --project=$ProjectId

# Artifact Registry
$repoExists = & gcloud artifacts repositories describe $Repository --location=$Region --project=$ProjectId 2>$null
if (-not $repoExists) {
  Invoke-Gcloud artifacts repositories create $Repository `
    --repository-format=docker `
    --location=$Region `
    --description="Aether Hire container images" `
    --project=$ProjectId
}

# GCS bucket for resumes
$bucketUri = "gs://$GcsBucket"
$bucketExists = & gcloud storage buckets describe $bucketUri --project=$ProjectId 2>$null
if (-not $bucketExists) {
  Invoke-Gcloud storage buckets create $bucketUri `
    --project=$ProjectId `
    --location=$Region `
    --uniform-bucket-level-access
}
Invoke-Gcloud storage buckets update $bucketUri --cors-file=- 2>$null

# Cloud Tasks queue
$queueExists = & gcloud tasks queues describe $TasksQueue --location=$Region --project=$ProjectId 2>$null
if (-not $queueExists) {
  Invoke-Gcloud tasks queues create $TasksQueue --location=$Region --project=$ProjectId
}

# Service accounts
$accounts = @{
  "aether-api"    = "Aether Hire API runtime"
  "aether-worker" = "Aether Hire Worker runtime"
  "aether-web"    = "Aether Hire Web runtime"
}
foreach ($sa in $accounts.Keys) {
  $email = "$sa@$ProjectId.iam.gserviceaccount.com"
  $exists = & gcloud iam service-accounts describe $email --project=$ProjectId 2>$null
  if (-not $exists) {
    Invoke-Gcloud iam service-accounts create $sa --display-name=$($accounts[$sa]) --project=$ProjectId
  }
}

$apiSa = "aether-api@$ProjectId.iam.gserviceaccount.com"
$workerSa = "aether-worker@$ProjectId.iam.gserviceaccount.com"
$webSa = "aether-web@$ProjectId.iam.gserviceaccount.com"
$projectNumber = (& gcloud projects describe $ProjectId --format="value(projectNumber)").Trim()
$buildSa = "$projectNumber@cloudbuild.gserviceaccount.com"

# API roles
@(
  "roles/aiplatform.user",
  "roles/documentai.apiUser",
  "roles/storage.objectAdmin",
  "roles/cloudtasks.enqueuer",
  "roles/secretmanager.secretAccessor",
  "roles/logging.logWriter",
  "roles/monitoring.metricWriter",
  "roles/run.invoker"
) | ForEach-Object {
  Invoke-Gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$apiSa" --role=$_ --condition=None --quiet
}

# Worker roles
@(
  "roles/aiplatform.user",
  "roles/documentai.apiUser",
  "roles/storage.objectAdmin",
  "roles/secretmanager.secretAccessor",
  "roles/logging.logWriter",
  "roles/monitoring.metricWriter"
) | ForEach-Object {
  Invoke-Gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$workerSa" --role=$_ --condition=None --quiet
}

# Web roles (minimal)
@(
  "roles/logging.logWriter",
  "roles/monitoring.metricWriter"
) | ForEach-Object {
  Invoke-Gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$webSa" --role=$_ --condition=None --quiet
}

# Cloud Build can push images and deploy Cloud Run + act as runtime SAs
@(
  "roles/artifactregistry.writer",
  "roles/run.admin",
  "roles/iam.serviceAccountUser",
  "roles/secretmanager.secretAccessor"
) | ForEach-Object {
  Invoke-Gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$buildSa" --role=$_ --condition=None --quiet
}

# Secret placeholders (create empty versions only if missing)
$secretNames = @(
  "database-url",
  "supabase-service-role",
  "worker-shared-secret",
  "github-token",
  "reddit-client-id",
  "reddit-client-secret"
)
foreach ($name in $secretNames) {
  $exists = & gcloud secrets describe $name --project=$ProjectId 2>$null
  if (-not $exists) {
    Invoke-Gcloud secrets create $name --replication-policy=automatic --project=$ProjectId
    Write-Host "Created secret $name - add a version with: gcloud secrets versions add $name --data-file=-" -ForegroundColor Yellow
  }
  foreach ($sa in @($apiSa, $workerSa)) {
    Invoke-Gcloud secrets add-iam-policy-binding $name `
      --member="serviceAccount:$sa" `
      --role="roles/secretmanager.secretAccessor" `
      --project=$ProjectId `
      --quiet
  }
}

Write-Host ""
Write-Host "Bootstrap complete." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  1. Add Secret Manager versions for database-url, supabase-service-role, worker-shared-secret"
Write-Host "  2. Set DOCUMENT_AI_PROCESSOR_ID (or create a processor in Document AI)"
Write-Host "  3. gcloud builds submit --config infrastructure/cloudbuild.yaml ."
Write-Host "  4. Update Supabase Auth redirect URLs to the aether-web Cloud Run URL"
Write-Host "  5. Set CORS_ORIGINS / WORKER_URL substitutions on the Cloud Build trigger"
