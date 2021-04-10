from logging import makeLogRecord
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from linebot import LineBotApi
from linebot.models import TextSendMessage
import json
import smbus
import RPi.GPIO as GPIO
import dht11
import time
import datetime
import pandas as pd

file = open("info.json", "r")
info = json.load(file)

CHANNEL_ACCESS_TOKEN = info["CHANNEL_ACCESS_TOKEN"]
SPREADSHEET_KEY = info["SPREADSHEET_KEY"]
USER_ID = info["USER_ID"]
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)


# 気圧センサ各レジスタアドレス
ADDR = 0x5C
CTRL_REG1 = 0x20
PRE_OUT_XL = 0x28
# 書き込みデータ
WRITE_REG1 = 0x90
MASK_DATA = 0x80

# 不快指数適正範囲最大値、最低値
ALART_DISC_MIN = 60
ALART_DISC_MAX = 75

# 気圧変化閾値
ALART_PRE_MIN = -1
ALART_PRE_MAX = 1

# 三日分のデータ
DATA_MAX = 864

GPIO.setwarnings(True)
GPIO.setmode(GPIO.BCM)

# 気温センサインスタンス
instance = dht11.DHT11(pin=18)

# 気圧センサ初期化
bus = smbus.SMBus(1)
bus.write_byte_data(ADDR, CTRL_REG1, WRITE_REG1)

# 定期的にシートを更新しないとエラーになる？


def get_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        "line-bot-project1-0a7f2b46fc9e.json", scope)
    gc = gspread.authorize(credentials)
    workbook = gc.open_by_key(SPREADSHEET_KEY)
    sh1 = workbook.worksheet("シート1")
    sh2 = workbook.worksheet("シート2")
    return sh1, sh2

# 不快指数が範囲外


def invalid_disc(disc):
    return disc < ALART_DISC_MIN or ALART_DISC_MAX < disc

# 気圧変化が大きい場合


def change_pressure_term(change_pre):
    return change_pre < ALART_PRE_MIN or ALART_PRE_MAX < change_pre

# 気圧の変化傾向が変わった場合


def change_pre_state(before_pre_ave, pre_ave):
    return (before_pre_ave <= 0 and 0 <= pre_ave) or (before_pre_ave >= 0 and 0 >= pre_ave)

# タイムスタンプ生成


def create_datetime():
    date = datetime.datetime.now()
    date = date.replace(microsecond=0)
    return date

# 温湿度データ取得


def get_temp(data):
    result = instance.read()
    if result.is_valid():
        temp = result.temperature
        humidity = result.humidity
        print("Temperature: %-3.1f C" % result.temperature)
        print("Humidity: %-3.1f %%" % result.humidity)
    else:
        # たまにバグってデータ取れないのでその時は前回値を使う
        temp = float(data[-1]["temp"])
        humidity = float(data[-1]["humidity"])
        print("Temperature: %-3.1f C" % temp)
        print("Humidity: %-3.1f %%" % humidity)
    return temp, humidity

# 不快指数算出


def disconfort_index(temp, humidity):
    temp = float(temp)
    humidity = float(humidity)
    return 0.81*temp + 0.01*humidity*(0.99*temp-14.3)+46.3

# 気圧データ取得


def get_pressure():
    p_data = bus.read_i2c_block_data(ADDR, PRE_OUT_XL | MASK_DATA, 3)
    pre = (p_data[2] << 16 | p_data[1] << 8 | p_data[0]) / 4096.0
    print("%.2f hpa" % pre)
    return pre

# 気圧変化平均値の生成


def make_pre_ave(data):
    ps = [d.get("change_pre") for d in data[-12:]]
    ave = sum(ps)/len(ps)
    return ave

# スプシに送信するデータをまとめて生成


def create_dataset(data):
    tp, hm = get_temp(data)
    pr = get_pressure()
    ch_pr = pr - (data[-12]["pressure"])
    dc = disconfort_index(tp, hm)
    pr_ave = make_pre_ave(data)
    return tp, hm, pr, ch_pr, dc, pr_ave

# 不快指数が適正範囲外になったら通知


