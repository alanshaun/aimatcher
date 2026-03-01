#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电商找客助手 - 专业版
智能匹配海外买家，深度挖掘决策人
"""

import streamlit as st
import PyPDF2
import pandas as pd
import json
import re
import time
import requests
from typing import List, Dict, Tuple
from datetime import datetime
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup

# 后端配置（用户不可见）
BACKEND_CONFIG = {
    "moonshot_api_key": "sk-jJ6WOdbVwIpdtV9Hksc7azzIUuMIfUrvU9sXcwpPek3h2Kka",
    "proxy": "http://127.0.0.1:7890"
}

# 尝试导入 DDGS
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

# ============== 页面配置 ==============
st.set_page_config(
    page_title="电商找客助手",
    page_icon="🎯",
    layout="wide"
)

# ============== Session State ==============
for key in ['product_data', 'companies', 'logs', 'analysis_complete']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'logs' else []

def log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {msg}")
    if len(st.session_state.logs) > 100:
        st.session_state.logs = st.session_state.logs[-100:]

# ============== AI 调用（后端） ==============
def call_moonshot(prompt: str, temperature: float = 0.7) -> str:
    """后端调用 Moonshot，用户不可见"""
    try:
        url = "https://api.moonshot.cn/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {BACKEND_CONFIG['moonshot_api_key']}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "moonshot-v1-128k",
            "messages": [
                {"role": "system", "content": "你是一位资深的跨境电商B2B销售专家，擅长海外市场分析和客户开发。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": 4000
        }
        
        resp = requests.post(url, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log(f"AI调用失败: {str(e)[:80]}")
        return ""

# ============== PDF 解析 ==============
def extract_pdf(file) -> str:
    try:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            try:
                t = page.extract_text()
                if t:
                    text += t + "\n"
            except:
                continue
        return text[:15000]
    except Exception as e:
        st.error(f"PDF解析失败: {e}")
        return ""

# ============== 智能搜索 ==============
def search_companies(keywords: List[str], country: str, min_results: int = 10) -> List[Dict]:
    """智能搜索目标公司"""
    all_results = []
    seen_urls = set()
    
    # 构建地区化搜索词
    country_terms = {
        "美国": "USA United States America",
        "欧洲": "Europe EU Germany UK France",
        "英国": "UK United Kingdom England",
        "德国": "Germany Deutschland",
        "日本": "Japan 日本",
        "澳洲": "Australia AU",
        "加拿大": "Canada CA",
        "全球": "global worldwide international"
    }
    country_suffix = country_terms.get(country, country)
    
    search_strategies = [
        # 策略1: 产品 + 国家 + distributor
        [(f"{kw} {country_suffix} distributor wholesale", 5) for kw in keywords[:2]],
        # 策略2: 产品 + 国家 + supplier
        [(f"{kw} {country_suffix} supplier manufacturer", 5) for kw in keywords[:2]],
        # 策略3: 宽泛搜索
        [(f"{' '.join(keywords[:2])} {country_suffix} B2B company", 8)],
        # 策略4: 行业搜索
        [(f"{keywords[0]} industry {country_suffix} contact", 5)],
    ]
    
    for strategy_idx, strategy in enumerate(search_strategies, 1):
        if len(all_results) >= min_results:
            break
            
        log(f"搜索策略 {strategy_idx}...")
        for search_kw, max_res in strategy:
            if len(all_results) >= min_results:
                break
                
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(search_kw, max_results=max_res))
                    for r in results:
                        url = r.get("href", "")
                        if url and url not in seen_urls:
                            # 基础过滤
                            if url.startswith("http") and not any(x in url.lower() for x in 
                                ['google.com', 'youtube.com', 'facebook.com', 'twitter.com', 
                                 'instagram.com', 'reddit.com', 'wikipedia.org', 'amazon.com']):
                                seen_urls.add(url)
                                all_results.append({
                                    "title": r.get("title", ""),
                                    "url": url,
                                    "snippet": r.get("body", "")
                                })
                    log(f"  找到 {len(results)} 个结果")
            except Exception as e:
                log(f"  搜索失败: {str(e)[:60]}")
            
            time.sleep(0.5)
    
    return all_results[:min_results]

# ============== 深度信息挖掘 ==============
def scrape_company_info(url: str) -> Dict:
    """深度抓取公司信息"""
    info = {
        "url": url,
        "title": "",
        "description": "",
        "emails": [],
        "phones": [],
        "linkedin_company": "",
        "facebook": "",
        "country": "",
        "contact_page": ""
    }
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=12)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        info["title"] = soup.title.string.strip() if soup.title else ""
        
        # 提取描述
        desc_meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if desc_meta:
            info["description"] = desc_meta.get("content", "")
        
        # 提取邮箱
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, resp.text)
        invalid = ['.png', '.jpg', 'example.com', 'test.com', 'babel-', 'polyfill@', 'runtime@', 'u003e']
        valid_emails = [e for e in emails if not any(p in e.lower() for p in invalid) and '@' in e]
        info["emails"] = list(set(valid_emails))[:5]
        
        # 提取电话
        phone_patterns = [
            r'\+?1[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',
            r'\+?[0-9]{1,3}[-.\s]?\(?[0-9]{2,4}\)?[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,4}'
        ]
        phones = []
        for p in phone_patterns:
            phones.extend(re.findall(p, resp.text))
        info["phones"] = list(set([p for p in phones if len(re.sub(r'\D', '', p)) >= 10]))[:3]
        
        # 提取社媒
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'linkedin.com/company' in href:
                info["linkedin_company"] = href if href.startswith('http') else urljoin(url, href)
            elif 'linkedin.com/in/' in href:
                info["linkedin_personal"] = href if href.startswith('http') else urljoin(url, href)
            elif 'facebook.com/' in href:
                info["facebook"] = href if href.startswith('http') else urljoin(url, href)
        
        # 找联系页面
        for a in soup.find_all('a', href=True):
            if any(x in a.get_text().lower() for x in ['contact', 'about us', 'about']):
                href = a['href']
                if href:
                    info["contact_page"] = urljoin(url, href)
                    break
        
        # 识别国家
        country_keywords = {
            'USA': ['usa', 'united states', ' america', ' us '],
            'UK': ['uk', 'united kingdom', ' england', ' britain'],
            'Germany': ['germany', 'deutschland', ' german'],
            'France': ['france', 'french'],
            'Japan': ['japan', 'japanese', '日本'],
            'Australia': ['australia', 'australian'],
            'Canada': ['canada', 'canadian']
        }
        text_lower = resp.text.lower()
        for country, keywords in country_keywords.items():
            if any(kw in text_lower for kw in keywords):
                info["country"] = country
                break
        
    except Exception as e:
        log(f"抓取失败: {str(e)[:60]}")
    
    return info

def search_linkedin_person(company_name: str) -> Dict:
    """搜索 LinkedIn 负责人"""
    person = {"name": "", "title": "", "linkedin_url": "", "email_guess": ""}
    
    try:
        # 搜索公司 + procurement manager
        search_queries = [
            f"{company_name} procurement manager buyer linkedin",
            f"{company_name} purchasing director linkedin",
            f"{company_name} supply chain manager linkedin",
            f"{company_name} CEO owner linkedin"
        ]
        
        for query in search_queries:
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=3))
                    for r in results:
                        title = r.get("title", "")
                        url = r.get("href", "")
                        
                        # 解析 LinkedIn 结果
                        if "linkedin.com/in/" in url:
                            # 提取姓名 (格式通常是 "Name - Title | LinkedIn")
                            if " - " in title and "LinkedIn" in title:
                                parts = title.split(" - ")
                                name = parts[0].strip()
                                title_part = parts[1].replace("| LinkedIn", "").strip()
                                
                                # 验证职位相关性
                                relevant_titles = ['procurement', 'purchasing', 'buyer', 'sourcing', 
                                                  'supply chain', 'category manager', 'director', 
                                                  'CEO', 'owner', 'president', 'VP', 'head of']
                                
                                if any(rt.lower() in title_part.lower() for rt in relevant_titles):
                                    person["name"] = name
                                    person["title"] = title_part
                                    person["linkedin_url"] = url
                                    
                                    # 猜测邮箱 (firstname@company.com)
                                    if name and " " in name:
                                        first_name = name.split()[0].lower()
                                        # 从公司名提取域名
                                        company_domain = company_name.lower().replace(" ", "").replace("&", "and")
                                        person["email_guess"] = f"{first_name}@{company_domain}.com"
                                    
                                    return person
            except:
                continue
            time.sleep(0.5)
        
    except Exception as e:
        log(f"LinkedIn搜索失败: {str(e)[:60]}")
    
    return person

# ============== AI 智能匹配评分 ==============
def analyze_company_match(company_info: Dict, product_text: str) -> Tuple[int, str, str]:
    """
    AI 分析公司匹配度
    返回: (匹配分数 0-100, 匹配理由, 公司规模/风格)
    """
    prompt = f"""作为资深B2B销售专家，请深度分析以下潜在买家与产品的匹配度。

