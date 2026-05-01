class Response:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code=status_code; self.text=text; self._json=json_data or {}
    def json(self): return self._json
    def raise_for_status(self):
        if self.status_code>=400: raise Exception(f"HTTP {self.status_code}")

def post(*args, **kwargs):
    return Response()

def get(*args, **kwargs):
    return Response()
