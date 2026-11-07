class RecordingVideoGeneration:
    """Capture transport-to-use-case mapping without running paid media boundaries."""

    def __init__(self, response):
        self.response = response
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return self.response