【我方产品】
{product_text[:2000]}

【目标公司信息】
- 公司名称: {company_info.get('title', 'Unknown')}
- 公司描述: {company_info.get('description', 'N/A')[:500]}
- 国家/地区: {company_info.get('country', 'Unknown')}
- 官网: {company_info.get('url', '')}

请从以下维度分析并评分（满分100分）：
1. **业务匹配度** (30分): 该公司业务是否真正需要我方产品
2. **采购能力** (25分): 公司规模、历史、是否具备进口采购能力
3. **市场定位** (25分): 品牌定位、价格带是否与我方产品匹配
4. **合作可能性** (20分): 基于描述判断其开放度、国际化程度

输出格式:
SCORE_START
[总分数字，0-100]
SCORE_END

MATCH_REASON_START
[用中文简洁说明匹配理由，50字以内]
MATCH_REASON_END

COMPANY_PROFILE_START
[公司画像: 规模(大/中/小)、风格(高端/大众/性价比)、历史年限估计、主要市场]
COMPANY_PROFILE_END
"""
    
    resp = call_moonshot(prompt, temperature=0.5)
    
    score = 50  # 默认中等
    match_reason = "基于AI分析的初步匹配"
    profile = "中型公司，风格待定"
    
    if resp:
        # 提取分数
        score_match = re.search(r'SCORE_START\s*(\d+)\s*SCORE_END', resp, re.DOTALL)
        if score_match:
            score = int(score_match.group(1))
            score = max(0, min(100, score))  # 确保0-100
        
        # 提取匹配理由
        reason_match = re.search(r'MATCH_REASON_START\s*(.*?)\s*MATCH_REASON_END', resp, re.DOTALL)
        if reason_match:
            match_reason = reason_match.group(1).strip()
        
        # 提取公司画像
        profile_match = re.search(r'COMPANY_PROFILE_START\s*(.*?)\s*COMPANY_PROFILE_END', resp, re.DOTALL)
        if profile_match:
            profile = profile_match.group(1).strip()
    
    return score, match_reason, profile

# ============== 生成开发信 ==============
def generate_email(company_name: str, person_name: str, person_title: str, 
                   product_text: str, match_reason: str, tone: str) -> str:
    """生成个性化开发信"""
    prompt = f"""作为资深外贸销冠，请为以下客户写一封高转化率的英文开发信。

