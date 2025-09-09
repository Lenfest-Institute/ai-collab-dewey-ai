# Dewey
[![Python Version](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Azure OpenAI](https://img.shields.io/badge/Azure%20OpenAI-Powered-green.svg)](https://azure.microsoft.com/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)

Dewey is an AI-powered librarian designed to help newsrooms make their archives easy to search, making use of LLMs to provide cited responses. 

Archival research methods are cumbersome. Often times, they rely on keyword searches and date range filtering, making it difficult to surface topics without specific preexisting knowledge. Moreover, archives can live across disparate source systems/databases because of how content management systems evolve over time. Unifying these systems with a state-of-the-art search engine hopes to make archive research easier and more efficient for reporters.


## Acknowledgements
Special thank you to the [Lenfest Institute AI Collaborative and Fellowship Program](https://www.lenfestinstitute.org/institute-news/lenfest-institute-openai-microsoft-ai-collaborative-fellowship/) for making this project happen.
- Patrick Kerkstra, Ross Maghielse - newsroom guidance, support, and tester recruiting
- Tommy Rowan, Nick Vidala, Jennifer Friedman-Perez - Alpha testing users
- Lenfest Institute - for providing and securing the grant that made this project possible
- Microsoft - for co-funding the grant and jumpstarting our progress
- OpenAI - for co-funding the grant and providing technical support


## Installation

1. Clone the repository
```bash
git clone https://github.com/phillymedia/dewey-ai.git
cd dewey
```

2. Create virtual environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows:
.venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```


## Configuration

To run this project, you will need to add the following environment variables to your .env file

1. Copy environment template
```
cp .env.template .env
```

2. Configure your `.env` file
*Note: While most environment variables must specify preexisting resources and deployments,`AZURE_SEARCH_INDEX_NAME` represents the desired name for your search index.*
```
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
AZURE_OPENAI_API_KEY="your-azure-openai-api-key"
EMBEDDING_DEPLOYMENT_NAME="your-embedding-deployment-name"
EMBEDDING_MODEL_NAME="text-embedding-3-large"
CHATGPT_DEPLOYMENT_NAME="your-chatgpt-deployment-name"
CHATGPT_MODEL_NAME="gpt-5"

# Azure AI Search Configuration
AZURE_SEARCH_ENDPOINT="https://your-search-service.search.windows.net"
AZURE_SEARCH_API_KEY="your-azure-search-api-key"
AZURE_SEARCH_INDEX_NAME="your-search-index-name"  

# Azure Blob Storage Configuration
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."
AZURE_STORAGE_CONTAINER_NAME="your-storage-container-name"
```

## Deployment
1. Prepare Your Documents

Any articles you wish to upload should be in JSON format in the `data/` folder. Each document should follow this structure:

```json
{
    "id": "unique-document-id",
    "headline": "Article Title",
    "content": "Full article content...",
    "url": "https://example.com/article",
    "authors": ["Author 1", "Author 2", ...],
    "publish_date": "2025-09-09T12:00:00Z",
}
```

- `id` (optional) - A unique ID for your article. Will be autopopulated if you do not provide
- `headline` - A title to your article
- `content` - The full text to your article. It is up to you how to format this. **This will end up being your searchable field**
- `url` - A URL facing your article. This is critical for citation functionality
- `authors` - A list of author names from the article's byline
- `publish_date` - The date in which your article as published ([ISO 8601 format](https://en.wikipedia.org/wiki/ISO_8601))

2. Run Setup Script

```bash
python app/setup.py
```

This will:
- Validate your configuration
- Create Azure AI Search index with proper schema
- Set up skillsets for document processing (chunking and embedding)
- Create indexer for automated processing
- Upload documents to blob storage
- Process documents through AI Search pipeline

3. Launch Dewey
```bash
python main.py
```
The application will be available at `http://localhost:7860`. This project uses Gradio to create a user-friendly web interface for our machine learning model. You can learn more about Gradio at https://www.gradio.app/.


## Usage

1. **Open your browser** to `http://localhost:7860`
2. **Ask questions** in natural language:
    - "What articles did *author X* about the election last month?"
    - "Summarize the last decade of coverage on *topic X*."
    - "Find me the best restaurants mentioned in 2024."
3. **Expand Dewey's though process** to see *what was searched* and *how many articles* were retrieved


## Contributing

All contributions are welcome! More details to come. In the meantime, please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
