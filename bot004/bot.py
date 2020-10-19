import re
import sys
import logging
import sonrai.platform.aws.arn

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')

    # Get the list of custom fields from the ticket
    customFields = ticket.get('customFields')
    user_srn = None
    policy_arn = None
    duration = None

    # Loop through each of the custom fields and set the values that we need
    for customField in ticket.get('customFields'):
        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_srn = value
        elif name == 'Policy select':
            policy_arn = value
        elif name == 'Duration hours':
            duration = value

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

