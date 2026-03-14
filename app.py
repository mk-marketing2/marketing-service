import os
import sys
import json
import logging
import asyncio
import ssl
import urllib.request
import urllib.error
import base64
import httpx
import re
from datetime import datetime
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from markdown_pdf import MarkdownPdf, Section

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process
from crewai_tools import TavilySearchTool
import tweepy

# ---------------------------------------------------------
# Logging Setup (Cloud Run defaults to standard out for JSON logs)
# ---------------------------------------------------------
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# SSL & HTTPX Bypasses (Required for your environment)
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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")
SITE_URL = os.environ.get("SITE_URL", "https://marketing-site-next.vercel.app").rstrip('/')

MODEL_NAME = "claude-sonnet-4-6" 
LLM_STRING = "anthropic/claude-sonnet-4-6"
NEXTJS_CONTENT_DIR = "marketing-site-next/src/content"

# ---------------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------------
app = FastAPI(
    title="Autonomous Media CrewAI API",
    description="API for triggering AI market research and report generation",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Models
# ---------------------------------------------------------
class ReportRequest(BaseModel):
    area: str
    business_type: str
    email: str | None = None

class ReportResponse(BaseModel):
    status: str
    message: str
    area: str
    business_type: str

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def call_claude_json(system_prompt: str, user_message: str):
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
    
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=context) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            content = res_body['content'][0]['text']
            
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx+1]
                return json.loads(json_str)
            else:
                return json.loads(content)
                
    except Exception as e:
        logger.error(f"❌ JSON抽出エラー: {e}")
        return None

def post_to_x(tweet_text: str):
    logger.info("🐦 X投稿中...")
    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY, consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN, access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
        )
        client.create_tweet(text=tweet_text)
        logger.info("✅ 投稿成功")
    except Exception as e: 
        logger.error(f"❌ X失敗: {e}")

def send_email(to_address: str, subject: str, body_text: str, attachment_path: str | None = None):
    logger.info(f"📧 Sending email to {to_address}...")
    try:
        gmail_user = os.environ.get("GMAIL_ADDRESS")
        gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

        if not gmail_user or not gmail_password:
            logger.warning("Email credentials missing. Cannot send email.")
            return
        
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_address
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body_text, 'plain'))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
        server.quit()
        logger.info("✅ Email sent successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")

