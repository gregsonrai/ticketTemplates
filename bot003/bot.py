import re
import sys
import logging
from azure.graphrbac import GraphRbacManagementClient
from azure.graphrbac.models import GraphErrorException

from sonrai.platform.azure.client import ManagedIdentityClient


def run(ctx):
    # Create Azure identity and access management client
    ticket = ctx.config.get('data').get('ticket')

    customFields = ticket.get('customFields')
    user_srn = None
    group_srn = None
    duration = None

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
        elif name == 'Duration hours':
            duration = value

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

    # If there is a duration, we need to create a followup ticket to revert the change
    # If there is not, we are done here
    if duration is None:
        return

    # Now that we are successful, create a ticket for followup
    query = "mutation TagBotCreateReversalQuery { "
    query = query + "CreateTicket(input: { "
    query = query + "title: " + "\"FOLLOWUP:  Revert " + ticket.get("title") + "\", "

    if ticket.get("description") is not None:
        query = query + "description: \"" + ticket.get("description") + "\", "

    query = query + "severityCategory: \"MEDIUM\", "
    query = query + "account: \"" + ticket.get("account") + "\", "

    # Until we get the swimlaneSRNs in the custom ticket passed in, we must tag the global swimlane:
    query = query + "swimlaneSRNs:[\"srn:" + ticket.get('orgName') + "::Swimlane/Global\"], " 

    query = query + "customFields: [ "
    first = 'true'
    for customField in ticket.get('customFields'):
        if 'value' not in customField.keys():
            continue

        # Fixes needed here = not just name : value - name: "name" and all the others
        if first == 'true':
            first = 'false'
        else:
            query = query + ", "


        query = query + "{ name: \"" + customField['name'] + "\", "
        query = query + "value: \"" + customField['value'] + "\", "
        query = query + "type:" + customField['type'] + ", "

        if 'isMulti' in customField:
            query = query + "isMulti:" + str(customField['isMulti']).lower() + ", "
        else: 
            query = query + "isMulti:false, "

        if 'isRequired' in customField:
            query = query + "isRequired:" + str(customField['isRequired']).lower()
        else:
            query = query + "isRequired:false"

        query = query + "}"

    query = query + "]}) "
    query = query + "{ srn } }"

    response = ctx.graphql_client().query(query)

    ticketSrn = response.get('CreateTicket').get('srn')
    logging.info('Created ticket {} for followup remediation'.format(ticketSrn))


    current_time = datetime.datetime.now()
    time_delta = timedelta(hours = int(duration))
    current_time = current_time + time_delta
    snoozedUntil = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    query = '''
        mutation snoozeTicket($srn: String, $snoozedUntil: DateTime) {
            SnoozeTickets(snoozedUntil: $snoozedUntil, input: {srns: [$srn]}) {
                successCount
                failureCount
            }
        }
    '''
    variables = { "srn": ticketSrn, "snoozedUntil": snoozedUntil }

    response = ctx.graphql_client().query(query, variables)
    logging.info("Snoozed the followup ticket for {} hours - until {}".format(duration, snoozedUntil))

