import re
import sys
import logging
import sonrai.platform.aws.arn

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')

    ticket_srn = ticket.get("srn")
    title = ticket.get("title")
    user_srn = None
    policy_arn = None

    # Loop through each of the custom fields and set the values that we need
    for customField in ticket.get('customFields'):
        if 'value' not in customField.keys():
            continue

        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_srn = value
        elif name == 'Policy select':
            policy_arn = value

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

    # Call the AWS attach_user_policy API to attaach the policy to the user
    logging.info('Attaching policy {} to user {}'.format(policy_arn, user_name))
    iam_client.attach_user_policy(UserName=user_name, PolicyArn=policy_arn)

    # Change ticket title to reflect that it has been approved
    title = title + " - Approved"
    query = '''
        mutation retitleTicket($srn: String, $title: String) {
            UpdateTicket(input: {title: $title, ticketSrn:$srn}) {
              title
              ticketKey
              srn
            }
        }
    '''
    variables = { "srn": ticket_srn, "title": title}
    response = ctx.graphql_client().query(query, variables)

    # Reopen the ticket (to allow escalation schemes to continue functioning)
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
