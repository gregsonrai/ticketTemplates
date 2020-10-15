import re
import sys
import logging
import sonrai.platform.aws.arn
import datetime
from datetime import timedelta

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')
    logging.info('Data looks like: {}'.format(ticket))

    # Get the list of custom fields from the ticket
    user_arn = None
    role_srn = None
    duration = None

    # Loop through each of the custom fields and set the values that we need
    for customField in ticket.get('customFields'):
        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_arn = value
        elif name == 'Role select':
            role_srn = value
        elif name == 'Duration hours':
            duration = value

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

    # Get the role so we can get the assume_role_policy_document
    logging.info('Retrieving role {} in account {}'.format(role_name, account_id))
    role = iam_client.get_role(RoleName = role_name)

    policy_document = role.get("Role").get("AssumeRolePolicyDocument")

    for statement in policy_document.get("Statement"):
        if (statement.get("Action") == 'sts:AssumeRole'):
            principal = statement.get("Principal")
            aws = principal.get("AWS")
            if aws is None:
                principal['AWS'] = user_arn
            elif isinstance(aws, str):
                principal['AWS'] = [ user_arn, aws ]
            else:
                aws.append(user_arn)

    iam_client.update_assume_role_policy(RoleName=role_name, PolicyDocument=policy_document)
    logging.info("Success!  Go check it out!")
    sys.exit()

    # If there is a duration, we need to create a followup ticket to revert the change
    # If there is not, we are done here
    if duration is None:
        return

    # Now that we are successful, create a ticket for followup
    query = "mutation TagBotCreateReversalQuery { "
    query = query + "CreateTicket(input: { "
    query = query + "title: " + "\"FOLLOWUP:  Revert " + ticket.get("title") + "\", "
    query = query + "description: \"" + ticket.get("description") + "\", "
    #    query = query + "severityCategory: " + ticket.get("severityCategory").name + ", "
    query = query + "severityCategory: \"MEDIUM\", "
    query = query + "account: \"" + ticket.get("account") + "\", "

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
    logging.info('Created ticket {} for remediation'.format(ticketSrn))


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
    log.info("Finally, response was {}".format(response))

