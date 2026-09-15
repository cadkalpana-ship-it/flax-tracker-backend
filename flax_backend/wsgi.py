import os
import pymysql

pymysql.install_as_MySQLdb()

from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flax_backend.settings')
application = get_wsgi_application()
