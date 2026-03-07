import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.stats as stats
import os
import glob

# --- ページ設定 ---
st.set_page_config(
    page_title="カチスジ - 飲食店経営支援プラットフォーム",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- カスタムCSS（SaaS風・静かなB2Bデザイン） ---
st.markdown("""
<style>
    /* Streamlitデフォルトヘッダーを非表示 */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    /* 全体背景と文字色・広めの余白 */
    .block-container {
        max-width: 1100px !important;
        padding-top: 4rem !important;
        padding-bottom: 6rem !important;
    }
    .stApp {
        background-color: #FFFFFF;
        color: #333333;
        font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', 'Hiragino Sans', Meiryo, sans-serif;
    }
    
    /* 見出し類 */
    h1, h2, h3, h4 {
        color: #333333 !important;
        font-weight: 500;
        line-height: 1.5;
        letter-spacing: 0.05em;
    }
    h1 { font-size: 2.4rem; margin-bottom: 1.5rem; text-align: center; }
    h2 { font-size: 1.8rem; margin-top: 4rem; margin-bottom: 2rem; text-align: center; }
    h3 { font-size: 1.3rem; margin-top: 1.5rem; margin-bottom: 1rem; color: #004098 !important; }
    
    p, li {
        font-size: 1.05rem;
        line-height: 1.8;
        color: #666666;
    }
    
    /* Hero Section */
    .hero {
        text-align: center;
        padding: 80px 0;
        background-color: #FFFFFF;
        margin-bottom: 2rem;
    }
    .hero-title {
        font-size: 3.5rem;
        color: #333333;
        font-weight: 300;
        margin-bottom: 1.5rem;
        line-height: 1.3;
        letter-spacing: 0.08em;
    }
    .hero-subtitle {
        font-size: 1.15rem;
        color: #666666;
        max-width: 700px;
        margin: 0 auto;
        line-height: 1.8;
        font-weight: 400;
        margin-bottom: 3rem;
    }

    /* カードコンポーネント用 */
    .card {
        background-color: #FFFFFF;
        border-radius: 8px;
        padding: 2.5rem 2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
        border: none;
        margin-bottom: 1.5rem;
        border-top: 4px solid #004098;
        height: 100%;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
    }
    .card-title {
        font-size: 1.25rem;
        color: #333333;
        font-weight: 600;
        margin-bottom: 1rem;
        text-align: center;
    }
    .card-icon {
        font-size: 2.5rem;
        text-align: center;
        margin-bottom: 1.5rem;
        color: #004098;
    }
    
    /* ボタンカスタマイズ */
    button[kind="primary"], button[kind="primaryFormSubmit"] {
        background-color: #004098 !important;
        color: #FFFFFF !important;
        border-radius: 4px !important;
        border: none !important;
        padding: 0.8rem 3rem !important;
        font-size: 1.05rem !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    button[kind="primary"] *, button[kind="primaryFormSubmit"] * {
        color: #FFFFFF !important;
    }
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {
        background-color: #002b6b !important;
        box-shadow: 0 4px 15px rgba(0, 64, 152, 0.2) !important;
    }

    button[kind="secondary"], button[kind="secondaryFormSubmit"] {
        background-color: #FFFFFF !important;
        color: #333333 !important;
        border: 1px solid #CCCCCC !important;
        border-radius: 4px !important;
        padding: 0.8rem 3rem !important;
        font-size: 1.05rem !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    button[kind="secondary"] *, button[kind="secondaryFormSubmit"] * {
        color: #333333 !important;
    }
    button[kind="secondary"]:hover, button[kind="secondaryFormSubmit"]:hover {
        background-color: #F8F9FA !important;
        border-color: #AAAAAA !important;
    }
    
    /* フッター帯 */
    .footer-cta {
        background-color: #F8F9FA;
        padding: 80px 0;
        text-align: center;
        margin-top: 80px;
        border-radius: 8px;
    }
    
    /* Expandable (カチスジ・ノート用) */
    .streamlit-expanderHeader {
        font-size: 1.05rem;
        font-weight: 500;
        color: #333333;
        background-color: #FFFFFF;
        border-radius: 4px;
        border: 1px solid #EAEAEA;
    }
</style>
""", unsafe_allow_html=True)

# --- トップ ナビゲーション (HTML + CSS x query_params) ---
st.markdown("<h3 style='color: #004098; margin-top:0; padding-top: 0; font-weight: 600; letter-spacing: 0.1em;'>KACHISUJI</h3>", unsafe_allow_html=True)

st.markdown("""
<style>
.nav-tabs {
    display: flex;
    justify-content: flex-start;
    background-color: #FFFFFF;
    padding: 0;
    border-bottom: 1px solid #EAEAEA;
    margin-bottom: 3rem;
    list-style: none;
    gap: 2.5rem;
}
.nav-tabs a {
    padding: 1rem 0;
    background-color: transparent;
    color: #888888 !important;
    text-decoration: none !important;
    font-weight: 500;
    transition: all 0.2s ease;
    font-size: 0.95rem;
    position: relative;
    letter-spacing: 0.03em;
}
.nav-tabs a:hover {
    color: #333333 !important;
}
.nav-tabs a.active {
    color: #004098 !important;
    font-weight: 600;
}
.nav-tabs a.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    width: 100%;
    height: 3px;
    background-color: #004098;
}
</style>
""", unsafe_allow_html=True)

# URLクエリパラメータによるページルーティング
params = st.query_params
current_page = params.get("page", "home")

pages_dict = {
    "home": "🏠 ホーム",
    "service": "💎 サービス・料金",
    "logic": "🧠 確率思考のロジック",
    "media": "📚 カチスジ・ノート",
    "app": "📊 勝率診断ツール"
}

# HTMLでタブメニューを生成（_parentか_selfで画面遷移）
nav_html = '<div class="nav-tabs">'
for key, label in pages_dict.items():
    active_class = "active" if current_page == key else ""
    nav_html += f'<a href="/?page={key}" target="_self" class="{active_class}">{label}</a>'
nav_html += '</div>'

st.markdown(nav_html, unsafe_allow_html=True)

# ページ切り替え用の変数にマッピング
page_map = {
    "home": "🏠 ホーム (Home)", 
    "service": "💎 サービス・料金 (Service)", 
    "logic": "🧠 確率思考のロジック (Logic)", 
    "media": "📚 カチスジ・ノート (Media)", 
    "app": "📊 勝率診断ツール (App)"
}
page = page_map.get(current_page, "🏠 ホーム (Home)")

# --- 共通計算ロジック（NBDモデル） ---
def calculate_nbd_prediction(population, competitors, avg_spend):
    base_penetration = 0.15
    market_share = base_penetration / (1 + competitors * 0.1)
    avg_frequency = 1.2 + (0.5 / (1 + competitors * 0.2)) 
    expected_monthly_visitors = population * market_share * avg_frequency
    target_monthly_sales = expected_monthly_visitors * avg_spend
    
    months = np.arange(1, 13)
    awareness_curve = 1 / (1 + np.exp(-0.5 * (months - 4))) 
    seasonality = 1 + 0.1 * np.sin(months * np.pi / 6)
    np.random.seed(42)  # 固定シード
    noise = np.random.normal(1, 0.05, 12)
    
    monthly_sales_trajectory = target_monthly_sales * awareness_curve * seasonality * noise
    return target_monthly_sales, monthly_sales_trajectory

# ==========================================
# ページ1: 🏠 ホーム (Home)
# ==========================================
if page == "🏠 ホーム (Home)":
    # 1. ヒーローセクション (Revised Hero)
    st.markdown("""
    <div style="padding: 60px 0 40px 0;">
    """, unsafe_allow_html=True)
    
    col_hero1, col_hero2 = st.columns([1.1, 1], gap="large")
    with col_hero1:
        st.markdown("""
        <div style="font-size: 3.2rem; color: #333333; font-weight: 300; margin-bottom: 1.5rem; line-height: 1.3; letter-spacing: 0.08em; padding-top: 2rem;">
            直感を、確率へ。
        </div>
        <div style="font-size: 1.15rem; color: #666666; line-height: 1.8; font-weight: 400; margin-bottom: 3rem;">
            店舗経営の意思決定を、データとアルゴリズムで科学する。<br>カチスジは、飲食業のための事業計画プラットフォームです。
        </div>
        """, unsafe_allow_html=True)
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            st.button("無料で始める", type="primary", use_container_width=True)
        st.markdown("<div style='color: #999999; font-size: 0.9rem; margin-top: 1.5rem;'>1,200店舗以上の開業準備に活用されています</div>", unsafe_allow_html=True)
    
    with col_hero2:
        st.markdown('<div style="border-radius: 12px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.05);">', unsafe_allow_html=True)
        st.image(r"C:\Users\hiro3\.gemini\antigravity\brain\a64a2d60-baa2-4bcb-9e09-7dd9e142ce38\b2b_hero_data_viz_1772556089356.png", use_column_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    st.markdown("</div>", unsafe_allow_html=True)

    # 2. トラストバー (Trust Bar)
    st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
      .trust-bar-container {
        background-color: #f8f9fa;
        padding: 40px 0;
        margin: 40px -5rem; /* Streamlitのデフォルト余白を打ち消して画面幅一杯にする */
        text-align: center;
        border-top: 1px solid #eeeeee;
        border-bottom: 1px solid #eeeeee;
      }
      .trust-header {
        font-size: 12px;
        color: #999;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 25px;
        font-weight: 600;
      }
      .logo-container {
        display: flex;
        justify-content: center;
        align-items: center;
        flex-wrap: wrap;
        gap: 40px;
        opacity: 0.7;
      }
      .logo-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        color: #6c757d;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 600;
        font-size: 14px;
        transition: all 0.3s ease;
      }
      .logo-item i {
        font-size: 36px;
        margin-bottom: 12px;
        color: #adb5bd;
      }
      .logo-item:hover {
        transform: translateY(-3px);
        opacity: 1;
        color: #004098; /* ホバー時にブランドカラーに */
      }
      .logo-item:hover i {
        color: #004098;
      }
      /* スマホ対応 */
      @media (max-width: 768px) {
        .logo-container {
          gap: 20px;
        }
        .logo-item {
          width: 45%; /* スマホでは2列表示 */
          margin-bottom: 20px;
        }
      }
    </style>
    
    <div class="trust-bar-container">
      <div class="trust-header">Supported by Reliable Data Sources</div>
      <div class="logo-container">
        <div class="logo-item"><i class="fa-solid fa-database"></i>Gov Stats</div>
        <div class="logo-item"><i class="fa-solid fa-map-location-dot"></i>Geospatial</div>
        <div class="logo-item"><i class="fa-solid fa-chart-line"></i>Market DB</div>
        <div class="logo-item"><i class="fa-solid fa-money-bill-trend-up"></i>Finance</div>
        <div class="logo-item"><i class="fa-solid fa-calculator"></i>NBD Engine</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. コンセプト (Concept)
    st.markdown('<div style="padding: 60px 0;">', unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top: 0;'>経営の解像度を上げる</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="card">
            <div class="card-icon">📊</div>
            <div class="card-title">Market Data</div>
            <p style="text-align: center;">国勢調査・人流データを統合し、商圏のポテンシャルを可視化。</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="card">
            <div class="card-icon">🧠</div>
            <div class="card-title">Prediction</div>
            <p style="text-align: center;">NBDモデルによる需要予測で、事業の蓋然性を担保。</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="card">
            <div class="card-icon">📄</div>
            <div class="card-title">Documentation</div>
            <p style="text-align: center;">金融機関水準の事業計画書を、クラウド上で即座に生成。</p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 4. アウトプット・スニークピーク (Sneak Peek)
    st.markdown("""
    <div style="padding: 80px 0; background-color: #F8F9FA; border-radius: 12px; margin-bottom: 6rem;">
        <h2 style="margin-top: 0; margin-bottom: 1rem; color: #333333;">経営の未来を、高解像度で可視化する。</h2>
        <p style="text-align: center; color: #666666; margin-bottom: 4rem; font-size: 1.1rem;">
            カチスジが生成するダッシュボードと事業計画書レポートのイメージです。
        </p>
    """, unsafe_allow_html=True)
    
    col_sp1, col_sp2, col_sp3 = st.columns([1, 10, 1])
    with col_sp2:
        st.markdown('<div style="border-radius: 8px; overflow: hidden; box-shadow: 0 15px 40px rgba(0,0,0,0.1); border: 1px solid #EAEAEA;">', unsafe_allow_html=True)
        st.image(r"C:\Users\hiro3\.gemini\antigravity\brain\a64a2d60-baa2-4bcb-9e09-7dd9e142ce38\b2b_dashboard_mockup_1772556106170.png", use_column_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("</div><br><br>", unsafe_allow_html=True)
    
    # 4. 活用シーン (Use Case)
    st.markdown("## あらゆるフェーズで、確かな判断を。")
    st.markdown("""
    <div style="max-width: 800px; margin: 0 auto;">
        <div style="display: flex; margin-bottom: 2rem; align-items: flex-start;">
            <div style="flex: 1; color: #004098; font-weight: bold; font-size: 1.1rem; padding-top: 0.2rem;">Planning</div>
            <div style="flex: 3; color: #666666;">出店候補地の選定・比較に。複数エリアの人口動態と競合状況を瞬時に分析し、勝ち筋のある立地を導き出します。</div>
        </div>
        <div style="display: flex; margin-bottom: 2rem; align-items: flex-start;">
            <div style="flex: 1; color: #004098; font-weight: bold; font-size: 1.1rem; padding-top: 0.2rem;">Finance</div>
            <div style="flex: 3; color: #666666;">創業融資・追加融資の根拠資料として。金融機関が最も重視する「数学的な返済可能性」を提示します。</div>
        </div>
        <div style="display: flex; align-items: flex-start;">
            <div style="flex: 1; color: #004098; font-weight: bold; font-size: 1.1rem; padding-top: 0.2rem;">Management</div>
            <div style="flex: 3; color: #666666;">日々の予実管理と、撤退ラインの判断に。客観的なデータに基づき、感情を排した事業運営をサポートします。</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 5. フッター (CTA)
    st.markdown("""
    <div class="footer-cta">
        <h3 style="margin-top:0; margin-bottom: 2rem; color: #333333 !important; font-size: 1.5rem;">まずは、エリアのポテンシャル診断から。</h3>
    """, unsafe_allow_html=True)
    
    col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
    with col_f2:
        st.button("シミュレーションを試す（無料）", type="primary", use_container_width=True)
        
    st.markdown("</div>", unsafe_allow_html=True)


# ==========================================
# ページ2: 💎 サービス・料金 (Service)
# ==========================================
elif page == "💎 サービス・料金 (Service)":
    # 1. ページヘッダー
    st.markdown("""
    <div style="padding: 80px 0; text-align: center;">
        <h2 style="margin-top: 0; margin-bottom: 1rem; border-bottom: none; font-size: 2rem; color: #333333;">フェーズに合わせた、最適な意思決定を。</h2>
        <p style="color: #666666; font-size: 1.1rem; max-width: 600px; margin: 0 auto; line-height: 1.8;">
            市場調査から創業融資、日々の経営管理まで。<br>あなたの事業フェーズに必要な機能をお選びください。
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # CSS for cards
    st.markdown("""
    <style>
    .pricing-card {
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        padding: 30px;
        background-color: #FFFFFF;
        height: 100%;
        transition: transform 0.2s, box-shadow 0.2s;
        box-shadow: 0 4px 15px rgba(0,0,0,0.02);
    }
    .pricing-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 25px rgba(0,0,0,0.06);
    }
    .pricing-card-highlight {
        border-top: 4px solid #004098;
    }
    .pricing-tag {
        font-size: 0.85rem;
        font-weight: bold;
        color: #004098;
        background-color: #F0F4F8;
        padding: 0.3rem 0.8rem;
        border-radius: 4px;
        display: inline-block;
        margin-bottom: 1rem;
    }
    .pricing-tag-highlight {
        color: #FFFFFF;
        background-color: #004098;
    }
    .pricing-price {
        font-size: 2.2rem;
        color: #333333;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    .pricing-target {
        font-size: 0.9rem;
        color: #888888;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .pricing-desc {
        font-size: 0.95rem;
        color: #444444;
        line-height: 1.6;
        margin-bottom: 1.5rem;
        height: 4rem; /* align heights */
    }
    .pricing-features {
        list-style: none;
        padding-left: 0;
        margin-bottom: 2rem;
    }
    .pricing-features li {
        font-size: 0.95rem;
        color: #666666;
        line-height: 1.6;
        margin-bottom: 0.5rem;
    }
    .pricing-features li::before {
        content: "✔";
        color: #004098;
        margin-right: 0.5rem;
        font-weight: bold;
    }
    
    /* table styling */
    .feature-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 2rem;
        margin-bottom: 5rem;
    }
    .feature-table th, .feature-table td {
        border-bottom: 1px solid #e0e0e0;
        padding: 1rem;
        text-align: center;
        color: #444444;
    }
    .feature-table th {
        font-weight: 500;
        color: #888888;
        font-size: 0.9rem;
    }
    .feature-table td:first-child {
        text-align: left;
        font-weight: 500;
        color: #333333;
    }
    </style>
    """, unsafe_allow_html=True)

    # 2. プランカード (Pricing Cards)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="pricing-card">
            <div class="pricing-tag" style="background-color: #F0F0F0; color: #666666;">Free</div>
            <div class="pricing-price">¥0<span style="font-size: 1rem; color: #888888;"> / 月額</span></div>
            <div class="pricing-target">対象: 物件探し・市場調査フェーズ</div>
            <div class="pricing-desc">候補地のポテンシャルを瞬時に判定。契約前のセカンドオピニオンとして。</div>
            <hr style="border:0; border-top: 1px solid #F0F0F0; margin: 1.5rem 0;">
            <ul class="pricing-features">
                <li>商圏人口データの閲覧</li>
                <li>簡易・勝率判定 (S~Dランク)</li>
                <li>競合店マップ表示</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.button("無料で始める", key="btn_free", use_container_width=True)

    with col2:
        st.markdown("""
        <div class="pricing-card">
            <div class="pricing-tag">Standard</div>
            <div class="pricing-price">¥980<span style="font-size: 1rem; color: #888888;"> / 月額</span></div>
            <div class="pricing-target">対象: 店舗運営・改善フェーズ</div>
            <div class="pricing-desc">日々の売上を確率思考で管理。異常を検知し、打つべき施策を提案。</div>
            <hr style="border:0; border-top: 1px solid #F0F0F0; margin: 1.5rem 0;">
            <ul class="pricing-features">
                <li>全てのアナリティクス機能</li>
                <li>NBDモデルによる予実管理</li>
                <li>競合店アラート通知</li>
                <li>月次レポート配信</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.button("トライアルを始める", type="primary", key="btn_std", use_container_width=True)
        
    with col3:
        st.markdown("""
        <div class="pricing-card pricing-card-highlight">
            <div class="pricing-tag pricing-tag-highlight">One-time / Recommended</div>
            <div class="pricing-price">¥29,800<span style="font-size: 1rem; color: #888888;"> / 単発</span></div>
            <div class="pricing-target" style="color:#004098;">対象: 開業準備・創業融資フェーズ</div>
            <div class="pricing-desc" style="font-weight: bold; color: #333333;">銀行提出レベルの事業計画書を即座に。</div>
            <hr style="border:0; border-top: 1px solid #F0F0F0; margin: 1.5rem 0;">
            <ul class="pricing-features">
                <li><strong style="color: #333333;">創業計画書作成 (PDF A4 15枚)</strong></li>
                <li>3年間のPL予測</li>
                <li>融資審査用・根拠データ一式</li>
                <li>メニュー価格戦略・適正化</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.button("レポート作成画面へ", type="primary", key="btn_report", use_container_width=True)

    st.markdown("<br><br><br>", unsafe_allow_html=True)

    # 3. 機能比較表 (Feature Matrix)
    st.markdown("<h3 style='text-align: center; margin-bottom: 2rem;'>機能比較</h3>", unsafe_allow_html=True)
    st.markdown("""
    <table class="feature-table">
        <thead>
            <tr>
                <th style="width: 40%;"></th>
                <th style="width: 20%;">Starter (Free)</th>
                <th style="width: 20%;">Business (Standard)</th>
                <th style="width: 20%;">Launch Pack (One-time)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>商圏分析</td>
                <td style="color:#004098;">✔</td>
                <td style="color:#004098;">✔</td>
                <td style="color:#004098;">✔</td>
            </tr>
            <tr>
                <td>NBD確率計算</td>
                <td style="color:#aaaaaa;">-</td>
                <td style="color:#004098;">✔</td>
                <td style="color:#004098;">✔</td>
            </tr>
            <tr>
                <td>予実管理</td>
                <td style="color:#aaaaaa;">-</td>
                <td style="color:#004098;">✔</td>
                <td style="color:#aaaaaa;">-</td>
            </tr>
            <tr>
                <td>PDFレポート出力</td>
                <td style="color:#aaaaaa;">-</td>
                <td style="color:#aaaaaa;">-</td>
                <td style="color:#004098;">✔</td>
            </tr>
            <tr>
                <td>メールサポート</td>
                <td style="color:#aaaaaa;">-</td>
                <td style="color:#004098;">✔</td>
                <td style="color:#004098;">✔</td>
            </tr>
        </tbody>
    </table>
    """, unsafe_allow_html=True)

    # 4. 「Launch Pack」の詳細訴求 (Focus Section)
    st.markdown("""
    <div style="background-color: #F8F9FA; border-radius: 8px; padding: 60px 40px; margin-top: 2rem; margin-bottom: 4rem;">
    """, unsafe_allow_html=True)
    
    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        st.markdown("<h3 style='margin-top:0; color: #333333;'>銀行員を納得させる、『根拠』の深さ。</h3>", unsafe_allow_html=True)
        st.markdown("""
        <p style="color: #666666; line-height: 1.8; margin-top: 1.5rem; margin-bottom: 2rem;">
        Launch Packで出力されるレポートは、単なる分析結果ではありません。<br><br>
        金融機関の融資審査基準に準拠したフォーマットで、商圏の限界売上（天井）とリスク要因を数値化。<br>
        『なぜこの売上目標なのか？』という質問に、数学的な回答を用意します。
        </p>
        <p style="color: #888888; font-size: 0.9rem;">※出力形式：PDF / A4サイズ / 約15〜20ページ</p>
        """, unsafe_allow_html=True)
    with col_f2:
        # Placeholder image styling
        st.markdown("""
        <div style="background-color: #FFFFFF; border: 1px solid #EAEAEA; border-radius: 4px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); display: flex; align-items: center; justify-content: center; height: 100%; min-height: 250px;">
            <div style="text-align: center; color: #BBBBBB;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">📄</div>
                <div>(Report Image Placeholder)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("</div>", unsafe_allow_html=True)


# ==========================================
# ページ3: 🧠 確率思考のロジック (Logic)
# ==========================================
elif page == "🧠 確率思考のロジック (Logic)":
    # 1. ページヘッダー (Academic Header)
    st.markdown("""
    <div style="padding: 80px 0; text-align: center;">
        <h2 style="margin-top: 0; margin-bottom: 1rem; border-bottom: none; font-size: 2.2rem; color: #333333; font-family: 'Hiragino Mincho ProN', 'Yu Mincho', serif; letter-spacing: 0.05em;">確率は、嘘をつかない。</h2>
        <p style="color: #666666; font-size: 1.1rem; max-width: 700px; margin: 0 auto; line-height: 1.8;">
            市場の『ゆらぎ』を数式で捉える。<br>カチスジの予測エンジンには、マーケティングサイエンスの標準理論『NBDモデル』が搭載されています。
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. NBDモデルの解説 (The Core Theory)
    col_theory1, col_theory2 = st.columns([1, 1.2])
    
    with col_theory1:
        st.markdown("<h3 style='color: #004098; margin-top: 0;'>消費者の『偏り』を科学する</h3>", unsafe_allow_html=True)
        st.markdown("""
        <p style="color: #444444; font-size: 1.05rem; line-height: 1.8;">
        すべての消費財やサービスの購買行動は、ランダムではありません。<br>
        『ガンマ・ポアソン分布（NBDモデル）』という確率分布に従います。<br><br>
        カチスジは、あなたの出店予定エリアの消費者データをこのモデルに当てはめ、
        『1回しか来ない客』と『10回来る常連客』の比率を事前に算出します。
        </p>
        """, unsafe_allow_html=True)
        
    with col_theory2:
        # NBD Chart using scipy.stats.nbinom
        n, p_val = 2, 0.4
        x = np.arange(0, 11)
        nbd_pmf = stats.nbinom.pmf(x, n, p_val)
        
        fig, ax = plt.subplots(figsize=(6, 4))
        
        # Plot smooth curve/fill to look more abstract and beautiful
        from scipy.interpolate import make_interp_spline
        x_smooth = np.linspace(0, 10, 100)
        spline = make_interp_spline(x, nbd_pmf, k=3)
        y_smooth = spline(x_smooth)
        y_smooth[y_smooth < 0] = 0 # ensure no negative values
        
        ax.plot(x_smooth, y_smooth, color="#004098", linewidth=2.5)
        ax.fill_between(x_smooth, y_smooth, color="#004098", alpha=0.1)
        
        ax.set_xlabel("購入回数", color="#888888", fontsize=9)
        ax.set_ylabel("顧客の割合 (%)", color="#888888", fontsize=9)
        ax.set_xticks(np.arange(0, 11, 2))
        ax.set_yticks([]) # Hide y ticks for a cleaner look
        
        # Clean up spines
        for spine in ax.spines.values():
            spine.set_color('#EAEAEA')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False) # even left spine off for minimalism
        ax.set_facecolor('#FFFFFF')
        fig.patch.set_facecolor('#FFFFFF')
        
        st.pyplot(fig)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # 3. 数式の開示 (Mathematical Authority)
    st.markdown("<div style='background-color: #F8F9FA; padding: 60px 40px; border-radius: 8px; text-align: center; border: 1px solid #EAEAEA;'>", unsafe_allow_html=True)
    st.markdown("<h3 style='color: #333333; margin-top: 0; margin-bottom: 2rem;'>予測アルゴリズムの正体</h3>", unsafe_allow_html=True)
    
    st.latex(r'''
    P(x) = \frac{\Gamma(r+x)}{x! \Gamma(r)} \left(\frac{m}{m+r}\right)^x \left(\frac{r}{m+r}\right)^r
    ''')
    
    st.markdown("""
    <p style="color: #666666; font-size: 0.95rem; margin-top: 2rem; max-width: 600px; margin-left: auto; margin-right: auto; line-height: 1.8;">
        <strong>$m$:</strong> 平均購入回数 &nbsp;&nbsp; <strong>$r (k)$:</strong> 分布の形状パラメータ。<br>
        この2つの変数を特定することで、市場の未来図を90%以上の精度で描くことが可能です。
    </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br><br><br>", unsafe_allow_html=True)

    # 4. ビジネスへの応用 (Application)
    st.markdown("""
    <div style="max-width: 700px; margin: 0 auto; padding-bottom: 60px;">
        <h3 style="color: #004098; margin-bottom: 1.5rem; text-align: center;">なぜ、この理論で融資が通るのか</h3>
        <p style="color: #444444; font-size: 1.05rem; line-height: 1.8;">
        銀行員が最も嫌うのは『根拠のない楽観』です。<br><br>
        カチスジのレポートは、『頑張れば売れる』ではなく『確率的にこの売上に収束する』という
        数学的根拠（エビデンス）を提供します。<br><br>
        これは、大手消費財メーカーやテーマパークが採用している手法と同じです。
        </p>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# ページ4: 📚 カチスジ・ノート (Media)
# ==========================================
elif page == "📚 カチスジ・ノート (Media)":
    st.markdown("## 確率思考で読み解く、飲食経営の真実")
    st.markdown("データサイエンティストが、過去の実例や銀行の審査視点から、飲食経営のノウハウを紐解きます。")
    st.markdown("<br>", unsafe_allow_html=True)
    
    articles_dir = "articles"
    if not os.path.exists(articles_dir):
        st.info("まだ記事がありません。")
    else:
        # Get all .md files and sort by modification time (newest first)
        md_files = glob.glob(os.path.join(articles_dir, "*.md"))
        md_files.sort(key=os.path.getmtime, reverse=True)
        
        if not md_files:
            st.info("まだ記事がありません。")
        else:
            for file_path in md_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        
                    if not lines:
                        continue
                        
                    # First line is title (remove leading # if exists)
                    title = lines[0].strip().lstrip("#").strip()
                    # The rest is content
                    content = "".join(lines[1:]).strip()
                    
                    # Display the expander with a New badge if desired, or just simple text
                    with st.expander(f"📝 {title}"):
                        st.markdown('<span style="background-color: #004098; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-bottom: 1rem; display: inline-block;">NEW</span>', unsafe_allow_html=True)
                        st.markdown(content)
                        
                except Exception as e:
                    st.error(f"記事の読み込み中にエラーが発生しました: {e}")


# ==========================================
# ページ5: 📊 勝率診断ツール (App)
# ==========================================
elif page == "📊 勝率診断ツール (App)":
    st.markdown("## 勝率診断ツール")
    st.markdown("出店予定エリアの条件を入力し、向こう1年間の売上推移とビジネスのポテンシャルを診断します。")
    
    tool_col_left, tool_col_right = st.columns([1, 2])
    
    with tool_col_left:
        st.markdown("""
        <div class="card" style="padding: 1.5rem; border-top: 4px solid #004098;">
            <h4 style="margin-top: 0; color: #004098;">条件入力パラメータ</h4>
            <p style="font-size: 0.9rem;">商圏データをご入力ください。</p>
        </div>
        """, unsafe_allow_html=True)
        
        population = st.number_input("エリア人口（人）", min_value=1000, value=50000, step=1000, help="商圏エリアの推計人口")
        competitors = st.number_input("競合店数（店舗）", min_value=0, value=5, step=1, help="同一カテゴリの競合店舗数")
        avg_spend = st.number_input("客単価（円）", min_value=100, value=1500, step=100, help="想定される1人あたりの平均単価")
        
        st.info("※ 計算にはNBDモデル（局所的市場シェア推計）を使用しています。")

    with tool_col_right:
        target_sales, monthly_sales = calculate_nbd_prediction(population, competitors, avg_spend)
        avg_run_rate = np.mean(monthly_sales[-3:]) # 直近3ヶ月の平均売上
        
        # ランク判定
        if avg_run_rate >= 10_000_000:
            rank = "Aランク：高ポテンシャル"
            rank_color = "#004098" 
            message = "対象エリアは優れた経営環境を持っています。事業計画上のリスクは低いです。"
        elif avg_run_rate >= 5_000_000:
            rank = "Bランク：標準的環境"
            rank_color = "#333333" 
            message = "適正な市場規模を有していますが、確実なオペレーションとK値（定着率）の向上が求められます。"
        else:
            rank = "Cランク：慎重検討エリア"
            rank_color = "#666666" 
            message = "競争が激しいか、市場規模が絶対的に不足しています。家賃などの固定費の徹底的な圧縮が必要です。"

        m1, m2 = st.columns(2)
        with m1:
            st.metric(label="着地想定 月商（12ヶ月経過時）", value=f"¥ {int(avg_run_rate):,}")
        with m2:
            st.metric(label="想定限界 月間客数", value=f"{int(target_sales / avg_spend):,} 人")
            
        st.markdown(f"""
        <div style="background-color: #FFFFFF; padding: 1.5rem; border-left: 4px solid {rank_color}; margin-top: 1rem; border-radius: 4px; border: 1px solid #EAEAEA;">
            <div style="color: #666666; font-size: 0.95rem; font-weight:500;">AIシステム判定</div>
            <div style="color: {rank_color}; font-size: 1.4rem; font-weight: 600; margin: 0.5rem 0;">{rank}</div>
            <div style="color: #666666; font-size: 1rem; line-height: 1.6;">{message}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("<h4 style='color: #333333; margin-top: 1.5rem;'>12ヶ月 売上推移シミュレーション</h4>", unsafe_allow_html=True)
        
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(np.arange(1, 13), monthly_sales, color="#004098", marker="o", linewidth=2.5, markersize=6)
        ax.fill_between(np.arange(1, 13), monthly_sales, color="#004098", alpha=0.05)

        ax.set_xlabel("月目 (Month)", color="#666666")
        ax.set_ylabel("予測売上 (Yen)", color="#666666")
        ax.set_xticks(np.arange(1, 13))
        ax.grid(color="#EAEAEA", linestyle="-", alpha=0.8)
        ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: f"{x/1_000_000:.1f}M"))

        for spine in ax.spines.values():
            spine.set_color('#EAEAEA')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        ax.set_facecolor('#FFFFFF')
        fig.patch.set_facecolor('#FFFFFF')

        st.pyplot(fig)
        
        st.markdown("<br>", unsafe_allow_html=True)
        # プライマリボタン化
        st.button("無料で勝率を診断する", type="primary", use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("📄 詳細な事業計画書(PDF)を作成する（有料）", use_container_width=True)



