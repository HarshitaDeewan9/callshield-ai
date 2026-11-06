class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 503, retryable: bool = False):
        super().__init__(code)
        self.code, self.message, self.status, self.retryable = code, message, status, retryable
        self.analysis_id = None

    def body(self, mock=False):
        return {
            "error": {"code": self.code, "message": self.message, "retryable": self.retryable},
            "analysisId": self.analysis_id,
            "status": "FAILED",
            "mock": mock,
        }
