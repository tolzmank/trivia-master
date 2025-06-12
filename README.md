# BWW Trivia Bot

This project consists of:

**Trivia Bot** (`app.py`):  
   A Python service that OCRs your mirrored screen region, parses out the question and options, calls an LLM (via OpenAI’s API) to pick the correct answer, and clicks that option on the screen.
---
   Flask app for a UI to easily enter in keyword trigger, active trigger, screen region coordinates/size, and mouse click offsets/spacing.
   Along with a simple "Trivia Bot On/Off" toggle to start/stop the bot.
  
## 📦 Installation

1. **Clone the repo**  
   ```bash
   git clone https://github.com/tolzmank/bww_trivia_master.git
   cd bww_trivia_master

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt

3. **Launch Trivia Bot**
   ```bash 
   flask run
