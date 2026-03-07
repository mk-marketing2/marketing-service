import os
import datetime
import time
import random
import json
import urllib.request
import urllib.error
import ssl
from tavily import TavilyClient
import tweepy

# ==========================================
# 🔑 設定エリア（最新モデル: Sonnet 4-6 指定）
# ==========================================

# 1. Anthropic API Key
# 環境変数から取得します（Streamlit CloudではSecretsから自動で設定されます）
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# 2. Tavily & Twitter Keys
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

# ★ここが最重要ポイント！
# Workbenchに表示されている最新のモデルIDを直接指定します
MODEL_NAME = "claude-sonnet-4-6" 

SAVE_DIR = "articles"
CHECK_INTERVAL_HOURS = 6

TOPIC_LIST = [
    "飲食店 倒産 理由 2026",
    "外食産業 トレンド Z世代",
    "行動経済学 マーケティング 飲食店",
    "個人経営 飲食店 集客 成功事例",
    "飲食店 DX 配膳ロボット 導入効果",
]

# ==========================================

tavily = TavilyClient(api_key=TAVILY_API_KEY)

def call_claude_direct(user_message, system_prompt="あなたは優秀なAIアシスタントです。"):
    """ライブラリを介さず、指定のモデル名で直接Anthropicにリクエストを送る"""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": MODEL_NAME,
        "max_tokens": 4000,
        "temperature": 0.7,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}]
    }
    
    json_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=json_data, headers=headers, method="POST")
    
    # SSL証明書エラー対策
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=context) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            return res_body['content'][0]['text']
    except urllib.error.HTTPError as e:
        print(f"❌ API Error: {e.code}")
        print(f"詳細: {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"❌ 通信エラー: {e}")
        return None

def fetch_content(keyword):
    print(f"🔍 Tavily検索中: {keyword}")
    try:
        res = tavily.search(query=keyword, search_depth="advanced", max_results=3)
        return res['results'][0] if res['results'] else None
    except: return None

def post_to_x(title, summary, link):
    print("🐦 X投稿中...")
    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY, consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN, access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
        )
        client.create_tweet(text=f"【新着記事】{title}\n\n{summary}...\n\n👇 続き\n{link}")
        print("✅ 投稿成功")
    except Exception as e: print(f"❌ X失敗: {e}")

if __name__ == "__main__":
    print(f"--- 🚀 全自動ロボット起動（Model: {MODEL_NAME}） ---")
    
    # 疎通テスト
    print("📡 接続テスト中...")
    test = call_claude_direct("Hello, are you active?")
    if test:
        print(f"✅ 成功！返信: {test[:30]}...")
    else:
        print("❌ 失敗。上記のエラー詳細を確認してください。")
        exit()

    while True:
        try:
            print(f"\n[{datetime.datetime.now().strftime('%H:%M')}] 記事生成開始...")
            keyword = random.choice(TOPIC_LIST)
            news = fetch_content(keyword)
            
            if news:
                system_p = "あなたは辛口の数学マーケターです。論理的に飲食店経営を語ってください。"
                prompt = f"ニュースタイトル: {news['title']}\n内容: {news['content'][:5000]}\nこれをもとにブログを書いて。"
                
                article = call_claude_direct(prompt, system_p)
                if article:
                    # 保存
                    if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)
                    filename = f"{SAVE_DIR}/{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                    with open(filename, "w", encoding="utf-8") as f: f.write(article)
                    print(f"✅ 保存完了: {filename}")
                    
                    # 要約と投稿
                    summary = call_claude_direct(f"40文字で要約して: {article[:1000]}")
                    post_to_x(news['title'], summary, "https://your-blog-link.com")
            
            print(f"💤 {CHECK_INTERVAL_HOURS}時間待機します...")
            time.sleep(CHECK_INTERVAL_HOURS * 3600)
            
        except Exception as e:
            print(f"❌ ループエラー: {e}")
            time.sleep(60)