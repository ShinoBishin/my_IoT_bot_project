from flask import Flask, request, abort
import gspread
import random
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageMessage, ImageSendMessage
)

import json
import subprocess
import time
import datetime


file = open("info.json", "r")
info = json.load(file)
SPREADSHEET_KEY = info["SPREADSHEET_KEY"]
CHANNEL_ACCESS_TOKEN = info["CHANNEL_ACCESS_TOKEN"]
USER_ID = info["USER_ID"]
WEBHOOK_HANDLER = info["WEBHOOK_HANDLER"]
PRESS_URL = info["PRESS_URL"]
TEMP_URL = info["TEMP_URL"]
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(WEBHOOK_HANDLER)

botRes = []
record = [""] * 7

app = Flask(__name__)


def create_datetime():
    date = datetime.datetime.now()
    date = date.replace(microsecond=0)
    return date


def init_record(record):
    record = [""] * 7
    return(record)


def get_sheet():
    gc = gspread.service_account(
        filename="line-bot-project1-0a7f2b46fc9e.json")
    workbook = gc.open_by_key(SPREADSHEET_KEY)
    sh2 = workbook.worksheet("シート2")
    return sh2


def get_sheet_all():
    gc = gspread.service_account(
        filename="line-bot-project1-0a7f2b46fc9e.json")
    workbook = gc.open_by_key(SPREADSHEET_KEY)
    sh2 = workbook.worksheet("シート2")
    sh3 = workbook.worksheet("シート3")
    return sh2, sh3


def select_temp_and_humidity(sheet2):
    values = sheet2.get_all_records()
    last = values[-1]
    return float(last["temp"]), float(last["humidity"])


def select_disc(sheet2):
    values = sheet2.get_all_records()
    last = values[-1]
    return float(last["disconfort"])


def select_press(sheet2):
    values = sheet2.get_all_records()
    last = values[-1]
    return float(last["pressure"])


def select_press_ave(sheet2):
    values = sheet2.get_all_records()
    p = [d.get("change_pre") for d in values[-12:]]
    return float(sum(p)/len(p))


def followUp_press(sheet2):
    values = sheet2.get_all_records()
    now = values[-1]["pressure"]
    before = values[-12]["pressure"]
    return (float(now - before))


def create_response_text():
    sheet2 = get_sheet()
    temp, humidity = select_temp_and_humidity(sheet2)
    return f"待ってました！\n現在の気温は{round(temp)}℃、湿度は{round(humidity)}％やね"


def create_response_disc():
    sheet2 = get_sheet()
    disc = select_disc(sheet2)
    disc_message = ["ちょっと暑い", "暑すぎ！！\n服にカビ生やさないでよ",
                    "ちょっと寒いかも", "寒すぎ！！", "普通に快適やで"]
    if 80 > disc > 75:
        return disc_message[0]
    elif disc > 80:
        return disc_message[1]
    elif 55 < disc < 60:
        return disc_message[2]
    elif disc < 55:
        return disc_message[3]
    else:
        return disc_message[4]


def create_response_pre():
    sheet2 = get_sheet()
    pressure = select_press(sheet2)
    return f"今の気圧ね、{round(pressure, 1)}hPaやで"


def create_response_pre_state():
    sheet2 = get_sheet()
    pre_ave = select_press_ave(sheet2)
    if 1 >= pre_ave > 0:
        return "ゆったり上向きやね。"
    elif 1 < pre_ave:
        return "ぐんぐん上がっとるで！"
    elif -1 <= pre_ave < 0:
        return "ゆったり下降中やね。"
    elif -1 > pre_ave:
        return "ぐんぐん下がっとるで！"
    elif pre_ave == 0:
        return "ピタ～っと止まってるわ"


