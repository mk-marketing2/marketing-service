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
from dotenv import load_dotenv

load_dotenv()

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

def post_to_x(tweet_text):
    print("🐦 X投稿中...")
    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY, consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN, access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
        )
        client.create_tweet(text=tweet_text)
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
                prompt = f"ニュースタイトル: {news['title']}\n内容: {news['content'][:5000]}\nこれをもとにブログを書いて。ただし、記事のタイトル（# 見出し1）は出力に含めず、本文（## 見出し2以降）から書き始めてください。"
                
                article = call_claude_direct(prompt, system_p)
                if article:
                    # Next.js用のFrontmatter（YAML）を作成
                    date_str = datetime.datetime.now().strftime('%Y-%m-%d')
                    summary_text = call_claude_direct(f"次の記事を40文字以内で要約して: {article[:1000]}")
                    clean_summary = summary_text.replace('"', '').replace('\n', '') if summary_text else "最新のマーケティング情報"
                    title_prompt = f"次の記事の魅力的で簡潔なタイトルを30文字以内で作成してください。出力はタイトルのみとし、カギ括弧等の装飾は含めないで: {article[:1000]}"
                    title_text = call_claude_direct(title_prompt)
                    clean_title = title_text.replace('"', '').replace('\n', '') if title_text else news['title'].replace('"', '')

                    tweet_prompt = f"""次の記事文案をもとに、専門家としての鋭い考察を感じさせる「インサイト型」のX（Twitter）投稿文を作成してください。

[条件]
- 文字数はトータルで110文字以内（URL用の文字数を残すため）
- 「ボットによる新着通知」ではなく「専門家による分析のシェア」というスタンス
- 語尾は「〜です」「〜と言えます」等、知的で落ち着いたトーン
- 冒頭は【業界分析】や【経営の視点】等の角括弧から始め、核心的なテーマを提示
- 中段は数字やキーワードを引用し、意味を要約
- 結びは「続きはサイトで詳しく読み解きます」とする
- ハッシュタグは文末に #カチスジ #飲食店経営 
- スマホで見やすいよう適度な改行を入れること

[記事文案]
{article[:1500]}"""
                    tweet_text = call_claude_direct(tweet_prompt)
                    if not tweet_text:
                        tweet_text = "【経営の視点】最新の業界動向と経営インサイトを更新しました。\n\n続きはサイトで詳しく読み解きます。\n\n#カチスジ #飲食店経営"

                    frontmatter = f"""---
title: "{clean_title}"
date: "{date_str}"
excerpt: "{clean_summary}"
---

"""
                    
                    # 保存先をNext.jsのcontentフォルダに変更
                    NEXTJS_CONTENT_DIR = "marketing-site-next/src/content"
                    if not os.path.exists(NEXTJS_CONTENT_DIR): 
                        os.makedirs(NEXTJS_CONTENT_DIR)
                        
                    slug = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{NEXTJS_CONTENT_DIR}/{slug}.md"
                    
                    with open(filename, "w", encoding="utf-8") as f: 
                        f.write(frontmatter + article)
                    print(f"✅ 保存完了: {filename}")
                    
                    # --- GitHubへ自動Push ---
                    print("🚀 GitHubへ自動デプロイ中...")
                    import subprocess
                    try:
                        # marketing-site-next フォルダ内でgitコマンドを実行
                        repo_dir = "marketing-site-next"
                        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
                        subprocess.run(["git", "commit", "-m", f"Auto-publish: {clean_title}"], cwd=repo_dir, check=True)
                        subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=True)
                        print("✅ GitHubへの自動デプロイ完了")
                    except Exception as git_err:
                        print(f"❌ Git自動デプロイ失敗: {git_err}")

                    # Xへ投稿
                    article_url = f"https://marketing-site-next.vercel.app/articles/{slug}"
                    final_tweet_text = f"{tweet_text}\n{article_url}"
                    post_to_x(final_tweet_text)
            
            print(f"💤 {CHECK_INTERVAL_HOURS}時間待機します...")
            time.sleep(CHECK_INTERVAL_HOURS * 3600)
            
        except Exception as e:
            print(f"❌ ループエラー: {e}")
            time.sleep(60)