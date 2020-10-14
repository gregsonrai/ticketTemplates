import re
import sys
import logging
import sonrai.platform.aws.arn

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')

    # Get the list of custom fields from the ticket
    user_srn = None
    tag_key = None
    tag_value = None

    # Loop through each of the custom fields and set the values that we need
    for customField in ticket.get('customFields'):
        name = customField['name']
        value = customField['value']

        if name == 'User select':
            user_srn = value
        elif name == 'TagKey':
            tag_key = value
        elif name == 'TagValue':
            tag_value = value

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

    # Call the AWS tag_user API to tag the user
    logging.info('Tagging user {} with {} : {}'.format(user_name, tag_key, tag_value))
    iam_client.tag_user(UserName=user_name, Tags=[ { 'Key': tag_key, 'Value': tag_value } ])

    # Now that we are successful, create a ticket for followup
    # response = ctx.graphql_client().query('''
    #   query MyData {
    #   }
    #  ''')
    # response.MyData ...

    query = "mutation TagBotCreateReversalQuery { "
    query = query + "CreateTicket(input: { "
    query = query + "title: " + "\"Revert: " + ticket.get("title") + "\", "
    query = query + "description: \"" + ticket.get("description") + "\", "
    query = query + "severityCategory: " + ticket.get("severityCategory") + ", "
    query = query + "account: \"" + ticket.get("account") + "\", "
#
#    query = query + "swimlaneSRNs: [ "
#    for swimlaneSRN in ticket.get("swimlaneSRNs"):
#        query = query + swimlaneSRN + ", "

#    query = query + "\"srn:arglebargle:foofaraw\" ], "

#    query = query + "templateSRN: " + ticket.get("templateSRN") + ","
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
            query = query + "isMulti:" + customField['isMulti'] + ", "
        query = query + "isRequired:" + customField['isRequired'] + "}"

    query = query + "]}) "
    query = query + "{ srn } }"

    response = ctx.graphql_client().query(query)
    ticketSrn = response.TagBotCreateReversalQuery.items.srn

    logging.info('Wowzahs - I created {}'.format(ticketSrn))

