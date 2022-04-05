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
    customFields = ticket.get('customFields')
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
        raise Exception('Could not parse User SRN {}'.format(user_srn))

    tenantId = a.group(1)
    userId = a.group(2)

    # ... and parse out the group ID
    #
    pattern = 'srn:azure.*/Group/(.*)$'
    a = re.search(pattern, group_srn)

    if a is None:
        logging.error('Could not parse Group SRN {}'.format(group_srn))
        raise Exception('Could not parse Group SRN {}'.format(group_srn))

    groupId = a.group(1)

    # Get the client and call the API to add a member
    #
    logging.info('Removing user {} from group {}'.format(userId, groupId))
    graphrbac_client = ctx.get_client(audience="https://graph.windows.net/").get(GraphRbacManagementClient)
    graphrbac_client.groups.remove_member(group_object_id=groupId, member_object_id=userId)

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
