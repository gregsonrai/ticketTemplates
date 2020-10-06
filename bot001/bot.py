import re
import sys
import logging
import sonrai.platform.aws.arn

def run(ctx):
    # Create AWS identity and access management client
    user_srn = ctx.User_select
    pattern = 'srn:aws:iam::(\d+).*/(.*)$'
    a = re.search(pattern, string_one)

    if a is None:
        logging.error('Could not parse AWS SRN {}'.format(user_srn))
        sys.exit()


    account_id = a.group(1)
    user_name = a.group(2)

    iam_client = ctx.get_client(account_id).get('iam')

    tag_key = ctx.TagKey
    tag_value = ctx.TagValue

    logging.info('Tagging user {} with {} : {}'.format(user_name, tag_key, tag_value))
    iam_client.tag_user(UserName=user_name, Tags=[ { 'Key': tag_key, 'Value': tag_value } ])
