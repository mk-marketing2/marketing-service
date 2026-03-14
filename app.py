import os
import sys
import json
import logging
import asyncio
import ssl
import urllib.request
import urllib.error
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

# ---------------------------------------------------------
# Core CrewAI Worker Task
# ---------------------------------------------------------
def run_crewai_pipeline(area: str, business_type: str, email: str | None = None):
    logger.info(f"🚀 バックグラウンド処理開始: {area} × {business_type}")
    
    try:
        # 1. CrewAIの実行
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
            description=f'リサーチャーのリアルな競合データを分析し、「{area}」で「{business_type}」を成功させる戦略を立案してください。\n1. 勝算判定\n2. プレファレンス向上策\n3. WHO/WHAT/HOW\n\n【重要事項】\n- 出力するレポートには、記事のタイトルとなる大見出し（# 見出し1）は絶対に含めないでください。本文（## 見出し2以降）から書き始めてください。\n- 「承知いたしました」「CMOとしてレポートを作成します」「以上が戦略です」などのAI特有の会話的な前置きやメタコメントは一切出力しないでください。純粋な記事の本文のみを出力してください。',
            expected_output='会話的な相槌を一切含まない、純粋な論理的戦略コンサルティングレポートのMarkdown本文のみ（# 見出し1を含まないこと）',
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
  "title": "Next.js用のSEOを意識した記事タイトル（例：勝率思考で紐解く、新宿駅東口高級焼肉の生存戦略）",
  "excerpt": "記事の要約（120文字以内）",
  "tweet": "X用のインサイト型投稿文。",
  "image_prompt": "{area}の{business_type}を美しく表現する、AI画像生成用の「英語」のプロンプト（例: A highly detailed, cinematic photography of a modern standing sushi bar in Shinbashi, Tokyo at night, neon lights, professional lighting, 8k resolution.）"
}}

【X用投稿文（tweet）のルール】
- 文字数は110文字以内
- ボット感を消し、専門家としての鋭い考察を含める
- 文末は「〜です」「〜と言えます」等
- 冒頭は【業界分析】等の角括弧から始め核心テーマを提示
- ※URLはシステム側で付与します。

【元となるレポート】
{report_markdown[:3000]}
"""
        meta_data = call_claude_json(system_prompt, user_message)
        
        if not meta_data:
            logger.warning("⚠️ メタデータ生成失敗につきデフォルト値を使用します。")
            meta_data = {
                "title": f"勝率思考で紐解く、{area}の{business_type}戦略",
                "excerpt": f"{area}エリアにおける{business_type}の勝筋についてデータで解説します。",
                "tweet": f"【エリア分析】{area}×{business_type}の成功要因を考察しました。\n続きはサイトで。\n#カチスジ",
                "image_prompt": f"A beautiful photographic establishing shot of a {business_type} in {area}, Japan, professional lighting, highly detailed"
            }

        title = meta_data.get("title", f"{area}の{business_type}戦略").replace('"', '')
        excerpt = meta_data.get("excerpt", "").replace('"', '').replace('\n', '')
        tweet = meta_data.get("tweet", "")
        image_prompt = meta_data.get("image_prompt", f"A beautiful cinematic photo of {business_type} in {area}")

        import hashlib
        seed = hashlib.md5(title.encode('utf-8')).hexdigest()
        thumbnail_url = f"https://picsum.photos/seed/{seed}/1200/630"

        date_str = datetime.now().strftime('%Y-%m-%d')
        slug = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        frontmatter = f"""---
title: "{title}"
date: "{date_str}"
excerpt: "{excerpt}"
thumbnail: "{thumbnail_url}"
---

"""
        # 3. ファイル保存 (GitHub連携など)
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
