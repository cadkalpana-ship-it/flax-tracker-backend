import os
import pymysql

# 1. Patch MySQL driver support immediately on startup
pymysql.install_as_MySQLdb()

# 2. Tell Django which settings module to target
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flax_backend.settings')

# 3. NOW safely initialize the WSGI handler after environment configuration is mapped
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
