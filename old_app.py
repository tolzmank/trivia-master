
import os
import random

# Screen scraping/filling
from PIL import Image
import pyautogui
from PIL import Image
from PIL import ImageGrab
import Vision
import Quartz

# OpenAI for answer bot
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

from difflib import SequenceMatcher


from flask import Flask, render_template, redirect, url_for, request
app = Flask(__name__)

import threading
import time

region = (112, 240, 299, 354)   # Region coordinates/size (x, y, w, h) of game play window onscreen
offset_x = 50                   # Pixel X-axis offset distance from left side of selected screen region
offset_y = 195                  # Pixel Y-axis offset distance from left side of selected screen region
space_y = 43                    # Pixel vertical spacing between answers

game_content = {}
answer = ''
scroller_version = False
keyword_trigger = '?'           # Word/character that indicates if and where a question is being displayed onscreen
active_trigger = 'Secs'         # Word/character that indicates game is ready to answer question now

trivia_bot = False
@app.route('/')
def index():
    return render_template('index.html',
                           scroller_version=scroller_version,
                           offset_x=offset_x,
                           offset_y=offset_y,
                           space_y=space_y,
                           region=region,
                           keyword_trigger=keyword_trigger,
                           active_trigger=active_trigger,
                           trivia_bot=trivia_bot
                           )


@app.route('/setup_game', methods=['POST'])
def setup_game():
    global offset_x, offset_y, space_y, keyword_trigger, active_trigger, region
    offset_x = request.form['offset_x']
    offset_y = request.form['offset_y']
    space_y = request.form['space_y']
    keyword_trigger = request.form['keyword_trigger']
    active_trigger = request.form['active_trigger']
    x = request.form['screen_region_x']
    y = request.form['screen_region_y']
    w = request.form['screen_region_w']
    h = request.form['screen_region_h']
    region = (x, y, w, h)
    return redirect(url_for('index'))
        

@app.route('/clear', methods=['POST'])
def clear():
    global offset_x, offset_y, space_y, keyword_trigger, active_trigger, game_content, answer
    offset_x = 0
    offset_y = 0
    space_y = 0
    keyword_trigger = ''
    active_trigger = ''
    return redirect(url_for('index'))


@app.route('/start_trivia_bot', methods=['POST'])
def start_trivia_bot():
    global trivia_bot
    trivia_bot = True
    threading.Thread(target=poll_and_answer, daemon=True).start()
    print('Trivia Bot Started...')
    return redirect(url_for('index'))


@app.route('/stop_trivia_bot', methods=['POST'])
def stop_trivia_bot():
    global trivia_bot
    trivia_bot = False
    print('Trivia Bot Stopped')
    return redirect(url_for('index'))


def grab_and_ocr(region):
    # Screen grab specified region
    x, y, w, h = region
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    text = vision_ocr(img)

    # Save screenshot for configuring/debugging screen region settings
    #os.makedirs('screenshots', exist_ok=True)
    #timestamp = int(time.time())
    #img.save(f"screenshots/screenshot_{timestamp}.png")
    return text


def vision_ocr(pil_img: Image.Image) -> str:
    # Convert PIL image to raw RGBA data and create CFData provider
    raw_data = pil_img.convert('RGBA').tobytes()
    cfdata = Quartz.CFDataCreate(None, raw_data, len(raw_data))
    provider = Quartz.CGDataProviderCreateWithCFData(cfdata)
    cg_image = Quartz.CGImageCreate(
        pil_img.width, pil_img.height,
        8,
        32,
        pil_img.width * 4,                # bytes per row (width * RGBA)
        Quartz.CGColorSpaceCreateDeviceRGB(),
        Quartz.kCGImageAlphaPremultipliedLast,
        provider,
        None, False, Quartz.kCGRenderingIntentDefault
    )
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
        cg_image, {}
    )
    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(None)
    # You can tweak recognitionLevel to .accurate or .fast
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    handler.performRequests_error_([request], None)
    # Gather the top candidate from each observation
    lines = []
    for obs in request.results():
        candidate = obs.topCandidates_(1)[0]
        lines.append(candidate.string())
    return "\n".join(lines)


def poll_and_answer():
    # Poll screen, look for new question, trigger answer bot to get answer, click/select answer
    global game_content, answer, keyword_trigger, active_trigger, trivia_bot, question_region, opt_region, region
    while trivia_bot:
        text = grab_and_ocr(region)
        #print(text)
        parse_text_game_content(text)
        time.sleep(1)


