# AI Sports Media Generation Pipeline

This project is an end-to-end backend system that transforms a user’s photo into a complete sports-themed media experience. It generates a stylized portrait, a trading card, and a branded video, then delivers the result via a unique download link.

This repository is a sanitized version of a real-world event deployment. All branding assets and sensitive data have been removed.

---

## Overview

The system is designed for event or kiosk environments where users submit a photo and receive personalized media generated using AI.

Outputs include:

* Stylized portrait (hero image)
* Trading card image
* Generated video
* Unique download link

---

## Architecture

```
User Submission
      ↓
Firestore (players collection)
      ↓
Listener (firestore_listener.py)
      ↓
hero_ai.py        → Image generation
video_ai.py       → Video generation
video_overlay.py  → Video branding
      ↓
storage_client.py → Upload to Firebase Storage
      ↓
email_client.py   → Send email with download link
```

---

## Project Structure

```
.
├── hero_ai.py              # AI image generation (portrait, face fix, card)
├── video_ai.py            # AI video generation (FAL models)
├── video_overlay.py       # Video overlay / branding system
├── firestore_listener.py  # Core processing worker
├── firestore_client.py    # Firestore helpers
├── storage_client.py      # Firebase Storage integration
├── email_client.py        # Email sending logic
├── player_pipeline.py     # Pipeline orchestration
├── export_players.py      # Post-event batch export
├── config.py              # Configuration
```

---

## Pipeline Flow

Each user creates a document in Firestore containing:

* `uniqueId`
* `firstName`, `lastName`, `email`
* `Power`, `Speed`, `TotalScore`
* `consent`

Processing stages:

1. **Hero generation** (`hero_ai.py`)
2. **Face enhancement**
3. **Card generation**
4. **Video generation** (`video_ai.py`)
5. **Overlay application** (`video_overlay.py`)
6. **Upload to storage** (`storage_client.py`)
7. **Email delivery** (`email_client.py`)

---

## AI Integration

The system is modular and supports different providers.

* Image generation:

  * Initially implemented with Gemini
  * Designed to support FAL-based models (e.g. Nano Banana Pro)

* Video generation:

  * FAL models (WAN / Nano Banana Flash)

AI logic is isolated, allowing model replacement without affecting the pipeline.

---

## Setup

### 1. Clone repository

```
git clone https://github.com/Guntera-ui/AI-Image-Hockey.git
cd AI-Image-Hockey
```

---

### 2. Create virtual environment

```
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install dependencies

Create `requirements.txt`:

```
firebase-admin
google-cloud-firestore
google-cloud-storage
requests
python-dotenv
pillow
fal-client
```

Then install:

```
pip install -r requirements.txt
```

---

### 4. Environment configuration

Create `.env`:

```
SERVICE_ACCOUNT_PATH=firebase-key.json
FIREBASE_STORAGE_BUCKET=your-bucket

FAL_KEY=your_fal_api_key
FAL_VIDEO_MODEL_ID=fal-ai/wan-2.5-preview/image-to-video

EMAIL_SMTP_HOST=smtp.sendgrid.net
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=apikey
EMAIL_PASSWORD=your_sendgrid_api_key
EMAIL_FROM=no-reply@example.com
```

---

### 5. Firebase credentials

Place your service account file:

```
firebase-key.json
```

Do not commit this file.

---

## Running the System

Start the processing worker:

```
python firestore_listener.py
```

The worker listens for new documents and processes them automatically.

---

## Batch Export

After processing is complete:

```
python export_players.py
```

### Output structure

```
export/
├── consented/
│   └── Player Name/
│       ├── data.txt
│       ├── Player_Name_Hockey_Card.png
│       └── Player_Name_Hockey_Video.mp4
└── not_consented/
```

### Data included

* Name, email, gender
* Leaderboard placement (computed)
* All Power values
* All Speed values
* Total score
* Download link (`/download/<uniqueId>`)

---

## Visual Asset Customization

This repository does not include original branding assets.

To reproduce full visuals, you should provide your own:

* Video overlay frames (`video_overlay.py`)
* Logos
* Email images
* Card templates

The system is designed to work with any branding by replacing these assets.

---

## Error Handling

* AI response validation prevents crashes
* Per-user failure isolation
* Firestore pagination avoids stream timeouts
* Export continues even if individual users fail

---

## Security

* No credentials included
* Use `.env` for secrets
* Do not commit service account files
* Do not expose real user data

---

## Notes

* This project is based on a real deployment
* Branding and sensitive data have been removed
* Intended for educational and portfolio use

---

## Status

Production-tested system adapted for demonstration purposes.
