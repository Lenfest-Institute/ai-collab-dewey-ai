import logging
from typing import List, Optional

from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    SplitSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    VectorSearch,
    VectorSearchProfile,
    VectorSearchVectorizer,
    AzureOpenAIEmbeddingSkill,
    SearchIndexerSkillset,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    SearchIndexerDataSourceConnection,
    SearchIndexerDataContainer,
    SearchIndexer,
    FieldMapping,
)

from azure.search.documents.indexes.aio import SearchIndexerClient
from .search_service import SearchInfo
from .embedding_service import EmbeddingService


logger = logging.getLogger("scripts")


class SearchManager:
    """
    Class to manage a search service. It can create indexes, and update or remove sections stored in these indexes
    To learn more, please visit https://learn.microsoft.com/azure/search/search-what-is-azure-search
    """

    def __init__(
        self,
        search_info: SearchInfo,
        embeddings: EmbeddingService,
        blob_connection_string: str,
        blob_container_name: str,
    ):
        self.search_info = search_info
        self.embeddings = embeddings
        self.embedding_dimensions = self.embeddings.DIMENSIONS
        self.blob_connection_string = blob_connection_string
        self.blob_container_name = blob_container_name

    async def create_index(self, vectorizers: Optional[List[VectorSearchVectorizer]] = None):
        logger.info("Checking whether search index %s exists...", self.search_info.index_name)

        async with self.search_info.create_search_index_client() as search_index_client:

            if self.search_info.index_name not in [name async for name in search_index_client.list_index_names()]:
                logger.info("Creating new search index %s", self.search_info.index_name)
                fields = [
                    SearchField(
                        name="chunk_id", 
                        type="Edm.String", 
                        key=True,
                        filterable=True,
                        sortable=True,
                        facetable=True,
                        analyzer_name="keyword",
                    ),
                    SearchableField(
                        name="content",
                        type="Edm.String",
                        analyzer_name="standard.lucene",
                    ),
                    SearchableField(
                        name="headline",
                        type="Edm.String",
                        analyzer_name="standard.lucene",
                    ),
                    SearchField(
                        name="content_vector",
                        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        hidden=False,
                        searchable=True,
                        filterable=False,
                        sortable=False,
                        facetable=False,
                        vector_search_dimensions=self.embedding_dimensions,
                        vector_search_profile_name="embedding_config",
                    ),
                    SimpleField(
                        name="url",
                        type="Edm.String",
                    ),
                    SimpleField(
                        name="authors",
                        type="Collection(Edm.String)",
                        filterable=True,
                        facetable=True,
                        retrievable=True,
                    ),
                    SimpleField(
                        name="publish_date",
                        type="Edm.DateTimeOffset",
                        filterable=True,
                        sortable=True,
                        facetable=True,
                        retrievable=True,
                        searchable=False
                    ),
                    SimpleField(
                        name="sourcepage",
                        type="Edm.String",
                        filterable=True,
                        facetable=True,
                    ),
                    SearchableField(
                        name="parent_id", 
                        type="Edm.String",
                        analyzer_name="standard.lucene",
                        filterable=True,
                        sortable=False,
                        facetable=False,
                        retrievable=True,
                    )
                ]

                vectorizers = [
                    AzureOpenAIVectorizer(
                        vectorizer_name=f"{self.search_info.index_name}-vectorizer",
                        parameters=AzureOpenAIVectorizerParameters(
                            resource_url=self.embeddings.endpoint,
                            deployment_name=self.embeddings.deployment,
                            model_name=self.embeddings.model_name,
                        ),
                    )
                ]

                index = SearchIndex(
                    name=self.search_info.index_name,
                    fields=fields,
                    semantic_search=SemanticSearch(
                        configurations=[
                            SemanticConfiguration(
                                name="default",
                                prioritized_fields=SemanticPrioritizedFields(
                                    title_field=SemanticField(field_name="headline"), 
                                    content_fields=[SemanticField(field_name="content")],
                                    keywords_fields=[SemanticField(field_name="content")],
                                ),
                            )
                        ]
                    ),
                    vector_search=VectorSearch(
                        algorithms=[
                            HnswAlgorithmConfiguration(
                                name="hnsw_config",
                                parameters=HnswParameters(metric="cosine"),
                            )
                        ],
                        profiles=[
                            VectorSearchProfile(
                                name="embedding_config",
                                algorithm_configuration_name="hnsw_config",
                                vectorizer_name=(
                                    f"{self.search_info.index_name}-vectorizer"
                                ),
                            ),
                        ],
                        vectorizers=vectorizers,
                    ),
                )

                await search_index_client.create_index(index)

    async def create_blob_data_source(self):
        """Create a blob data source for the indexer."""
        data_source_name = f"{self.search_info.index_name}-blob-ds"
        
        data_source = SearchIndexerDataSourceConnection(
            name=data_source_name,
            type="azureblob",
            connection_string=self.blob_connection_string,
            container=SearchIndexerDataContainer(name=self.blob_container_name)
        )
        
        return data_source, data_source_name

    async def create_index_skills(self):
        skillset_name = f"{self.search_info.index_name}-skillset"

        split_skill = SplitSkill(
            name=f"{self.search_info.index_name}-split-skill",
            description="Split skill to chunk documents",
            text_split_mode="pages",
            context="/document",
            maximum_page_length=512,
            page_overlap_length=96,
            maximum_pages_to_take=0,
            unit="azureOpenAITokens",
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/content"),
            ],
            outputs=[
                OutputFieldMappingEntry(name="textItems", target_name="pages")
            ],
        )

        text_embedding_skill = AzureOpenAIEmbeddingSkill(
            name=f"{self.search_info.index_name}-text-embedding-skill",
            description="Embedding skill to generate embeddings",
            context="/document/pages/*",
            resource_url=self.embeddings.endpoint,
            deployment_name=self.embeddings.deployment,
            model_name=self.embeddings.model_name,
            dimensions=self.embeddings.DIMENSIONS,
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/pages/*"),
            ],
            outputs=[
                OutputFieldMappingEntry(name="embedding", target_name="content_vector")
            ],
        )

        index_projection = SearchIndexerIndexProjection(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=self.search_info.index_name,
                    parent_key_field_name="parent_id",
                    source_context="/document/pages/*",
                    mappings=[
                        InputFieldMappingEntry(name="content", source="/document/pages/*"),
                        InputFieldMappingEntry(name="headline", source="/document/headline"),
                        InputFieldMappingEntry(name="content_vector", source="/document/pages/*/content_vector"),
                        InputFieldMappingEntry(name="url", source="/document/url"),
                        InputFieldMappingEntry(name="authors", source="/document/authors"),
                        InputFieldMappingEntry(name="publish_date", source="/document/publish_date"),
                        InputFieldMappingEntry(name="sourcepage", source="/document/metadata_storage_name"),
                    ],
                ),
            ],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
            ),
        )

        skillset = SearchIndexerSkillset(
            name=skillset_name,
            description="Skillset to process documents and generate embeddings",
            skills=[split_skill, text_embedding_skill],
            index_projection=index_projection,
        )

        return skillset

    async def create_indexer(self, skillset_name: str, data_source_name: str):
        """Create an indexer to connect data source through skillset to index."""
        indexer_name = f"{self.search_info.index_name}-indexer"
        
        indexer = SearchIndexer(
            name=indexer_name,
            description="Indexer to automatically process documents through skillset",
            skillset_name=skillset_name,
            target_index_name=self.search_info.index_name,
            data_source_name=data_source_name,
            field_mappings=[
                FieldMapping(source_field_name="content", target_field_name="content"),
                FieldMapping(source_field_name="headline", target_field_name="headline"),
                FieldMapping(source_field_name="url", target_field_name="url"),
                FieldMapping(source_field_name="authors", target_field_name="authors"),
                FieldMapping(source_field_name="publish_date", target_field_name="publish_date"),
            ],
            parameters={
                "configuration": {
                    "parsingMode": "json",
                    "dataToExtract": "contentAndMetadata"
                }
            }
        )
        
        return indexer, indexer_name

    async def setup(self):
        ds_client = SearchIndexerClient(endpoint=self.search_info.endpoint, credential=self.search_info.credential)

        # Create blob data source
        data_source, data_source_name = await self.create_blob_data_source()
        await ds_client.create_or_update_data_source_connection(data_source)

        # Create skillset
        embedding_skillset = await self.create_index_skills()
        await ds_client.create_or_update_skillset(embedding_skillset)

        # Create indexer
        indexer, indexer_name = await self.create_indexer(embedding_skillset.name, data_source_name)
        await ds_client.create_or_update_indexer(indexer)

        await ds_client.close()

        return indexer_name


async def main(search_info, embeddings):
    search_manager = SearchManager(
        search_info,
        embeddings
    )

    await search_manager.create_index()
    await search_manager.setup()
