# KOL Performance Tracker 🧩

A lightweight web app that extracts **YouTube / Instagram / TikTok** video statistics (views, likes, comments) and calculates **engagement rate**, then displays the results in a **simple dashboard**. Designed for weekly use in influencer campaign tracking.

---

## ✨ Features

- Upload `.csv` or `.xlsx` files with KOL video links
- Auto-detect platform: YouTube / TikTok / Instagram
- Fetch stats via **YouTube Data API v3**
- Calculates engagement rate: `engagement_rate = (likes + comments) / views * 100%`
- Auto-fill `creator` and `posted_at` from the video
- Save results to a local SQLite database
- Prevent duplicate entries: update existing records if the same URL is re-uploaded
- View full history and export CSV
- One-click “Fetch Now” button in the web UI

---

## 💻 Tech Stack

- Backend: Python + SQLAlchemy
- Frontend: [Streamlit](https://streamlit.io)
- Database: SQLite3
- API: YouTube Data API v3

---

## 🚀 Quick Start
1.**Clone the repo**:
 ```bash
 git clone <your-repo-url>
 cd kol_clawer
 ```
2.**Set up the environment**:
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
 ```
3.**Run the app**:
```bash
streamlit run app.py
 ```

## 🔑 Get a YouTube API Key
1.Go to Google Cloud Console

2.Create a new project and enable YouTube Data API v3

3.Create API credentials → API Key

4.Paste the key into the Streamlit web page when prompted

ps:
Free quota = 10,000 units/day,Fetching video stats typically consumes 1 unit per request.


## 📁 Input File Format

Supported formats: `.csv` or `.xlsx`

Required columns: `platform` and `url`

## 🗂 How Data is Stored

All data is saved to `kol_results.sqlite3` in the project root.

**Fields include:**

- `id`: Auto-increment  
- `platform`: youtube / instagram / tiktok  
- `url`: Must be unique  
- `creator`: Channel or account name  
- `posted_at`: Original post date  
- `views`, `likes`, `comments`: Stats  
- `engagement_rate`: Calculated as above  
- `fetched_at`: Timestamp of scraping  

> If a URL already exists, it will be updated — not duplicated.


## 🧠 Web App Overview

- Upload your weekly report (e.g. `kol_links.csv`)  
- Click **Start Fetching** to grab data  
- Table view updates with the latest stats  
- Full history shown below with CSV export  


## 🛠 Common Issues & Tips

- If Instagram / TikTok videos fail, it’s due to anti-scraping or missing API.
- YouTube is the most stable via official API
- To reset database:

```bash
rm kol_results.sqlite3
```

Are you getting `ModuleNotFoundError: No module named 'yt_dlp'` when deploying? Please confirm that `yt-dlp` is installed in the dependencies.
(Use hyphens when installing and underscores when importing).

## 📌 Future Improvements

- Add native API support for TikTok / Instagram

- Add charts: growth trend, ranking by views or engagement

- Add login / user management for multi-team usage