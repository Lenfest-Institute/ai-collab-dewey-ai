from dataclasses import dataclass


@dataclass
class AzureOpenAIConfig:
    endpoint: str
    api_key: str
    embedding_deployment: str
    embedding_model: str
    chat_deployment: str  
    chat_model: str

@dataclass
class AzureSearchConfig:
    """
    Azure Config Helper.

    ## Paramaters
    **service_endpoint**: *str* The URL to your Azure AI Search resource.

    index_name: str
    key: str
    """
    service_endpoint: str
    index_name: str
    key: str