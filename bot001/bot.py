import sonrai.platform.aws.arn

import logging

def run(ctx):
    # Create AWS identity and access management client
    iam_client = ctx.get_client().get('iam')

    user_name = ctx.User_select
    tag_key = ctx.TagKey
    tag_value = ctx.TagValue

    logging.info('Tagging user {} with {} : {}'.format(user_name, tag_key, tag_value))
    iam_client.tag_user(UserName=user_name, Tags=[ { 'Key': tag_key, 'Value': tag_value } ])
