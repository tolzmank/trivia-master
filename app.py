
import os
import random
import re

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

#region = (112, 240, 299, 354)  # BWW app game

#region = (4, 124, 810, 1300)    # Region coordinates/size (x, y, w, h) of game play window onscreen
region = (80, 148, 1015, 1291)
game_content = {}
answer = ''
answer_start = ''
active_trigger = ''

keyword_trigger = '?'
min_words = 2
last_gc_blocks = ""
targ_y = 0
scroller_version = False

trivia_bot = False
@app.route('/')
def index():
    return render_template('index.html',
                           scroller_version=scroller_version,
                           region=region,
                           keyword_trigger=keyword_trigger,
                           active_trigger=active_trigger,
                           answer_start=answer_start,
                           trivia_bot=trivia_bot
                           )


@app.route('/setup_game', methods=['POST'])
def setup_game():
    global keyword_trigger, region, min_words, active_trigger, answer_start, scroller_version, trivia_bot
    trivia_bot = False
    keyword_trigger = request.form['keyword_trigger']
    active_trigger = request.form['active_trigger']
    answer_start = request.form['answer_start']
    scroll = request.form['scroll']
    x = int(request.form['screen_region_x'])
    y = int(request.form['screen_region_y'])
    w = int(request.form['screen_region_w'])
    h = int(request.form['screen_region_h'])
    #min_words = request.form['min_words']
    region = (x, y, w, h)

    if scroll == 'yes':
        scroller_version = True
    else:
        scroller_version = False

    return redirect(url_for('index'))
        

@app.route('/clear', methods=['POST'])
def clear():
    global keyword_trigger, game_content, region, answer_start, active_trigger, min_words, last_gc_blocks, targ_y, scroller_version
    game_content = {}
    answer_start = ''
    active_trigger = ''
    keyword_trigger = '?'
    min_words = 2
    last_gc_blocks = ""
    targ_y = 0
    region = None
    scroller_version = False
    return redirect(url_for('index'))


@app.route('/start_trivia_bot', methods=['POST'])
def start_trivia_bot():
    global trivia_bot, scroller_version
    trivia_bot = True

    if scroller_version:
        threading.Thread(target=poll_and_answer, daemon=True).start()
    else:
        threading.Thread(target=poll_and_answer_no_scroll, daemon=True).start()

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


def poll_and_answer_no_scroll():
    # Poll screen, look for new question, trigger answer bot to get answer, click/select answer
    global region
    while trivia_bot:
        text = grab_and_ocr(region)
        #print(text)
        parse_text_game_content_no_scroll(text)
        time.sleep(2)


def parse_text_game_content_no_scroll(text):
    global keyword_trigger, active_trigger, game_content, answer_start
    excluded_word = ''
    current_question = game_content.get('question')
    # Parse question/answer options text
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    print()
    print('LINES:')
    print(lines)
    # Construct question from lines (seeks the keyword as the stopping point for the question construction)
    preq_lines = []
    q_lines = []
    question_full = ''
    q_end = 0

    # Build temp array to find end of question
    for i in range(len(lines)):
        preq_lines.append(lines[i])
        if keyword_trigger.lower() in lines[i].lower():
            q_end = i
            break

    # Iterate backwards from end of question, stop when a non-approved character is found
    if preq_lines:
        for i in range(len(preq_lines)-1, -1, -1):
            if keyword_trigger in preq_lines[i]:
                q_lines.append(lines[i])
            elif re.fullmatch(r"[A-Za-z0-9 ,'']+", preq_lines[i]) and len(preq_lines[i].split()) >= 2:
                q_lines.append(preq_lines[i])
            else:
                break
        q_lines = q_lines[::-1]

        # Build full question
        if q_lines:
            for line in q_lines:
                question_full += ' ' + line
    
    if keyword_trigger not in question_full:
        return

    print()
    print('QUESTION:', question_full)

    # Check if question on screen ready to answer
    for i in range(len(lines)):
        if not answer_start:
            option_lines = lines[q_end + 1:]
        elif answer_start.lower() in lines[i].lower():
            option_lines = lines[i + 1:]
        if not active_trigger or active_trigger.lower() in lines[i].lower():
            if not answer_start or answer_start.lower() in lines[i].lower():
                # Check if new question (compensate for slight variations in screen grab to text conversions)
                sim = SequenceMatcher(None, current_question.lower() if current_question else "", question_full.lower()).ratio()
                #print('SIM:', sim)
                if not game_content or sim < 0.9:
                    # Build game content structure (ensure only 4 non-None answer options)
                    option_labels = ['optA', 'optB', 'optC', 'optD']

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
                    clean_gc_answers(game_content, option_labels)
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
                    select_answer(answer, region, keyword_trigger)
                    break


