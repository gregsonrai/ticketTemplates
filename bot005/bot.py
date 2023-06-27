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

    # Call the AWS detach_user_policy API to detach the policy from the user
    logging.info('Detaching policy {} from user {}'.format(policy_arn, user_name))
    iam_client.detach_user_policy(UserName=user_name, PolicyArn=policy_arn)

    # Change ticket title to reflect that it is once again revoked
    if title.endswith('- Approved'):
        title = title.replace('- Approved', '- Revoked')
    else:
        title = title + " - Revoked"

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


    # Close the ticket - we are done now
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
