import re
import sys
import logging
import sonrai.platform.aws.arn
import datetime
from datetime import timedelta

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')
    logging.info('Data looks like: {}'.format(ticket))

    # Get the list of custom fields from the ticket
    ticket_srn = ticket.get("srn")
    reopen_ticket = 'false'
    close_ticket = 'false'
    user_srn = None
    tag_key = None
    tag_value = None
    duration = None

    # Loop through each of the custom fields and set the values that we need
    for customField in ticket.get('customFields'):
        if 'value' not in customField.keys():
            continue

        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_srn = value
        elif name == 'TagKey':
            tag_key = value
        elif name == 'TagValue':
            tag_value = value
        elif name == 'Reopen ticket after bot remediation':
            reopen_ticket = value
        elif name == 'Close ticket after bot remediation':
            close_ticket = value

    # Read the account and username out of the user srn
    # Note:  Account here is used by the frameworks to know which collector
    #        needs to run the bot
    pattern = 'srn:aws:iam::(\d+).*/(.*)$'
    a = re.search(pattern, user_srn)

    if a is None:
        logging.error('Could not parse AWS SRN {}'.format(user_srn))
        sys.exit()

    account_id = a.group(1)
    user_name = a.group(2)

    # Get the AWS IAM client from our frameworks
    iam_client = ctx.get_client(account_id = account_id).get('iam')

    # Call the AWS tag_user API to tag the user
    logging.info('Tagging user {} with {} : {}'.format(user_name, tag_key, tag_value))
    iam_client.tag_user(UserName=user_name, Tags=[ { 'Key': tag_key, 'Value': tag_value } ])

    # If we were asked to reopen the ticket (to allow escalation schemes to continue functioning), then do that now
    if reopen_ticket = 'true':
        query = '''
            mutation reopenTicket($srn: String) {
                ReopenTickets(input: {srns: [$srn]}) {   
                  successCount
                  failureCount
                  __typename
                }
            }
        '''
        variables = { "srn": ticket_srn }
        response = ctx.graphql_client().query(query, variables)
