class EmbeddingService:
    DIMENSIONS = 1536
    
    def __init__(self, endpoint, deployment, model_name):
        self.endpoint = endpoint
        self.deployment = deployment
        self.model_name = model_name


    