def create_response_followUp():
    sheet2 = get_sheet()
    follow_up = followUp_press(sheet2)
    if -1 <= follow_up <= 0:
        return f"直近1時間の変化は{round(follow_up, 1)}hPaやね。\n緩やかに下降中。"
    elif 0 <= follow_up <= 1:
        return f"直近1時間の変化は{round(follow_up, 1)}hPaやね。\n緩やかに上昇中。"
    elif 1 < follow_up < 4:
        return f"直近1時間の変化は{round(follow_up, 1)}hPaやね。\n急上昇中！お天気変わってへん？。"
    elif -1 > follow_up > -4:
        return f"直近1時間の変化は{round(follow_up, 1)}hPaやね。\n急降下中！お天気崩れてへん？。"
    elif 4 <= follow_up:
        return f"直近1時間の変化は{round(follow_up, 1)}hPaやね。\nって、超急上昇中やわ！！"
    elif -4 >= follow_up:
        return f"直近1時間の変化は{round(follow_up, 1)}hPaやね。\nって、超急降下！！天気荒れてへんよな！？"
    elif follow_up == 0:
        return "特に変化してないなぁ"


def sheet_update(record):
    sheet2, sheet3 = get_sheet_all()
    values = sheet2.get_all_records()
    length = sheet3.get_all_records()
    last = values[-1]
    sheet3.update(f"A{len(length) + 2}:L",
                  [[str(create_datetime()), float(last["temp"]), float(last["humidity"]), float(round(last["pressure"])), float(last["change_pre"]), float(record[5]), str(record[4]), str(record[1]), str(record[2]), str(record[3]), float(record[0]), str(record[6])]])