def poll_and_answer():
    # Poll screen, look for new question, trigger answer bot to get answer, click/select answer
    global region, targ_y, last_gc_blocks
    while trivia_bot:
        text = grab_and_ocr(region)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        gc_blocks = parse_text_game_content(lines, [])

        # Check if new question
        if gc_blocks:
            gc_blocks = answer_incomplete_filter(gc_blocks)
            for game_content in gc_blocks:
                if not gc_sim(game_content, last_gc_blocks):
                    print()
                    print('QUESTION: ', game_content['question'])
                    print('ANSWERS')
                    print(game_content['optA'])
                    print(game_content['optB'])
                    print(game_content['optC'])
                    print(game_content['optD'])
                    print()

                    answer = get_answer(game_content)
                    select_answer(answer, region, keyword_trigger)
            last_gc_blocks = gc_blocks

            # Scroll
            anchor = region[1]
            delta_pixels = targ_y - anchor
            pixels_per_notch = 40
            clicks = int(delta_pixels / pixels_per_notch)
            #time.sleep(.25)
            pyautogui.scroll(-clicks)
            #time.sleep(.25)

        else:
            print('No new questions visible')


def answer_incomplete_filter(gc_blocks):
    empty_count = 0
    for gc in gc_blocks:
        for k, v in gc.items():
            if k != 'question':
                if v == ' ':
                    empty_count += 1
        if empty_count > 0:
            gc_blocks.remove(gc)
            break
    return gc_blocks


def gc_sim(game_content, last_gc_blocks):
    # Determine if the question in game content has already been answered before
    current_question = game_content['question']
    for gc in last_gc_blocks:
        sim = SequenceMatcher(None, current_question.lower() if current_question else "", gc['question'].lower()).ratio()
        if sim > 0.9:
            return True
    return False
        

def clean_gc_answers(game_content, option_labels):
    char_filter_out = ['A ', 'B ', 'C ', 'D ', '®', '©', '•', 'O ']
    # Characters to remove from option strings (parentheses, brackets, braces, quotes, bullets, symbols)
    chars_strip = '()[]{}"\'“”‘’•®©™'
    escaped = "".join(re.escape(c) for c in chars_strip)
    pattern = f"[{escaped}]"
    for k, v in game_content.items():
        if k in option_labels:
            for char in char_filter_out:
                if char in game_content[k][:2]:
                    game_content[k] = game_content[k][2:]
            game_content[k] = re.sub(pattern, '', game_content[k])
    return game_content


def parse_text_game_content(lines, gc_blocks):
    global keyword_trigger, active_trigger, game_content, answer_start, min_words
    current_question = game_content.get('question')
    # Parse question/answer options text
    #print()
    #print('LINES:')
    #print(lines)
    # Construct question from lines (seeks the keyword as the stopping point for the question construction)
    preq_lines = []
    q_lines = []
    question_full = ''
    q_end = 0

    # Build temp array to find end of question
    for i in range(len(lines)):
        preq_lines.append(lines[i])
        if keyword_trigger.lower() in lines[i].lower() and lines[i][-1] == '?':
            q_end = i
            break

    # Iterate backwards from end of question, stop when a non-approved character is found
    if preq_lines:
        for i in range(len(preq_lines)-1, -1, -1):
            if keyword_trigger in preq_lines[i]:
                if preq_lines[i][:2] != '? ':
                    q_lines.append(lines[i])
                else:
                    q_lines.append(lines[i][2:])
            elif re.fullmatch(r"[A-Za-z0-9 ,''.|$¢]+", preq_lines[i]) and len(preq_lines[i].split()) >= min_words:
                q_lines.append(preq_lines[i])
            else:
                break
        q_lines = q_lines[::-1]

        if q_lines:
            for line in q_lines:
                line = re.sub(r'\|', 'I', line)
                question_full += ' ' + line
    
    if keyword_trigger not in question_full:
        #print('No new questions visible')
        return gc_blocks

    # Check if question on screen ready to answer
    for i in range(len(lines)):
        if not answer_start:
            option_lines = lines[q_end + 1:]
        elif answer_start.lower() in lines[i].lower():
            option_lines = lines[i + 1:]
        if not active_trigger or active_trigger.lower() in lines[i].lower():
            if not answer_start or answer_start.lower() in lines[i].lower():
                #if not gc_blocks:
                # Build game content structure (ensure only 4 non-None answer options)
                option_labels = ['optA', 'optB', 'optC', 'optD']

                # Filter out letter option labels
                for option in option_lines:
                    if option.upper() in ['A', 'B', 'C', 'D']:
                        option_lines.remove(option)

                # Create a new game_content block for question
                gc = {
                    'question': question_full,
                    'optA': ' ',
                    'optB': ' ',
                    'optC': ' ',
                    'optD': ' '
                }

                for idx in range(len(min(option_lines, option_labels, key=len))):
                    gc[option_labels[idx]] = option_lines[idx]
                clean_gc_answers(gc, option_labels)
                gc_blocks.append(gc)
                break
    rem_lines = lines[q_end+1:]
    if rem_lines:
        return parse_text_game_content(rem_lines, gc_blocks)
    return gc_blocks


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
        else:
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


