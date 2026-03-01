# 电商找客助手

AI 驱动的跨境电商 B2B 客户开发工具。上传产品 PDF，自动分析并匹配海外买家，深度挖掘决策人联系方式。

## 🚀 快速开始

### 方式 1: Docker 运行（推荐）

```bash
# 拉取镜像
docker pull yourusername/ecommerce-finder:latest

# 运行
docker run -p 8501:8501 yourusername/ecommerce-finder:latest
```

访问 http://localhost:8501

### 方式 2: 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
streamlit run app.py
```

## 🎯 功能特性

- 📄 **PDF 智能解析** - 自动提取产品信息
- 🌍 **多国家支持** - 美国、欧洲、英国、德国、日本等
- 🤖 **AI 匹配评分** - 0-100分智能评估买家匹配度
- 👤 **深度联系人挖掘** - 官网 + LinkedIn 双重搜索
- ✉️ **自动生成开发信** - 个性化 Cold Email
- 📊 **数据导出** - CSV / JSON / 邮箱列表

## 🛠 技术栈

- Python 3.11
- Streamlit
- Moonshot AI (Kimi)
- DuckDuckGo Search
- BeautifulSoup4

## 📝 使用说明

1. **步骤1** - 上传产品 PDF，AI 自动分析
2. **步骤2** - 选择目标国家，启动智能匹配
3. **步骤3** - 查看匹配结果，导出客户名单

## 🔒 隐私说明

- API Key 存储在服务端配置，前端不可见
- 所有数据本地处理，不上传第三方服务器

## 📄 License

MIT License
