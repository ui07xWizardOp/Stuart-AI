from dataclasses import dataclass, asdict, field
import json, os
from typing import Optional

@dataclass
class DatabaseConfig:
    host:str='localhost'; port:int=5432; name:str='pca_db'; min_connections:int=2; max_connections:int=10

@dataclass
class AgentRuntimeConfig:
    max_iterations_per_task:int=20

@dataclass
class ContextManagerConfig:
    max_tokens:int=4000; system_instructions_budget:int=1000; current_task_budget:int=1500

@dataclass
class SystemConfig:
    system_mode:str='NORMAL'; enable_dev_mode:bool=False
    database:DatabaseConfig=field(default_factory=DatabaseConfig)
    agent_runtime:AgentRuntimeConfig=field(default_factory=AgentRuntimeConfig)
    context_manager:ContextManagerConfig=field(default_factory=ContextManagerConfig)
    def validate(self):
        e=[]
        if not (1<=self.database.port<=65535): e.append('port must be between 1 and 65535')
        if self.database.max_connections<self.database.min_connections: e.append('max_connections must be >= min_connections')
        if self.context_manager.system_instructions_budget+self.context_manager.current_task_budget>self.context_manager.max_tokens:
            e.append('total budget exceeds max_tokens')
        return e
    def to_dict(self): return asdict(self)

_config: Optional[SystemConfig]=None
_config_file_path: Optional[str]=None

def _apply(d,c):
    for k,v in d.items():
        if hasattr(c,k):
            cur=getattr(c,k)
            if hasattr(cur,'__dataclass_fields__') and isinstance(v,dict): _apply(v,cur)
            else: setattr(c,k,v)

def load_config(path=None):
    global _config,_config_file_path
    c=SystemConfig(); _config_file_path=path
    if path:
        try:
            with open(path) as f: data=json.load(f)
            _apply(data,c)
        except json.JSONDecodeError as ex:
            raise ValueError('Invalid JSON') from ex
    if os.getenv('PCA_DB_HOST'): c.database.host=os.getenv('PCA_DB_HOST')
    if os.getenv('PCA_DB_PORT'): c.database.port=int(os.getenv('PCA_DB_PORT'))
    if os.getenv('PCA_AGENT_MAX_ITERATIONS'): c.agent_runtime.max_iterations_per_task=int(os.getenv('PCA_AGENT_MAX_ITERATIONS'))
    if os.getenv('PCA_DEV_MODE'): c.enable_dev_mode=os.getenv('PCA_DEV_MODE').lower()=='true'
    _config=c; return c

def reload_config():
    return load_config(_config_file_path)

def get_config():
    if _config is None: raise RuntimeError('Configuration has not been loaded')
    return _config
