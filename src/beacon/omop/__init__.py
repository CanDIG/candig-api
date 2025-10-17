import psycopg2
from beacon import conf
import os
import logging

LOG = logging.getLogger(__name__)

db_url = os.getenv('POSTGRES_URL', default="postgresql://pgadmin:admin@localhost:5432/omopdb")
LOG.debug(db_url)

client = psycopg2.connect(db_url)

