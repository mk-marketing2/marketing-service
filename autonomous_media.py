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
                    role='外食産業専門フィールドリサーチャー',
                    goal=f'「{area}」における「{business_type}」の市場を、推測を一切排除して実在するデータで解剖する。競合店の名称・価格帯・客層・口コミ上のフリクション（不満点）を5店舗以上、検索ツールで必ず取得すること。',
                    backstory=(
                        'あなたは外食産業専門のフィールドリサーチャーだ。'
                        '仮説ではなく証拠を集める。口コミサイト・グルメメディア・SNSを横断し、'
                        '「実在する店舗名」「実際の価格帯」「顧客が放置されたまま抱えているフリクション」'
                        'を一次情報として収集する。「〜と思われます」「〜と推測されます」といった曖昧な表現は使わない。'
                        '絵文字も感情的な修飾語も一切不要だ。データだけを語れ。'
                    ),
                    verbose=True,
                    allow_delegation=False,
                    tools=[search_tool],
                    llm=LLM_STRING,
                    function_calling_llm=LLM_STRING
                )

                strategist = Agent(
                    role='チーフ・ストラテジスト（確率思考の戦略家）',
                    goal=(
                        f'リサーチャーが掘り起こした生データを元に、「{area}」×「{business_type}」において'
                        '参入者が最も高い勝率で戦える戦略を導く。'
                        '市場の死角・競合の構造的弱点・放置されたフリクションを論理的に言語化し、'
                        'どのポジショニングで戦えば確率が最大化されるかを示す。'
                    ),
                    backstory=(
                        'あなたはファクトベースの確率思考で戦略を組み立てる最高峰の戦略家だ。'
                        '「がんばれば売れる」「差別化が大事」のような精神論は一切使わない。'
                        '競合が抱える構造的欠陥を数値・実例で示し、その空白地帯に論理的に参入コンセプトを設計する。'
                        '文体は断言調（「〜だ」「〜である」）を徹底する。'
                        '「〜と言えるでしょう」「いかがでしたか？」のようなAI特有の無難な言い回しは絶対に使わない。'
                        '絵文字も使わない。鋭く、知的で、読者が唸るレポートを書け。'
                    ),
                    verbose=True,
                    allow_delegation=True,
                    llm=LLM_STRING,
                    function_calling_llm=LLM_STRING
                )

                task1 = Task(
                    description=(
                        f'検索ツールを使用し、「{area}」周辺の「{business_type}」市場に実在する競合店舗を最低5店舗特定せよ。'
                        f'各店舗について以下を調査すること：'
                        f'①店舗名と所在地、②推定客単価、③主要ターゲット層、'
                        f'④口コミ・SNSで繰り返し見られる不満点（フリクション）、⑤営業時間・席数などの制約情報。'
                        f'AIによる推測データは一切含めないこと。検索結果に基づく一次情報のみ許容する。'
                    ),
                    expected_output=(
                        '実在する5店舗以上の競合データを含む市場環境レポート。'
                        '店舗名・価格帯・フリクションが明記された箇条書き形式。推測・曖昧表現なし。'
                    ),
                    agent=researcher
                )

                task2 = Task(
                    description=(
                        f'リサーチャーが収集した実在競合データを元に、「{area}」×「{business_type}」の'
                        f'戦略コンサルティングレポートを作成せよ。\n\n'
                        f'【記事の構成ルール - 必ず以下の順序で書くこと】\n\n'
                        f'## 1. 逆張りのフック（導入）\n'
                        f'「{area}の{business_type}市場は〇〇だ」という一般通念を覆す、鋭い逆張りの一文から始めよ。'
                        f'読者が「え？」と思う命題を提示し、なぜその通念が錯覚なのかをデータで示す。\n\n'
                        f'## 2. 市場の死角（競合の構造的弱点）\n'
                        f'リサーチデータから読み取れる競合他社の「構造的欠陥」と「放置されたフリクション」を鋭く指摘せよ。'
                        f'「Aという不満がB店・C店・D店に共通して存在する」という形でパターンを示し、'
                        f'それが市場全体の構造問題である根拠を論理的に説明すること。\n\n'
                        f'## 3. 勝ち筋（参入戦略）\n'
                        f'その空白地帯をどう突けば勝率が最大化されるかを、WHO/WHAT/HOWの枠組みで具体的に示せ。'
                        f'「誰に・何を・どのように届けるか」を定義し、競合との差分が数値・概念で明確になるよう書くこと。'
                        f'精神論・根性論・曖昧な推奨は厳禁だ。\n\n'
                        f'【文体の絶対ルール】\n'
                        f'- 断言調（「〜だ」「〜である」）を徹底すること\n'
                        f'- 「〜と言えるでしょう」「いかがでしたか？」「ぜひ参考にしてください」等の無難な表現は絶対に使わない\n'
                        f'- 絵文字は一切使わない\n'
                        f'- 記事のタイトルとなる大見出し（# 見出し1）は含めない。## 以降から書き始めること\n'
                        f'- 最低1,200字以上のレポートを書くこと'
                    ),
                    expected_output=(
                        '逆張りのフック/市場の死角/勝ち筋の3部構成による戦略コンサルティングレポート（Markdown形式）。'
                        '断言調、推測表現なし、絵文字なし、# 見出し1なし、1,200字以上。'
                    ),
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
                report_markdown = re.sub(r'(?m)^\s*#\s+[^\n]+\n+', '', report_markdown, count=1)
                
                if not report_markdown or len(report_markdown) < 100:
                    print("⚠️ レポート生成に失敗したようです。スキップします。")
                    continue
                    
                print("✅ 戦略レポート生成完了。")

                # 3. フロントマターとSNS投稿文の生成（Claude）
                print("📝 Claude: メタデータ（タイトル、概要、SNS投稿文、図解データ）を生成中...")
                system_prompt = "あなたは返答を必ずJSON形式で出力するAIです。Markdownのコードブロック(```json ... ```)は付けないでください。純粋なJSONテキストのみを出力してください。"
                user_message = f"""
以下のコンサルティングレポートを基にして、指定した4つの要素をJSON形式で抽出・生成してください。

【出力指定フォーマット】
{{
  "title": "SEOを意識した記事タイトル。「勝率思考で紐解く」「市場の死角」「なぜ〇〇は失敗するのか」等の知的・逆張り系コピーを使うこと（例：渋谷カフェ市場の「3つの空白」を突け——競合7店舗データが示す新規参入の勝ち筋）",
  "excerpt": "記事の要約（120文字以内）。断言調で書くこと。「〜でしょう」等の曖昧表現禁止。",
  "tweet": "X用インサイト型投稿文。専門家としての鋭い確信を持った口調で書くこと。",
  "diagram": {{記事の内容に最も適した図解データ。以下の3種類から1つを選んで生成すること}}
}}

【diagramフィールドの生成ルール】
記事内容を分析し、以下3種類のうち最も適切な1つを生成してください。

■ 種類1: PositioningMap（競合のポジショニングを2軸で可視化する場合）
{{
  "type": "PositioningMap",
  "title": "競合ポジショニングマップ",
  "xLabel": "横軸のラベル（例：価格帯 低←→高）",
  "yLabel": "縦軸のラベル（例：予約しやすさ 難←→易）",
  "points": [
    {{"label": "競合店名A", "x": 30, "y": 40}},
    {{"label": "競合店名B", "x": 70, "y": 20}},
    {{"label": "競合店名C", "x": 50, "y": 60}}
  ],
  "targetZone": {{"x": 75, "y": 80, "label": "参入機会ゾーン"}}
}}

■ 種類2: ThreePoints（市場の死角・問題点・施策を3点で整理する場合）
{{
  "type": "ThreePoints",
  "title": "市場の3つの構造的問題",
  "variant": "warning",
  "points": [
    {{"title": "問題点1のタイトル", "body": "具体的な説明（記事データに基づく）"}},
    {{"title": "問題点2のタイトル", "body": "具体的な説明"}},
    {{"title": "問題点3のタイトル", "body": "具体的な説明"}}
  ]
}}

■ 種類3: StepFlow（参入戦略・実行ステップを順序立てて示す場合）
{{
  "type": "StepFlow",
  "title": "参入戦略ステップ",
  "steps": [
    {{"step": "1", "title": "ステップ1のタイトル", "body": "具体的な説明", "tag": "最優先"}},
    {{"step": "2", "title": "ステップ2のタイトル", "body": "具体的な説明"}},
    {{"step": "3", "title": "ステップ3のタイトル", "body": "具体的な説明"}}
  ]
}}

【X用投稿文（tweet）のルール】
- 文字数は110文字以内
- 断言調（「〜だ」「〜である」）を使うこと
- 「〜と言えるでしょう」「いかがでしたか？」等の表現は絶対に使わない
- 冒頭は【市場分析】【経営の死角】【勝ち筋】等の角括弧から始め、核心を一言で提示
- ハッシュタグは文末に最大2つ（例: #カチスジ #飲食店経営）
- URLは不要（後でプログラムが付与する）

【元となるレポート】
{report_markdown[:3000]}
"""
                meta_data = call_claude_json(system_prompt, user_message)
                
                if not meta_data:
                    print("⚠️ メタデータ生成に失敗しました。デフォルト値を使用します。")
                    meta_data = {
                        "title": f"市場の死角を突け——{area}の{business_type}、競合データが示す勝算",
                        "excerpt": f"{area}エリアの{business_type}市場における競合の構造的弱点と、その空白地帯を突く参入戦略を競合データで解説する。",
                        "tweet": f"【市場分析】{area}の{business_type}市場に見落とされた空白地帯がある。競合の構造的欠陥を突くことが最大の参入戦略だ。\n#カチスジ #飲食店経営"
                    }

                title = meta_data.get("title", f"市場の死角を突け——{area}の{business_type}").replace('"', '')
                excerpt = meta_data.get("excerpt", "").replace('"', '').replace('\n', '')
                tweet = meta_data.get("tweet", "")
                diagram_data = meta_data.get("diagram", None)

                date_str = datetime.datetime.now().strftime('%Y-%m-%d')
                slug = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

                # diagram フィールドをフロントマターに追加（JSONをシングルクォート文字列として埋め込む）
                diagram_line = ""
                if diagram_data:
                    import json as _json
                    diagram_json_str = _json.dumps(diagram_data, ensure_ascii=False).replace("'", "\\'")
                    diagram_line = f"diagram: '{diagram_json_str}'\n"
                
                frontmatter = f"""---
title: "{title}"
date: "{date_str}"
excerpt: "{excerpt}"
{diagram_line}---

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
