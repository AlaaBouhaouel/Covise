import boto3
import uuid
from django.conf import settings


def upload_cv_to_s3(file, user_email):
    """
    Uploads a CV file to S3 and returns the S3 key.
    Returns None if upload fails.
    """
    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        # Clean email for use in filename
        clean_email = user_email.replace('@', '_').replace('.', '_')
        unique_id = uuid.uuid4().hex[:8]
        extension = file.name.split('.')[-1].lower()
        
        file_key = f"cvs/{clean_email}_{unique_id}.{extension}"

        s3.upload_fileobj(
            file,
            settings.AWS_STORAGE_BUCKET_NAME,
            file_key,
            ExtraArgs={
                'ContentType': 'application/pdf',
                'ServerSideEncryption': 'AES256'
            }
        )

        return file_key

    except Exception as e:
        print(f"[S3] Upload failed for {user_email}: {e}")
        return None


def get_cv_download_url(s3_key, expiry_seconds=3600):
    """
    Generates a temporary signed URL to download a CV.
    Link expires in 1 hour by default.
    """
    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=expiry_seconds
        )

        return url

    except Exception as e:
        print(f"[S3] URL generation failed for {s3_key}: {e}")
        return None