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


def modify_policy_remove_member(policy, role, member):
    binding = next(b for b in policy["bindings"] if b["role"] == role)
    if "members" in binding and member in binding["members"]:
        binding["members"].remove(member)
    return policy
