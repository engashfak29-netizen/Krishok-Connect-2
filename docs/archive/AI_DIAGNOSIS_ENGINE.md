# Krishok Connect — AI Crop Diagnosis Engine

## Goal
কৃষক ৩ভাবে সমস্যা জানাতে পারবেন:
1. উপসর্গ লিখে
2. রোগ/পোকার নাম লিখে
3. ফসলের সমস্যার ছবি দিয়ে (সাথে ফসল/উপসর্গ দিলে আরও ভালো)

## Pipeline
Farmer input → visual observation (if image) → crop/symptom normalization → structured diagnosis cases + approved knowledge retrieval → OpenAI reasoning → Bengali safety response.

## Structured case data
`ai_diagnosis_cases` stores crop, disease, pest, problem type, symptoms, visual signs, causes, actions, prevention, red flags, source and confidence.

Admin endpoints:
- POST `/api/v1/ai/diagnosis/cases`
- GET `/api/v1/ai/diagnosis/cases`

## Image rules
Only JPG/PNG/WEBP are accepted for diagnosis. Images are sent server-side to the configured OpenAI model; the browser never receives the API key. The visual step is instructed to describe visible signs, not declare a certain diagnosis.

## Knowledge safety
Only approved knowledge chunks are used as authoritative evidence. The engine must not invent pesticide doses. If authoritative dose data is absent, it tells the farmer to follow the product label and local agricultural officer.

## Important
This is a decision-support/triage engine, not a laboratory diagnosis. For uncertain or severe cases it should request more photos/details or recommend local expert confirmation.
