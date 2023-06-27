import re
import sys
import logging
import sonrai.platform.aws.arn

def run(ctx):
    # Create AWS identity and access management client
    ticket = ctx.config.get('data').get('ticket')

    ticket_srn = ticket.get("srn")
    user_srn = None
    tag_key = None

    for customField in ticket.get('customFields'):
        if 'value' not in customField.keys():
            continue
        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_srn = value
        elif name == 'TagKey':
            tag_key = value

    pattern = 'srn:aws:iam::(\d+).*/(.*)$'
    a = re.search(pattern, user_srn)

    if a is None:
        logging.error('Could not parse AWS SRN {}'.format(user_srn))
        sys.exit()

    account_id = a.group(1)
    user_name = a.group(2)

    iam_client = ctx.get_client(account_id = account_id).get('iam')

    logging.info('UnTagging user {} with {}'.format(user_name, tag_key))
    iam_client.untag_user(UserName=user_name, TagKeys=[ tag_key ])

    # We were successful.  Close the ticket
    query = '''
        mutation closeTicket($srn: String) {
          CloseTickets(input: {srns: [$srn]}) {
            successCount
            failureCount
            __typename
          }
        }
    '''
    variables = { "srn": ticket_srn }
    response = ctx.graphql_client().query(query, variables)
