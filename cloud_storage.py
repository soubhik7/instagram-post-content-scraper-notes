import os
import boto3

def is_configured() -> bool:
    return all([
        os.environ.get('AWS_ACCESS_KEY_ID'),
        os.environ.get('AWS_SECRET_ACCESS_KEY'),
        os.environ.get('AWS_S3_BUCKET'),
    ])

def _client():
    return boto3.client(
        's3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION', 'us-east-1'),
    )

def upload_file(local_path: str, s3_key: str) -> str:
    """Upload a single file and return a 24-hour presigned URL."""
    bucket = os.environ.get('AWS_S3_BUCKET')
    client = _client()
    client.upload_file(local_path, bucket, s3_key)
    return client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': s3_key},
        ExpiresIn=86400,
    )

def upload_post(raw_dir: str, shortcode: str) -> dict:
    """Upload every file in raw_dir to S3 under posts/<shortcode>/. Returns {filename: url}."""
    urls = {}
    for filename in sorted(os.listdir(raw_dir)):
        path = os.path.join(raw_dir, filename)
        if os.path.isfile(path):
            urls[filename] = upload_file(path, f"posts/{shortcode}/{filename}")
    return urls
