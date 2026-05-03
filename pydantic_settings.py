class BaseSettings:
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self,k,v)

    def model_dump(self):
        return dict(self.__dict__)

class SettingsConfigDict(dict):
    pass
