import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, List
import sys

from setup import SearchManager, SearchInfo, EmbeddingService
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob.aio import BlobServiceClient
from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when configuration is invalid or incomplete."""
    pass


class SetupManager:
    """Professional setup manager for Azure AI Search integration."""
    
    def __init__(self):
        self.data_folder = Path(__file__).parent.parent / "data"
        self.env_file = Path(__file__).parent.parent / ".env"
        
        # Load environment variables
        load_dotenv(self.env_file)
        
    def validate_configuration(self) -> Dict[str, str]:
        """Validate and return configuration from environment variables."""
        
        required_vars = {
            'AZURE_OPENAI_ENDPOINT': 'Azure OpenAI service endpoint',
            'AZURE_OPENAI_API_KEY': 'Azure OpenAI API key',
            'EMBEDDING_DEPLOYMENT_NAME': 'Azure OpenAI embedding deployment name',
            'EMBEDDING_MODEL_NAME': 'Azure OpenAI embedding model name',
            'AZURE_SEARCH_ENDPOINT': 'Azure AI Search service endpoint',
            'AZURE_SEARCH_API_KEY': 'Azure AI Search API key',
            'AZURE_SEARCH_INDEX_NAME': 'Azure AI Search index name',
            'AZURE_STORAGE_CONNECTION_STRING': 'Azure Storage connection string',
            'AZURE_STORAGE_CONTAINER_NAME': 'Azure Storage container name'
        }
        
        config = {}
        missing_vars = []
        
        for var_name, description in required_vars.items():
            value = os.getenv(var_name)
            if not value or value.strip() == "":
                missing_vars.append(f"  - {var_name}: {description}")
            else:
                config[var_name] = value.strip()
                
        if missing_vars:
            error_msg = (
                "Missing required environment variables in .env file:\n"
                + "\n".join(missing_vars) +
                f"\n\nPlease update your .env file at: {self.env_file}"
            )
            raise ConfigurationError(error_msg)
            
        return config
        
    def check_data_folder(self) -> List[Path]:
        """Check for JSON documents in data folder."""
        if not self.data_folder.exists():
            print(f"📁 Creating data folder at {self.data_folder}")
            self.data_folder.mkdir(exist_ok=True)
            return []
            
        json_files = list(self.data_folder.glob("*.json"))
        
        if json_files:
            print(f"📄 Found {len(json_files)} JSON document(s) in data folder:")
            for file in json_files:
                print(f"  - {file.name}")
        else:
            print("📁 No JSON documents found in data folder.")
            print(f"   Place your JSON documents in: {self.data_folder}")
            
        return json_files
        
    def load_documents(self, json_files: List[Path]) -> List[Dict[str, Any]]:
        """Load and validate JSON documents."""
        documents = []
        required_fields = ['headline', 'content', 'url', 'authors', 'publish_date']
        
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                file_documents = data if isinstance(data, list) else [data]
                
                for i, doc in enumerate(file_documents):
                    # Validate required fields
                    missing_fields = [field for field in required_fields if field not in doc or not doc[field]]
                    
                    if missing_fields:
                        print(f"⚠️  Skipping document {i} in {file_path.name}: missing required fields: {', '.join(missing_fields)}")
                        continue
                        
                    documents.append(doc)
                    
                print(f"✅ Loaded {len([doc for doc in file_documents if all(field in doc and doc[field] for field in required_fields)])} valid document(s) from {file_path.name}")
                
            except Exception as e:
                print(f"❌ Error loading {file_path.name}: {e}")
                
        return documents
        
    async def setup_azure_resources(self, config: Dict[str, str]) -> tuple:
        """Set up Azure AI Search resources."""
        
        # Initialize services
        search_info = SearchInfo(
            endpoint=config['AZURE_SEARCH_ENDPOINT'],
            credential=AzureKeyCredential(config['AZURE_SEARCH_API_KEY']),
            index_name=config['AZURE_SEARCH_INDEX_NAME']
        )
        
        embeddings = EmbeddingService(
            endpoint=config['AZURE_OPENAI_ENDPOINT'],
            deployment=config['EMBEDDING_DEPLOYMENT_NAME'],
            model_name=config['EMBEDDING_MODEL_NAME']
        )
        
        # Create search manager
        search_manager = SearchManager(
            search_info, 
            embeddings, 
            config['AZURE_STORAGE_CONNECTION_STRING'],
            config['AZURE_STORAGE_CONTAINER_NAME']
        )
        
        print("🔧 Creating Azure AI Search index...")
        await search_manager.create_index()
        print("✅ Index created successfully")
        
        print("⚙️  Setting up skillset and indexer...")
        indexer_name = await search_manager.setup()
        print(f"✅ Skillset and indexer '{indexer_name}' created successfully")
        
        return search_info, embeddings, search_manager
        
    async def upload_documents_to_blob(self, blob_connection_string: str, container_name: str, documents: List[Dict[str, Any]]):
        """Upload documents to blob storage for indexer processing."""
        if not documents:
            print("📄 No documents to upload")
            return
            
        print(f"📤 Uploading {len(documents)} document(s) to blob storage...")
        
        async with BlobServiceClient.from_connection_string(blob_connection_string) as blob_service_client:
            try:
                # Ensure container exists
                container_client = blob_service_client.get_container_client(container_name)
                try:
                    await container_client.create_container()
                    print(f"✅ Created container '{container_name}'")
                except Exception:
                    # Container already exists
                    pass
                
                success_count = 0
                for i, doc in enumerate(documents):
                    try:
                        # Create a JSON document for the blob
                        blob_name = f"doc_{doc.get('id', i)}.json"
                        blob_data = json.dumps(doc, ensure_ascii=False, indent=2)
                        
                        # Upload to blob storage
                        blob_client = blob_service_client.get_blob_client(
                            container=container_name, 
                            blob=blob_name
                        )
                        await blob_client.upload_blob(blob_data, overwrite=True)
                        success_count += 1
                        
                    except Exception as e:
                        print(f"❌ Error uploading document {i}: {e}")
                
                print(f"✅ Successfully uploaded {success_count} document(s) to blob storage")
                
                if success_count < len(documents):
                    failed_count = len(documents) - success_count
                    print(f"❌ Failed to upload {failed_count} document(s)")
                    
            except Exception as e:
                print(f"❌ Error uploading documents to blob storage: {e}")
    
    async def run_indexer(self, search_info: SearchInfo, indexer_name: str):
        """Run the indexer to process documents from blob storage."""
        print(f"🔄 Running indexer '{indexer_name}' to process documents...")
        
        from azure.search.documents.indexes.aio import SearchIndexerClient
        
        async with SearchIndexerClient(endpoint=search_info.endpoint, credential=search_info.credential) as indexer_client:
            try:
                # Run the indexer
                await indexer_client.run_indexer(indexer_name)
                print(f"✅ Indexer '{indexer_name}' started successfully")
                print("📋 Documents will be processed automatically by the indexer")
                print("   - Text will be chunked into manageable pieces") 
                print("   - Embeddings will be generated automatically")
                print("   - Processed chunks will be added to the search index")
                
            except Exception as e:
                print(f"❌ Error running indexer: {e}")
        
    async def run_setup(self):
        """Run the complete setup process."""
        print("=" * 60)
        print("🔍 Azure AI Search Setup")
        print("=" * 60)
        
        try:
            # Validate configuration
            print("🔧 Validating configuration...")
            config = self.validate_configuration()
            print("✅ Configuration validated successfully")
            
            # Check for documents
            json_files = self.check_data_folder()
            documents = []
            
            if json_files:
                print("\n📄 Loading documents...")
                documents = self.load_documents(json_files)
                
            # Set up Azure resources
            print("\n🚀 Setting up Azure AI Search resources...")
            search_info, embeddings, search_manager = await self.setup_azure_resources(config)
            indexer_name = f"{config['AZURE_SEARCH_INDEX_NAME']}-indexer"
            
            # Upload documents to blob storage if available
            if documents:
                await self.upload_documents_to_blob(
                    config['AZURE_STORAGE_CONNECTION_STRING'],
                    config['AZURE_STORAGE_CONTAINER_NAME'],
                    documents
                )
                
                # Run the indexer to process uploaded documents
                print("\n🔄 Processing documents through skillset...")
                await self.run_indexer(search_info, indexer_name)
                
            print("\n🎉 Setup completed successfully!")
            print("=" * 60)
            print("Your Azure AI Search environment is ready to use.")
            print(f"Index: {config['AZURE_SEARCH_INDEX_NAME']}")
            print(f"Documents indexed: {len(documents)}")
            print("=" * 60)
            
        except ConfigurationError as e:
            print(f"❌ Configuration Error:\n{e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            sys.exit(1)


async def main():
    """Main entry point."""
    setup_manager = SetupManager()
    await setup_manager.run_setup()


if __name__ == "__main__":
    asyncio.run(main())