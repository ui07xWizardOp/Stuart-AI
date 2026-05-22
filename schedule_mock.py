class _Job:
    def __getattr__(self, name):
        return self
    def do(self, *args, **kwargs):
        return self

def every(*args, **kwargs):
    return _Job()

def run_pending():
    return None

def clear(*args, **kwargs):
    return None


def cancel_job(job):
    return None
