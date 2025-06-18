# Trivia Bot

This project consists of:

**Trivia Bot** (`app.py`):  
   A Python service that OCRs your mirrored screen region, parses out the question and options, calls an LLM (via OpenAI’s API) to pick the correct answer, and clicks that option on the screen.
---
   Flask app for a UI to easily enter in keyword trigger, active trigger, screen region coordinates/size, and enable/disable scrolling feature (if trivia game type is one page with many questions or one question on the screen at a time).
   Along with a simple "Trivia Bot On/Off" toggle to start/stop the bot.

   Note: Currently only works on Mac OS, due to use of Apple's Vision and Quartz frameworks.
  
## 📦 Installation

1. **Clone the repo**  
   ```bash
   git clone https://github.com/tolzmank/trivia-master.git
   cd trivia_master

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt

3. **Launch Trivia Bot**
   ```bash 
   flask run
