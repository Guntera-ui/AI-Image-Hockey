# AI Hockey Player Pipeline

This project is an end-to-end AI pipeline that transforms a user’s selfie into a personalized hockey player experience. It generates a hero portrait, a hockey card, a branded video, and delivers the result via email. The system is built for real-world deployment using Firebase and AI model providers.

---

## Features

* Automated image and video generation pipeline
* AI-generated hero portraits and hockey cards
* AI-generated branded videos
* Firebase Firestore and Storage integration
* Email delivery system (SendGrid)
* Fault-tolerant processing worker
* Unique user ID system (no email collisions)
* Leaderboard ranking (computed dynamically)
* Batch export with consent-based separation

---

## Architecture Overview

```
User Input (Frontend / Kiosk)
        ↓
Firestore (players collection)
        ↓
Listener (firestore_listener.py)
        ↓
Hero Generation (hero_ai.py)
        ↓
Video Generation (video_ai.py)
        ↓
Video Overlay (video_overlay.py)
        ↓
Firebase Storage (storage_client.py)
        ↓
Email Delivery (email_client.py)
        ↓
Download Link (/download/<uniqueId>)
```

---

## Project Structure

```
.
├── hero_ai.py
├── video_ai.py
├── video_overlay.py
├── firestore_listener.py
├── firestore_client.py
├── storage_client.py
├── email_client.py
├── player_pipeline.py
├── export_players.py
├── config.py
└── firebase-key.json   # not committed
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/your-repo/ai-hockey-pipeline.git
cd ai-hockey-pipeline
```

---

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Configure environment variables

Create a `.env` file:

```
SERVICE_ACCOUNT_PATH=firebase-key.json
FIREBASE_STORAGE_BUCKET=your-bucket-name

FAL_KEY=your_fal_api_key
FAL_VIDEO_MODEL_ID=fal-ai/wan-2.5-preview/image-to-video

EMAIL_SMTP_HOST=smtp.sendgrid.net
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=apikey
EMAIL_PASSWORD=your_sendgrid_api_key
EMAIL_FROM=no-reply@yourdomain.com
```

---

### 5. Add Firebase credentials

Place your Firebase service account file in the root directory:

```
firebase-key.json
```

Do not commit this file to version control.

---

## Running the System

Start the pipeline worker:

```bash
python firestore_listener.py
```

The system will listen for new player documents in Firestore and process them through all pipeline stages automatically.

---

## Pipeline Description

Each player document contains:

* uniqueId
* firstName, lastName, email
* Power, Speed, TotalScore
* consent
* generated media URLs

Processing stages:

1. Hero image generation
2. Face enhancement
3. Card generation
4. Video generation
5. Overlay branding
6. Upload to Firebase Storage
7. Email delivery

---

## AI Models

Image generation:

* Gemini (initial implementation)
* Nano Banana Pro via FAL (recommended)

Video generation:

* WAN / Nano Banana Flash via FAL

---

## Email System

The system uses SendGrid SMTP to send:

* Branded HTML email
* Download link based on uniqueId

---

## Batch Export (Post-Event)

Run:

```bash
python export_players.py
```

Output structure:

```
export/
├── consented/
│   └── Player Name/
│       ├── Player Name.txt
│       ├── Player_Name_Hockey_Card.png
│       └── Player_Name_Hockey_Video.mp4
└── not_consented/
```

The text file includes:

* Name
* Email
* Gender
* Leaderboard placement
* All Power values
* All Speed values
* Total score
* Download link

---

## Leaderboard

Leaderboard placement is not stored in Firestore. It is computed during export by sorting players based on TotalScore in descending order.

---

## Error Handling

* Defensive checks for AI responses
* Per-player isolation in processing
* Retry-safe export pipeline
* Pagination to avoid Firestore stream timeouts

---

## Security

* Do not commit API keys or Firebase credentials
* Store secrets in `.env`
* Rotate credentials if exposed

---

## Development Notes

* Test with a small dataset first
* Verify outputs (images, videos, emails)
* Check rendering on Gmail and iOS Mail
* Monitor logs during execution

---

## License

MIT License

---

## Status

Production-ready and event-tested.
