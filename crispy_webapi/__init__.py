from flask import Flask

UPLOAD_PATH = "../uploads"

app = Flask(__name__)
app.config.from_object(__name__)

import crispy_webapi.api
import crispy_webapi.error_handlers
