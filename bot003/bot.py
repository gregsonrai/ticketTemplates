import re
import sys
import logging
from azure.graphrbac import GraphRbacManagementClient
from azure.graphrbac.models import GraphErrorException

from sonrai.platform.azure.client import ManagedIdentityClient


def run(ctx):
    # Create Azure identity and access management client
    ticket = ctx.config.get('data').get('ticket')

    ticket_srn = ticket.get("srn")
    reopen_ticket = 'false'
    close_ticket = 'false'
    user_srn = None
    group_srn = None

    # Parse all custom fields looking for what we are expecting
    # in this case, the user SRN is in "User select"
    # and the group SRN is in "Group select"
    #
    for customField in ticket.get('customFields'):
        if 'value' not in customField.keys():
            continue

        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_srn = value
        elif name == 'Group select':
            group_srn = value
        elif name == 'Reopen ticket after bot remediation':
            reopen_ticket = value
        elif name == 'Close ticket after bot remediation':
            close_ticket = value

    # Parse out the user ID and account / tenant ID
    #
    pattern = 'srn:azure.*::(.*)?/User/(.*)$'
    a = re.search(pattern, user_srn)

    if a is None:
        logging.error('Could not parse User SRN {}'.format(user_srn))
        sys.exit()

    tenantId = a.group(1)
    userId = a.group(2)

    # ... and parse out the group ID
    #
    pattern = 'srn:azure.*/Group/(.*)$'
    a = re.search(pattern, group_srn)

    if a is None:
        logging.error('Could not parse Group SRN {}'.format(user_srn))
        sys.exit()

    groupId = a.group(1)

    # Get the client and call the API to add a member
    #
    logging.info('Adding user {} to group {}'.format(userId, groupId))
    graphrbac_client = ctx.get_client().get(GraphRbacManagementClient)
    graphrbac_client.groups.add_member(group_object_id=groupId, url='https://graph.windows.net/' + tenantId + '/directoryObjects/' + userId)


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
