import re
import sys
import logging
import sonrai.platform.aws.arn

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')

    ticket_srn = ticket.get("srn")
    reopen_ticket = 'false'
    close_ticket = 'false'
    role_srn = None
    policy_arn = None

    # Loop through each of the custom fields and set the values that we need
    for customField in ticket.get('customFields'):
        if 'value' not in customField.keys():
            continue

        name = customField['name']
        value = customField['value']

        if name == 'Role select':
            user_srn = value
        elif name == 'Policy select':
            policy_arn = value
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

    # Call the AWS attach_role_policy API to attaach the policy to the role
    logging.info('Attaching policy {} to role {}'.format(policy_arn, role_name))
    iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)


    # If we were asked to reopen the ticket (to allow escalation schemes to continue functioning), then do that now
    if reopen_ticket == 'true':
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

