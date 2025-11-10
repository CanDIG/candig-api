import os
import importlib.util

config_file_path = os.getenv('BEACON_CONF', default="src/beacon/confTemplate.py")
if not config_file_path:
    raise EnvironmentError("CONFIG information set to default")

spec = importlib.util.spec_from_file_location("config", config_file_path)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

for attr in dir(config):
    if not attr.startswith("__"):
        globals()[attr] = getattr(config, attr)

