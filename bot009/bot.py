import re
import sys
import logging
import datetime
from datetime import timedelta

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')

    # Get the list of custom fields from the ticket
    user_name = None
    project_resource_id = None
    duration = None

    # GREG Remove debugging
    logging.info("Ticket looks like {}".format(ticket))

    # Loop through each of the custom fields and set the values that we need
    for customField in ticket.get('customFields'):
        if 'value' not in customField:
            next

        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_name = value
        elif name == 'Project select':
            project_resource_id = value
        elif name == 'Duration hours':
            duration = value

    # Read the project id out of the project's resource ID
    pattern = '.*project/(.*)$'
    a = re.search(pattern, project_resource_id)

    if a is None:
        logging.error('Could not parse GCP project id from {}'.format(project_resource_id))
        sys.exit()

    project_id = a.group(1)

    cloudresourcemanager_v1 = ctx.get_client().get('cloudresourcemanager', 'v1')

    # To start, we get the policy for the project
    policy = (
        cloudresourcemanager_v1.projects()
        .getIamPolicy(
            resource=project_id,
            body={"options": {"requestedPolicyVersion": 1}},
        )
        .execute()
    )

    logging.info("Policy looks liks {}".format(policy))

    policy = modify_policy_add_member(policy, "roles/owner", user_name)

    policy = (
        service.projects()
        .setIamPolicy(resource=project_id, body={"policy": policy})
        .execute()
    )

    logging.info("Successfully added {} as an owner to {}".format(user_name, project_id))

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


def modify_policy_add_member(policy, role, member):
    binding = next(b for b in policy["bindings"] if b["role"] == role)
    binding["members"].append(member)
    print(binding)
    return policy