def parse_text_game_content(text):
    global keyword_trigger, active_trigger, game_content
    excluded_word = 'Question'
    current_question = game_content.get('question')
    # Parse question/answer options text
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    print()
    print('LINES:')
    print(lines)
    # Construct question from lines (seeks the keyword as the stopping point for the question construction)
    question_full = ''
    for i in range(len(lines)):
        if keyword_trigger in lines[i]:
            question_full += ' ' + lines[i]
            break
        elif excluded_word:
            if excluded_word.lower() not in lines[idx].lower():
                question_full += ' ' + lines[idx]
        else:
            question_full += ' ' + lines[idx]
    print()
    print('QUESTION:', question_full)

    # Check if question on screen ready to answer
    for i in range(len(lines)):
        if active_trigger.lower() in lines[i].lower() and keyword_trigger.lower() in question_full.lower():
            # Check if new question (compensate for slight variations in screen grab to text conversions)
            sim = SequenceMatcher(None, current_question.lower() if current_question else "", question_full.lower()).ratio()
            print('SIM:', sim)
            if not game_content or sim < 0.75:
                # Build game content structure (ensure only 4 non-None answer options)
                option_labels = ['optA', 'optB', 'optC', 'optD']
                option_lines = lines[i+1:]
                # Filter out letter option labels
                for option in option_lines:
                    if option.upper() in ['A', 'B', 'C', 'D']:
                        option_lines.remove(option)

                game_content['question'] = question_full
                game_content['optA'] = ' '
                game_content['optB'] = ' '
                game_content['optC'] = ' '
                game_content['optD'] = ' '

                for idx in range(len(min(option_lines, option_labels, key=len))):
                    game_content[option_labels[idx]] = option_lines[idx]

                print()
                print('ANSWERS:')
                print(game_content['optA'])
                print(game_content['optB'])
                print(game_content['optC'])
                print(game_content['optD'])
                print()
                print('GAME CONTENT:', game_content)
                print()
                
                opts = [game_content['optA'], game_content['optB'],
                        game_content['optC'], game_content['optD']]
                answer = get_answer(game_content)
                select_answer(answer, opts, region)
                break


def get_answer(game_content):
    prompt = (
        f"You are a knowledgeable trivia assistant. "
        f"Here is a question:\n"
        f"{game_content['question']}\n\n"
        f"Options:\n"
        f"A) {game_content['optA']}\n"
        f"B) {game_content['optB']}\n"
        f"C) {game_content['optC']}\n"
        f"D) {game_content['optD']}\n\n"
        f"Please reply with the letter (A, B, C, D) and the corresponding answer text, "
        f"for example: 'B) Paris'."
    )
    try:
        resp = openai.chat.completions.create(
            model='gpt-4.1-nano',
            messages=[
                {'role': 'system', 'content': 'You answer trivia questions accurately and concisely.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0
        )
        text = resp.choices[0].message.content.strip()
        if ")" in text:
            _, answer_text = text.split(")", 1)
            final_answer = answer_text.strip()
            print(f"ChatGPT answered: {final_answer}")
            print()
            return final_answer
        print(f"ChatGPT answered: {text}")
        print()
        return text
    except Exception as e:
        print(f"OpenAI error in get_answer: {e}")
        # Fallback to random choice
        answers = []
        for key, value in game_content.items():
            if key != 'question':
                answers.append(value)
        selected_answer = random.choice(answers)
        print(f"Randomly selected answer: {selected_answer}")
        print()
        return selected_answer


def select_answer(answer, options, region):
    # Calc and map coordinates of correct answer to location onscreen, click answer
    global offset_x, offset_y, space_y
    set_x = region[0] + offset_x
    set_y = region[1] + offset_y
    try:
        index = options.index(answer)
    except ValueError:
        click_x = set_x
        click_y = set_y
        print(f"Could not find '{answer}' in options {options}")
        print(f"Clicking at first option({click_x}, {click_y}) for answer '{answer}'")
        pyautogui.click(click_x, click_y)
        time.sleep(0.25)
        pyautogui.click(click_x, click_y)
        return

    # Click coordinates
    click_x = set_x
    click_y = set_y + (space_y * index)
    print(f"Clicking at ({click_x}, {click_y}) for answer '{answer}'")

    # Double click answer (to ensure game play window is selected)
    pyautogui.click(click_x, click_y)
    time.sleep(0.25)
    pyautogui.click(click_x, click_y)


def start_bww_trivia_bot():
    global game_content, answer, trivia_bot, driver, chrome_opts
    trivia_bot = True
    threading.Thread(target=poll_and_answer, daemon=True).start()
    print('Trivia Bot Started...')
    return


if __name__ == "__main__":
    #app.run(host='0.0.0.0', port=8080, debug=True)

    # Uncomment to run headless
    #start_bww_trivia_bot()
    app.run(debug=False)