def create_message(my_comments):
    global botRes
    global record
    common_messages = ["気圧のこと色々わかるで！", "気温と湿度が分かるで", "どうしたん？",
                       "無駄使いはあかんで？", "今日は何を開発するん？", "変な事言わんとって！", "はよ学習機能つくってよ～"]
    wait_messages = ["行ってらっしゃい！気を付けてね！",
                     "早く帰ってきてよ！", "財布忘れてへん？", "ちゃんとマスク持った？"]

    # データゲット
    if "気温わかる？" in my_comments:
        botRes = create_response_text()
    elif "快適？" in my_comments:
        botRes = create_response_disc()
    elif "気圧調べて" in my_comments:
        botRes = create_response_pre()
    elif "状況は？" in my_comments:
        botRes = create_response_pre_state()
    elif "直近の変化は？" in my_comments:
        botRes = create_response_followUp()

    # お留守番実行
    elif "行ってきます" in my_comments:
        botRes = wait_messages[random.randint(0, 3)]
        subprocess.Popen(["python3", "facial_req_bot.py"],
                         cwd="./facial_recognition")

    #　グラフゲット
    elif "気圧グラフある？" in my_comments:
        messages = ImageSendMessage(original_content_url=PRESS_URL,
                                    preview_image_url=PRESS_URL)
        line_bot_api.push_message(USER_ID, messages=messages)
        time.sleep(2)
        botRes = "送った！直近2時間の変化が見れるよ"
    elif "気温グラフある？" in my_comments:
        messages = ImageSendMessage(original_content_url=TEMP_URL,
                                    preview_image_url=TEMP_URL)
        line_bot_api.push_message(USER_ID, messages=messages)
        time.sleep(2)
        botRes = "メカ使いが荒い・・・送ったよ！\n直近二時間のデータまとめといたからね。"

    # チートシート
    elif "コマンド忘れた" in my_comments:
        botRes = "え～！！はよ覚えてよ・・・\n\n気温わかる？:温湿度を見ます\n快適？:不快指数を見ます\n気圧調べて:気圧を見ます\n状況は？:気圧の傾向を見ます\n直近の変化は？:直近1時間の気圧変化を見ます\n行ってきます:お留守番モードに入ります\n気圧or気温グラフある？:リアルタイムグラフ送ります\n釣れた:釣果報告書作ります\nおやすみ:本体の電源を切ります\n\nって私に言わすな！リアリティに欠けるやん・・・ちゃんと覚えて！"
    elif "出来る事なんだっけ？" in my_comments:
        botRes = "今出来ることは\n\n・不快指数から暑い、寒いを判断して連絡するで。ブーブー言わんと快適に戻ったらちゃんと言うから。\n\n・気圧の大きな変化があれば連絡するで。天気の変化や時合の目安にして。\n\n・気圧の上昇、下降の傾向が切り変わったら連絡するわ。\n\n現在のデータやグラフが欲しい時は連絡してな！"
    elif my_comments in "おやすみ":
        botRes = "おやすみなさい！また明日ね～！"

    # 釣果記録モード
    elif my_comments in ["釣れた", "釣れたで"]:
        botRes = "すごいやん！\nほな自慢タイムやね！\nサイズはどうやった？"
    elif botRes in ["すごいやん！\nほな自慢タイムやね！\nサイズはどうやった？", "ほなもっぺんいくで！\nサイズどんぐらいやっけ？"]:
        record = []
        record.append(my_comments)
        botRes = "ええやん、ところでいまどこおるん？"
    elif "ええやん、ところでいまどこおるん？" in botRes:
        record.append(my_comments)
        botRes = "ようそこで釣れたな。どのルアーで釣れたん！？"
    elif "ようそこで釣れたな。どのルアーで釣れたん！？" in botRes:
        record.append(my_comments)
        botRes = "なるほどなぁ。どんな釣り方してたん？"
    elif "なるほどなぁ。どんな釣り方してたん？" in botRes:
        record.append(my_comments)
        botRes = "ほうほう、ところでそっちの天気は？"
    elif "ほうほう、ところでそっちの天気は？" in botRes:
        record.append(my_comments)
        botRes = "あ、そういえば水温測った？"
    elif "あ、そういえば水温測った？" in botRes:
        record.append(my_comments)
        botRes = "OK！ほな決めセリフをどうぞ～！"
    elif "OK！ほな決めセリフをどうぞ～！" in botRes:
        record.append(my_comments)
        botRes = "オッケー、ほんまよう釣ったな！\nほな報告書作っとくから確認だけ頼むね。\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(
            record)
    elif botRes in ["オッケー、ほんまよう釣ったな！\nほな報告書作っとくから確認だけ頼むね。\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(record), "私まだアホなん知ってるやろ！しゃぁないもっぺんいくで！\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(record)] and my_comments in "よろしく":
        sheet_update(record)
        record = init_record(record)
        botRes = "ほな作っとくね～！\n役に立ちそうなデータはこっちでまとめとくわ！"
    elif botRes in ["オッケー、ほんまよう釣ったな！\nほな報告書作っとくから確認だけ頼むね。\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(record), "私まだアホなん知ってるやろ！しゃぁないもっぺんいくで！\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(record)] and my_comments in "やり直す":
        record = init_record(record)
        botRes = "ほなもっぺんいくで！\nサイズどんぐらいやっけ？"
    elif botRes in ["オッケー、ほんまよう釣ったな！\nほな報告書作っとくから確認だけ頼むね。\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(record), "私まだアホなん知ってるやろ！しゃぁないもっぺんいくで！\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(record)] and my_comments not in ["よろしく", "やり直す", "やめとく"]:
        botRes = "私まだアホなん知ってるやろ！しゃぁないもっぺんいくで！\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(
            record)
    elif botRes in ["オッケー、ほんまよう釣ったな！\nほな報告書作っとくから確認だけ頼むね。\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(record), "私まだアホなん知ってるやろ！しゃぁないもっぺんいくで！\nサイズ:{0[0]}cm\n場所:{0[1]}\nヒットルアー:{0[2]}\nメソッド:{0[3]}\n天気:{0[4]}\n水温:{0[5]}℃\nコメント:{0[6]}\nこれで報告書作っといていい？".format(record)] and my_comments in "やめとく":
        record = init_record(record)
        botRes = "ほな話だけ聞いといたるわ。"

    # コモンメッセージ
    else:
        botRes = common_messages[random.randint(0, 6)]

    return botRes


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    my_comments = event.message.text

    comment = create_message(my_comments)

    line_bot_api.reply_message(
        event.reply_token, TextSendMessage(text=comment))

    if comment == "おやすみなさい！また明日ね～！":
        subprocess.run(["sudo", "shutdown", "now"])


if __name__ == "__main__":
    app.run()