def send_temp_message(data, temp, disc):
    if not invalid_disc(float(data[-1]["disconfort"])):
        if disc < ALART_DISC_MIN:
            messages = TextSendMessage(
                text=f"寒くなって来たよ・・・\n今{round(temp)}℃です～")
            line_bot_api.push_message(USER_ID, messages=messages)
        if disc > ALART_DISC_MAX:
            messages = TextSendMessage(
                text=f"暑くなって来たよ・・・\n今{round(temp)}℃です～")
            line_bot_api.push_message(USER_ID, messages=messages)

# 不快指数が適正範囲外から戻ったら通知


def send_conf_disc_message(data):
    if invalid_disc(float(data[-1]["disconfort"])):
        messages = TextSendMessage(text="快適な状態に戻ったよ！")
        line_bot_api.push_message(USER_ID, messages=messages)

# 気圧が大きく変化したら通知


def send_pre_message(data, change_pre):
    before = float(data[-1]["change_pre"])
    if not change_pressure_term(before):
        if change_pre > ALART_PRE_MAX:
            messages = TextSendMessage(
                text=f"気圧が大きく上がったよ！\n直近で{round(change_pre, 1)}hPa変化したけど、何か変化あった？")
            line_bot_api.push_message(USER_ID, messages=messages)
        if change_pre < ALART_PRE_MIN:
            messages = TextSendMessage(
                text=f"気圧が大きく下がったよ！\n直近で{round(change_pre, 1)}hPa変化したから、お天気悪くなるかも。")
            line_bot_api.push_message(USER_ID, messages=messages)

# 気圧の傾向が変化したら通知


def send_change_message(pre_ave):
    if pre_ave >= 0:
        messages = TextSendMessage(
            text="気圧が上昇傾向に変わったよ！")
        line_bot_api.push_message(USER_ID, messages=messages)
    if pre_ave <= 0:
        messages = TextSendMessage(
            text="気圧が下降傾向に変わったよ！一気に下がるようならまた連絡するね")
        line_bot_api.push_message(USER_ID, messages=messages)


# スプシの古いデータ削除、消した分の行を追加
def delete_rows(sheet1):
    sheet1.add_rows(1)
    sheet1.delete_rows(2)

# スプシにデータを書き込み


def sheet_update(sheet1, column, temp, humidity, disc, pressure, change_pre):
    sheet1.update(f"A{column + 2}:F",
                  [[str(create_datetime()), temp, humidity,  int(disc), round(pressure, 1), round(change_pre, 1)]])

# 別シートに2時間分のデータをコピペ


def sheet_copy(sheet2, data, temp, humidity, disc, pressure, change_pre):
    del(data[0:841])
    df = pd.DataFrame(data)
    sheet2.update([df.columns.values.tolist()] + df.values.tolist())
    sheet2.update(f"A25:F25",
                  [[str(create_datetime()), temp, humidity, int(disc), round(pressure, 1), round(change_pre, 1)]])


def main():
    print("System enable ...")
    time_buff = 0
    count = 0
    before_pre_ave = 0
    while True:
        while(time.time() - time_buff < 1):
            pass
        time_buff = time.time()
        count += 1
        if (count == 1) or (count % 300) == 0:
            sheet1, sheet2 = get_sheet()
            data = sheet1.get_all_records()
            column = len(data)
            if column >= DATA_MAX:
                delete_rows(sheet1)
                column -= 1

            temp, humidity, pressure, change_pre, disc, pre_ave = create_dataset(
                data)

            if change_pressure_term(change_pre):
                send_pre_message(data, change_pre)

            if invalid_disc(disc):
                send_temp_message(data, temp, disc)

            if not invalid_disc(disc):
                send_conf_disc_message(data)

            if change_pre_state(before_pre_ave, pre_ave):
                if(count != 1):
                    send_change_message(pre_ave)

            sheet_update(sheet1, column, temp, humidity,
                         disc, pressure, change_pre)

            sheet_copy(sheet2, data, temp, humidity,
                       disc, pressure, change_pre)

            before_pre_ave = pre_ave
        if (count % 3600) == 0:
            count = 1


if __name__ == "__main__":
    main()
