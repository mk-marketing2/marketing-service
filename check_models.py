import os
import google.generativeai as genai

# ★環境変数からAPIキーを取得します
API_KEY = os.environ.get("GEMINI_API_KEY", "")

genai.configure(api_key=API_KEY)

print("--- 利用可能なモデル一覧 ---")
try:
    with open("models_out.txt", "w", encoding="utf-8") as f:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                f.write(f"表示名: {m.display_name}\n")
                f.write(f"ID (コードに使う名前): {m.name}\n")
                f.write("-" * 20 + "\n")
except Exception as e:
    print(f"エラーが発生しました: {e}")