def generate_thumbnail(image_prompt: str, slug: str) -> str | None:
    """
    Imagen 4.0 Fast (v1beta REST predict) を使って画像を生成し、
    marketing-site-next/public/images/{slug}.png に保存。
    成功したら Web 上のパス文字列 '/images/{slug}.png' を返す。
    失敗した場合は None を返す。
    """
    if not GEMINI_API_KEY:
        logger.warning("⚠️ GEMINI_API_KEY が未設定のため画像生成をスキップします")
        return None
    
    logger.info(f"🎨 Imagen 4.0 で画像生成中... prompt: {image_prompt[:80]}")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-fast-generate-001:predict?key={GEMINI_API_KEY}"
    payload = {
        "instances": [{"prompt": image_prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            body = json.loads(resp.read().decode())
            predictions = body.get('predictions', [])
            if predictions and 'bytesBase64Encoded' in predictions[0]:
                img_bytes = base64.b64decode(predictions[0]['bytesBase64Encoded'])
                images_dir = os.path.join("marketing-site-next", "public", "images")
                os.makedirs(images_dir, exist_ok=True)
                img_path = os.path.join(images_dir, f"{slug}.png")
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
                logger.info(f"✅ 画像保存完了: {img_path} ({len(img_bytes):,} bytes)")
                return f"/images/{slug}.png"
            else:
                logger.warning(f"⚠️ 画像データが見つかりません: {list(body.keys())}")
                return None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        logger.error(f"❌ Imagen API HTTPエラー {e.code}: {error_body[:300]}")
        return None
    except Exception as e:
        logger.error(f"❌ Imagen API エラー: {e}")
        return None


# ---------------------------------------------------------
# Core CrewAI Worker Task
# ---------------------------------------------------------
def run_crewai_pipeline(area: str, business_type: str, email: str | None = None):
    logger.info(f"🚀 バックグラウンド処理開始: {area} × {business_type}")
    
    try:
        # 1. CrewAIの実行
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
                f'- AIの会話的前置き（「承知いたしました」「CMOとして」等）は一切出力しない。純粋な記事本文のみを書け\n'
                f'- 記事のタイトルとなる大見出し（# 見出し1）は含めない。## 以降から書き始めること\n'
                f'- 最低1,200字以上のレポートを書くこと'
            ),
            expected_output=(
                '逆張りのフック/市場の死角/勝ち筋の3部構成による戦略コンサルティングレポート（Markdown形式）。'
                '断言調、推測表現なし、絵文字なし、AI前置きなし、# 見出し1なし、1,200字以上。'
            ),
            agent=strategist
        )

        consulting_crew = Crew(
            agents=[researcher, strategist],
            tasks=[task1, task2],
            verbose=True,
            process=Process.sequential
        )

        logger.info("🤖 CrewAI: リサーチ＆戦略立案を開始します...")
        result = consulting_crew.kickoff()
        report_markdown = getattr(result, 'raw', str(result))
        
        # H1重複防止のストリップ
        report_markdown = re.sub(r'(?m)^\s*#\s+[^\n]+\n+', '', report_markdown, count=1)
        
        # AI特有のメタコメントや前置きを強制除去
        unwanted_patterns = [
            r"^十分な競合データが揃っているため、リサーチャーへの追加質問は不要と判断し、CMOとして直接戦略レポートを作成します。?\n*",
            r"^承知いたしました。.*?\n",
            r"^以下の通り、.*?\n",
            r"^それでは、.*?\n"
        ]
        for pattern in unwanted_patterns:
            report_markdown = re.sub(pattern, '', report_markdown, flags=re.MULTILINE)
        
        report_markdown = report_markdown.lstrip()
        
        if not report_markdown or len(report_markdown) < 100:
            logger.warning("⚠️ レポート生成に失敗したようです。スキップします。")
            return
            
        logger.info("✅ 戦略レポート生成完了。")

        # 2. メタデータ生成 (Claude)
        logger.info("📝 Claude: メタデータ生成中...")
        system_prompt = "あなたは返答を必ずJSON形式で出力するAIです。Markdownのコードブロックは付けず、純粋なJSONテキストのみを出力してください。"
        user_message = f"""
以下のコンサルティングレポートを基にして、指定した3つの要素をJSON形式で抽出・生成してください。

【出力指定フォーマット】
{{
  "title": "SEOを意識した記事タイトル。「勝率思考で紐解く」「市場の死角」「なぜ〇〇は失敗するのか」等の知的・逆張り系コピーを使うこと（例：渋谷カフェ市場の「3つの空白」を突け——競合7店舗データが示す新規参入の勝ち筋）",
  "excerpt": "記事の要約（120文字以内）。断言調で書くこと。「〜でしょう」等の曖昧表現禁止。",
  "tweet": "X用インサイト型投稿文。専門家としての鋭い確信を持った口調で書くこと。",
  "image_prompt": "A professional photorealistic cinematic photograph, Japanese restaurant business scene in {area}, inspired by {business_type}. Beautiful atmospheric lighting, modern interior. No text, no letters, no words, no watermarks. Pure photography."
}}

【X用投稿文（tweet）のルール】
- 文字数は110文字以内
- 断言調（「〜だ」「〜である」）を使うこと
- 「〜と言えるでしょう」「いかがでしたか？」等の表現は絶対に使わない
- 冒頭は【市場分析】【経営の死角】【勝ち筋】等の角括弧から始め、核心を一言で提示
- ハッシュタグは文末に最大2つ（例: #カチスジ #飲食店経営）
- URLはシステム側で付与するため不要

【元となるレポート】
{report_markdown[:3000]}
"""
        meta_data = call_claude_json(system_prompt, user_message)
        
        if not meta_data:
            logger.warning("⚠️ メタデータ生成失敗につきデフォルト値を使用します。")
            meta_data = {
                "title": f"市場の死角を突け——{area}の{business_type}、競合データが示す勝算",
                "excerpt": f"{area}エリアの{business_type}市場における競合の構造的弱点と、その空白地帯を突く参入戦略を解説する。",
                "tweet": f"【市場分析】{area}の{business_type}市場に見落とされた空白地帯がある。競合の構造的欠陥を突くことが最大の参入戦略だ。\n#カチスジ #飲食店経営",
                "image_prompt": f"A professional photorealistic cinematic photograph of a {business_type} business in {area}, Japan, beautiful atmospheric lighting, modern interior, no text, no words"
            }

        title = meta_data.get("title", f"市場の死角を突け——{area}の{business_type}").replace('"', '')
        excerpt = meta_data.get("excerpt", "").replace('"', '').replace('\n', '')
        tweet = meta_data.get("tweet", "")
        image_prompt = meta_data.get("image_prompt", f"A professional cinematic photo of a {business_type} restaurant in {area}, Japan, beautiful lighting, no text, no words")
        # Enforce no-text constraint on all prompts
        if "no text" not in image_prompt.lower():
            image_prompt += ". No text, no letters, no words, no watermarks, no labels. Pure photography."

        date_str = datetime.now().strftime('%Y-%m-%d')
        slug = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 3. Imagen 4.0 Fast で画像生成
        thumbnail_path = generate_thumbnail(image_prompt, slug)
        thumbnail_value = thumbnail_path if thumbnail_path else ""
        
        frontmatter = f"""---
title: "{title}"
date: "{date_str}"
excerpt: "{excerpt}"
thumbnail: "{thumbnail_value}"
---

"""
        # 4. ファイル保存 (GitHub連携など)
        # ※Cloud Run上で動作するため書き込み権限とGitの運用は要検討。
        # 今回要件のStep1としてファイル生成＆リモートリポジトリpush、またはログ出力を残す。
        if not os.path.exists(NEXTJS_CONTENT_DIR): 
            try:
                os.makedirs(NEXTJS_CONTENT_DIR, exist_ok=True)
            except Exception as e:
                logger.warning(f"ディレクトリ作成に失敗（Cloud Runコンテナ環境依存の可能性）: {e}")
            
        filename = f"{NEXTJS_CONTENT_DIR}/{slug}.md"
        try:
            with open(filename, "w", encoding="utf-8") as f: 
                f.write(frontmatter + report_markdown)
            logger.info(f"✅ ローカルファイル保存完了: {filename}")
        except Exception as e:
            logger.error(f"ファイル保存エラー（Cloud Run等の読み取り専用FSの可能性）: {e}")
            # エラーであってもデバッグ用に出力する
            logger.info(f"生成されたコンテンツ:\n{frontmatter + report_markdown}")

        # GitHubへのPush (コンテナ環境ではSSHやPATの設定が別途必要になります)
        import subprocess
        logger.info("🚀 GitHubへ自動デプロイ中...")
        repo_dir = "marketing-site-next"
        if os.path.exists(repo_dir) and os.path.isdir(os.path.join(repo_dir, '.git')):
            try:
                subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
                subprocess.run(["git", "commit", "-m", f"Auto-publish: {title}"], cwd=repo_dir, check=True)
                subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=True)
                logger.info("✅ GitHubへの自動デプロイ完了")
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Git自動デプロイ失敗: {e}")
        else:
            logger.warning("⚠️ marketing-site-next Gitリポジトリが見つからないか未設定のためPushをスキップします。")

        # 4. Xへの自動投稿
        article_url = f"{SITE_URL}/articles/{slug}"
        final_tweet_text = f"{tweet}\n{article_url}"
        post_to_x(final_tweet_text)
        
        # 5. メール送信 (入力されていた場合)
        if email:
            pdf_filename = f"/tmp/report_{slug}.pdf" if os.environ.get("K_SERVICE") else f"report_{slug}.pdf"
            try:
                # MarkdownをPDFに変換して保存
                pdf = MarkdownPdf(toc_level=2)
                pdf_content = f"# {title}\n\n{report_markdown}"
                pdf.add_section(Section(pdf_content))
                pdf.save(pdf_filename)
                logger.info(f"✅ PDF生成完了: {pdf_filename}")
            except Exception as e:
                logger.error(f"❌ PDF生成エラー: {e}")
                pdf_filename = None

            email_subject = f"【AI出店診断】{area}×{business_type} の分析レポートが完了しました"
            email_body = f"""お申し込みありがとうございます。
{area}周辺の「{business_type}」に関するAI出店診断レポートが完了いたしました。
実在する競合データを基に、確率思考のCMOエージェントが導き出した勝筋をPDF形式にて添付しております。

ぜひ貴社のビジネス検証やご出店の戦略にお役立てください。

---
カチスジ AIコンサルティングチーム"""
            send_email(email, email_subject, email_body, attachment_path=pdf_filename)
            
            # クリーンアップ（Cloud Runのメモリを圧迫しないよう削除）
            if pdf_filename and os.path.exists(pdf_filename):
                try:
                    os.remove(pdf_filename)
                except Exception:
                    pass

        logger.info(f"🎉 バックグラウンド処理終了: {area} × {business_type}")
        
    except Exception as e:
        logger.error(f"❌ パイプライン全体のエラー: {e}", exc_info=True)

# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.post("/api/generate_report", response_model=ReportResponse)
async def generate_report(request: ReportRequest, background_tasks: BackgroundTasks):
    """
    非同期でCrewAIのレポート生成プロセスをキックするエンドポイント。
    Cloud Runのタイムアウト（デフォルト300秒等）を避けるため、BackgroundTasksを利用する。
    """
    logger.info(f"リクエストを受付: {request.area} の {request.business_type}")
    
    # BackgroundTasksを利用して長時間の推論タスクを裏側へ流す
    # （Cloud Runの場合、レスポンス後も一定時間CPUが割り当てられるように設定するか、
    #  単一リクエストのタイムアウトを伸ばして非同期awaitにする構成がありますが、
    #  Step1としてはFastAPI標準のバックグラウンドタスクを採用します）
    background_tasks.add_task(run_crewai_pipeline, request.area, request.business_type, request.email)
    
    return ReportResponse(
        status="accepted",
        message="Request accepted. CrewAI pipeline is running in the background.",
        area=request.area,
        business_type=request.business_type
    )

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
