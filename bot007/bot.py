import re
import sys
import logging
import sonrai.platform.aws.arn
import json
import datetime
from datetime import timedelta

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')

    ticket_srn = ticket.get("srn")
    reopen_ticket = 'false'
    close_ticket = 'false'
    user_arn = None
    role_srn = None

    # Loop through each of the custom fields and set the values that we need
    for customField in ticket.get('customFields'):
        if 'value' not in customField.keys():
            continue

        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_arn = value
        elif name == 'Role select':
            role_srn = value
        elif name == 'Reopen ticket after bot remediation':
            reopen_ticket = value
        elif name == 'Close ticket after bot remediation':
            close_ticket = value

    # Read the account and username out of the user srn
    # Note:  Account here is used by the frameworks to know which collector
    #        needs to run the bot
    pattern = 'srn:aws:iam::(\d+).*/(.*)$'
    a = re.search(pattern, role_srn)

    if a is None:
        logging.error('Could not parse AWS SRN {}'.format(role_srn))
        sys.exit()

    account_id = a.group(1)
    role_name = a.group(2)

    # Get the AWS IAM client from our frameworks
    iam_client = ctx.get_client(account_id = account_id).get('iam')

    # Get the role so we can get the assume_role_policy_document
    role = iam_client.get_role(RoleName = role_name)
    policy_document = role.get("Role").get("AssumeRolePolicyDocument")

    # Add the new user to the trust relationship
    for statement in policy_document.get("Statement"):
        if (statement.get("Action") == "sts:AssumeRole"):
            principal = statement.get("Principal")
            aws = principal.get("AWS")
            if isinstance(aws, str) and principal['AWS'] == user_arn:
                del principal['AWS']
            else:
                aws.remove(user_arn)

        break

    iam_client.update_assume_role_policy(RoleName=role_name, PolicyDocument=json.dumps(policy_document))
    logging.info("Successfully updated {} AssumeRolePolicyDocument".format(role_name))

    # If we were asked to close the ticket then do that now
    if close_ticket == 'true':
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
