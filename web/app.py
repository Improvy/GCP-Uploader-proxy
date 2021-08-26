#!/usr/bin/python
from flask import Flask, request, json
from werkzeug.exceptions import HTTPException
from google.cloud import storage
import os.path
import string
import random

app = Flask(__name__)

BUCKET = os.getenv('GCP_BUCKET')
CREDENTIALS_PATH = os.getenv('GCP_CREDENTIALS_PATH')
if os.getenv('ALLOWED_FILES'):
    ALLOWED_FILES = os.getenv('ALLOWED_FILES').split(',')
    print(ALLOWED_FILES)
if os.getenv('UPROXY_HOST'):
    HOST = os.getenv('UPROXY_HOST')
else:
    HOST = '0.0.0.0'
if os.getenv('UPROXY_PORT'):
    PORT = os.getenv('UPROXY_PORT')
else:
    PORT = '8000'
if os.getenv('UPROXY_MAX_FILESIZE'):
    app.config['MAX_CONTENT_LENGTH'] = os.getenv('UPROXY_MAX_FILESIZE') * 1024 * 1024

print(BUCKET)
print(CREDENTIALS_PATH)
print(HOST)
print(PORT)

@app.route('/upload', methods = ['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        f = request.files['file']
        f.save(f.filename)
        client = storage.Client.from_service_account_json(json_credentials_path=CREDENTIALS_PATH)
        bucket = client.get_bucket(BUCKET)
        split_name = os.path.splitext(f.filename)
        if "ALLOWED_FILES" in globals() and (split_name[1] not in ALLOWED_FILES):
            response = app.response_class(
                response=json.dumps({
                    "code": 400,
                    "name": "Bad Request",
                    "description": "Incorrect file",
                }),
                status=400,
                mimetype='application/json'
            )
            return response

        filename = id_generator()+split_name[1]
        object_name_in_gcs_bucket = bucket.blob(filename)
        print(f.read())
        f.seek(0)
        object_name_in_gcs_bucket.upload_from_string(f.stream.read())
        object_name_in_gcs_bucket.make_public()

        response = app.response_class(
            response=json.dumps({
                "code": 200,
                "name": "Success",
                "description": object_name_in_gcs_bucket.public_url,
            }),
            status=200,
            mimetype='application/json'
        )
        return response

@app.errorhandler(413)
def error413(e):
    return print("Big file"), 413

@app.errorhandler(HTTPException)
def handle_exception(e):
    response = e.get_response()

    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    response.content_type = "application/json"
    return response

def id_generator(size=24, chars=string.ascii_lowercase + string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug = False)