def select_answer(answer, region, keyword_trigger):
    global targ_y
    # Locate answer string onscreen
    target_box = None
    rx, ry, rw, rh = region
    img = ImageGrab.grab(bbox=(rx, ry, rx + rw, ry + rh))
    boxes = vision_ocr_answer_boxes(img)

    question_bottom = None
    for txt, (bx, by, bw, bh) in boxes:
        if keyword_trigger in txt:
            bottom = by + bh
            question_bottom = bottom if question_bottom is None else max(question_bottom, bottom)

    passed_question_zone = False
    for text, (x, y, w, h) in boxes:
        if keyword_trigger.lower() in text.lower():
            passed_question_zone = True
        
        if answer.lower() in text.lower() and passed_question_zone:
            target_box = (x, y, w, h)
            break

    if not target_box:
        print('No answer box found')
        return

    x, y, w, h = target_box

    # Calc click coordinates
    click_x = rx + x + w//2
    click_y = ry + y + h//2
    targ_y = click_y

    print(f"Clicking at ({click_x}, {click_y}) for answer '{answer}'")

    # Double click answer (to ensure game play window is selected)
    pyautogui.click(click_x, click_y)
    #time.sleep(0.1)
    pyautogui.click(click_x, click_y)


def vision_ocr_answer_boxes(pil_img):
    # Convert PIL image to CGImage for Vision
    raw_data = pil_img.convert('RGBA').tobytes()
    cfdata = Quartz.CFDataCreate(None, raw_data, len(raw_data))
    provider = Quartz.CGDataProviderCreateWithCFData(cfdata)
    cg_image = Quartz.CGImageCreate(
        pil_img.width, pil_img.height,
        8,
        32,
        pil_img.width * 4,
        Quartz.CGColorSpaceCreateDeviceRGB(),
        Quartz.kCGImageAlphaPremultipliedLast,
        provider,
        None, False, Quartz.kCGRenderingIntentDefault
    )
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, {})
    req = Vision.VNRecognizeTextRequest.alloc()\
             .initWithCompletionHandler_(None)
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    handler.performRequests_error_([req], None)

    # Returns list of (string, (x,y,w,h)) in pixel coords
    results = []
    for obs in req.results():
        txt = obs.topCandidates_(1)[0].string()
        # boundingBox is CGRect in normalized coords (0–1)
        # Get normalized bounding box coordinates
        rect = obs.boundingBox()
        nx = rect.origin.x
        ny = rect.origin.y
        nw = rect.size.width
        nh = rect.size.height
        # map into PIL image
        img_w, img_h = pil_img.size
        x = int(nx * img_w)
        y = int((1 - ny - nh) * img_h)      # Vision’s y=0 is bottom
        w = int(nw * img_w)
        h = int(nh * img_h)
        results.append((txt, (x, y, w, h)))
    return results


def start_bww_trivia_bot():
    global game_content, answer, trivia_bot
    trivia_bot = True
    threading.Thread(target=poll_and_answer, daemon=True).start()
    print('Trivia Bot Started...')
    return


if __name__ == "__main__":
    # Uncomment to run headless
    #start_bww_trivia_bot()
    app.run(debug=True)