【客户信息】
- 公司名称: {company_name}
- 收件人: {person_name} ({person_title})
- 匹配理由: {match_reason}

【我方产品】
{product_text[:1500]}

【要求】
- 语气: {tone}
- 开头必须提及对方公司名称
- 结合匹配理由，说明为什么我们的产品适合他们
- 150-200字
- 含引人注目的Subject Line
- 落款: Best regards

输出格式:
SUBJECT: [邮件主题]

[正文]

Best regards"""
    
    return call_moonshot(prompt) or "Email generation failed"

# ============== UI 界面 ==============
st.title("🎯 电商找客助手")
st.caption("智能匹配海外买家 · 深度挖掘决策人")

# 步骤指示器
step = st.radio("选择步骤", ["1. 上传产品资料", "2. 智能匹配买家", "3. 查看与导出"], 
                horizontal=True, label_visibility="collapsed")

# ============== 步骤1: 上传产品 ==============
if step == "1. 上传产品资料":
    st.header("📄 上传产品资料")
    
    uploaded_file = st.file_uploader("选择产品PDF", type=['pdf'])
    
    if uploaded_file:
        text = extract_pdf(uploaded_file)
        if text:
            st.success(f"成功提取 {len(text)} 字符")
            with st.expander("预览内容"):
                st.text(text[:2000])
            
            if st.button("🚀 开始分析", type="primary"):
                with st.spinner("AI正在分析产品..."):
                    log("开始产品分析...")
                    
                    # AI 分析产品
                    prompt = f"""分析以下产品，提取关键信息：
{text[:10000]}

