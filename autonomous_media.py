import os
import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
import datetime
import time
import json
import subprocess
import urllib.request
import urllib.error
import ssl
import httpx
import re
from dotenv import load_dotenv

import tweepy
from crewai import Agent, Task, Crew, Process
from crewai_tools import TavilySearchTool

# ---------------------------------------------------------
# SSL & HTTPX Bypasses
# ---------------------------------------------------------
orig_init = httpx.Client.__init__
httpx.Client.__init__ = lambda self, *a, **kw: orig_init(self, *a, **{**kw, 'verify': False})
orig_ainit = httpx.AsyncClient.__init__
httpx.AsyncClient.__init__ = lambda self, *a, **kw: orig_ainit(self, *a, **{**kw, 'verify': False})

# ---------------------------------------------------------
# Environment & Configuration
# ---------------------------------------------------------
load_dotenv()
os.environ["OPENAI_API_KEY"] = "NA"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")
SITE_URL = os.environ.get("SITE_URL", "https://marketing-site-next-sirn.vercel.app").rstrip('/')

MODEL_NAME = "claude-sonnet-4-6" 
LLM_STRING = "anthropic/claude-sonnet-4-6"

# 1. ターゲットのリスト化 (100件の駅名 × トレンド・ニッチ業態)
TARGETS = [
    # --- 東京：都心・ビジネスエリア ---
    ("新橋駅", "立ち食い高級寿司"), ("新橋駅", "ネオ大衆酒場"), ("新橋駅", "会員制サウナ併設バー"),
    ("銀座駅", "ヴィーガン向けガストロノミー"), ("銀座駅", "日本茶ペアリング特化型フレンチ"), ("銀座駅", "完全個室のジン専門店"),
    ("東京駅", "地方創生アンテナショップ型バル"), ("東京駅", "朝食特化型高級カフェ"), ("東京駅", "一人焼肉（A5ランク限定）"),
    ("神田駅", "クラフトビール×本格スパイスカレー"), ("神田駅", "昭和レトロ純喫茶（Z世代向け再解釈）"),
    ("秋葉原駅", "eスポーツ完全没入型カフェ"), ("秋葉原駅", "コンカフェ×本格ジビエ"), ("秋葉原駅", "ガジェット愛好家向けDIYバー"),
    ("品川駅", "出張族向け「30分完結」高級和食"), ("品川駅", "早朝営業の薬膳スープ専門店"),
    ("五反田駅", "立ち飲みワイン×ホルモン"), ("五反田駅", "ITワーカー向けCBDカフェ"), ("大崎駅", "ファミリー向けシェアキッチン型レストラン"),

    # --- 東京：副都心・トレンド発信地 ---
    ("新宿駅 東口", "深夜パフェ専門店"), ("新宿駅 西口", "おひとりさま専用・黙食ジンギスカン"),
    ("新宿三丁目駅", "ナチュールワイン×おでん"), ("歌舞伎町", "モクテル（ノンアル）専門ラウンジ"),
    ("渋谷駅", "シーシャ×コワーキングスペース"), ("渋谷駅", "レコード音楽×立ち飲みクラフトジン"),
    ("奥渋エリア", "北欧風ヴィーガンスイーツ"), ("原宿駅", "台湾レトロスイーツ＆台湾茶"),
    ("表参道駅", "昆虫食アレンジ・フュージョン"), ("表参道駅", "完全キャッシュレス・パーソナライズサラダ"),
    ("恵比寿駅", "スタンディング・オイスターバー"), ("恵比寿駅", "スナック（20代女性向けアップデート版）"),
    ("中目黒駅", "中東料理（メゼ）×ナチュールワイン"), ("中目黒駅", "愛犬同伴特化型・高級デリ"),
    ("代官山駅", "グルテンフリー専門・オーガニックベーカリー"), ("六本木駅", "シーフード特化型メキシカン"),
    ("赤坂駅", "接待特化型・全室プロジェクションマッピング和食"), ("麻布十番駅", "韓国宮廷料理×モダンアレンジ"),

    # --- 東京：カルチャー・住宅街・ディープスポット ---
    ("下北沢駅", "スパイスカレー×古着屋併設"), ("下北沢駅", "クラフトコーラ専門店"),
    ("高円寺駅", "アジアン屋台村風フードホール"), ("高円寺駅", "レコード視聴特化型・深煎り珈琲店"),
    ("吉祥寺駅", "絵本の世界観・没入型カフェ"), ("吉祥寺駅", "クラフトサケ（ドブロク）醸造所併設パブ"),
    ("西荻窪駅", "フレンチ惣菜・量り売りバル"), ("中野駅", "サブカル特化・ボードゲーム×クラフトビール"),
    ("赤羽駅", "センベロ×フレンチ"), ("北千住駅", "路地裏古民家・台湾朝食"),
    ("錦糸町駅", "ガチ中華（東北地方特化）"), ("清澄白河駅", "ロースタリーカフェ×盆栽ギャラリー"),
    ("蔵前駅", "Bean to Barチョコレート×ウイスキーバー"), ("浅草駅", "インバウンド向け「おにぎり×高級茶」"),
    ("蒲田駅", "羽根つき餃子×世界のクラフトビール"), ("三軒茶屋駅", "発酵食品特化型おばんざい"),
    ("二子玉川駅", "グランピング体験型テラスレストラン"), ("自由が丘駅", "ギルトフリー（低糖質）パティスリー"),

    # --- 関東近郊・ベッドタウン ---
    ("横浜駅", "台湾夜市風ビアガーデン"), ("みなとみらい駅", "プロテイン＆アサイーボウル特化型カフェ"),
    ("野毛エリア", "ホルモン焼き×立ち飲みシャンパン"), ("鎌倉駅", "鎌倉野菜特化・ヴィーガン定食"),
    ("川崎駅", "韓国ドラム缶焼肉"), ("武蔵小杉駅", "キッズスペース完備・ワインバル"),
    ("大宮駅", "埼玉地酒×深谷ねぎ料理専門店"), ("浦和駅", "完全予約制・うなぎフュージョン"),
    ("千葉駅", "千葉県産ジビエ特化型ビストロ"), ("柏駅", "裏路地・隠れ家シーシャカフェ"),

    # --- 関西：商業中心地 ---
    ("大阪 梅田駅", "立ち食いフレンチ"), ("大阪 梅田駅", "夜アイス・パフェ専門店"),
    ("大阪 難波駅", "インバウンド向け「たこ焼き×シャンパン」"), ("心斎橋駅", "完全会員制・住所非公開パフェバー"),
    ("大阪 京橋駅", "朝飲み対応・海鮮立ち飲み"), ("天王寺駅", "串カツ×クラフトビールペアリング"),
    ("京都 河原町駅", "抹茶×モクテル専門バー"), ("京都 烏丸駅", "京町家改装・ヴィーガンおばんざい"),
    ("京都 祇園四条駅", "訪日客向け・ハラール対応すき焼き"), ("神戸 三宮駅", "神戸牛・立ち食いステーキ"),
    ("神戸 元町駅", "英国風アフタヌーンティー・スタンド"),

    # --- 地方中枢都市・観光都市 ---
    ("札幌 すすきの駅", "シメパフェ×北海道産クラフトジン"), ("札幌 大通駅", "スープカレー×サウナ併設"),
    ("仙台駅", "牛タン×ナチュラルワイン"), ("仙台 国分町", "東北6県日本酒・立ち飲みテイスティング"),
    ("新潟駅", "日本酒ペアリング・フレンチ"), ("金沢駅", "金沢おでん×次世代大衆酒場"),
    ("名古屋 栄駅", "名古屋めし（味噌カツ・手羽先）×クラフトビール"), ("名古屋 名駅", "スパイシー台湾ラーメン風つけ麺"),
    ("大須観音駅", "韓国屋台スイーツテイクアウト"), ("広島駅", "牡蠣×立ち飲みレモンサワー特化"),
    ("福岡 博多駅", "もつ鍋×一人用個室"), ("福岡 天神駅", "ネオ屋台（屋台のモダンアップデート）"),
    ("福岡 薬院駅", "スパイスカレー×レコードバー"), ("那覇 国際通り", "琉球ヴィーガン料理"),
    ("那覇 おもろまち駅", "沖縄クラフトラム専門店"),

    # --- 少しエッジの効いたニッチ・未来型業態 ---
    ("豊洲駅", "完全無人・AI決済カフェ"), ("虎ノ門ヒルズ駅", "朝活特化・プロテインスムージー＆マインドフルネス"),
    ("下北沢駅", "スマホ使用禁止・デジタルデトックス喫茶"), ("日本橋駅", "CBD入り和菓子と抹茶のペアリング"),
    ("渋谷駅", "Z世代向け・ノンアルコール「スナック」"), ("高田馬場駅", "ガロニ（付け合わせ）主役のフレンチ"),
    ("池袋駅 東口", "推し活特化・カラーカスタマイズ可能なアフタヌーンティー"), ("新宿御苑前駅", "漢方・薬膳酒専門スタンディングバー"),
    ("上野駅", "インバウンド向け・和牛100%「立ち食いハンバーガー」"), ("町田駅", "昭和レトロ・クリームソーダ専門店")
]

