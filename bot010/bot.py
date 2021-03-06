import re
import sys
import logging
import datetime
from datetime import timedelta

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')

    ticket_srn = ticket.get("srn")
    reopen_ticket = 'false'
    close_ticket = 'false'
    user_name = None
    project_resource_id = None

    # Loop through each of the custom fields and set the values that we need
    for customField in ticket.get('customFields'):
        if 'value' not in customField.keys():
            continue

        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_name = "user:" + value
        elif name == 'Project select':
            project_resource_id = value
        elif name == 'Duration hours':
            duration = value
        elif name == 'Reopen ticket after bot remediation':
            reopen_ticket = value
        elif name == 'Close ticket after bot remediation':
            close_ticket = value

    # Read the project id out of the project's resource ID
    pattern = '.*projects/(.*)$'
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

    policy = modify_policy_remove_member(policy, "roles/editor", user_name)

    policy = (
        cloudresourcemanager_v1.projects()
        .setIamPolicy(resource=project_id, body={"policy": policy})
        .execute()
    )

    logging.info("Successfully removed {} as an editor from {}".format(user_name, project_id))

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


def modify_policy_remove_member(policy, role, member):
    binding = next(b for b in policy["bindings"] if b["role"] == role)
    if "members" in binding and member in binding["members"]:
        binding["members"].remove(member)
    return policy
