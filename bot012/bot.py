import botocore
import logging
import sonrai.platform.aws.arn


def run(ctx):
    # Create AWS S3 client
    s3 = ctx.get_client().get('s3')

    resource_id = ctx.resource_id

    # Enable S3 versioning : AWS ref(https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#bucketversioning)

    # Step 1)
    bucket_versioning = s3.BucketVersioning(resource_id)

    logging.info('Logging is currently {}'.format(bucket_versioning.status))

    # Enable versioning
    bucket_versioning.enable()
