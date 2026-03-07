import anthropic

import os

# 環境変数からキーを取得します
KEY = os.environ.get("ANTHROPIC_API_KEY", "")

print(f"現在のライブラリバージョン: {anthropic.__version__}")

try:
    client = anthropic.Anthropic(api_key=KEY.strip())
    print("📡 Claudeに接続中...")
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello! Can you hear me?"}]
    )
    print("✅ 成功しました！返事: " + message.content[0].text)

except Exception as e:
    print(f"❌ エラー発生: {e}")