输出：
1. 核心卖点（3-5点）
2. 目标客户类型
3. 适合的英文搜索关键词（5个）
格式: KEYWORDS: word1, word2, word3, word4, word5"""
                    
                    analysis = call_moonshot(prompt)
                    
                    # 提取关键词
                    keywords = []
                    kw_match = re.search(r'KEYWORDS:\s*(.+)', analysis, re.IGNORECASE)
                    if kw_match:
                        keywords = [k.strip() for k in kw_match.group(1).split(',')]
                    
                    st.session_state.product_data = {
                        "text": text,
                        "analysis": analysis,
                        "keywords": keywords
                    }
                    log("产品分析完成")
                    st.success("✅ 分析完成！请前往下一步")

# ============== 步骤2: 智能匹配 ==============
if step == "2. 智能匹配买家":
    st.header("🔍 智能匹配买家")
    
    if not st.session_state.product_data:
        st.warning("请先完成步骤1：上传产品资料")
        st.stop()
    
    # 国家选择
    col1, col2 = st.columns([1, 3])
    with col1:
        country = st.selectbox("🌍 目标国家/地区", 
            ["美国", "欧洲", "英国", "德国", "法国", "日本", "澳洲", "加拿大", "全球"],
            index=0)
    with col2:
        keywords = st.session_state.product_data["keywords"]
        st.info(f"搜索关键词: {', '.join(keywords[:5])}")
    
    # 开发信语气
    tone = st.selectbox("📧 开发信语气", 
        ["非常正式", "正式", "友好专业", "轻松"],
        index=2)
    
    if st.button("🚀 启动智能匹配", type="primary"):
        st.session_state.companies = []
        st.session_state.logs = []
        
        # 阶段1: 搜索公司
        with st.spinner("🔍 正在全网搜索目标客户..."):
            log(f"开始搜索 {country} 市场的潜在客户...")
            companies = search_companies(keywords, country, min_results=10)
            log(f"找到 {len(companies)} 家潜在公司")
        
        if not companies:
            st.error("未找到任何公司，请尝试更换关键词或国家")
            st.stop()
        
        # 阶段2: 深度挖掘（后台进行，不显示）
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        enriched_companies = []
        for i, company in enumerate(companies):
            progress = (i + 1) / len(companies)
            progress_bar.progress(min(int(progress * 100), 99))
            status_text.text(f"正在深度分析第 {i+1}/{len(companies)} 家公司...")
            
            # 抓取官网信息
            log(f"[{i+1}/{len(companies)}] 分析: {company['title'][:50]}...")
            info = scrape_company_info(company["url"])
            
            # 如果官网没找到联系人，搜索 LinkedIn
            person = {"name": "", "title": "", "linkedin": "", "email": ""}
            if not info.get("emails") and not info.get("linkedin_personal"):
                company_name = company["title"].split(" - ")[0].split(" | ")[0][:50]
                log(f"  搜索 LinkedIn 负责人...")
                person = search_linkedin_person(company_name)
            
            # 如果 LinkedIn 也没找到，尝试从邮箱反推
            if not person["name"] and info["emails"]:
                email = info["emails"][0]
                local_part = email.split("@")[0]
                if "." in local_part:
                    # firstname.lastname@company.com
                    parts = local_part.split(".")
                    person["name"] = " ".join([p.capitalize() for p in parts])
                    person["title"] = "Procurement Manager"
                    person["email"] = email
            
            # AI 匹配度评分（后台）
            log(f"  AI评估匹配度...")
            score, match_reason, profile = analyze_company_match(info, st.session_state.product_data["text"])
            
            # 生成开发信
            company_name_clean = company["title"].split(" - ")[0][:60]
            person_name = person["name"] if person["name"] else "Manager"
            person_title = person["title"] if person["title"] else "Procurement"
            
            log(f"  生成专属开发信...")
            email = generate_email(company_name_clean, person_name, person_title,
                                  st.session_state.product_data["text"], match_reason, tone)
            
            enriched_companies.append({
                **company,
                **info,
                "person": person,
                "match_score": score,
                "match_reason": match_reason,
                "profile": profile,
                "email_content": email,
                "ai_tone": tone
            })
            
            time.sleep(0.3)
        
        # 按匹配度排序
        enriched_companies.sort(key=lambda x: x["match_score"], reverse=True)
        
        st.session_state.companies = enriched_companies
        progress_bar.empty()
        status_text.empty()
        
        st.success(f"✅ 成功分析 {len(enriched_companies)} 家公司！请前往下一步查看")

# ============== 步骤3: 查看与导出 ==============
if step == "3. 查看与导出":
    st.header("📋 匹配结果")
    
    if not st.session_state.companies:
        st.warning("请先完成步骤2：智能匹配买家")
        st.stop()
    
    companies = st.session_state.companies
    
    # 筛选显示
    min_score = st.slider("最低匹配分数", 0, 100, 40)
    filtered = [c for c in companies if c["match_score"] >= min_score]
    
    st.write(f"显示 {len(filtered)} 家公司（共 {len(companies)} 家）")
    
    # 显示列表
    for i, c in enumerate(filtered, 1):
        score_color = "🟢" if c["match_score"] >= 70 else "🟡" if c["match_score"] >= 50 else "🔴"
        
        with st.container(border=True):
            cols = st.columns([0.5, 3, 1])
            with cols[0]:
                st.markdown(f"### {score_color} {c['match_score']}分")
            with cols[1]:
                st.markdown(f"**{i}. {c['title']}**")
                st.caption(f"[访问官网]({c['url']})")
                st.write(f"📝 {c['match_reason']}")
                st.caption(f"📊 {c['profile']}")
            with cols[2]:
                if c.get("country"):
                    st.write(f"📍 {c['country']}")
            
            # 联系信息
            st.markdown("---")
            contact_cols = st.columns(3)
            
            with contact_cols[0]:
                st.markdown("**👤 决策者**")
                if c["person"].get("name"):
                    st.write(f"姓名: {c['person']['name']}")
                    st.write(f"职位: {c['person']['title']}")
                    if c["person"].get("linkedin"):
                        st.markdown(f"[LinkedIn]({c['person']['linkedin']})")
                elif c.get("emails"):
                    st.write("📧 通过邮箱联系")
                else:
                    st.write("📧 建议通过官网联系表单")
            
            with contact_cols[1]:
                st.markdown("**📞 联系方式**")
                if c.get("emails"):
                    for e in c["emails"][:2]:
                        st.code(e)
                else:
                    st.caption("官网未公开邮箱")
                
                if c.get("phones"):
                    for p in c["phones"][:1]:
                        st.write(f"📱 {p}")
            
            with contact_cols[2]:
                st.markdown("**🔗 社媒**")
                if c.get("linkedin_company"):
                    st.markdown(f"[LinkedIn公司页]({c['linkedin_company']})")
                if c.get("facebook"):
                    st.markdown(f"[Facebook]({c['facebook']})")
            
            # 开发信
            with st.expander("📧 查看开发信"):
                if c.get("email_content"):
                    parts = c["email_content"].split("\n\n", 1)
                    if len(parts) == 2 and "SUBJECT:" in parts[0].upper():
                        st.markdown(f"**主题:** {parts[0].replace('SUBJECT:', '').strip()}")
                        st.markdown("---")
                        st.text(parts[1])
                    else:
                        st.text(c["email_content"])
                else:
                    st.write("开发信生成失败")
    
    # 导出
    st.divider()
    st.header("📥 导出数据")
    
    export_data = []
    for c in companies:
        export_data.append({
            "匹配分数": c["match_score"],
            "公司名称": c["title"],
            "国家": c.get("country", ""),
            "官网": c["url"],
            "匹配理由": c["match_reason"],
            "公司画像": c["profile"],
            "负责人姓名": c["person"].get("name", ""),
            "负责人职位": c["person"].get("title", ""),
            "负责人LinkedIn": c["person"].get("linkedin", ""),
            "邮箱": ", ".join(c.get("emails", [])),
            "电话": ", ".join(c.get("phones", [])),
            "开发信": c.get("email_content", "")
        })
    
    df = pd.DataFrame(export_data)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("📄 CSV", df.to_csv(index=False, encoding='utf-8-sig'), 
                          f"客户名单_{datetime.now().strftime('%Y%m%d')}.csv")
    with col2:
        st.download_button("📄 JSON", json.dumps(export_data, ensure_ascii=False, indent=2),
                          f"客户名单_{datetime.now().strftime('%Y%m%d')}.json")
    with col3:
        valid_emails = [e for c in companies for e in c.get("emails", [])]
        if c["person"].get("email"):
            valid_emails.append(c["person"]["email"])
        st.download_button("📧 邮箱列表", "\n".join(list(set(valid_emails))),
                          f"邮箱列表_{datetime.now().strftime('%Y%m%d')}.txt")
    
    # 统计
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总客户数", len(companies))
    c2.metric("高匹配(≥70分)", sum(1 for c in companies if c["match_score"] >= 70))
    c3.metric("有负责人姓名", sum(1 for c in companies if c["person"].get("name")))
    c4.metric("有邮箱", sum(1 for c in companies if c.get("emails") or c["person"].get("email")))

# 调试日志（默认隐藏）
with st.sidebar:
    if st.checkbox("显示调试日志"):
        st.header("📋 日志")
        for log_msg in st.session_state.logs[-30:]:
            st.text(log_msg)