NEXTJS_CONTENT_DIR = "marketing-site-next/src/content"

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def call_claude_json(system_prompt, user_message):
    """ライブラリを介さず、JSON出力を期待して直接Anthropicにリクエストを送る"""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": MODEL_NAME,
        "max_tokens": 1000,
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
            content = res_body['content'][0]['text']
            
            # JSONブロックのみを抽出する簡易処理
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx+1]
                return json.loads(json_str)
            else:
                return json.loads(content)
                
    except Exception as e:
        print(f"❌ JSON抽出エラー: {e}")
        return None

def post_to_x(tweet_text):
    print("🐦 X投稿中...")
    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY, consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN, access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
        )
        client.create_tweet(text=tweet_text)
        print("✅ 投稿成功")
    except Exception as e: 
        print(f"❌ X失敗: {e}")

# ---------------------------------------------------------
# Main Execution Loop
# ---------------------------------------------------------
def main():
    print("--- 🚀 Autonomous Media Agent Started ---")
    
    # Target を無限ループで処理する
    while True:
        for area, business_type in TARGETS:
            print(f"\n=========================================")
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ターゲット処理開始: {area} × {business_type}")
            print(f"=========================================")
            
            try:
                # 2. CrewAIの実行
                search_tool = TavilySearchTool()

                researcher = Agent(
                    role='シニア・マーケットリサーチャー',
                    goal='指定されたエリアと業態に関する、リアルな最新の市場データをウェブ検索で収集する',
                    backstory='あなたは外食産業のデータ分析のプロです。推測ではなく、必ず検索ツールを使って「実在する店舗名」「価格帯」「口コミの不満点」などの生きたデータを収集します。',
                    verbose=True,
                    allow_delegation=False,
                    tools=[search_tool],
                    llm=LLM_STRING,
                    function_calling_llm=LLM_STRING
                )

                strategist = Agent(
                    role='チーフ・マーケティング・オフィサー（確率思考の戦略家）',
                    goal='リサーチャーのリアルなデータに基づき、プレファレンスを高める勝筋を導き出す',
                    backstory='あなたは確率思考を駆使する戦略家です。リサーチャーが集めた「実在する競合店」のデータから、論理的な根拠で勝てるコンセプトを提案します。データが推測であれば再調査を指示します。',
                    verbose=True,
                    allow_delegation=True,
                    llm=LLM_STRING,
                    function_calling_llm=LLM_STRING
                )

                task1 = Task(
                    description=f'検索ツールを使用して、「{area}」の「{business_type}」の【実在する競合店舗】を最低5店舗特定してください。それぞれの店舗名、推測される客単価、ターゲット層、口コミでよく見られる不満点をリストアップしてください。AIの推測は一切禁止です。',
                    expected_output='実在する店舗名と具体的なデータを含む、市場環境・不満点の箇条書きレポート',
                    agent=researcher
                )

                task2 = Task(
                    description=f'リサーチャーのリアルな競合データを分析し、「{area}」で「{business_type}」を成功させる戦略を立案してください。\n1. 勝算判定\n2. プレファレンス向上策\n3. WHO/WHAT/HOW\n\n【重要】出力するレポートには、記事のタイトルとなる大見出し（# 見出し1）は絶対に含めないでください。本文（## 見出し2以降）から書き始めてください。',
                    expected_output='論理的で辛口な戦略コンサルティングレポート（Markdown形式。# 見出し1を含まないこと）',
                    agent=strategist
                )

                consulting_crew = Crew(
                    agents=[researcher, strategist],
                    tasks=[task1, task2],
                    verbose=True,
                    process=Process.sequential
                )

                print("🤖 CrewAI: リサーチ＆戦略立案を開始します...")
                result = consulting_crew.kickoff()
                report_markdown = getattr(result, 'raw', str(result))
                
                # CrewAIが万が一「# 見出し1」を出力してしまった場合の強制除去処理
                # "---" などがない、先頭付近の "# タイトル" だけを消す
                report_markdown = re.sub(r'(?m)^\s*#\s+[^\n]+\n+', '', report_markdown, count=1)
                
                if not report_markdown or len(report_markdown) < 100:
                    print("⚠️ レポート生成に失敗したようです。スキップします。")
                    continue
                    
                print("✅ 戦略レポート生成完了。")

                # 3. フロントマターとSNS投稿文の生成（Claude）
                print("📝 Claude: メタデータ（タイトル、概要、SNS投稿文）を生成中...")
                system_prompt = "あなたは返答を必ずJSON形式で出力するAIです。Markdownのコードブロック(```json ... ```)は付けないでください。純粋なJSONテキストのみを出力してください。"
                user_message = f"""
以下のコンサルティングレポートを基にして、指定した3つの要素をJSON形式で抽出・生成してください。

【出力指定フォーマット】
{{
  "title": "Next.js用のSEOを意識した記事タイトル（例：勝率思考で紐解く、新宿駅東口高級焼肉の生存戦略）",
  "excerpt": "記事の要約（120文字以内）",
  "tweet": "X用のインサイト型投稿文。"
}}

【X用投稿文（tweet）のルール】
- 文字数は110文字以内
- ボット感を消し、専門家としての鋭い考察を含める
- 文末は「〜です」「〜と言えます」等の知的で落ち着いた口調
- 冒頭は【業界分析】や【経営の視点】等の角括弧から始め、記事が扱う核心的なテーマを一言で提示
- ハッシュタグは文末に最大2つ（例: #カチスジ #飲食店経営 など）
- ※後でプログラム側で最後にURLを付与するため、URLを含める必要はありません。

【元となるレポート】
{report_markdown[:3000]}
"""
                meta_data = call_claude_json(system_prompt, user_message)
                
                if not meta_data:
                    print("⚠️ メタデータ生成に失敗しました。デフォルト値を使用します。")
                    meta_data = {
                        "title": f"勝率思考で紐解く、{area}の{business_type}戦略",
                        "excerpt": f"{area}エリアの{business_type}市場における競合分析と、プレファレンスを高める勝筋について独自データで解説します。",
                        "tweet": f"【エリア分析】{area}における{business_type}の成功に必要な要素とは。競合の弱点から見出す、独自の戦い方を考察しました。\n続きはサイトで解説します。\n#カチスジ #エリア戦略"
                    }

                title = meta_data.get("title", f"勝率思考で紐解く、{area}の{business_type}戦略").replace('"', '')
                excerpt = meta_data.get("excerpt", "").replace('"', '').replace('\n', '')
                tweet = meta_data.get("tweet", "")

                date_str = datetime.datetime.now().strftime('%Y-%m-%d')
                slug = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                
                frontmatter = f"""---
title: "{title}"
date: "{date_str}"
excerpt: "{excerpt}"
---

"""
                # 4. ファイル保存とGitHubデプロイ
                if not os.path.exists(NEXTJS_CONTENT_DIR): 
                    os.makedirs(NEXTJS_CONTENT_DIR)
                    
                filename = f"{NEXTJS_CONTENT_DIR}/{slug}.md"
                with open(filename, "w", encoding="utf-8") as f: 
                    f.write(frontmatter + report_markdown)
                print(f"✅ ファイル保存完了: {filename}")

                # GitHubへのPush
                print("🚀 GitHubへ自動デプロイ中...")
                repo_dir = "marketing-site-next"
                if os.path.exists(repo_dir):
                    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
                    subprocess.run(["git", "commit", "-m", f"Auto-publish: {title}"], cwd=repo_dir, check=True)
                    subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=True)
                    print("✅ GitHubへの自動デプロイ完了")
                else:
                    print("⚠️ marketing-site-next フォルダが見つかりません。Git Pushをスキップします。")

                # 5. Xへの自動投稿
                article_url = f"{SITE_URL}/articles/{slug}"
                final_tweet_text = f"{tweet}\n{article_url}"
                post_to_x(final_tweet_text)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"❌ ターゲット '{area} × {business_type}' 処理中にエラーが発生しました: {e}")
                
            # 6. 次の処理まで待機
            sleep_hours = 24
            print(f"💤 次のターゲットに進むまで {sleep_hours}時間待機します...")
            time.sleep(sleep_hours * 3600)

if __name__ == "__main__":
    main()
