import re
import sys
import logging
import sonrai.platform.aws.arn

def run(ctx):
    # Create AWS identity and access management client
    ticket = ctx.config.get('data').get('ticket')

    title = ticket.get("title")
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
