from __future__ import unicode_literals
import os
from flask import Flask, request, abort, render_template
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import FollowEvent, UnfollowEvent, PostbackEvent, MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, FlexSendMessage
import random
import urllib
import psycopg2
import datetime
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ['CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['CHANNEL_SECRET'])

# 導入主頁
@app.route("/")
def home():
    return render_template('home.html')

# 接收 LINE 的資訊
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
        
    return 'OK'

# 加入好友
@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    my_headers = {"Authorization": f"Bearer {os.environ['DATABASE_TOKEN']}"}
    response = requests.get(f'https://api.line.me/v2/bot/profile/{user_id}', headers = my_headers)
    jsonResponse = response.json()

    if response.status_code == requests.codes.ok:
        DATABASE_URL = os.environ['DATABASE_URL']
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()

        # 判斷資料是否存在
        postgres_select_query = f"""SELECT * FROM user_info WHERE user_id = %s"""
        cursor.execute(postgres_select_query, (user_id,))
        result = bool(cursor.rowcount)

        if result:
            postgres_update_query = f"""UPDATE user_info SET name = '{jsonResponse['displayName']}', follow_status = 'true' WHERE user_id = %s"""
            cursor.execute(postgres_update_query, (user_id,))
        else:
            table_columns = '(user_id, name, pic_url, follow_status, created_on)'
            postgres_insert_query = f"""INSERT INTO user_info {table_columns} VALUES (%s, %s, %s, %s, %s);"""
            info = (user_id, jsonResponse['displayName'], jsonResponse['pictureUrl'], 'true', datetime.datetime.now())
            cursor.execute(postgres_insert_query, info)
        
        conn.commit()
        conn.close()
        cursor.close()
    else:
        print("加入好友, 讀取好友資料失敗")


# 封鎖好友
@handler.add(UnfollowEvent)
def handle_unfollow(event):
    user_id = event.source.user_id
    
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    # 判斷資料是否存在
    postgres_select_query = f"""SELECT * FROM user_info WHERE user_id = %s"""
    cursor.execute(postgres_select_query, (user_id,))
    result = bool(cursor.rowcount)

    if result:
        postgres_update_query = f"""UPDATE user_info SET follow_status = 'false' WHERE user_id = %s"""
        cursor.execute(postgres_update_query, (user_id,))
        conn.commit()
        conn.close()
    else:
        my_headers = {"Authorization": f"Bearer {os.environ['DATABASE_TOKEN']}"}
        response = requests.get(f'https://api.line.me/v2/bot/profile/{user_id}', headers = my_headers)
        jsonResponse = response.json()
        table_columns = '(user_id, name, pic_url, follow_status, created_on)'
        postgres_insert_query = f"""INSERT INTO user_info {table_columns} VALUES (%s, %s, %s, %s, %s);"""
        info = (user_id, jsonResponse['displayName'], jsonResponse['pictureUrl'], 'false', datetime.datetime.now())
        cursor.execute(postgres_insert_query, info)
    
    cursor.close()

# google 搜圖
@handler.add(MessageEvent, message=TextMessage)
def google_isch(event):
    try:
        op = webdriver.ChromeOptions()
        op.binary_location = os.environ.get("GOOGLE_CHROME_BIN")
        op.add_argument("--headless")
        op.add_argument("--disable-dev-shm-usage")
        op.add_argument("--no-sandbox")

        driver = webdriver.Chrome(executable_path=os.environ.get("CHROMEDRIVER_PATH"), options=op)

        message = event.message.text
        if event.message.text == '早安':
            message = '早安圖'
        elif event.message.text == '祝福':
            message = '祝福圖'

        q_string = {'tbm': 'isch', 'q': message}
        url = f"https://www.google.com/search?{urllib.parse.urlencode(q_string)}/"
        driver.get(url)

        img_list = driver.find_elements_by_xpath("//img[@class='rg_i Q4LuWd']")
        print(f'img_list size: {len(img_list)}')

        img_src = ''
        while img_src.find("http") == -1:
            img = img_list[random.randint(0, len(img_list))]
            ActionChains(driver).move_to_element(img).click().perform()
            img_src = driver.find_element_by_xpath("//img[@class='n3VNCb']").get_attribute('src')
        driver.quit()
        print(f'imgSrc: {img_src}')

        line_bot_api.reply_message(
            event.reply_token,
            ImageSendMessage(
                original_content_url=img_src, 
                preview_image_url=img_src
            )
        )
    except Exception as e:
        reply = f'很抱歉，找不到符合「{event.message.text}」關鍵字的圖片'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        print(f'error: {e}')
        pass

if __name__ == "__main__":
    app.run()