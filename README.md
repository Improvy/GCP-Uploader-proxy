# Proxy for uploading files to GCP Storage
This project provides a simple uploader proxy for upload files to the Google Cloud Platform Storage

## Run uploader proxy
* You need to get GCP credentials as json-file, just create a new service account here https://console.cloud.google.com/iam-admin/serviceaccounts with role "Storage Objects Creator" (don't forget to save this file!)
* Put this file in some folder (ex. /home/user/gcp/)
* Now you can run the pre-built image
``` docker run -d -v <FOLDER_WITH_GCP_JSON>:/mnt/secret -p 0.0.0.0:8000:8000/tcp -e GCP_BUCKET=<YOUR_GCP_BUCKET> -e GCP_CREDENTIALS_PATH=/mnt/secret/<json_name>.json improvy/gcp_uploader:latest ```
Change `<FOLDER_WITH_GCP_JSON>` to your folder path where you saved the GCP credentials json-file
`<YOUR_GCP_BUCKET>` with your GCP Storage bucket name
`<json_name>` with name of your credentials json-file

This is a minimal configuration for running uploader proxy, but you can specify some additional variables:
* ALLOWED_FILES - list of allowed files' extensions, for example: `-e ALLOWED_FILES=.jpg,.png,.gif,.webp`
* UPROXY_HOST - IP on which proxy will accept connections (almost useless for Docker)
* UPROXY_PORT - Port on which uploader proxy will listen `-e UPROXY_PORT=8800` (don't forget to change port mapping while run your container)
* UPROXY_MAX_FILESIZE - Maximum allowed file size in MB. It works, but due to [bug](https://stackoverflow.com/a/66243421/13379510) answer code for an exceeded file size will be 500

## Example of usage
```
curl --location --request POST 'http://<host>:<port>/upload' \
--form 'file=@"/path/to/upload.file"'

{
    "code": 200,
    "description": "https://storage.googleapis.com/<bucket_name>/<generated_filename>.file",
    "name": "Success"
}
```